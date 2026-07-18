"""Unity向け 具体名 + 大分類つき物体解析スクリプト。

目的:
    Unity側で写真内の物体をタッチしたとき、まず大分類(category)で処理し、
    後から具体名(name)ごとの音や演出へ細分化できるJSONを作ります。

入力:
    解析したい画像ファイルを1つ指定します。
    例: sample1.jpg

出力:
    unity_output_category/analysis_result.json
    unity_output_category/result.jpg
    unity_output_category/masks/object_0001.png

処理の流れ:
    1. 日本語パス対応の画像読み込みで、元画像を読み込みます。
    2. YOLO-Worldで物体の具体名候補、confidence、検出枠を取得します。
    3. DeepLabV3とYOLOの検出枠を組み合わせ、物体ごとの二値マスクを作ります。
    4. DeepLabV3で対応できない物体は、GrabCutで箱内の前景を推定します。
    5. 二値マスクから、元画像基準の4角座標と輪郭座標を取得します。
    6. nameとcategoryを英語表記でJSONに保存します。

注意:
    Unityのタッチ判定では4角座標だけを使わず、必ずmask_pathの二値マスクを
    使ってください。白い画素が物体、黒い画素が背景です。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import argparse
import json
import sys
import time

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]


UNITY_CATEGORIES = [
    "living_thing",
    "instrument",
    "food",
    "water",
    "sky",
    "person",
    "vehicle",
    "device",
    "building",
    "other",
    "unknown",
]


# YOLO-Worldに優先して探してほしい名前です。
# 具体名を増やすほど、nameに具体名が残る可能性が上がります。
UNITY_PRIORITY_CLASSES = [
    "dog",
    "cat",
    "bear",
    "bird",
    "cow",
    "horse",
    "rabbit",
    "fish",
    "insect",
    "tree",
    "plant",
    "flower",
    "piano",
    "keyboard",
    "musical keyboard",
    "electronic keyboard",
    "piano keyboard",
    "computer keyboard",
    "guitar",
    "violin",
    "drum",
    "trumpet",
    "saxophone",
    "flute",
    "pizza",
    "apple",
    "banana",
    "cake",
    "bread",
    "rice",
    "meat",
    "ice cream",
    "water",
    "sea",
    "ocean",
    "river",
    "lake",
    "pond",
    "pool",
    "waterfall",
    "sky",
    "sun",
    "moon",
    "cloud",
    "star",
    "person",
    "human",
    "man",
    "woman",
    "child",
    "car",
    "truck",
    "van",
    "bus",
    "train",
    "bicycle",
    "motorcycle",
    "phone",
    "cell phone",
    "monitor",
    "television",
    "computer",
    "laptop",
    "mouse",
    "building",
    "house",
    "office building",
    "apartment building",
    "warehouse",
    "animal",
    "instrument",
    "musical instrument",
    "food",
]


NAME_ALIASES = {
    "musical keyboard": "keyboard",
    "electronic keyboard": "keyboard",
    "piano keyboard": "keyboard",
    "computer keyboard": "keyboard",
    "cell phone": "phone",
    "television": "monitor",
    "tv": "monitor",
    "motorbike": "motorcycle",
    "pottedplant": "plant",
    "potted plant": "plant",
}


CATEGORY_BY_NAME = {
    "dog": "living_thing",
    "cat": "living_thing",
    "bear": "living_thing",
    "bird": "living_thing",
    "cow": "living_thing",
    "horse": "living_thing",
    "rabbit": "living_thing",
    "fish": "living_thing",
    "insect": "living_thing",
    "animal": "living_thing",
    "tree": "living_thing",
    "plant": "living_thing",
    "flower": "living_thing",
    "piano": "instrument",
    "keyboard": "instrument",
    "guitar": "instrument",
    "violin": "instrument",
    "drum": "instrument",
    "trumpet": "instrument",
    "saxophone": "instrument",
    "flute": "instrument",
    "instrument": "instrument",
    "musical instrument": "instrument",
    "pizza": "food",
    "apple": "food",
    "banana": "food",
    "cake": "food",
    "bread": "food",
    "rice": "food",
    "meat": "food",
    "ice cream": "food",
    "food": "food",
    "water": "water",
    "sea": "water",
    "ocean": "water",
    "river": "water",
    "lake": "water",
    "pond": "water",
    "pool": "water",
    "waterfall": "water",
    "sky": "sky",
    "sun": "sky",
    "moon": "sky",
    "cloud": "sky",
    "star": "sky",
    "person": "person",
    "human": "person",
    "man": "person",
    "woman": "person",
    "child": "person",
    "car": "vehicle",
    "truck": "vehicle",
    "van": "vehicle",
    "bus": "vehicle",
    "train": "vehicle",
    "bicycle": "vehicle",
    "motorcycle": "vehicle",
    "vehicle": "vehicle",
    "phone": "device",
    "monitor": "device",
    "computer": "device",
    "laptop": "device",
    "mouse": "device",
    "building": "building",
    "house": "building",
    "office building": "building",
    "apartment building": "building",
    "warehouse": "building",
}


UNKNOWN_NAMES = {
    "",
    "object",
    "thing",
    "unknown",
    "unknown object",
    "unknown_object",
}


@dataclass(frozen=True)
class OutputPaths:
    """出力先をまとめるデータクラス。

    引数:
        output_dir: JSON、確認画像、masksフォルダを置く親フォルダ。
        json_path: Unity向けJSONの保存先。
        result_image_path: 確認用画像の保存先。
        mask_dir: object_idごとの二値マスク保存フォルダ。
    """

    output_dir: Path
    json_path: Path
    result_image_path: Path
    mask_dir: Path


def require_cv() -> Tuple[Any, Any]:
    """OpenCVとNumPyが使えるか確認します。

    戻り値:
        (cv2_module, numpy_module)

    注意点:
        画像処理にはOpenCVとNumPyが必須です。不足している場合は、学生が
        原因を見つけやすいよう日本語エラーを出します。
    """

    if cv2 is None or np is None:
        raise ImportError(
            "OpenCVまたはNumPyを読み込めません。"
            ".venvに opencv-python と numpy が入っているか確認してください。"
        )
    return cv2, np


def load_pipeline_modules() -> Dict[str, Any]:
    """既存実装から再利用するクラスと関数を遅延読み込みします。

    戻り値:
        既存実装の検出器、マスク作成器、画像読み書き関数などを入れた辞書。

    注意点:
        この関数の中で初めてYOLOやDeepLab関連を読み込みます。
        そのため、カテゴリー変換だけをテストするときに重いAIライブラリを
        読み込まずに済みます。
    """

    from ml_detector_complete import MagicPhotoDetector, imread_unicode, imwrite_unicode
    from ml_detector_instance_segmentation import (
        InstanceObject,
        consolidate_instance_detections,
        consolidate_overlapping_semantic_masks,
    )
    from object_segmentation import DeepLabBoxObjectSegmenter
    from semantic_segmentation_multi import SemanticSegmenterMulti

    return {
        "MagicPhotoDetector": MagicPhotoDetector,
        "imread_unicode": imread_unicode,
        "imwrite_unicode": imwrite_unicode,
        "InstanceObject": InstanceObject,
        "consolidate_instance_detections": consolidate_instance_detections,
        "consolidate_overlapping_semantic_masks": (
            consolidate_overlapping_semantic_masks
        ),
        "DeepLabBoxObjectSegmenter": DeepLabBoxObjectSegmenter,
        "SemanticSegmenterMulti": SemanticSegmenterMulti,
    }


def parse_args() -> argparse.Namespace:
    """コマンドライン引数を読み取ります。

    戻り値:
        argparse.Namespace。画像パス、検出モード、出力先などを持ちます。

    座標系:
        引数では座標を扱いません。出力される座標はすべて元画像基準です。
    """

    parser = argparse.ArgumentParser(
        description=(
            "画像内の物体を検出し、具体名と大分類つきのUnity向けJSON、"
            "確認画像、二値マスクを保存します。"
        )
    )
    parser.add_argument(
        "image_path",
        nargs="?",
        help="解析する画像ファイル。相対パスの場合はスクリプトのフォルダ基準です。",
    )
    parser.add_argument(
        "--mode",
        choices=("standard", "accuracy", "auto"),
        default="accuracy",
        help="検出モード。精度重視ならaccuracy、軽く試すならstandardです。",
    )
    parser.add_argument(
        "--output-dir",
        default="unity_output_category",
        help="結果を保存するフォルダです。",
    )
    parser.add_argument(
        "--json-name",
        default="analysis_result.json",
        help="Unity向けJSONのファイル名です。",
    )
    parser.add_argument(
        "--result-name",
        default="result.jpg",
        help="確認用画像のファイル名です。",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="カテゴリー変換など、AIモデルを使わない軽量テストだけを実行します。",
    )
    return parser.parse_args()


def resolve_input_image(image_path_text: str) -> Path:
    """入力画像パスを絶対パスへ変換します。

    引数:
        image_path_text: ユーザーが指定した画像パス。

    戻り値:
        絶対パス化したPath。

    注意点:
        相対パスは、このスクリプトが置かれているフォルダ基準で解決します。
        これにより、コマンドプロンプト、PowerShell、VS Codeで結果が揃います。
    """

    image_path = Path(image_path_text)
    if not image_path.is_absolute():
        image_path = CURRENT_DIR / image_path
    return image_path.resolve()


def make_output_paths(
    output_dir_text: str,
    json_name: str,
    result_name: str,
) -> OutputPaths:
    """出力先フォルダとファイル名を作ります。

    引数:
        output_dir_text: 出力フォルダ名。相対パスならスクリプト基準。
        json_name: JSONファイル名。
        result_name: 確認用画像ファイル名。

    戻り値:
        OutputPaths。

    注意点:
        masksフォルダはここで作成します。既存のPythonファイルは変更しません。
    """

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


def normalize_detection_name(raw_name: str) -> str:
    """AIが返した物体名を英語表記のまま整理します。

    引数:
        raw_name: YOLO-Worldなどが返した物体名。

    戻り値:
        Unity側で扱いやすい英語のname。

    注意点:
        animal、instrument、food、waterなどの総称はunknownに変換しません。
        大分類として意味があるため、そのまま残します。
    """

    name = str(raw_name or "").strip().lower().replace("_", " ")
    if name in UNKNOWN_NAMES:
        return "unknown_object"
    return NAME_ALIASES.get(name, name)


def category_for_name(name: str) -> str:
    """具体名または総称から、Unity用の大分類を返します。

    引数:
        name: normalize_detection_name済みの英語名。

    戻り値:
        living_thing、instrument、foodなどのcategory。

    注意点:
        完全に判断できない名前だけunknownにします。
        分類表にないが物体名としては存在する名前はotherにします。
    """

    if name == "unknown_object":
        return "unknown"
    return CATEGORY_BY_NAME.get(name, "other")


def normalize_name_category_confidence(
    raw_name: str,
    raw_confidence: float,
) -> Tuple[str, str, float, bool]:
    """検出結果をname、category、confidenceへ整理します。

    引数:
        raw_name: AIが返した名前。
        raw_confidence: AIが返したconfidence。

    戻り値:
        (name, category, confidence, is_unknown)

    注意点:
        間違った具体名を無理に出すより、大分類を正しく残す方を優先します。
        総称はunknownへ落とさず、対応するcategoryに入れます。
    """

    name = normalize_detection_name(raw_name)
    category = category_for_name(name)
    confidence = float(raw_confidence)
    is_unknown = name == "unknown_object" or category == "unknown"
    if is_unknown:
        confidence = min(confidence, 0.20)
    return name, category, confidence, is_unknown


def configure_detector_for_category_unity(detector: Any) -> None:
    """Unity用の具体名候補を既存YOLO-World検出器へ追加します。

    引数:
        detector: 既存のMagicPhotoDetector。

    戻り値:
        なし。detector内部のcustom_classesを更新します。

    注意点:
        既存ファイルは変更しません。実行中のdetectorインスタンスだけに候補名を
        追加します。
    """

    classes = list(detector.custom_classes)
    for class_name in UNITY_PRIORITY_CLASSES:
        if class_name not in classes:
            classes.append(class_name)
    detector.custom_classes = classes
    detector.model.set_classes(classes)

    for class_name in UNITY_PRIORITY_CLASSES:
        detector.class_confidence_thresholds.setdefault(class_name, 0.18)


def json_point(point: Point) -> List[int]:
    """点をJSON用の[x, y]へ変換します。"""

    return [int(point[0]), int(point[1])]


def json_box(box: Sequence[int]) -> Dict[str, int]:
    """xyxy形式の箱をUnityで読みやすい辞書に変換します。

    座標系:
        元画像基準。左上が原点、右がX正方向、下がY正方向です。
    """

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


def clip_box_to_image(box: Sequence[int], width: int, height: int) -> Box:
    """4角座標が画像範囲を越えないように補正します。

    引数:
        box: x1, y1, x2, y2。
        width: 元画像の幅。
        height: 元画像の高さ。

    戻り値:
        画像範囲内に収めたBox。
    """

    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1, min(x2, width - 1))
    y2 = max(y1, min(y2, height - 1))
    return x1, y1, x2, y2


def corners_from_box(box: Box, width: int, height: int) -> Dict[str, List[int]]:
    """元画像基準の4角座標を指定順で作ります。

    引数:
        box: x1, y1, x2, y2。
        width: 元画像の幅。
        height: 元画像の高さ。

    戻り値:
        top_left、top_right、bottom_right、bottom_leftを持つ辞書。
    """

    x1, y1, x2, y2 = clip_box_to_image(box, width, height)
    return {
        "top_left": [x1, y1],
        "top_right": [x2, y1],
        "bottom_right": [x2, y2],
        "bottom_left": [x1, y2],
    }


def contour_to_json(contour: Sequence[Point]) -> List[List[int]]:
    """輪郭点をJSON用の[[x, y], ...]へ変換します。"""

    return [json_point(point) for point in contour]


def mask_box(mask: Any, fallback: Box) -> Box:
    """二値マスクの白い部分を囲む最小の箱を返します。

    注意点:
        白い部分がない場合は、検出枠fallbackを返します。
    """

    cv2_module, _ = require_cv()
    points = cv2_module.findNonZero(mask)
    if points is None:
        return fallback
    x, y, width, height = cv2_module.boundingRect(points)
    return int(x), int(y), int(x + width - 1), int(y + height - 1)


def contour_points(contour: Any) -> List[Point]:
    """OpenCVの輪郭配列をPythonの座標リストへ変換します。"""

    return [
        (int(point[0][0]), int(point[0][1]))
        for point in contour
    ]


def contour_data(mask: Any) -> Tuple[List[Point], List[Point], List[List[Point]]]:
    """二値マスクから詳細輪郭と簡略輪郭を取得します。

    引数:
        mask: 元画像と同じ幅・高さの二値マスク。

    戻り値:
        (詳細輪郭, 簡略輪郭, 全輪郭)

    注意点:
        contourはタッチ判定の補助やデバッグに使えます。
        実際のタッチ判定はmask_pathの画像を使う方が安全です。
    """

    cv2_module, _ = require_cv()
    contours, _ = cv2_module.findContours(
        mask,
        cv2_module.RETR_EXTERNAL,
        cv2_module.CHAIN_APPROX_NONE,
    )
    if not contours:
        return [], [], []
    contours = sorted(contours, key=cv2_module.contourArea, reverse=True)
    primary = contours[0]
    perimeter = cv2_module.arcLength(primary, True)
    simplified = cv2_module.approxPolyDP(primary, max(0.5, perimeter * 0.002), True)
    return (
        contour_points(primary),
        contour_points(simplified),
        [contour_points(item) for item in contours],
    )


def update_mask_result_from_mask(
    result: Any,
    mask: Any,
    mask_source: str,
    fallback_reason: Optional[str],
) -> None:
    """改善したマスクを既存のObjectMaskResultへ反映します。

    引数:
        result: object_segmentation.pyが返すObjectMaskResult。
        mask: 改善後の二値マスク。
        mask_source: マスクの作成方法。
        fallback_reason: fallbackや補正の理由。

    注意点:
        ObjectMaskResultは既存実装のデータクラスです。新規ファイル内で値だけ更新し、
        既存ファイル自体は変更しません。
    """

    cv2_module, np_module = require_cv()
    final_mask = ((mask > 0) * 255).astype(np_module.uint8)
    result.mask = final_mask
    result.mask_box = mask_box(final_mask, result.detection_box)
    result.corners = {
        "top_left": (result.mask_box[0], result.mask_box[1]),
        "top_right": (result.mask_box[2], result.mask_box[1]),
        "bottom_right": (result.mask_box[2], result.mask_box[3]),
        "bottom_left": (result.mask_box[0], result.mask_box[3]),
    }
    contour, contour_simplified, all_contours = contour_data(final_mask)
    result.contour = contour
    result.contour_simplified = contour_simplified
    result.all_contours = all_contours
    result.area_pixels = int(np_module.count_nonzero(final_mask))
    result.mask_source = mask_source
    result.segmentation_supported = True
    result.fallback_reason = fallback_reason

    image_area = max(1, final_mask.shape[0] * final_mask.shape[1])
    x1, y1, x2, y2 = result.detection_box
    box_area = max(1, (x2 - x1 + 1) * (y2 - y1 + 1))
    result.mask_area_ratio = result.area_pixels / image_area
    result.box_fill_ratio = result.area_pixels / box_area
    result.detection_mask_iou = result.area_pixels / box_area
    component_count, _ = cv2_module.connectedComponents(
        (final_mask > 0).astype(np_module.uint8),
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


def try_grabcut_mask(image: Any, detection_box: Box) -> Optional[Any]:
    """box fallbackを減らすため、GrabCutで箱内の前景を推定します。

    引数:
        image: 元画像。
        detection_box: YOLOが返した検出枠。

    戻り値:
        成功時は元画像と同じ幅・高さの二値マスク。失敗時はNone。

    注意点:
        DeepLabV3が知らない楽器などは矩形マスクになりやすいです。
        矩形マスクは背景も含むため、背景タッチ誤反応の原因になります。
        GrabCutは完全ではありませんが、矩形より背景を減らせることがあります。
    """

    cv2_module, np_module = require_cv()
    height, width = image.shape[:2]
    x1, y1, x2, y2 = clip_box_to_image(detection_box, width, height)
    box_width = x2 - x1 + 1
    box_height = y2 - y1 + 1
    if box_width < 8 or box_height < 8:
        return None

    box_area_ratio = (box_width * box_height) / max(1, width * height)
    if box_area_ratio > 0.65:
        return None

    grabcut_mask = np_module.zeros((height, width), dtype=np_module.uint8)
    rectangle = (int(x1), int(y1), int(box_width), int(box_height))
    bgd_model = np_module.zeros((1, 65), np_module.float64)
    fgd_model = np_module.zeros((1, 65), np_module.float64)
    try:
        cv2_module.grabCut(
            image,
            grabcut_mask,
            rectangle,
            bgd_model,
            fgd_model,
            5,
            cv2_module.GC_INIT_WITH_RECT,
        )
    except Exception:
        return None

    foreground = np_module.where(
        (grabcut_mask == cv2_module.GC_FGD)
        | (grabcut_mask == cv2_module.GC_PR_FGD),
        255,
        0,
    ).astype(np_module.uint8)
    foreground[:, :x1] = 0
    foreground[:, x2 + 1:] = 0
    foreground[:y1, :] = 0
    foreground[y2 + 1:, :] = 0

    kernel = cv2_module.getStructuringElement(cv2_module.MORPH_ELLIPSE, (3, 3))
    foreground = cv2_module.morphologyEx(
        foreground,
        cv2_module.MORPH_CLOSE,
        kernel,
        iterations=1,
    )

    foreground_area = int(np_module.count_nonzero(foreground))
    box_area = max(1, box_width * box_height)
    fill_ratio = foreground_area / box_area
    if foreground_area < 12 or fill_ratio < 0.01 or fill_ratio > 0.98:
        return None
    return foreground


def refine_fallback_masks_with_grabcut(image: Any, mask_results: Sequence[Any]) -> None:
    """box fallbackになった物体をGrabCutで補正します。

    引数:
        image: 元画像。
        mask_results: 物体ごとのマスク結果。

    戻り値:
        なし。mask_resultsの中身を必要に応じて更新します。
    """

    for result in mask_results:
        if result.mask_source != "box_fallback":
            continue
        refined = try_grabcut_mask(image, result.detection_box)
        if refined is None:
            continue
        update_mask_result_from_mask(
            result,
            refined,
            "grabcut_box",
            "deeplab unsupported; refined by grabcut",
        )


def remove_old_mask_files(mask_dir: Path) -> None:
    """前回実行時の古いobject_*.pngを削除します。

    注意点:
        JSONにない古いマスクが残ると、Unity側で取り違えやすくなります。
        削除対象はこのスクリプトの出力先masksフォルダ内だけです。
    """

    for path in mask_dir.glob("object_*.png"):
        path.unlink()


def save_binary_masks(mask_dir: Path, mask_results: Sequence[Any], imwrite_unicode: Any) -> None:
    """各物体の二値マスクをPNG保存します。

    引数:
        mask_dir: 保存先masksフォルダ。
        mask_results: 物体ごとのマスク結果。
        imwrite_unicode: 既存実装の日本語パス対応画像保存関数。

    注意点:
        保存するマスクは元画像と同じ幅・高さです。
        白が物体、黒が背景です。
    """

    remove_old_mask_files(mask_dir)
    for result in mask_results:
        mask_path = mask_dir / f"{result.object_id}.png"
        if not imwrite_unicode(str(mask_path), result.mask):
            raise OSError(f"二値マスクを保存できませんでした: {mask_path}")
        result.mask_path = mask_path.relative_to(mask_dir.parent).as_posix()


def draw_result_image(image: Any, objects: Sequence[Tuple[Any, Any]]) -> Any:
    """検出結果を確認するためのresult.jpgを作ります。

    引数:
        image: 元画像。
        objects: (検出結果, マスク結果)のリスト。

    戻り値:
        検出枠、輪郭、object_id、name、categoryを書いた画像。
    """

    cv2_module, _ = require_cv()
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
        name, category, confidence, _ = normalize_name_category_confidence(
            detection.name,
            detection.confidence,
        )
        cv2_module.rectangle(result_image, (x1, y1), (x2, y2), color, 2)
        contours, _ = cv2_module.findContours(
            mask_result.mask,
            cv2_module.RETR_EXTERNAL,
            cv2_module.CHAIN_APPROX_SIMPLE,
        )
        cv2_module.drawContours(result_image, contours, -1, color, 2)
        label = f"{mask_result.object_id} {name}/{category} {confidence:.2f}"
        cv2_module.putText(
            result_image,
            label,
            (x1, max(24, y1 - 8)),
            cv2_module.FONT_HERSHEY_SIMPLEX,
            0.52,
            color,
            2,
            cv2_module.LINE_AA,
        )
    return result_image


def build_unity_json_object(
    detection: Any,
    mask_result: Any,
    image_width: int,
    image_height: int,
) -> Dict[str, Any]:
    """1つの物体をUnity向けJSONへ変換します。

    引数:
        detection: YOLO-Worldの検出結果。
        mask_result: 物体ごとの二値マスクと輪郭。
        image_width: 元画像の幅。
        image_height: 元画像の高さ。

    戻り値:
        Unityが読む1物体分の辞書。

    座標系:
        detection_box、corners、contour、contour_simplifiedはすべて元画像基準です。
    """

    name, category, confidence, is_unknown = normalize_name_category_confidence(
        detection.name,
        detection.confidence,
    )
    detection_box = clip_box_to_image(mask_result.detection_box, image_width, image_height)
    mask_box_clipped = clip_box_to_image(mask_result.mask_box, image_width, image_height)
    fallback_reason = mask_result.fallback_reason
    is_box_fallback = mask_result.mask_source == "box_fallback"

    return {
        "object_id": mask_result.object_id,
        "name": name,
        "category": category,
        "confidence": confidence,
        "detection_box": json_box(detection_box),
        "corners": corners_from_box(mask_box_clipped, image_width, image_height),
        "contour": contour_to_json(mask_result.contour),
        "contour_simplified": contour_to_json(mask_result.contour_simplified),
        "mask_path": mask_result.mask_path,
        "mask_source": mask_result.mask_source,
        "mask_quality": {
            "fallback_reason": fallback_reason,
            "is_box_fallback": is_box_fallback,
            "is_exact_contour": not is_box_fallback,
            "segmentation_supported": bool(mask_result.segmentation_supported),
            "area_pixels": int(mask_result.area_pixels),
            "box_fill_ratio": float(mask_result.box_fill_ratio),
            "detection_mask_iou": float(mask_result.detection_mask_iou),
            "connected_component_count": int(mask_result.connected_component_count),
            "mask_width": int(mask_result.mask.shape[1]),
            "mask_height": int(mask_result.mask.shape[0]),
            "white_pixels_are_object": True,
        },
        "classification": {
            "raw_name": str(detection.name),
            "is_unknown": is_unknown,
        },
    }


def save_unity_json(
    image_path: Path,
    image: Any,
    detection_mode: str,
    processing_time: float,
    objects: Sequence[Tuple[Any, Any]],
    output_path: Path,
) -> None:
    """Unity向けJSONをUTF-8で保存します。

    引数:
        image_path: 入力画像パス。
        image: 元画像。
        detection_mode: standard、accuracy、autoのいずれか。
        processing_time: 処理時間。
        objects: (検出結果, マスク結果)のリスト。
        output_path: JSON保存先。
    """

    image_height, image_width = image.shape[:2]
    payload = {
        "schema_version": "unity_objects_category_1.0",
        "coordinate_space": "original_image_pixels",
        "coordinate_origin": "top_left",
        "coordinate_unit": "pixel",
        "image": {
            "path": str(image_path),
            "width": int(image_width),
            "height": int(image_height),
        },
        "categories": UNITY_CATEGORIES,
        "detection_mode": detection_mode,
        "processing_time_seconds": float(processing_time),
        "object_count": len(objects),
        "objects": [
            build_unity_json_object(
                detection,
                mask_result,
                image_width,
                image_height,
            )
            for detection, mask_result in objects
        ],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def analyze_image(image_path: Path, detection_mode: str, paths: OutputPaths) -> None:
    """画像を解析し、カテゴリーつきUnity JSON、確認画像、二値マスクを保存します。

    引数:
        image_path: 入力画像パス。
        detection_mode: YOLO検出モード。
        paths: 出力先情報。

    注意点:
        既存のPythonファイルは変更しません。
        出力はunity_output_categoryフォルダ以下だけに作ります。
    """

    require_cv()
    modules = load_pipeline_modules()
    imread_unicode = modules["imread_unicode"]
    imwrite_unicode = modules["imwrite_unicode"]

    if not image_path.exists():
        raise FileNotFoundError(f"入力画像が見つかりません: {image_path}")

    started = time.perf_counter()
    image = imread_unicode(str(image_path))
    if image is None or image.size == 0:
        raise ValueError(f"画像を読み込めませんでした: {image_path}")

    print(f"入力画像: {image_path}")
    print(f"入力画像サイズ: width={image.shape[1]}, height={image.shape[0]}")
    print(f"検出モード: {detection_mode}")

    detector = modules["MagicPhotoDetector"](detection_mode=detection_mode)
    configure_detector_for_category_unity(detector)
    detections = detector.detect_from_image(image)
    detections = modules["consolidate_instance_detections"](detections)

    semantic_segmenter = modules["SemanticSegmenterMulti"](input_size=640)
    semantic_mask = semantic_segmenter.segment_image(image)

    object_segmenter = modules["DeepLabBoxObjectSegmenter"](
        semantic_segmenter=semantic_segmenter,
        epsilon_ratio=0.002,
        max_simplified_points=512,
    )
    mask_results = object_segmenter.segment_objects(
        image,
        detections,
        semantic_mask=semantic_mask,
    )
    refine_fallback_masks_with_grabcut(image, mask_results)

    instance_objects = [
        modules["InstanceObject"](detected=detection, mask_result=mask_result)
        for detection, mask_result in zip(detections, mask_results)
    ]
    instance_objects, merged_count = modules["consolidate_overlapping_semantic_masks"](
        instance_objects
    )
    mask_results = [item.mask_result for item in instance_objects]
    save_binary_masks(paths.mask_dir, mask_results, imwrite_unicode)

    objects = [(item.detected, item.mask_result) for item in instance_objects]
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
    print(f"重複統合数: {merged_count}")
    box_fallback_items = []
    for detection, mask_result in objects:
        name, category, confidence, _ = normalize_name_category_confidence(
            detection.name,
            detection.confidence,
        )
        if mask_result.mask_source == "box_fallback":
            box_fallback_items.append(mask_result.object_id)
        print(
            f"- {mask_result.object_id}: "
            f"name={name}, category={category}, "
            f"confidence={confidence:.4f}, "
            f"mask={mask_result.mask_path}, "
            f"mask_source={mask_result.mask_source}, "
            f"fallback_reason={mask_result.fallback_reason or 'none'}"
        )

    print(f"JSON保存先: {paths.json_path}")
    print(f"result.jpg保存先: {paths.result_image_path}")
    print(f"masksフォルダ保存先: {paths.mask_dir}")
    print(
        "box fallbackになった物体: "
        + (", ".join(box_fallback_items) if box_fallback_items else "なし")
    )
    print(f"処理時間: {processing_time:.3f}秒")


def run_self_tests() -> None:
    """AIモデルを使わず、分類表とJSON前提の軽量テストを実行します。

    注意点:
        実画像の検出精度テストではありません。
        dogがliving_thingになる、総称がunknownへ落ちない、などの
        ルールが壊れていないかを確認します。
    """

    expected_categories = {
        "dog": "living_thing",
        "cat": "living_thing",
        "bear": "living_thing",
        "piano": "instrument",
        "guitar": "instrument",
        "pizza": "food",
        "river": "water",
        "sun": "sky",
        "phone": "device",
        "car": "vehicle",
        "animal": "living_thing",
        "instrument": "instrument",
        "musical instrument": "instrument",
        "food": "food",
        "water": "water",
        "unknown object": "unknown",
    }
    for name, expected in expected_categories.items():
        actual_name, actual_category, _, _ = normalize_name_category_confidence(
            name,
            0.9,
        )
        assert actual_category == expected, (
            f"{name} のcategoryが違います: "
            f"actual={actual_category}, expected={expected}"
        )
        if name in {"animal", "instrument", "musical instrument", "food", "water"}:
            assert actual_name != "unknown_object", f"{name} がunknown化されています"

    corners = corners_from_box((5, 6, 20, 30), width=100, height=80)
    assert corners == {
        "top_left": [5, 6],
        "top_right": [20, 6],
        "bottom_right": [20, 30],
        "bottom_left": [5, 30],
    }
    clipped = corners_from_box((-10, -2, 200, 300), width=100, height=80)
    assert clipped == {
        "top_left": [0, 0],
        "top_right": [99, 0],
        "bottom_right": [99, 79],
        "bottom_left": [0, 79],
    }
    print("軽量テスト成功: カテゴリー変換、総称保持、unknown判定、4角座標補正")


def main() -> None:
    """プログラムの入口です。"""

    args = parse_args()
    if args.self_test:
        run_self_tests()
        return
    if not args.image_path:
        raise ValueError("入力画像を指定してください。例: sample1.jpg")
    image_path = resolve_input_image(args.image_path)
    paths = make_output_paths(args.output_dir, args.json_name, args.result_name)
    analyze_image(image_path, args.mode, paths)


if __name__ == "__main__":
    main()
