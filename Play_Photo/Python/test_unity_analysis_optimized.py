"""
Magic Photo Museum - 最適化版Unity解析の回帰テスト

このファイルは unity_analysis_optimized.py と
analyze_objects_optimized_for_unity.py の重要なルールを自動確認します。

他のファイルとの関係:
    AIモデルを読み込まず、NumPyとOpenCVで作った小さな疑似マスクを使います。
    実画像精度とは別に、water統合やJSON互換性がコード変更で壊れていないかを
    短時間で確認するためのテストです。

主な入力:
    テスト内で作成する疑似検出枠、疑似二値マスク、疑似画像

主な出力:
    unittestの成功・失敗結果

今回追加した確認:
    ・river/oceanからwater 1件への統合と品質値の再計算
    ・skyの全画面処理とthing処理からの分離
    ・同じ車と別の車を区別する保守的な重複判定
    ・既存Unity JSONキー、保存省略引数、古いマスク削除

Unity側との関係:
    object_id、元画像座標、二値マスクサイズ、既存JSONキーの不一致を、
    Unityへ渡す前に検出します。
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import ast
import unittest

import cv2
import numpy as np

from analyze_objects_optimized_for_unity import parse_args, save_masks, OutputPaths
from unity_analysis_optimized import (
    PROFILE_STAGE_NAMES,
    StageProfiler,
    UnityObject,
    build_global_sky_mask,
    build_payload,
    consolidate_detections,
    is_duplicate_detection,
    make_detection,
    make_mask_result,
    merge_water_objects,
    partition_stuff_detections,
    remove_stale_outputs,
)


def fake_detection(
    name: str,
    confidence: float,
    box: tuple[int, int, int, int],
) -> SimpleNamespace:
    """既存DetectedObjectと同じ主要属性を持つ軽量な疑似検出を作ります。"""

    return SimpleNamespace(
        name=name,
        confidence=confidence,
        box=box,
        center=((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
        source="test",
        sources=["test"],
        raw_names=[name],
    )


def water_object(
    name: str,
    confidence: float,
    mask: np.ndarray,
    object_id: str,
) -> UnityObject:
    """water統合テスト用のUnityObjectを作ります。"""

    ys, xs = np.where(mask > 0)
    box = (
        int(xs.min()),
        int(ys.min()),
        int(xs.max()),
        int(ys.max()),
    )
    result = make_mask_result(mask, box, object_id, "test_mask")
    detection = make_detection(name, confidence, box, raw_names=[name])
    return UnityObject(
        detected=detection,
        mask_result=result,
        name=name,
        category="water",
        region_type="stuff",
        raw_names=[name],
        source_object_ids=[object_id],
    )


class OptimizedUnityAnalysisTests(unittest.TestCase):
    """仕様で要求された重要動作をAIなしで確認します。"""

    def setUp(self) -> None:
        self.river_mask = np.zeros((80, 120), dtype=np.uint8)
        self.river_mask[30:55, 10:65] = 255
        self.ocean_mask = np.zeros((80, 120), dtype=np.uint8)
        self.ocean_mask[35:65, 55:105] = 255
        self.water_inputs = [
            water_object("river", 0.72, self.river_mask, "object_0001"),
            water_object("ocean", 0.91, self.ocean_mask, "object_0002"),
        ]

    def test_01_river_and_ocean_become_one_water(self) -> None:
        merged, merged_count = merge_water_objects(self.water_inputs, (80, 120, 3))
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].name, "water")
        self.assertEqual(merged_count, 1)

    def test_02_water_raw_names_are_preserved(self) -> None:
        merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))
        self.assertEqual(set(merged[0].raw_names), {"river", "ocean"})
        self.assertEqual(
            merged[0].source_object_ids,
            ["object_0001", "object_0002"],
        )

    def test_03_water_mask_box_is_recalculated(self) -> None:
        merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))
        self.assertEqual(merged[0].mask_result.mask_box, (10, 30, 104, 64))

    def test_04_water_confidence_uses_maximum(self) -> None:
        merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))
        self.assertAlmostEqual(merged[0].detected.confidence, 0.91)

    def test_05_sky_is_removed_from_per_object_path(self) -> None:
        things, water, sky = partition_stuff_detections([
            fake_detection("car", 0.8, (1, 1, 10, 10)),
            fake_detection("river", 0.7, (0, 20, 40, 40)),
            fake_detection("sky", 0.9, (0, 0, 30, 10)),
        ])
        self.assertEqual([item.name for item in things], ["car"])
        self.assertEqual([item.name for item in water], ["river"])
        self.assertEqual([item.name for item in sky], ["sky"])

    def test_06_sky_mask_uses_full_image(self) -> None:
        image = np.zeros((100, 160, 3), dtype=np.uint8)
        image[:60, :] = (220, 150, 70)
        sky_box = fake_detection("sky", 0.8, (10, 5, 40, 25))
        mask, source, _ = build_global_sky_mask(image, [sky_box])
        self.assertEqual(mask.shape, image.shape[:2])
        self.assertGreater(np.count_nonzero(mask[:, 80:]), 0)
        self.assertEqual(source, "global_opencv_sky_heuristic")

    def test_07_mask_size_matches_original_image(self) -> None:
        merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))
        self.assertEqual(merged[0].mask_result.mask.shape, (80, 120))

    def test_08_existing_json_fields_are_preserved(self) -> None:
        profiler = StageProfiler()
        profiler.times["total"] = 1.25
        merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))
        payload = build_payload(
            Path("sample.jpg"),
            (80, 120, 3),
            "accuracy",
            merged,
            profiler,
            model_names={"detector": "test"},
        )
        for key in (
            "schema_version",
            "coordinate_space",
            "coordinate_origin",
            "coordinate_unit",
            "image",
            "detection_mode",
            "processing_time_seconds",
            "object_count",
        ):
            self.assertIn(key, payload)
        object_data = payload["objects"][0]
        for key in (
            "object_id",
            "name",
            "confidence",
            "position_original",
            "center",
            "detection_box",
            "mask_box",
            "four_corners_original",
            "contour_original",
            "contour_simplified_original",
            "all_contours_original",
            "binary_mask",
            "mask_quality",
        ):
            self.assertIn(key, object_data)

    def test_09_same_car_is_merged(self) -> None:
        first = fake_detection("car", 0.82, (10, 10, 50, 50))
        second = fake_detection("vehicle", 0.76, (11, 10, 51, 50))
        self.assertTrue(is_duplicate_detection(first, second))
        merged, count = consolidate_detections([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(count, 1)

    def test_10_adjacent_cars_are_not_merged(self) -> None:
        first = fake_detection("car", 0.82, (10, 10, 35, 40))
        second = fake_detection("car", 0.80, (31, 10, 56, 40))
        self.assertFalse(is_duplicate_detection(first, second))
        merged, count = consolidate_detections([first, second])
        self.assertEqual(len(merged), 2)
        self.assertEqual(count, 0)

    def test_11_old_mask_files_are_removed(self) -> None:
        with TemporaryDirectory() as directory:
            mask_dir = Path(directory)
            stale = mask_dir / "object_9999.png"
            stale.write_bytes(b"old")
            remove_stale_outputs(mask_dir)
            self.assertFalse(stale.exists())

    def test_12_no_result_image_argument_works(self) -> None:
        args = parse_args(["sample.jpg", "--no-result-image"])
        self.assertFalse(args.save_result_image)
        args = parse_args(["sample.jpg", "--save-result-image"])
        self.assertTrue(args.save_result_image)

    def test_13_no_save_masks_removes_stale_masks(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            paths = OutputPaths(
                output_dir=root,
                json_path=root / "analysis_result.json",
                result_image_path=root / "result.jpg",
                mask_dir=root / "masks",
            )
            paths.mask_dir.mkdir()
            (paths.mask_dir / "object_9999.png").write_bytes(b"old")
            merged, _ = merge_water_objects(self.water_inputs, (80, 120, 3))

            def unused_writer(path: str, image: np.ndarray) -> bool:
                self.fail("保存無効時に画像保存関数が呼ばれました")
                return False

            save_masks(paths, merged, unused_writer, enabled=False)
            self.assertEqual(list(paths.mask_dir.glob("object_*.png")), [])
            self.assertIsNone(merged[0].mask_result.mask_path)

    def test_14_timing_is_in_json(self) -> None:
        profiler = StageProfiler()
        profiler.add("image_load", 0.1)
        profiler.times["total"] = 1.0
        payload = build_payload(
            Path("sample.jpg"),
            (80, 120, 3),
            "standard",
            [],
            profiler,
            model_names={},
        )
        self.assertIn("processing_stage_times", payload)
        self.assertEqual(
            set(PROFILE_STAGE_NAMES),
            set(payload["processing_stage_times"]),
        )
        self.assertAlmostEqual(
            payload["processing_stage_times"]["image_load"],
            0.1,
        )

    def test_15_python_sources_parse(self) -> None:
        root = Path(__file__).resolve().parent
        for name in (
            "unity_analysis_optimized.py",
            "analyze_objects_optimized_for_unity.py",
            "test_unity_analysis_optimized.py",
        ):
            ast.parse((root / name).read_text(encoding="utf-8"))

    def test_16_sky_excludes_known_object_mask(self) -> None:
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        image[:55, :] = (220, 150, 70)
        exclusion = np.zeros((80, 120), dtype=np.uint8)
        exclusion[5:30, 30:60] = 255
        sky, _, _ = build_global_sky_mask(
            image,
            [],
            exclusion_masks=[exclusion],
        )
        self.assertEqual(np.count_nonzero(sky[5:30, 30:60]), 0)

    def test_17_exact_cross_class_duplicate_is_merged(self) -> None:
        phone = fake_detection("phone", 0.81, (60, 20, 100, 70))
        mouse = fake_detection("mouse", 0.55, (60, 21, 100, 70))
        merged, count = consolidate_detections([phone, mouse])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].name, "phone")
        self.assertEqual(count, 1)

    def test_18_indoor_image_without_sky_detection_is_rejected(self) -> None:
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        image[:40, :] = (40, 40, 180)
        mask, _, reason = build_global_sky_mask(image, [])
        self.assertEqual(np.count_nonzero(mask), 0)
        self.assertIn("insufficient blue-sky evidence", reason)

    def test_19_dark_roof_is_not_daytime_sky(self) -> None:
        image = np.zeros((100, 160, 3), dtype=np.uint8)
        image[:70, :] = (220, 150, 70)
        image[:20, 30:130] = (20, 20, 20)
        sky_detection = fake_detection("sky", 0.8, (0, 0, 159, 70))
        mask, _, _ = build_global_sky_mask(image, [sky_detection])
        self.assertEqual(np.count_nonzero(mask[:20, 30:130]), 0)
        self.assertGreater(np.count_nonzero(mask[20:60, :]), 0)

    def test_20_night_sky_uses_top_connected_dark_region(self) -> None:
        image = np.full((100, 160, 3), 10, dtype=np.uint8)
        image[70:, :] = (140, 140, 140)
        image[20:80, 65:95] = (220, 220, 220)
        wrong_sky_box = fake_detection("sky", 0.4, (0, 65, 159, 95))
        mask, _, _ = build_global_sky_mask(image, [wrong_sky_box])
        self.assertGreater(np.count_nonzero(mask[:20, :]), 0)
        self.assertEqual(np.count_nonzero(mask[85:, :]), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
