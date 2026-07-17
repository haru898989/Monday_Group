"""Unity向けに、画像内の物体情報だけを出力する精度重視スクリプト。

このファイルは、既存実装のうち次の処理だけを再利用します。

* YOLO-World による物体名、confidence、検出位置の取得
* DeepLabV3 と YOLO の検出枠を組み合わせた物体ごとの二値マスク作成
* 日本語ファイル名や日本語フォルダ名でも読み書きしやすい画像入出力

GUI表示、クリック操作、発光、スポットライト、reaction、複数表示モードなど、
Unity用JSONに不要な処理は入れていません。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import argparse
import json
import sys
import time

import cv2
import numpy as np


# このスクリプトと同じフォルダにある既存モジュールを読み込めるようにします。
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ml_detector_complete import MagicPhotoDetector, imread_unicode, imwrite_unicode
from ml_detector_instance_segmentation import (
    InstanceObject,
    consolidate_instance_detections,
    consolidate_overlapping_semantic_masks,
)
from object_segmentation import DeepLabBoxObjectSegmenter, ObjectMaskResult
from semantic_segmentation_multi import SemanticSegmenterMulti


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]


@dataclass(frozen=True)
class OutputPaths:
    """解析結果を書き出す場所をまとめて持つための小さな入れ物です。"""

    output_dir: Path
    json_path: Path
    result_image_path: Path
    mask_dir: Path


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を読み取ります。

    学生が最初に使うときは、画像ファイル名だけを指定すれば動きます。
    精度重視のため、検出モードの初期値は ``accuracy`` にしています。
    """

    parser = argparse.ArgumentParser(
        description="画像内の物体を検出し、Unity向けJSONと二値マスクを保存します。"
    )
    parser.add_argument(
        "image_path",
        help="解析する画像ファイル。相対パスの場合は、このスクリプトのフォルダ基準です。",
    )
    parser.add_argument(
        "--mode",
        choices=("standard", "accuracy", "auto"),
        default="accuracy",
        help="検出モード。精度重視なら accuracy、軽く試すなら standard を使います。",
    )
    parser.add_argument(
        "--output-dir",
        default="unity_output",
        help="JSON、確認画像、masksフォルダを保存するフォルダ名です。",
    )
    parser.add_argument(
        "--json-name",
        default="analysis_result.json",
        help="Unity向けJSONのファイル名です。",
    )
    parser.add_argument(
        "--result-name",
        default="result.jpg",
        help="検出枠と輪郭を描いた確認用画像のファイル名です。",
    )
    return parser.parse_args()


def resolve_input_image(image_path_text: str) -> Path:
    """入力画像のパスを絶対パスに変換します。

    ``sample1.jpg`` のような相対パスは、カレントディレクトリではなく
    このスクリプトが置かれているフォルダを基準に探します。
    これにより、コマンドプロンプト、PowerShell、VS Code のどれから実行しても
    同じ結果になりやすくしています。
    """

    image_path = Path(image_path_text)
    if not image_path.is_absolute():
        image_path = CURRENT_DIR / image_path
    return image_path.resolve()


def make_output_paths(output_dir_text: str, json_name: str, result_name: str) -> OutputPaths:
    """出力先フォルダとファイル名を決め、必要なフォルダを作成します。"""

    output_dir = Path(output_dir_text)
    if not output_dir.is_absolute():
        output_dir = CURRENT_DIR / output_dir
    output_dir = output_dir.resolve()
    mask_dir = output_dir / "masks"
    mask_dir.mkdir(parents=True, exist_ok=True)
    return OutputPaths(
        output_dir=output_dir,
        json_path=output_dir / json_name,
        result_image_path=output_dir / result_name,
        mask_dir=mask_dir,
    )


def json_point(point: Point) -> List[int]:
    """JSONに入れやすい ``[x, y]`` 形式へ変換します。"""

    return [int(point[0]), int(point[1])]


