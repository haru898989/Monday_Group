"""Magic Photo Museum 認識エンジンのモデル不要単体テスト。"""

from __future__ import annotations

import json
import importlib.util
import math
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any

from magic_brain import MagicBrain, SCENE_ORDER
from ml_detector import DetectedObject, MagicPhotoDetector, postprocess_detections
from recognition_config import RELATION_THRESHOLDS


class MagicPhotoRecognitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.brain = MagicBrain()

    def assert_valid_result(self, result: dict[str, Any]) -> None:
        """全ケース共通のUnity JSON契約を確認する。"""
        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
        self.assertTrue(serialized)
        self.assertNotIn('"recommended_effects"', serialized)
        self.assertNotIn('"reaction"', serialized)
        self.assertNotIn('"action"', serialized)
        self.assertEqual(result["schema_version"], "1.0")
        self.assertEqual(tuple(result["scene"]["scores"].keys()), SCENE_ORDER)
        self.assertIn(result["scene"]["primary"], result["scene"]["scores"])
        self.assertTrue(all(0.0 <= score <= 1.0 for score in result["scene"]["scores"].values()))
        self.assertLessEqual(len(result["main_objects"]), 3)
        self.assertLessEqual(len(result["relations"]), int(RELATION_THRESHOLDS["max_relations"]))
        ids = {item["object_id"] for item in result["objects"]}
        self.assertEqual(len(ids), len(result["objects"]))
        self.assertTrue(all(isinstance(object_id, int) and 1 <= object_id <= 2_147_483_647 for object_id in ids))
        main_ids = [item["object_id"] for item in result["main_objects"]]
        self.assertEqual(len(main_ids), len(set(main_ids)))
        self.assertTrue(all(object_id in ids for object_id in main_ids))
        self.assertEqual(
            [item["importance"] for item in result["main_objects"]],
            sorted((item["importance"] for item in result["main_objects"]), reverse=True),
        )
        for item in result["objects"]:
            self.assertTrue(math.isfinite(item["confidence"]))
            self.assertTrue(math.isfinite(item["importance"]))
            if item["geometry_valid"]:
                self.assertTrue(all(0.0 <= value <= 1.0 for value in item["normalized_center"]))
                self.assertEqual(len(item["normalized_box"]), 4)
                self.assertTrue(all(0.0 <= value <= 1.0 for value in item["normalized_box"]))
                self.assertTrue(0.0 <= item["area_ratio"] <= 1.0)
                self.assertAlmostEqual(item["width"], item["box"][2] - item["box"][0])
                self.assertAlmostEqual(item["height"], item["box"][3] - item["box"][1])
        relation_keys: set[tuple[int, int, str]] = set()
        for relation in result["relations"]:
            self.assertIn(relation["subject_id"], ids)
            self.assertIn(relation["object_id"], ids)
            self.assertNotEqual(relation["subject_id"], relation["object_id"])
            self.assertTrue(0.0 <= relation["score"] <= 1.0)
            key = (relation["subject_id"], relation["object_id"], relation["type"])
            self.assertNotIn(key, relation_keys)
            relation_keys.add(key)
        for key in ("removed_duplicates", "removed_low_confidence", "removed_invalid", "warnings"):
            self.assertIsInstance(result["debug"][key], list)

    @staticmethod
    def detected(name: str, confidence: float, box: tuple[int, int, int, int]) -> DetectedObject:
        x1, y1, x2, y2 = box
        return DetectedObject(
            name=name,
            reaction="test",
            confidence=confidence,
            box=box,
            center=((x1 + x2) // 2, (y1 + y2) // 2),
        )

    def test_01_person_and_ice_cream(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "person", "confidence": 0.92, "box": [100, 50, 500, 900]},
                {"name": "ice cream", "confidence": 0.88, "box": [250, 450, 330, 600]},
            ],
            1000,
            1000,
        )
        self.assertEqual(result["scene"]["primary"], "food_scene")
        self.assertIn("holding_candidate", {item["type"] for item in result["relations"]})
        self.assert_valid_result(result)

    def test_02_person_and_phone(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "person", "confidence": 0.90, "box": [100, 60, 500, 920]},
                {"name": "smartphone", "confidence": 0.84, "box": [280, 430, 350, 560]},
            ],
            1000,
            1000,
        )
        self.assertEqual(result["objects"][1]["canonical_name"], "phone")
        self.assertIn("holding_candidate", {item["type"] for item in result["relations"]})
        self.assert_valid_result(result)

    def test_03_person_and_monitor(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "person", "confidence": 0.90, "box": [100, 80, 480, 900]},
                {"name": "monitor", "confidence": 0.86, "box": [500, 180, 820, 520]},
            ],
            1000,
            1000,
        )
        self.assertEqual(result["objects"][1]["canonical_name"], "display")
        self.assertGreater(result["scene"]["scores"]["office"], 0.0)
        self.assertIn("using_candidate", {item["type"] for item in result["relations"]})
        self.assert_valid_result(result)

    def test_04_monitor_and_lamp(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "monitor", "confidence": 0.85, "box": [100, 150, 500, 500]},
                {"name": "lamp", "confidence": 0.78, "box": [650, 80, 780, 480]},
            ],
            900,
            700,
        )
        self.assertGreater(result["scene"]["scores"]["indoor"], 0.0)
        self.assertNotIn("recommended_effects", result)
        self.assert_valid_result(result)

    def test_05_dog_tree_and_sky(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "dog", "confidence": 0.90, "box": [280, 500, 600, 900]},
                {"name": "tree", "confidence": 0.84, "box": [20, 120, 300, 950]},
                {"name": "sky", "confidence": 0.92, "box": [0, 0, 1000, 480]},
            ],
            1000,
            1000,
        )
        self.assertGreater(result["scene"]["scores"]["nature"], 0.0)
        self.assertGreater(result["scene"]["scores"]["animal_scene"], 0.0)
        self.assertGreater(result["scene"]["scores"]["outdoor"], 0.0)
        self.assert_valid_result(result)

    def test_06_car_and_road(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "car", "confidence": 0.91, "box": [320, 380, 720, 700]},
                {"name": "road", "confidence": 0.86, "box": [0, 500, 1000, 1000]},
            ],
            1000,
            1000,
        )
        self.assertGreater(result["scene"]["scores"]["transportation_scene"], 0.0)
        self.assert_valid_result(result)

    def test_07_duplicate_person_and_human(self) -> None:
        processed, debug = postprocess_detections(
            [
                self.detected("person", 0.88, (100, 80, 480, 900)),
                self.detected("human", 0.76, (105, 85, 475, 895)),
            ],
            1000,
            1000,
        )
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].canonical_name, "person")
        self.assertIn("human", processed[0].aliases)
        self.assertEqual(len(debug["removed_duplicates"]), 1)
        result = self.brain.analyze(processed, 1000, 1000, debug=debug)
        self.assert_valid_result(result)

    def test_08_duplicate_monitor_and_television(self) -> None:
        processed, debug = postprocess_detections(
            [
                self.detected("monitor", 0.87, (100, 100, 600, 500)),
                self.detected("television", 0.79, (105, 105, 595, 495)),
            ],
            1000,
            800,
        )
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].canonical_name, "display")
        self.assertIn("television", processed[0].aliases)
        self.assertEqual(len(debug["removed_duplicates"]), 1)
        self.assert_valid_result(self.brain.analyze(processed, 1000, 800, debug=debug))

    def test_09_unknown_object_only(self) -> None:
        result = self.brain.analyze(
            [{"name": "mysterious artifact", "confidence": 0.70, "box": [10, 20, 110, 180]}],
            300,
            300,
        )
        self.assertEqual(result["scene"]["primary"], "unknown")
        self.assertEqual(result["objects"][0]["canonical_name"], "mysterious artifact")
        self.assert_valid_result(result)

    def test_10_empty_input_and_atomic_save(self) -> None:
        result = self.brain.analyze([], 640, 480)
        self.assertEqual(result["objects"], [])
        self.assertEqual(result["relations"], [])
        self.assertEqual(result["scene"]["primary"], "unknown")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis_result.json"
            saved = self.brain.save_json(result, output)
            self.assertEqual(saved, output)
            self.assertTrue(output.exists())
            self.assertFalse(output.with_suffix(".tmp").exists())
            json.loads(output.read_text(encoding="utf-8"))
        self.assert_valid_result(result)

    def test_11_missing_box(self) -> None:
        result = self.brain.analyze([{"name": "person", "confidence": 0.8}], 640, 480)
        self.assertFalse(result["objects"][0]["geometry_valid"])
        self.assertEqual(result["objects"][0]["box"], [])
        self.assertTrue(result["debug"]["warnings"])
        self.assert_valid_result(result)

    def test_12_missing_or_non_finite_confidence(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "dog", "box": [0, 0, 100, 100]},
                {"name": "cat", "confidence": float("nan"), "box": [150, 0, 250, 100]},
            ],
            400,
            300,
        )
        self.assertEqual([item["confidence"] for item in result["objects"]], [0.0, 0.0])
        self.assert_valid_result(result)

    def test_13_portrait_image(self) -> None:
        result = self.brain.analyze(
            [{"name": "person", "confidence": 0.9, "box": [100, 300, 300, 900]}],
            400,
            1200,
        )
        item = result["objects"][0]
        self.assertEqual(item["normalized_center"], [0.5, 0.5])
        self.assertAlmostEqual(item["area_ratio"], 0.25)
        self.assert_valid_result(result)

    def test_14_landscape_image(self) -> None:
        result = self.brain.analyze(
            [{"name": "car", "confidence": 0.9, "box": [300, 100, 900, 300]}],
            1200,
            400,
        )
        item = result["objects"][0]
        self.assertEqual(item["normalized_center"], [0.5, 0.5])
        self.assertAlmostEqual(item["area_ratio"], 0.25)
        self.assert_valid_result(result)

    def test_15_multiple_objects_with_same_name(self) -> None:
        processed, debug = postprocess_detections(
            [
                self.detected("dog", 0.90, (20, 200, 220, 500)),
                self.detected("dog", 0.82, (600, 180, 850, 520)),
                self.detected("dog", 0.74, (350, 500, 520, 760)),
            ],
            1000,
            800,
        )
        self.assertEqual(len(processed), 3)
        self.assertEqual(debug["removed_duplicates"], [])
        result = self.brain.analyze(processed, 1000, 800, debug=debug)
        self.assertEqual(len({item["object_id"] for item in result["objects"]}), 3)
        detector_without_model = object.__new__(MagicPhotoDetector)
        detector_without_model.last_objects = processed
        self.assertIsNotNone(detector_without_model.find_clicked_object(*processed[0].center))
        self.assert_valid_result(result)

    def test_16_category_confidence_thresholds(self) -> None:
        processed, debug = postprocess_detections(
            [
                self.detected("person", 0.19, (10, 10, 100, 250)),
                self.detected("face", 0.24, (150, 10, 220, 90)),
                self.detected("cake", 0.14, (250, 20, 350, 140)),
                self.detected("mouse", 0.12, (400, 30, 450, 70)),
            ],
            600,
            400,
        )
        self.assertEqual([item.canonical_name for item in processed], ["mouse"])
        self.assertEqual(len(debug["removed_low_confidence"]), 3)

    def test_17_confusable_classes_require_very_high_iou(self) -> None:
        objects = [
            self.detected("monitor", 0.88, (100, 100, 600, 500)),
            self.detected("computer", 0.80, (105, 105, 595, 495)),
            self.detected("computer", 0.75, (650, 100, 950, 450)),
        ]
        processed, debug = postprocess_detections(objects, 1000, 700)
        self.assertEqual(len(processed), 2)
        self.assertEqual(len(debug["removed_duplicates"]), 1)

    def test_18_string_input_human_summary_and_safe_ids(self) -> None:
        string_result = self.brain.analyze("person")
        self.assertEqual(string_result["objects"][0]["canonical_name"], "person")
        self.assertTrue(string_result["summary"]["has_person"])
        result = self.brain.analyze(
            [
                {"name": "face", "object_id": 1.5, "confidence": 0.8},
                {"name": "hand", "object_id": 9_999_999_999, "confidence": 0.7},
            ],
            640,
            480,
        )
        self.assertTrue(result["summary"]["has_person"])
        self.assertEqual([item["object_id"] for item in result["objects"]], [1, 2])
        self.assert_valid_result(result)

    def test_19_partial_overlap_and_edge_gap_near(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "person", "confidence": 0.9, "box": [0, 0, 500, 900]},
                {"name": "phone", "confidence": 0.8, "box": [450, 500, 550, 620]},
                {"name": "book", "confidence": 0.75, "box": [550, 0, 1000, 400]},
            ],
            1200,
            1000,
        )
        relation_types = {relation["type"] for relation in result["relations"]}
        self.assertIn("overlap", relation_types)
        self.assertIn("near", relation_types)
        self.assert_valid_result(result)

    def test_20_atomic_tmp_name_and_non_finite_sanitizing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.tmp"
            self.brain.save_json({"value": float("nan"), "other": float("inf")}, output)
            self.assertTrue(output.exists())
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded, {"value": 0.0, "other": 0.0})
            self.assertFalse((Path(directory) / "result.tmp.writing").exists())

    def test_21_tiny_or_background_objects_are_not_held(self) -> None:
        result = self.brain.analyze(
            [
                {"name": "person", "confidence": 0.9, "box": [100, 50, 600, 950]},
                {"name": "unknown speck", "confidence": 0.9, "box": [300, 500, 301, 501]},
                {"name": "table", "confidence": 0.9, "box": [150, 450, 550, 800]},
                {"name": "sky", "confidence": 0.9, "box": [0, 0, 1000, 500]},
            ],
            1000,
            1000,
        )
        self.assertNotIn("holding_candidate", {relation["type"] for relation in result["relations"]})
        self.assert_valid_result(result)

    def test_22_invalid_postprocess_settings_fall_back_safely(self) -> None:
        objects = [
            self.detected("dog", 0.8, (0, 0, 100, 100)),
            self.detected("dog", 0.7, (500, 500, 600, 600)),
        ]
        processed, _ = postprocess_detections(
            objects,
            800,
            800,
            base_confidence=float("nan"),
            duplicate_iou_threshold=0.0,
        )
        self.assertEqual(len(processed), 2)

    def test_23_person_synonyms_all_merge(self) -> None:
        processed, debug = postprocess_detections(
            [
                self.detected("person", 0.90, (100, 50, 500, 900)),
                self.detected("human", 0.85, (102, 52, 498, 898)),
                self.detected("man", 0.80, (104, 54, 496, 896)),
                self.detected("woman", 0.75, (106, 56, 494, 894)),
            ],
            1000,
            1000,
        )
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].canonical_name, "person")
        self.assertTrue({"person", "human", "man", "woman"} <= set(processed[0].aliases))
        self.assertEqual(len(debug["removed_duplicates"]), 3)

    def test_24_resize_preserves_aspect_ratio_without_gui(self) -> None:
        class FakeImage:
            def __init__(self, shape: tuple[int, int, int]) -> None:
                self.shape = shape

        class FakeCv2:
            INTER_AREA = 3

            def __init__(self) -> None:
                self.last_size: tuple[int, int] | None = None

            def resize(self, image: Any, size: tuple[int, int], interpolation: int) -> tuple[int, int]:
                self.last_size = size
                return size

        detector = object.__new__(MagicPhotoDetector)
        detector._cv2 = FakeCv2()
        self.assertEqual(
            detector.resize_image_to_fit(FakeImage((1000, 2000, 3)), 1000, 1000),
            (1000, 500),
        )
        self.assertEqual(
            detector.resize_image_to_fit(FakeImage((2000, 1000, 3)), 1000, 1000),
            (500, 1000),
        )
        detector.max_display_size = 100
        self.assertEqual(detector.resize_image(FakeImage((1, 100000, 3))), (100, 1))

    def test_25_demo_draws_box_and_all_four_corners(self) -> None:
        fake_cv2 = types.ModuleType("cv2")
        fake_cv2.FONT_HERSHEY_SIMPLEX = 0
        rectangles: list[tuple[tuple[int, int], tuple[int, int]]] = []
        circles: list[tuple[int, int]] = []
        fake_cv2.rectangle = lambda image, first, second, color, width: rectangles.append((first, second))
        fake_cv2.circle = lambda image, center, radius, color, width: circles.append(center)
        fake_cv2.putText = lambda *args, **kwargs: None

        class FakeImage:
            def copy(self) -> "FakeImage":
                return self

        module_name = "demo_click_compatibility_test"
        spec = importlib.util.spec_from_file_location(module_name, Path(__file__).with_name("demo_click.py"))
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        previous_cv2 = sys.modules.get("cv2")
        try:
            sys.modules["cv2"] = fake_cv2
            spec.loader.exec_module(module)
        finally:
            if previous_cv2 is None:
                sys.modules.pop("cv2", None)
            else:
                sys.modules["cv2"] = previous_cv2

        obj = self.detected("person", 0.9, (10, 20, 110, 220))
        module.cv2 = fake_cv2
        module.draw_objects(FakeImage(), [obj])
        self.assertEqual(rectangles, [((10, 20), (110, 220))])
        self.assertEqual(set(circles), {(10, 20), (110, 20), (10, 220), (110, 220)})


if __name__ == "__main__":
    unittest.main(verbosity=2)
