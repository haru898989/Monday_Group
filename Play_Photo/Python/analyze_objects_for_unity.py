"""MagicPhotoの正式なUnity向け画像解析エントリーポイント。

このファイルは、既存実装のうち次の処理だけを再利用します。

* YOLO-World による物体名、confidence、検出位置の取得
* DeepLabV3 と YOLO の検出枠を組み合わせた物体ごとの二値マスク作成
* 採用済みOneFormer scene-exclusiveによるsky/water/plantマスク
* 採用済み品質処理、人物保護、touch対象判定
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

from ml_detector_complete import (
    DetectedObject,
    MagicPhotoDetector,
    category_name_for,
    imread_unicode,
    imwrite_unicode,
)
from ml_detector_instance_segmentation import (
    InstanceObject,
    consolidate_instance_detections,
    consolidate_overlapping_semantic_masks,
)
from object_segmentation import (
    DeepLabBoxObjectSegmenter,
    ObjectMaskResult,
    rebuild_mask_result,
)
from semantic_segmentation_multi import SemanticSegmenterMulti
from magicphoto_quality import (
    compare_grabcut_to_box,
    evaluate_touch_eligibility,
    postprocess_mask_results,
    refine_person_boundaries,
    target_category_for,
)
from udp_sender import send_to_unity


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]
SCENE_CATEGORIES = {"sky", "water", "plant"}
DEFAULT_SCENE_SEGMENTATION = "oneformer-scene-exclusive"
UNITY_UDP_HOST = "127.0.0.1"
UNITY_UDP_PORT = 1140
UNITY_UDP_MODE = "legacy"


# Unityで音を鳴らす対象として、特に具体名を優先したいクラスです。
# 既存のYOLO-World設定に足りない名前を、このスクリプト側で追加します。
UNITY_PRIORITY_CLASSES = [
    "piano",
    "keyboard",
    "musical keyboard",
    "electronic keyboard",
    "piano keyboard",
    "guitar",
    "violin",
    "drum",
    "trumpet",
    "saxophone",
    "dog",
    "cat",
    "bird",
    "cow",
    "horse",
    "pizza",
    "food",
    "sun",
    "moon",
    "sky",
]


# この名前だけでは音を決めにくいため、unknown_objectとして扱います。
# 例: animal だけでは dog/cat/bird のどれか分からない。
GENERIC_UNSAFE_NAMES = {
    "animal",
    "instrument",
    "musical instrument",
    "object",
    "thing",
}


CATEGORY_BY_NAME = {
    "piano": "instrument",
    "keyboard": "instrument",
    "musical keyboard": "instrument",
    "electronic keyboard": "instrument",
    "piano keyboard": "instrument",
    "guitar": "instrument",
    "violin": "instrument",
    "drum": "instrument",
    "trumpet": "instrument",
    "saxophone": "instrument",
    "dog": "animal",
    "cat": "animal",
    "bird": "animal",
    "cow": "animal",
    "horse": "animal",
    "pizza": "food",
    "food": "food",
    "sun": "sky_object",
    "moon": "sky_object",
    "sky": "background",
    "water": "background",
    "sea": "background",
    "ocean": "background",
    "river": "background",
    "lake": "background",
    "pond": "background",
    "pool": "background",
    "waterfall": "background",
    "tree": "plant",
    "grass": "plant",
    "plant": "plant",
    "flower": "plant",
    "bush": "plant",
    "shrub": "plant",
    "vegetation": "plant",
    "person": "person",
    "human": "person",
    "man": "person",
    "woman": "person",
    "child": "person",
    "car": "vehicle",
    "truck": "vehicle",
    "van": "vehicle",
    "bus": "vehicle",
    "vehicle": "vehicle",
    "bicycle": "vehicle",
    "motorcycle": "vehicle",
    "monitor": "device",
    "television": "device",
    "tv": "device",
    "phone": "device",
    "cell phone": "device",
    "bottle": "object",
    "cup": "object",
}


NORMALIZED_NAME_BY_ALIAS = {
    "musical keyboard": "keyboard",
    "electronic keyboard": "keyboard",
    "piano keyboard": "keyboard",
    "motorbike": "motorcycle",
    "television": "monitor",
    "tv": "monitor",
    "cell phone": "phone",
}


@dataclass(frozen=True)
class OutputPaths:
    """解析結果を書き出す場所をまとめて持つための小さな入れ物です。"""

    output_dir: Path
    json_path: Path
    result_image_path: Path
    mask_dir: Path


@dataclass(frozen=True)
class AnalysisResult:
    """解析後の物体と保存先を、別のスクリプトから再利用するための戻り値です。"""

    objects: List[InstanceObject]
    paths: OutputPaths
    processing_time: float


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
    parser.add_argument(
        "--scene-segmentation",
        choices=(DEFAULT_SCENE_SEGMENTATION, "existing"),
        default=DEFAULT_SCENE_SEGMENTATION,
        help=(
            "scene処理。既定は正式採用済みOneFormer scene-exclusive。"
            "従来scene処理を明示する場合だけ existing を使います。"
        ),
    )
    parser.add_argument(
        "--oneformer-fallback",
        choices=("existing", "error"),
        default="existing",
        help="OneFormerを使えない場合に従来sceneへ戻すか、エラー終了するかを選びます。",
    )
    parser.add_argument(
        "--oneformer-model-dir",
        default=None,
        help="通常は不要。ローカルOneFormerモデルフォルダを明示する場合に使います。",
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


def configure_detector_for_unity(detector: MagicPhotoDetector) -> None:
    """Unityの音判定で必要な具体名をYOLO-Worldの候補に追加します。

    YOLO-Worldは「探してほしいクラス名」を渡すと、その名前を優先して検出します。
    既存実装には ``musical instrument`` のような総称が含まれていますが、
    Unityで音を鳴らすには ``piano`` や ``guitar`` のような具体名が必要です。
    """

    classes = list(detector.custom_classes)
    for class_name in UNITY_PRIORITY_CLASSES:
        if class_name not in classes:
            classes.append(class_name)
    detector.custom_classes = classes
    detector.model.set_classes(classes)

    # 小さく写った楽器や動物を拾いやすくするため、優先クラスのしきい値を少し下げます。
    # 低すぎると誤検出が増えるので、あとで品質フィルタとunknown処理で守ります。
    for class_name in UNITY_PRIORITY_CLASSES:
        detector.class_confidence_thresholds.setdefault(class_name, 0.18)


def normalize_name_category_confidence(
    raw_name: str,
    raw_confidence: float,
) -> Tuple[str, str, float, bool]:
    """検出名をUnityで音に結びつけやすい名前と分類へ整理します。

    ``animal`` や ``musical instrument`` のような総称だけでは、正しい音を
    選べません。その場合は無理に犬やピアノと決めず、``unknown_object`` として
    confidenceを低くします。
    """

    lower_name = str(raw_name).strip().lower()
    if lower_name in GENERIC_UNSAFE_NAMES:
        return "unknown_object", "unknown", min(float(raw_confidence), 0.20), True

    normalized_name = NORMALIZED_NAME_BY_ALIAS.get(lower_name, lower_name)
    category = CATEGORY_BY_NAME.get(normalized_name)
    if category is None:
        # 新しい具体名（例: ice cream）も既存検出モジュールの正式カテゴリ変換へ
        # 追随させます。Unityで従来使っているdevice/object表記だけ互換変換します。
        detector_category = category_name_for(normalized_name)
        category = {
            "electronics": "device",
            "other": "object",
            "sky": "background",
            "water": "background",
        }.get(detector_category, detector_category)
    return normalized_name, category, float(raw_confidence), False


def mask_box(mask: np.ndarray, fallback: Box) -> Box:
    """マスクの白い部分を囲む最小の四角形を返します。"""

    points = cv2.findNonZero(mask)
    if points is None:
        return fallback
    x, y, width, height = cv2.boundingRect(points)
    return int(x), int(y), int(x + width - 1), int(y + height - 1)


def contour_points(contour: np.ndarray) -> List[Point]:
    """OpenCVの輪郭配列を、Pythonの ``(x, y)`` リストへ変換します。"""

    return [
        (int(point[0][0]), int(point[0][1]))
        for point in contour
    ]


def contour_data(mask: np.ndarray) -> Tuple[List[Point], List[Point], List[List[Point]]]:
    """二値マスクから正確な輪郭と、軽量な簡略輪郭を作ります。"""

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return [], [], []
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    primary = contours[0]
    perimeter = cv2.arcLength(primary, True)
    simplified = cv2.approxPolyDP(primary, max(0.5, perimeter * 0.002), True)
    return (
        contour_points(primary),
        contour_points(simplified),
        [contour_points(item) for item in contours],
    )


def update_mask_result_from_mask(
    result: ObjectMaskResult,
    mask: np.ndarray,
    mask_source: str,
    fallback_reason: Optional[str],
) -> None:
    """GrabCutなどで改善したマスクを、既存の結果オブジェクトへ反映します。"""

    final_mask = ((mask > 0) * 255).astype(np.uint8)
    result.mask = final_mask
    result.mask_box = mask_box(final_mask, result.detection_box)
    result.corners = {
        key: tuple(value)
        for key, value in {
            "top_left": corners_from_box(result.mask_box)["top_left"],
            "top_right": corners_from_box(result.mask_box)["top_right"],
            "bottom_right": corners_from_box(result.mask_box)["bottom_right"],
            "bottom_left": corners_from_box(result.mask_box)["bottom_left"],
        }.items()
    }
    contour, contour_simplified, all_contours = contour_data(final_mask)
    result.contour = contour
    result.contour_simplified = contour_simplified
    result.all_contours = all_contours
    result.area_pixels = int(np.count_nonzero(final_mask))
    result.mask_source = mask_source
    result.segmentation_supported = True
    result.fallback_reason = fallback_reason

    image_area = max(1, final_mask.shape[0] * final_mask.shape[1])
    x1, y1, x2, y2 = result.detection_box
    box_area = max(1, (x2 - x1 + 1) * (y2 - y1 + 1))
    result.mask_area_ratio = result.area_pixels / image_area
    result.box_fill_ratio = result.area_pixels / box_area
    result.detection_mask_iou = result.area_pixels / box_area
    component_count, _ = cv2.connectedComponents(
        (final_mask > 0).astype(np.uint8),
        connectivity=8,
    )
    result.connected_component_count = max(0, int(component_count) - 1)
    mx1, my1, mx2, my2 = result.mask_box
    result.box_delta = {
        "left": mx1 - x1,
        "top": my1 - y1,
        "right": mx2 - x2,
        "bottom": my2 - y2,
        "width": (mx2 - mx1 + 1) - (x2 - x1 + 1),
        "height": (my2 - my1 + 1) - (y2 - y1 + 1),
    }


def try_grabcut_mask(image: np.ndarray, detection_box: Box) -> Optional[np.ndarray]:
    """DeepLabが使えない物体に対して、箱内の前景だけをGrabCutで推定します。

    楽器のようにVOC版DeepLabV3が知らない物体でも、矩形全体をマスクにすると
    背景タッチで誤反応します。GrabCutは完璧ではありませんが、矩形だけより
    背景を減らせることが多いため、Unityのタッチ判定に向いています。
    """

    height, width = image.shape[:2]
    x1, y1, x2, y2 = detection_box
    box_width = x2 - x1 + 1
    box_height = y2 - y1 + 1
    if box_width < 8 or box_height < 8:
        return None

    box_area_ratio = (box_width * box_height) / max(1, width * height)
    if box_area_ratio > 0.65:
        return None

    grabcut_mask = np.zeros((height, width), dtype=np.uint8)
    rectangle = (int(x1), int(y1), int(box_width), int(box_height))
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            image,
            grabcut_mask,
            rectangle,
            bgd_model,
            fgd_model,
            5,
            cv2.GC_INIT_WITH_RECT,
        )
    except cv2.error:
        return None

    foreground = np.where(
        (grabcut_mask == cv2.GC_FGD) | (grabcut_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    foreground[:, :x1] = 0
    foreground[:, x2 + 1:] = 0
    foreground[:y1, :] = 0
    foreground[y2 + 1:, :] = 0

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    foreground = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, kernel, iterations=1)

    foreground_area = int(np.count_nonzero(foreground))
    box_area = max(1, box_width * box_height)
    fill_ratio = foreground_area / box_area
    if foreground_area < 12 or fill_ratio < 0.01 or fill_ratio > 0.98:
        return None
    return foreground


def refine_fallback_masks_with_grabcut(
    image: np.ndarray,
    detections: Sequence[object],
    mask_results: Sequence[ObjectMaskResult],
) -> Dict[str, int]:
    """非personの矩形fallbackだけを、品質比較付きGrabCutで改善します。

    正式採用方針としてpersonはこの共通経路へ入れません。personの境界は後段の
    ``refine_person_boundaries`` がDeepLabマスクを安全なseedとして個別処理します。
    """

    stats = {"candidate_count": 0, "accepted_count": 0, "rejected_count": 0}
    for detection, result in zip(detections, mask_results):
        if result.mask_source != "box_fallback":
            continue
        if category_name_for(detection.name) == "person":
            continue
        stats["candidate_count"] += 1
        refined = try_grabcut_mask(image, result.detection_box)
        if refined is None:
            stats["rejected_count"] += 1
            continue
        accepted, comparison = compare_grabcut_to_box(
            image,
            refined,
            result.detection_box,
            category_name_for(detection.name),
        )
        result.quality_details = {
            **dict(result.quality_details or {}),
            "grabcut_quality_comparison": comparison,
        }
        if not accepted:
            stats["rejected_count"] += 1
            continue
        update_mask_result_from_mask(
            result,
            refined,
            "grabcut_box",
            "deeplab unsupported; refined by grabcut",
        )
        result.correction_reasons = list(result.correction_reasons or []) + [
            "grabcut_selected_over_box"
        ]
        stats["accepted_count"] += 1
    return stats


def filter_sun_moon_candidates(
    image: np.ndarray,
    objects: Sequence[InstanceObject],
    sky_mask: np.ndarray,
) -> Tuple[List[InstanceObject], Dict[str, object]]:
    """採用済みのsky支持・形状・明度条件でsun/moon候補を安定化します。"""

    height, width = image.shape[:2]
    image_area = max(1, height * width)
    sky_binary = ((sky_mask > 0) * 255).astype(np.uint8)
    proximity = max(3, int(round(min(height, width) * 0.015)))
    nearby_sky = cv2.dilate(
        sky_binary,
        cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (proximity * 2 + 1, proximity * 2 + 1),
        ),
        iterations=1,
    ) > 0
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    kept: List[InstanceObject] = []
    details: List[Dict[str, object]] = []

    for item in objects:
        category = category_name_for(item.detected.name)
        if category not in {"sun", "moon"}:
            kept.append(item)
            continue

        pixels = item.mask > 0
        area = int(np.count_nonzero(pixels))
        area_ratio = area / image_area
        x1, y1, x2, y2 = item.mask_result.mask_box
        center_x = max(0, min(width - 1, (x1 + x2) // 2))
        center_y = max(0, min(height - 1, (y1 + y2) // 2))
        sky_overlap = float(np.count_nonzero(pixels & nearby_sky)) / max(1, area)
        sky_supported = bool(sky_overlap >= 0.20 or nearby_sky[center_y, center_x])

        contours, _ = cv2.findContours(
            item.mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        circularity = 0.0
        if contours:
            contour = max(contours, key=cv2.contourArea)
            contour_area = float(cv2.contourArea(contour))
            perimeter = float(cv2.arcLength(contour, True))
            if perimeter > 0:
                circularity = min(
                    1.0,
                    4.0 * np.pi * contour_area / (perimeter ** 2),
                )

        value = hsv[:, :, 2][pixels]
        saturation = hsv[:, :, 1][pixels]
        mean_brightness = float(np.mean(value)) if value.size else 0.0
        mean_saturation = float(np.mean(saturation)) if saturation.size else 255.0
        pad = max(3, int(round(max(x2 - x1, y2 - y1) * 0.45)))
        rx1, ry1 = max(0, x1 - pad), max(0, y1 - pad)
        rx2, ry2 = min(width, x2 + pad + 1), min(height, y2 + pad + 1)
        ring_mask = np.zeros((height, width), dtype=bool)
        ring_mask[ry1:ry2, rx1:rx2] = True
        ring_mask &= ~pixels
        ring_values = hsv[:, :, 2][ring_mask]
        surrounding_brightness = (
            float(np.mean(ring_values)) if ring_values.size else mean_brightness
        )
        local_contrast = mean_brightness - surrounding_brightness
        model_supported = float(item.detected.confidence) >= (
            0.40 if category == "sun" else 0.36
        )
        valid_size = 0.000003 <= area_ratio <= 0.08
        valid_position = center_y <= int(height * 0.88)
        box_aspect = max(1, x2 - x1 + 1) / max(1, y2 - y1 + 1)
        shape_supported = 0.42 <= box_aspect <= 2.38
        if category == "sun":
            visual_supported = (
                circularity >= 0.28
                and shape_supported
                and mean_brightness >= 145.0
                and (
                    local_contrast >= 6.0
                    or (
                        float(item.detected.confidence) >= 0.75
                        and mean_brightness >= 210.0
                        and area_ratio >= 0.0005
                    )
                )
            )
        else:
            visual_supported = (
                circularity >= 0.30
                and shape_supported
                and mean_brightness >= 95.0
                and mean_saturation <= 155.0
                and (local_contrast >= 5.0 or mean_brightness >= 190.0)
            )
        accepted = bool(
            sky_supported
            and model_supported
            and valid_size
            and valid_position
            and visual_supported
        )
        details.append({
            "name": category,
            "confidence": float(item.detected.confidence),
            "accepted": accepted,
            "sky_overlap_ratio": float(sky_overlap),
            "circularity": float(circularity),
            "mean_brightness": mean_brightness,
            "mean_saturation": mean_saturation,
            "local_contrast": float(local_contrast),
            "mask_area_ratio": float(area_ratio),
        })
        if accepted:
            kept.append(item)

    accepted_count = sum(1 for detail in details if detail["accepted"])
    return kept, {
        "candidate_count": len(details),
        "accepted_count": accepted_count,
        "rejected_count": len(details) - accepted_count,
        "candidates": details,
    }


def build_oneformer_scene_instances(
    scene_output: Dict[str, object],
    foreground_mask: np.ndarray,
    start_index: int,
) -> Tuple[List[InstanceObject], Dict[str, object]]:
    """正式採用OneFormerマスクを既存のUnity物体契約へ変換します。

    scene-exclusive方針に従い、既存の非scene物体を一切変更せず、その白画素を
    sceneから差し引きます。色・位置による局所救済PoCはここでは行いません。
    """

    masks = scene_output.get("masks")
    if not isinstance(masks, dict):
        raise ValueError("OneFormer scene output does not contain masks")
    category_details = scene_output.get("category_details")
    if not isinstance(category_details, dict):
        category_details = {}
    instances: List[InstanceObject] = []
    details: Dict[str, object] = {}

    for category in ("sky", "water", "plant"):
        raw_mask = masks.get(category)
        if not isinstance(raw_mask, np.ndarray) or raw_mask.ndim != 2:
            raise ValueError(f"invalid OneFormer {category} mask")
        mask = np.where(raw_mask > 0, 255, 0).astype(np.uint8)
        if mask.shape != foreground_mask.shape:
            raise ValueError(
                f"OneFormer {category} mask size {mask.shape} does not match "
                f"image size {foreground_mask.shape}"
            )
        before_foreground = int(np.count_nonzero(mask))
        mask[foreground_mask > 0] = 0
        foreground_removed = before_foreground - int(np.count_nonzero(mask))
        points = cv2.findNonZero(mask)
        source_detail = dict(category_details.get(category) or {})
        if points is None:
            details[category] = {
                **source_detail,
                "accepted": False,
                "foreground_removed_pixels": foreground_removed,
                "reason": "empty_after_foreground_subtraction",
            }
            continue

        x, y, width, height = cv2.boundingRect(points)
        box = (x, y, x + width - 1, y + height - 1)
        confidence = float(source_detail.get("mean_confidence_grid", 0.0))
        object_id = f"object_{start_index + len(instances):04d}"
        result = ObjectMaskResult(
            object_id=object_id,
            mask=mask,
            detection_box=box,
            mask_box=box,
            corners={},
            contour=[],
            contour_simplified=[],
            all_contours=[],
            area_pixels=int(np.count_nonzero(mask)),
            mask_source=f"oneformer_scene_exclusive:{category}",
            segmentation_supported=True,
            model_class_supported=True,
            semantic_class=category,
            fallback_reason=None,
            mask_area_ratio=0.0,
            box_fill_ratio=0.0,
            detection_mask_iou=0.0,
            connected_component_count=0,
            semantic_candidate_component_count=int(
                (source_detail.get("component_filter") or {}).get(
                    "components_before", 0
                )
            ),
            box_delta={},
            category=category,
            analysis_scope="full_image",
            merged_from_names=[category],
            quality_score=confidence,
            quality_details={
                "provider": "OneFormer-Swin-L ADE20K scene-exclusive",
                "foreground_removed_pixels": foreground_removed,
                "color_texture_rescue_used": False,
                "source_category_details": source_detail,
            },
            correction_reasons=[
                (
                    "tree_confidence_0.6"
                    if category == "plant"
                    else "sky_water_probability_competition"
                ),
                "foreground_mask_subtracted",
            ],
        )
        rebuild_mask_result(
            result,
            mask,
            mask_source=f"oneformer_scene_exclusive:{category}",
            fallback_reason=None,
            detection_box=box,
            segmentation_supported=True,
            analysis_scope="full_image",
        )
        detected = DetectedObject(
            name=category,
            reaction="unknown_magic",
            confidence=confidence,
            box=box,
            center=((box[0] + box[2]) // 2, (box[1] + box[3]) // 2),
            source="oneformer_scene_exclusive",
            original_name=category,
            canonical_name=category,
        )
        instances.append(InstanceObject(detected=detected, mask_result=result))
        details[category] = {
            **source_detail,
            "accepted": True,
            "foreground_removed_pixels": foreground_removed,
            "final_area_pixels": int(result.area_pixels),
        }

    return instances, {
        "provider": "oneformer-scene-exclusive",
        "candidate_count": 3,
        "accepted_count": len(instances),
        "details": details,
    }


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
        name, _, confidence, _ = normalize_name_category_confidence(
            detection.name,
            detection.confidence,
        )
        cv2.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
        contours, _ = cv2.findContours(
            mask_result.mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        cv2.drawContours(result_image, contours, -1, color, 2)
        label = f"{mask_result.object_id} {name} {confidence:.2f}"
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

    name, category, confidence, is_unknown = normalize_name_category_confidence(
        detection.name,
        detection.confidence,
    )
    corners = corners_from_box(mask_result.mask_box)
    contour = contour_to_json(mask_result.contour)
    return {
        "object_id": mask_result.object_id,
        "name": name,
        "category": category,
        "target_category": target_category_for(name),
        "confidence": confidence,
        "excluded_from_touch": False,
        "touch_eligibility": dict(
            getattr(mask_result, "touch_eligibility", None) or {}
        ),
        "corners": corners,
        "contour": contour,
        "mask_path": mask_result.mask_path,
        "position_original": {
            "center": json_point(detection.center_original),
            "detection_box": json_box(mask_result.detection_box),
            "mask_box": json_box(mask_result.mask_box),
        },
        "four_corners_original": corners,
        "contour_original": contour,
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
            "quality_score": float(getattr(mask_result, "quality_score", 0.0)),
            "quality_details": dict(
                getattr(mask_result, "quality_details", None) or {}
            ),
            "correction_reasons": list(
                getattr(mask_result, "correction_reasons", None) or []
            ),
            "segmentation_supported": bool(mask_result.segmentation_supported),
            "fallback_reason": mask_result.fallback_reason,
            "area_pixels": int(mask_result.area_pixels),
            "box_fill_ratio": float(mask_result.box_fill_ratio),
            "detection_mask_iou": float(mask_result.detection_mask_iou),
        },
        "classification": {
            "raw_name": str(detection.name),
            "is_unknown": is_unknown,
        },
    }


def save_unity_json(
    image_path: Path,
    image: np.ndarray,
    detection_mode: str,
    processing_time: float,
    objects: Sequence[Tuple[object, ObjectMaskResult]],
    output_path: Path,
    analysis_features: Optional[Dict[str, object]] = None,
    excluded_objects: Optional[Sequence[Dict[str, object]]] = None,
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
        "analysis_features": dict(analysis_features or {}),
        "excluded_objects": list(excluded_objects or []),
        "objects": [
            build_unity_json_object(detection, mask_result)
            for detection, mask_result in objects
        ],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def analyze_image(
    image_path: Path,
    detection_mode: str,
    paths: OutputPaths,
    scene_segmentation: str = DEFAULT_SCENE_SEGMENTATION,
    oneformer_fallback: str = "existing",
    oneformer_model_dir: Optional[str] = None,
) -> AnalysisResult:
    """画像を解析し、成果物を保存して、物体一覧を呼び出し元へ返します。"""

    if not image_path.exists():
        raise FileNotFoundError(f"入力画像が見つかりません: {image_path}")

    started = time.perf_counter()
    image = imread_unicode(str(image_path))
    if image is None or image.size == 0:
        raise ValueError(f"画像を読み込めませんでした: {image_path}")

    print(f"入力画像: {image_path}")
    print(f"入力画像サイズ: width={image.shape[1]}, height={image.shape[0]}")
    print(f"検出モード: {detection_mode}")
    print(f"scene処理: {scene_segmentation}")

    # 1. YOLO-Worldで物体名、confidence、元画像基準の検出枠を取得します。
    detector = MagicPhotoDetector(detection_mode=detection_mode)
    # 不採用PoCは正式入口から明示的に無効化します。通常の共有promptによる
    # YOLO-World検出・crop再分類は維持し、food専用追加passは実行しません。
    detector.enable_focused_food_pass = False
    detector.enable_dominant_food_background_suppression = False
    configure_detector_for_unity(detector)
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
    for detection, mask_result in zip(detections, mask_results):
        mask_result.category = category_name_for(detection.name)
        mask_result.merged_from_names = list(
            getattr(detection, "merged_from_names", None) or [detection.name]
        )
    grabcut_analysis = refine_fallback_masks_with_grabcut(
        image,
        detections,
        mask_results,
    )

    # 4. 同じ意味の検出がほぼ同じマスクを指している場合は、1つの物体にまとめます。
    #    これにより、Unity側で同じ物体が二重に出る問題を減らします。
    instance_objects = [
        InstanceObject(detected=detection, mask_result=mask_result)
        for detection, mask_result in zip(detections, mask_results)
    ]
    instance_objects, semantic_merged_count = (
        consolidate_overlapping_semantic_masks(instance_objects)
    )

    # 採用済みperson専用境界補正。DeepLab personだけを安全なseedとして扱い、
    # 共通の微小成分除去や矩形GrabCutとは分離します。
    person_boundary_analysis = refine_person_boundaries(
        image,
        [item.detected for item in instance_objects],
        [item.mask_result for item in instance_objects],
        enabled=True,
    )

    scene_output: Optional[Dict[str, object]] = None
    scene_effective = "existing"
    scene_fallback_reason: Optional[str] = None
    if scene_segmentation == DEFAULT_SCENE_SEGMENTATION:
        try:
            from magicphoto_oneformer_scene import run_fixed_oneformer_scene

            scene_output = run_fixed_oneformer_scene(
                image,
                image_path,
                model_dir=(
                    Path(oneformer_model_dir).resolve()
                    if oneformer_model_dir
                    else None
                ),
            )
            scene_effective = DEFAULT_SCENE_SEGMENTATION
        except Exception as error:
            if oneformer_fallback == "error":
                raise
            scene_fallback_reason = f"{type(error).__name__}: {error}"
            print(f"OneFormer scene処理をexistingへフォールバック: {scene_fallback_reason}")

    if scene_output is not None:
        sky_mask = np.asarray(scene_output["masks"]["sky"], dtype=np.uint8)
    else:
        sky_mask = next(
            (
                item.mask
                for item in instance_objects
                if category_name_for(item.detected.name) == "sky"
            ),
            np.zeros(image.shape[:2], dtype=np.uint8),
        )

    # 採用済みsun/moon安定化。OneFormer（fallback時は既存）のskyだけを探索領域にし、
    # CLIP支持・形状・明度・局所contrastを満たす候補だけを残します。
    sun_moon_detections, sun_moon_model_analysis = (
        detector.detect_sun_moon_candidates(image, sky_mask)
    )
    sun_moon_results = [
        object_segmenter.segment_object(
            image,
            detection,
            f"object_{len(instance_objects) + index:04d}",
            semantic_mask=semantic_mask,
        )
        for index, detection in enumerate(sun_moon_detections, start=1)
    ]
    for detection, mask_result in zip(sun_moon_detections, sun_moon_results):
        mask_result.category = category_name_for(detection.name)
        mask_result.merged_from_names = [detection.name]
    refine_fallback_masks_with_grabcut(
        image,
        sun_moon_detections,
        sun_moon_results,
    )
    instance_objects.extend(
        InstanceObject(detected=detection, mask_result=mask_result)
        for detection, mask_result in zip(sun_moon_detections, sun_moon_results)
    )
    instance_objects, additional_merged_count = (
        consolidate_overlapping_semantic_masks(instance_objects)
    )
    instance_objects, sun_moon_analysis = filter_sun_moon_candidates(
        image,
        instance_objects,
        sky_mask,
    )
    sun_moon_analysis["model_pass"] = sun_moon_model_analysis

    scene_analysis: Dict[str, object] = {
        "requested": scene_segmentation,
        "effective": scene_effective,
        "fallback_used": scene_fallback_reason is not None,
        "fallback_reason": scene_fallback_reason,
    }
    if scene_output is not None:
        # 正式採用scene-exclusive: legacyのsky/water/plant/treeを全て除外し、
        # freeze済み非scene物体のmaskを差し引いたOneFormer結果だけを追加します。
        non_scene_objects = [
            item
            for item in instance_objects
            if category_name_for(item.detected.name) not in SCENE_CATEGORIES
        ]
        foreground_union = np.zeros(image.shape[:2], dtype=np.uint8)
        for item in non_scene_objects:
            foreground_union[item.mask > 0] = 255
        scene_objects, oneformer_instance_analysis = build_oneformer_scene_instances(
            scene_output,
            foreground_union,
            len(non_scene_objects) + 1,
        )
        instance_objects = non_scene_objects + scene_objects
        scene_analysis.update({
            "scene_exclusive": True,
            "legacy_scene_providers_excluded": True,
            "model_id": scene_output.get("model_id"),
            "model_dir": scene_output.get("model_dir"),
            "pretrained_dataset": scene_output.get("pretrained_dataset"),
            "tree_confidence_threshold": scene_output.get(
                "tree_confidence_threshold"
            ),
            "uncertain_margin": scene_output.get("uncertain_margin"),
            "color_texture_rescue_used": False,
            "additional_training_used": False,
            "instance_conversion": oneformer_instance_analysis,
        })

    # 採用済み品質処理。personはmagicphoto_quality側で共通の微小成分除去を
    # 明示的に回避し、それ以外だけを保守的に修正します。
    mask_quality_analysis = postprocess_mask_results(
        image,
        [item.detected for item in instance_objects],
        [item.mask_result for item in instance_objects],
        apply_repairs=True,
    )
    instance_objects = [
        item for item in instance_objects
        if item.mask_result.exclusion_reason is None
    ]

    # 展示touch対象の採用済みサイズ判定。sun/moonは保護、sceneは免除します。
    touch_records: List[Dict[str, object]] = []
    touch_excluded: List[Dict[str, object]] = []
    touch_kept: List[InstanceObject] = []
    for item in instance_objects:
        decision = evaluate_touch_eligibility(
            image.shape,
            item.detected,
            item.mask_result,
        )
        item.mask_result.touch_eligibility = decision
        record = {"object_id": item.object_id, **decision}
        touch_records.append(record)
        if not bool(decision.get("excluded_from_touch", False)):
            touch_kept.append(item)
            continue
        touch_excluded.append({
            **record,
            "stage": "touch_eligibility",
            "mask_source": str(item.mask_result.mask_source),
            "action": "excluded_before_mask_save",
        })
    instance_objects = touch_kept
    for index, item in enumerate(instance_objects, start=1):
        item.mask_result.object_id = f"object_{index:04d}"

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
        analysis_features={
            "official_entrypoint": "analyze_objects_for_unity.py",
            "scene_segmentation": scene_analysis,
            "person_boundary_refinement": person_boundary_analysis,
            "grabcut_quality_comparison": grabcut_analysis,
            "mask_quality": mask_quality_analysis,
            "sun_moon_stabilization": sun_moon_analysis,
            "touch_eligibility": {
                "evaluated_count": len(touch_records),
                "excluded_count": len(touch_excluded),
                "decisions": touch_records,
            },
            "duplicate_merge_count": (
                semantic_merged_count + additional_merged_count
            ),
            "additional_training_models_used": {
                "person_mask_refinement_unet": False,
                "person_deeplab_finetuned": False,
                "deeplab_finetuned": False,
            },
            "disabled_experiments": [
                "food_focused_prompt",
                "large_food_bbox_priority",
                "sky_water_local_correction",
            ],
        },
        excluded_objects=touch_excluded,
    )

    try:
        sent_bytes = send_to_unity(
            objects,
            host=UNITY_UDP_HOST,
            port=UNITY_UDP_PORT,
            mode=UNITY_UDP_MODE,
        )
        print(
            f"UnityへUDP送信しました: {UNITY_UDP_HOST}:{UNITY_UDP_PORT} "
            f"/ {sent_bytes} bytes"
        )
    except Exception as error:
        print(f"UnityへのUDP送信に失敗しました: {error}")

    print(f"検出物体数: {len(objects)}")
    for detection, mask_result in objects:
        name, category, confidence, _ = normalize_name_category_confidence(
            detection.name,
            detection.confidence,
        )
        print(
            f"- {mask_result.object_id}: "
            f"name={name}, "
            f"category={category}, "
            f"confidence={confidence:.4f}, "
            f"mask={mask_result.mask_path}, "
            f"source={mask_result.mask_source}"
        )
    print(f"JSON保存先: {paths.json_path}")
    print(f"result.jpg保存先: {paths.result_image_path}")
    print(f"masksフォルダ保存先: {paths.mask_dir}")
    print(
        "正式採用処理: "
        f"scene={scene_effective}, "
        f"person_refined={person_boundary_analysis.get('accepted_count', 0)}, "
        f"touch_excluded={len(touch_excluded)}"
    )
    print(f"処理時間: {processing_time:.3f}秒")
    return AnalysisResult(
        objects=instance_objects,
        paths=paths,
        processing_time=processing_time,
    )


def main() -> None:
    """プログラムの入口です。引数を読み取り、画像解析を実行します。"""

    args = parse_args()
    image_path = resolve_input_image(args.image_path)
    paths = make_output_paths(args.output_dir, args.json_name, args.result_name)
    analyze_image(
        image_path,
        args.mode,
        paths,
        scene_segmentation=args.scene_segmentation,
        oneformer_fallback=args.oneformer_fallback,
        oneformer_model_dir=args.oneformer_model_dir,
    )


if __name__ == "__main__":
    main()