def json_box(box: Sequence[int]) -> Dict[str, int]:
    """左上と右下を持つ箱情報を、Unity側で読みやすい辞書に変換します。"""

    x1, y1, x2, y2 = (int(value) for value in box)
    return {
        "x": x1,
        "y": y1,
        "width": max(0, x2 - x1 + 1),
        "height": max(0, y2 - y1 + 1),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def corners_from_box(box: Box) -> Dict[str, List[int]]:
    """左上、右上、右下、左下の4角座標を作ります。"""

    x1, y1, x2, y2 = box
    return {
        "top_left": [int(x1), int(y1)],
        "top_right": [int(x2), int(y1)],
        "bottom_right": [int(x2), int(y2)],
        "bottom_left": [int(x1), int(y2)],
    }


def contour_to_json(contour: Sequence[Point]) -> List[List[int]]:
    """OpenCVで得た輪郭点を、Unityで扱いやすい数値配列へ変換します。"""

    return [json_point(point) for point in contour]


def remove_old_mask_files(mask_dir: Path) -> None:
    """前回実行時の古い ``object_*.png`` を削除し、今回の結果と混ざらないようにします。"""

    for path in mask_dir.glob("object_*.png"):
        path.unlink()


def save_binary_masks(mask_dir: Path, mask_results: Sequence[ObjectMaskResult]) -> None:
    """各物体の二値マスクをPNGとして保存します。

    白い部分が物体、黒い部分が背景です。画像サイズは元画像と同じなので、
    Unity側ではJSON座標とマスク座標をそのまま対応させられます。
    """

    remove_old_mask_files(mask_dir)
    for result in mask_results:
        mask_path = mask_dir / f"{result.object_id}.png"
        if not imwrite_unicode(str(mask_path), result.mask):
            raise OSError(f"二値マスクを保存できませんでした: {mask_path}")
        result.mask_path = mask_path.relative_to(mask_dir.parent).as_posix()


def draw_result_image(image: np.ndarray, objects: Sequence[Tuple[object, ObjectMaskResult]]) -> np.ndarray:
    """確認用に、元画像へ検出枠・輪郭・object_idを書き込んだ画像を作ります。"""

    result_image = image.copy()
    palette = [
        (0, 255, 255),
        (255, 0, 255),
        (255, 255, 0),
        (0, 255, 0),
        (255, 140, 0),
        (180, 80, 255),
        (0, 160, 255),
        (255, 255, 255),
    ]

    for index, (detection, mask_result) in enumerate(objects):
        color = palette[index % len(palette)]
        x1, y1, x2, y2 = mask_result.detection_box
        cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
        contours, _ = cv2.findContours(
            mask_result.mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(result_image, contours, -1, color, 2)
        label = f"{mask_result.object_id} {detection.name} {detection.confidence:.2f}"
        cv2.putText(
            result_image,
            label,
            (x1, max(24, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )

    return result_image


def build_unity_json_object(detection: object, mask_result: ObjectMaskResult) -> Dict[str, object]:
    """1つの物体をUnity向けJSONの形式に変換します。

    reactionや表示モード用の情報は入れません。必要な情報だけに限定します。
    """

    return {
        "object_id": mask_result.object_id,
        "name": str(detection.name),
        "confidence": float(detection.confidence),
        "position_original": {
            "center": json_point(detection.center_original),
            "detection_box": json_box(mask_result.detection_box),
            "mask_box": json_box(mask_result.mask_box),
        },
        "four_corners_original": corners_from_box(mask_result.mask_box),
        "contour_original": contour_to_json(mask_result.contour),
        "contour_simplified_original": contour_to_json(mask_result.contour_simplified),
        "all_contours_original": [
            contour_to_json(contour)
            for contour in mask_result.all_contours
        ],
        "binary_mask": {
            "path": mask_result.mask_path,
            "width": int(mask_result.mask.shape[1]),
            "height": int(mask_result.mask.shape[0]),
            "white_pixels_are_object": True,
        },
        "mask_quality": {
            "mask_source": mask_result.mask_source,
            "segmentation_supported": bool(mask_result.segmentation_supported),
            "fallback_reason": mask_result.fallback_reason,
            "area_pixels": int(mask_result.area_pixels),
            "box_fill_ratio": float(mask_result.box_fill_ratio),
            "detection_mask_iou": float(mask_result.detection_mask_iou),
        },
    }


def save_unity_json(
    image_path: Path,
    image: np.ndarray,
    detection_mode: str,
    processing_time: float,
    objects: Sequence[Tuple[object, ObjectMaskResult]],
    output_path: Path,
) -> None:
    """Unityで読み込むためのJSONをUTF-8で保存します。"""

    height, width = image.shape[:2]
    payload = {
        "schema_version": "unity_objects_1.0",
        "coordinate_space": "original_image_pixels",
        "coordinate_origin": "top_left",
        "coordinate_unit": "pixel",
        "image": {
            "path": str(image_path),
            "width": int(width),
            "height": int(height),
        },
        "detection_mode": detection_mode,
        "processing_time_seconds": float(processing_time),
        "object_count": len(objects),
        "objects": [
            build_unity_json_object(detection, mask_result)
            for detection, mask_result in objects
        ],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def analyze_image(image_path: Path, detection_mode: str, paths: OutputPaths) -> None:
    """画像を解析し、JSON、確認画像、二値マスクを保存します。"""

    if not image_path.exists():
        raise FileNotFoundError(f"入力画像が見つかりません: {image_path}")

    started = time.perf_counter()
    image = imread_unicode(str(image_path))
    if image is None or image.size == 0:
        raise ValueError(f"画像を読み込めませんでした: {image_path}")

    print(f"入力画像: {image_path}")
    print(f"入力画像サイズ: width={image.shape[1]}, height={image.shape[0]}")
    print(f"検出モード: {detection_mode}")

    # 1. YOLO-Worldで物体名、confidence、元画像基準の検出枠を取得します。
    detector = MagicPhotoDetector(detection_mode=detection_mode)
    detections = detector.detect_from_image(image)
    detections = consolidate_instance_detections(detections)

    # 2. DeepLabV3で元画像サイズのセマンティックマスクを作ります。
    #    CUDAが使える環境では自動でGPU、使えない環境ではCPUで動きます。
    semantic_segmenter = SemanticSegmenterMulti(input_size=640)
    semantic_mask = semantic_segmenter.segment_image(image)

    # 3. 各YOLO検出枠とDeepLabマスクを組み合わせ、物体ごとの二値マスクと輪郭を作ります。
    object_segmenter = DeepLabBoxObjectSegmenter(
        semantic_segmenter=semantic_segmenter,
        epsilon_ratio=0.002,
        max_simplified_points=512,
    )
    mask_results = object_segmenter.segment_objects(
        image,
        detections,
        semantic_mask=semantic_mask,
    )

    # 4. 同じ意味の検出がほぼ同じマスクを指している場合は、1つの物体にまとめます。
    #    これにより、Unity側で同じ物体が二重に出る問題を減らします。
    instance_objects = [
        InstanceObject(detected=detection, mask_result=mask_result)
        for detection, mask_result in zip(detections, mask_results)
    ]
    instance_objects, _ = consolidate_overlapping_semantic_masks(instance_objects)
    mask_results = [item.mask_result for item in instance_objects]

    save_binary_masks(paths.mask_dir, mask_results)
    objects = [
        (item.detected, item.mask_result)
        for item in instance_objects
    ]

    result_image = draw_result_image(image, objects)
    if not imwrite_unicode(str(paths.result_image_path), result_image):
        raise OSError(f"確認画像を保存できませんでした: {paths.result_image_path}")

    processing_time = time.perf_counter() - started
    save_unity_json(
        image_path=image_path,
        image=image,
        detection_mode=detection_mode,
        processing_time=processing_time,
        objects=objects,
        output_path=paths.json_path,
    )

    print(f"検出物体数: {len(objects)}")
    for detection, mask_result in objects:
        print(
            f"- {mask_result.object_id}: "
            f"name={detection.name}, "
            f"confidence={detection.confidence:.4f}, "
            f"mask={mask_result.mask_path}, "
            f"source={mask_result.mask_source}"
        )
    print(f"JSON保存先: {paths.json_path}")
    print(f"result.jpg保存先: {paths.result_image_path}")
    print(f"masksフォルダ保存先: {paths.mask_dir}")
    print(f"処理時間: {processing_time:.3f}秒")


def main() -> None:
    """プログラムの入口です。引数を読み取り、画像解析を実行します。"""

    args = parse_args()
    image_path = resolve_input_image(args.image_path)
    paths = make_output_paths(args.output_dir, args.json_name, args.result_name)
    analyze_image(image_path, args.mode, paths)


if __name__ == "__main__":
    main()
