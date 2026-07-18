"""
Magic Photo Museum - Unity向け解析の共通処理

このファイルは、物体検出後の重複整理、二値マスクの品質計算、
water領域の統合、画像全体を使ったsky候補抽出、Unity向けJSON作成を担当します。

他のファイルとの関係:
    analyze_objects_optimized_for_unity.py から呼び出されます。
    既存の ml_detector_complete.py と object_segmentation.py が返す結果を受け取り、
    既存ファイルを変更せずにUnity用の形式へ整えます。

主な入力:
    YOLO-Worldの検出結果、元画像、元画像サイズの二値マスク

主な出力:
    重複を減らした物体一覧、統合water、全画面sky、Unity互換JSON用の辞書

今回追加した機能:
    ・thingとstuffを分ける処理
    ・water候補を1つの連続領域へ統合する処理
    ・skyをYOLOの小さな枠だけに制限しない全画面解析
    ・車両と人物を誤統合しにくい重複判定
    ・全処理段階と物体別マスク処理の時間計測

Unity側での使い方:
    Unityはobject_id、name、categoryを音へ対応付けます。
    タッチ判定には四角形ではなく、binary_mask.pathの白画素を使用します。
    座標とマスクは表示用に縮小せず、常に元画像と同じ座標系を保ちます。
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple
import time

import cv2
import numpy as np


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]

WATER_NAMES = {
    "water", "sea", "ocean", "river", "lake", "pond", "pool",
    "stream", "canal", "waterfall",
}
SKY_NAMES = {"sky"}
PERSON_NAMES = {"person", "human", "man", "woman", "child"}
VEHICLE_NAMES = {
    "vehicle", "car", "truck", "van", "bus", "train", "bicycle",
    "motorcycle", "motorbike",
}
BUILDING_NAMES = {
    "building", "office building", "apartment building", "warehouse",
    "house",
}

CANONICAL_NAME = {
    **{name: "water" for name in WATER_NAMES},
    **{name: "person" for name in PERSON_NAMES},
    **{name: "vehicle" for name in VEHICLE_NAMES},
    **{name: "building" for name in BUILDING_NAMES},
    "phone": "phone",
    "cell phone": "phone",
    "monitor": "monitor",
    "television": "monitor",
    "tv": "monitor",
}

CLASS_SPECIFICITY = {
    "vehicle": 0,
    "person": 1,
    "human": 0,
    "building": 1,
    "water": 0,
    "animal": 0,
    "instrument": 0,
    "musical instrument": 0,
    "car": 2,
    "truck": 2,
    "van": 2,
    "bus": 2,
    "man": 2,
    "woman": 2,
    "child": 2,
    "office building": 2,
    "apartment building": 2,
    "house": 2,
}

# thingは犬や車のように「1個、2個」と数えられる独立物体です。
# stuffは空や水面のように画像へ広がり、個数より領域そのものが重要です。
# 修正前は両方をYOLOの四角形ごとに処理したため、空の一部しか取れず、
# 同じ水面がriverとoceanの2物体になる問題がありました。
STUFF_CATEGORIES = {"water", "sky"}

PROFILE_STAGE_NAMES = [
    "image_load",
    "detector_init",
    "yolo_full_image_detection",
    "yolo_tile_detection",
    "yolo_post_filter",
    "detection_consolidation",
    "semantic_model_init",
    "semantic_inference",
    "object_segmenter_init",
    "object_mask_generation",
    "per_object_mask_generation",
    "water_global_segmentation",
    "sky_global_segmentation",
    "grabcut_total",
    "grabcut_per_object",
    "mask_consolidation",
    "mask_save",
    "result_image_draw",
    "result_image_save",
    "json_build",
    "json_save",
    "total",
]


@dataclass
class StageProfiler:
    """処理段階ごとの経過時間をtime.perf_counter()で加算します。

    同じ段階が複数回呼ばれる場合も合計値を保持します。例えばGrabCutは
    物体ごとに実行されるため、grabcut_totalへ各回の時間を加算します。
    """

    times: Dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in PROFILE_STAGE_NAMES}
    )

    @contextmanager
    def measure(self, stage: str) -> Iterator[None]:
        """指定した段階の実行時間を加算するコンテキストマネージャです。"""

        started = time.perf_counter()
        try:
            yield
        finally:
            self.add(stage, time.perf_counter() - started)

    def add(self, stage: str, seconds: float) -> None:
        """計測値を加算します。未知の段階名も将来拡張用として保持します。"""

        self.times[stage] = self.times.get(stage, 0.0) + max(0.0, float(seconds))

    def percentages(self) -> Dict[str, float]:
        """totalに対する各段階の割合を返します。"""

        total = max(self.times.get("total", 0.0), 1e-12)
        return {name: value / total * 100.0 for name, value in self.times.items()}

    def top_bottlenecks(self, count: int = 3) -> List[Tuple[str, float, float]]:
        """補助的な合計段階を除き、時間の長い処理を返します。"""

        excluded = {
            "total",
            "object_mask_generation",
            "per_object_mask_generation",
            "grabcut_total",
        }
        rows = [
            (name, seconds, self.percentages().get(name, 0.0))
            for name, seconds in self.times.items()
            if name not in excluded and seconds > 0.0
        ]
        return sorted(rows, key=lambda row: row[1], reverse=True)[:count]


@dataclass
class UnityObject:
    """検出結果とマスクをUnity出力用の追加情報と一緒に保持します。"""

    detected: Any
    mask_result: Any
    name: str
    category: str
    region_type: str = "thing"
    raw_names: List[str] = field(default_factory=list)
    source_object_ids: List[str] = field(default_factory=list)
    merged_instance_count: int = 1
    mask_generation_time_seconds: float = 0.0
    model_name: Optional[str] = None


def normalized_name(value: str) -> str:
    """比較用に英語名の大文字小文字とアンダースコアを整理します。"""

    return str(value or "").strip().lower().replace("_", " ")


def canonical_name_for(value: str) -> str:
    """同じ意味の別名を、重複判定用の代表名へ変換します。"""

    name = normalized_name(value)
    return CANONICAL_NAME.get(name, name)


def category_for_name(value: str) -> str:
    """この補助モジュールで重複判定に必要な大分類を返します。"""

    name = normalized_name(value)
    if name in WATER_NAMES:
        return "water"
    if name in SKY_NAMES:
        return "sky"
    if name in PERSON_NAMES:
        return "person"
    if name in VEHICLE_NAMES:
        return "vehicle"
    if name in BUILDING_NAMES:
        return "building"
    return "other"


def partition_stuff_detections(
    detections: Sequence[Any],
) -> Tuple[List[Any], List[Any], List[Any]]:
    """検出をthing、water、skyへ分けます。

    skyとwaterを物体別GrabCutから外すことが高速化の要点です。背景領域を
    小さな検出枠ごとに何度も処理せず、元画像全体に対して各1回だけ扱います。
    """

    things: List[Any] = []
    water: List[Any] = []
    sky: List[Any] = []
    for detection in detections:
        name = normalized_name(detection.name)
        if name in WATER_NAMES:
            water.append(detection)
        elif name in SKY_NAMES:
            sky.append(detection)
        else:
            things.append(detection)
    return things, water, sky


def box_area(box: Sequence[int]) -> int:
    """xyxy形式の箱の面積を返します。"""

    x1, y1, x2, y2 = (int(value) for value in box)
    return max(0, x2 - x1 + 1) * max(0, y2 - y1 + 1)


def box_iou(first: Sequence[int], second: Sequence[int]) -> float:
    """2つの検出枠のIoUを返します。1に近いほど同じ場所です。"""

    ax1, ay1, ax2, ay2 = (int(value) for value in first)
    bx1, by1, bx2, by2 = (int(value) for value in second)
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    intersection = max(0, ix2 - ix1 + 1) * max(0, iy2 - iy1 + 1)
    if intersection <= 0:
        return 0.0
    return intersection / max(1, box_area(first) + box_area(second) - intersection)


def intersection_over_smaller(first: Sequence[int], second: Sequence[int]) -> float:
    """交差部分が小さい方の箱をどれだけ覆うかを返します。"""

    ax1, ay1, ax2, ay2 = (int(value) for value in first)
    bx1, by1, bx2, by2 = (int(value) for value in second)
    intersection = (
        max(0, min(ax2, bx2) - max(ax1, bx1) + 1)
        * max(0, min(ay2, by2) - max(ay1, by1) + 1)
    )
    return intersection / max(1, min(box_area(first), box_area(second)))


def normalized_center_distance(first: Any, second: Any) -> float:
    """箱の大きさで正規化した中心間距離を返します。"""

    first_center = getattr(first, "center", None) or (
        (first.box[0] + first.box[2]) // 2,
        (first.box[1] + first.box[3]) // 2,
    )
    second_center = getattr(second, "center", None) or (
        (second.box[0] + second.box[2]) // 2,
        (second.box[1] + second.box[3]) // 2,
    )
    scale = max(
        1.0,
        float(np.hypot(
            max(first.box[2] - first.box[0], second.box[2] - second.box[0]),
            max(first.box[3] - first.box[1], second.box[3] - second.box[1]),
        )),
    )
    return float(np.hypot(
        first_center[0] - second_center[0],
        first_center[1] - second_center[1],
    ) / scale)


def size_similarity(first: Any, second: Any) -> float:
    """2つの箱の面積比を0から1で返します。"""

    first_area = box_area(first.box)
    second_area = box_area(second.box)
    return min(first_area, second_area) / max(1, max(first_area, second_area))


def is_duplicate_detection(first: Any, second: Any) -> bool:
    """IoU、包含、中心距離、大分類を組み合わせて同一物体か判定します。

    車両と人物は隣同士に並ぶことが多いため、通常物体より厳しいしきい値を
    使用します。IoU 0.84は、箱の大部分が同じでなければ統合しない設定です。
    """

    first_name = normalized_name(first.name)
    second_name = normalized_name(second.name)
    first_canonical = canonical_name_for(first_name)
    second_canonical = canonical_name_for(second_name)

    iou = box_iou(first.box, second.box)
    containment = intersection_over_smaller(first.box, second.box)
    distance = normalized_center_distance(first, second)
    similarity = size_similarity(first, second)

    # phone、keyboard、mouseのように意味が異なる名前でも、ほぼ完全に同じ箱が
    # 付くことがあります。修正前はカテゴリーが違うだけで別物体として残り、
    # 同じ場所をタッチしたとき複数の音候補が生まれました。90%以上同じ箱で
    # 中心と大きさも一致する場合だけ、confidenceの高い1件へ統合します。
    if (
        iou >= 0.90
        and containment >= 0.97
        and distance <= 0.06
        and similarity >= 0.75
    ):
        return True

    if first_canonical != second_canonical:
        return False

    if first_canonical in {"vehicle", "person"}:
        return (
            iou >= 0.84
            or (
                containment >= 0.96
                and distance <= 0.10
                and similarity >= 0.68
            )
        )
    return (
        iou >= 0.72
        or (
            containment >= 0.93
            and distance <= 0.16
            and similarity >= 0.55
        )
    )


def _specificity(name: str) -> int:
    return CLASS_SPECIFICITY.get(normalized_name(name), 1)


def _merge_detection_metadata(target: Any, duplicate: Any) -> None:
    """統合元の名前と検出経路を、採用した検出結果へ残します。"""

    raw_names = list(getattr(target, "raw_names", []) or [target.name])
    for value in list(getattr(duplicate, "raw_names", []) or [duplicate.name]):
        if value not in raw_names:
            raw_names.append(value)
    target.raw_names = raw_names

    sources = list(getattr(target, "sources", []) or [getattr(target, "source", "yolo")])
    for value in list(
        getattr(duplicate, "sources", [])
        or [getattr(duplicate, "source", "yolo")]
    ):
        if value not in sources:
            sources.append(value)
    target.sources = sources


def consolidate_detections(detections: Sequence[Any]) -> Tuple[List[Any], int]:
    """高コストなマスク生成より前に、ほぼ同じ検出枠を統合します。

    修正前は重複したcar/buildingごとにDeepLab切り出しやGrabCutを実行して
    いました。先に統合すると、精度を保ちながら不要なマスク処理を省けます。
    """

    kept: List[Any] = []
    merged_count = 0
    ordered = sorted(
        detections,
        key=lambda item: (_specificity(item.name), float(item.confidence)),
        reverse=True,
    )
    for candidate in ordered:
        duplicate_index = next(
            (
                index
                for index, current in enumerate(kept)
                if is_duplicate_detection(candidate, current)
            ),
            None,
        )
        if duplicate_index is None:
            candidate.raw_names = list(
                getattr(candidate, "raw_names", []) or [candidate.name]
            )
            kept.append(candidate)
            continue

        current = kept[duplicate_index]
        candidate_key = (_specificity(candidate.name), float(candidate.confidence))
        current_key = (_specificity(current.name), float(current.confidence))
        if candidate_key > current_key:
            _merge_detection_metadata(candidate, current)
            kept[duplicate_index] = candidate
        else:
            _merge_detection_metadata(current, candidate)
        merged_count += 1

    kept.sort(key=lambda item: float(item.confidence), reverse=True)
    return kept, merged_count


def clip_box(box: Sequence[int], width: int, height: int) -> Box:
    """箱を元画像の有効なピクセル範囲へ収めます。"""

    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1, min(x2, width - 1))
    y2 = max(y1, min(y2, height - 1))
    return x1, y1, x2, y2


def box_from_mask(mask: np.ndarray, fallback: Box) -> Box:
    """白画素を囲む最小の箱を返します。白画素がなければfallbackを返します。"""

    points = cv2.findNonZero(mask)
    if points is None:
        return fallback
    x, y, width, height = cv2.boundingRect(points)
    return int(x), int(y), int(x + width - 1), int(y + height - 1)


def corners_from_box(box: Box) -> Dict[str, Point]:
    """Unityが期待する左上、右上、右下、左下の順で4角を返します。"""

    x1, y1, x2, y2 = box
    return {
        "top_left": (x1, y1),
        "top_right": (x2, y1),
        "bottom_right": (x2, y2),
        "bottom_left": (x1, y2),
    }


def contour_points(contour: np.ndarray) -> List[Point]:
    """OpenCVの輪郭配列をPythonの(x, y)リストへ変換します。"""

    return [(int(point[0][0]), int(point[0][1])) for point in contour]


def contour_data(
    mask: np.ndarray,
    epsilon_ratio: float = 0.002,
    max_points: int = 512,
) -> Tuple[List[Point], List[Point], List[List[Point]]]:
    """二値マスクから詳細輪郭、簡略輪郭、全輪郭を作ります。"""

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        return [], [], []
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    primary = contours[0]
    perimeter = cv2.arcLength(primary, True)
    ratio = max(0.0001, float(epsilon_ratio))
    simplified = primary
    for _ in range(12):
        simplified = cv2.approxPolyDP(primary, max(0.5, perimeter * ratio), True)
        if len(simplified) <= max_points:
            break
        ratio *= 1.5
    return (
        contour_points(primary),
        contour_points(simplified),
        [contour_points(item) for item in contours],
    )


def mask_metrics(mask: np.ndarray, detection_box: Box) -> Dict[str, Any]:
    """統合や補正後のマスク品質値をまとめて再計算します。"""

    height, width = mask.shape[:2]
    detection_box = clip_box(detection_box, width, height)
    area_pixels = int(np.count_nonzero(mask))
    dx1, dy1, dx2, dy2 = detection_box
    detection_mask = np.zeros_like(mask)
    detection_mask[dy1:dy2 + 1, dx1:dx2 + 1] = 255
    intersection = int(np.count_nonzero(cv2.bitwise_and(mask, detection_mask)))
    union = max(1, area_pixels + box_area(detection_box) - intersection)
    component_count, _ = cv2.connectedComponents(
        (mask > 0).astype(np.uint8),
        connectivity=8,
    )
    return {
        "area_pixels": area_pixels,
        "mask_area_ratio": area_pixels / max(1, width * height),
        "box_fill_ratio": area_pixels / max(1, box_area(detection_box)),
        "detection_mask_iou": intersection / union,
        "connected_component_count": max(0, int(component_count) - 1),
    }


def apply_mask_to_result(
    result: Any,
    mask: np.ndarray,
    mask_source: str,
    fallback_reason: Optional[str],
    segmentation_supported: bool = True,
) -> Any:
    """新しいマスクをObjectMaskResult互換オブジェクトへ反映します。"""

    final_mask = ((mask > 0) * 255).astype(np.uint8)
    result.mask = final_mask
    result.mask_box = box_from_mask(final_mask, result.detection_box)
    result.corners = corners_from_box(result.mask_box)
    contour, simplified, all_contours = contour_data(final_mask)
    result.contour = contour
    result.contour_simplified = simplified
    result.all_contours = all_contours
    metrics = mask_metrics(final_mask, result.detection_box)
    for key, value in metrics.items():
        setattr(result, key, value)
    result.mask_source = mask_source
    result.segmentation_supported = bool(segmentation_supported)
    result.fallback_reason = fallback_reason
    result.mask_path = getattr(result, "mask_path", None)
    return result


def make_mask_result(
    mask: np.ndarray,
    detection_box: Box,
    object_id: str,
    mask_source: str,
    fallback_reason: Optional[str] = None,
) -> Any:
    """stuff領域用にObjectMaskResultと同じ属性を持つ結果を作ります。"""

    result = SimpleNamespace(
        object_id=object_id,
        mask=((mask > 0) * 255).astype(np.uint8),
        detection_box=detection_box,
        mask_box=detection_box,
        corners=corners_from_box(detection_box),
        contour=[],
        contour_simplified=[],
        all_contours=[],
        area_pixels=0,
        mask_source=mask_source,
        segmentation_supported=True,
        model_class_supported=True,
        semantic_class=None,
        fallback_reason=fallback_reason,
        mask_area_ratio=0.0,
        box_fill_ratio=0.0,
        detection_mask_iou=0.0,
        connected_component_count=0,
        semantic_candidate_component_count=0,
        box_delta={},
        mask_path=None,
    )
    return apply_mask_to_result(
        result,
        mask,
        mask_source,
        fallback_reason,
        segmentation_supported=fallback_reason is None,
    )


def make_detection(
    name: str,
    confidence: float,
    box: Box,
    raw_names: Optional[Sequence[str]] = None,
    source: str = "derived",
) -> Any:
    """waterやskyの統合結果用に検出結果と同じ属性を持つ値を作ります。"""

    center = ((box[0] + box[2]) // 2, (box[1] + box[3]) // 2)
    return SimpleNamespace(
        name=name,
        confidence=float(confidence),
        box=box,
        center=center,
        center_original=center,
        box_original=box,
        source=source,
        sources=[source],
        raw_names=list(raw_names or [name]),
        original_name=name,
        canonical_name=canonical_name_for(name),
    )


def grabcut_roi_mask(
    image: np.ndarray,
    detection_box: Box,
    iterations: int = 3,
) -> Optional[np.ndarray]:
    """検出枠周辺のROIだけでGrabCutを行い、元画像サイズへ戻します。

    修正前は物体ごとに元画像全体と同じ大きさの作業配列を作り、5回反復して
    いました。ここでは検出枠の周辺だけを処理し、通常3回、fastでは1回にします。
    結果だけ元画像サイズへ戻すため、Unity座標との対応は変わりません。
    """

    height, width = image.shape[:2]
    x1, y1, x2, y2 = clip_box(detection_box, width, height)
    object_width, object_height = x2 - x1 + 1, y2 - y1 + 1
    if object_width < 8 or object_height < 8:
        return None

    margin_x = max(2, int(object_width * 0.08))
    margin_y = max(2, int(object_height * 0.08))
    rx1 = max(0, x1 - margin_x)
    ry1 = max(0, y1 - margin_y)
    rx2 = min(width - 1, x2 + margin_x)
    ry2 = min(height - 1, y2 + margin_y)
    roi = image[ry1:ry2 + 1, rx1:rx2 + 1]
    local_rect = (
        max(1, x1 - rx1),
        max(1, y1 - ry1),
        min(object_width, roi.shape[1] - 2),
        min(object_height, roi.shape[0] - 2),
    )
    if local_rect[2] < 2 or local_rect[3] < 2:
        return None

    work_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            roi,
            work_mask,
            local_rect,
            background_model,
            foreground_model,
            max(1, int(iterations)),
            cv2.GC_INIT_WITH_RECT,
        )
    except cv2.error:
        return None

    local = np.where(
        (work_mask == cv2.GC_FGD) | (work_mask == cv2.GC_PR_FGD),
        255,
        0,
    ).astype(np.uint8)
    full = np.zeros((height, width), dtype=np.uint8)
    full[ry1:ry2 + 1, rx1:rx2 + 1] = local
    full[:y1, :] = 0
    full[y2 + 1:, :] = 0
    full[:, :x1] = 0
    full[:, x2 + 1:] = 0

    foreground_area = int(np.count_nonzero(full))
    fill_ratio = foreground_area / max(1, box_area((x1, y1, x2, y2)))
    if foreground_area < 12 or not 0.01 <= fill_ratio <= 0.98:
        return None
    return full


def _cleanup_stuff_mask(
    mask: np.ndarray,
    min_area_ratio: float = 0.0008,
    close_ratio: float = 0.006,
) -> np.ndarray:
    """stuff領域の小さなノイズを除き、細い切れ目と穴を軽く補正します。"""

    height, width = mask.shape[:2]
    kernel_size = max(3, int(round(min(height, width) * close_ratio)))
    if kernel_size % 2 == 0:
        kernel_size += 1
    kernel_size = min(kernel_size, 21)
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, 8)
    output = np.zeros_like(cleaned)
    min_area = max(24, int(height * width * min_area_ratio))
    for label_id in range(1, count):
        if int(stats[label_id, cv2.CC_STAT_AREA]) >= min_area:
            output[labels == label_id] = 255
    return output


def build_global_water_mask(
    image: np.ndarray,
    detections: Sequence[Any],
    fast: bool = False,
) -> Tuple[np.ndarray, str, Optional[str]]:
    """全water候補を1回のGrabCutへ渡し、同じ水面を論理和で統合します。

    river、ocean、seaは名前が異なりますが、Unityでは同じ水の領域として
    同じ音へ対応します。修正後は候補ごとの物体を残さず、全候補を1枚の
    probable-foregroundマスクへまとめてから1回だけGrabCutを行います。
    """

    height, width = image.shape[:2]
    if not detections:
        return np.zeros((height, width), dtype=np.uint8), "none", "no water detection"

    work = np.full((height, width), cv2.GC_BGD, dtype=np.uint8)
    union_box_mask = np.zeros((height, width), dtype=np.uint8)
    all_boxes = [clip_box(item.box, width, height) for item in detections]
    for x1, y1, x2, y2 in all_boxes:
        union_box_mask[y1:y2 + 1, x1:x2 + 1] = 255
        work[y1:y2 + 1, x1:x2 + 1] = cv2.GC_PR_FGD
        inset_x = max(1, int((x2 - x1 + 1) * 0.12))
        inset_y = max(1, int((y2 - y1 + 1) * 0.12))
        if x2 - x1 > inset_x * 2 and y2 - y1 > inset_y * 2:
            work[y1 + inset_y:y2 - inset_y + 1, x1 + inset_x:x2 - inset_x + 1] = (
                cv2.GC_FGD
            )

    background_model = np.zeros((1, 65), np.float64)
    foreground_model = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(
            image,
            work,
            None,
            background_model,
            foreground_model,
            1 if fast else 2,
            cv2.GC_INIT_WITH_MASK,
        )
        mask = np.where(
            (work == cv2.GC_FGD) | (work == cv2.GC_PR_FGD),
            255,
            0,
        ).astype(np.uint8)
        # 検出枠から遠い画素が偶然水にならないよう、候補領域の近傍に制限します。
        kernel_size = max(3, int(min(height, width) * 0.02))
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (kernel_size | 1, kernel_size | 1),
        )
        allowed = cv2.dilate(union_box_mask, kernel, iterations=1)
        mask = cv2.bitwise_and(mask, allowed)
        if np.count_nonzero(mask) >= 16:
            return _cleanup_stuff_mask(mask), "global_water_grabcut", None
    except cv2.error:
        pass

    # fallbackでは四角形を使うため正確な輪郭ではありません。
    # JSONのfallback_reasonに残し、Unity側が品質を判断できるようにします。
    return (
        _cleanup_stuff_mask(union_box_mask),
        "water_boxes_union_fallback",
        "global water GrabCut failed; merged detection boxes were used",
    )


def build_global_sky_mask(
    image: np.ndarray,
    sky_detections: Sequence[Any],
    exclusion_masks: Sequence[np.ndarray] = (),
) -> Tuple[np.ndarray, str, Optional[str]]:
    """画像全体の色・明るさ・位置からsky候補を1回だけ抽出します。

    現在のDeepLabV3/VOCにはskyクラスがありません。新しいモデルを勝手に
    インストールできないため、既存のOpenCVだけで動く保守的な方式を使います。
    青空、明るい雲、夕焼け、暗い夜空の候補を作り、上部またはYOLOのsky枠へ
    接続する領域を残します。建物などの既知マスクは最後に除外します。
    """

    height, width = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    hue, saturation, value = cv2.split(hsv)

    y = np.arange(height, dtype=np.float32)[:, None]
    upper_weight = y <= height * 0.82

    blue = (
        (hue >= 82)
        & (hue <= 138)
        & (saturation >= 25)
        & (value >= 35)
    )
    bright_cloud = (saturation <= 58) & (value >= 145)
    sunset = (
        ((hue <= 28) | (hue >= 150))
        & (saturation >= 25)
        & (value >= 55)
    )
    night = (value <= 95) & (saturation <= 185)

    if not sky_detections:
        # YOLOがskyを見つけていない室内写真では、白い壁や暗いテレビ画面を
        # 雲・夜空と誤る危険があります。検出枠がない場合は、上部25%に青空色が
        # 18%以上あり、上端8%にも10%以上続くときだけ解析を続けます。曇天・夕焼け・夜空は
        # YOLOのsky候補がある場合に解析し、誤反応を抑える方を優先します。
        top_height = max(1, int(height * 0.25))
        border_height = max(1, int(height * 0.08))
        blue_top_ratio = float(np.count_nonzero(blue[:top_height])) / max(
            1,
            top_height * width,
        )
        blue_border_ratio = float(np.count_nonzero(blue[:border_height])) / max(
            1,
            border_height * width,
        )
        if blue_top_ratio < 0.18 or blue_border_ratio < 0.10:
            return (
                np.zeros((height, width), dtype=np.uint8),
                "global_opencv_sky_heuristic",
                "no sky detection and insufficient blue-sky evidence",
            )

    # 建物や電線は局所的な明るさ変化が大きいことが多いため、強い輪郭を
    # 候補から少し減らします。ただし雲の輪郭まで消さないよう緩い条件です。
    gradient_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gradient_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    low_edge = cv2.magnitude(gradient_x, gradient_y) < 95.0
    day_reference_height = max(1, int(height * 0.60))
    blue_day_ratio = float(
        np.count_nonzero(blue[:day_reference_height])
    ) / max(1, day_reference_height * width)
    upper_value_median = float(np.median(value[:day_reference_height]))
    # 観覧車などの青い照明がある夜景では青色率が4%を少し超えることがあります。
    # 明度中央値が80未満なら全体は十分暗いため、青色率15%未満まで夜景として
    # 許可します。昼画像の明度中央値は通常これより大きく、屋根除外と両立します。
    night_scene = blue_day_ratio < 0.15 and upper_value_median < 80.0
    # 昼の青空が十分ある写真で暗色条件を使うと、屋根や建物の影まで夜空として
    # 白くなる問題がありました。青空率4%以上ならnight候補を無効にし、
    # 本当に暗い夜景だけでnight候補を利用します。
    color_candidate = blue | bright_cloud | sunset
    if night_scene:
        color_candidate = color_candidate | night

    candidate = (
        color_candidate
        & upper_weight
        & low_edge
    ).astype(np.uint8) * 255

    seed = np.zeros((height, width), dtype=np.uint8)
    top_rows = max(1, int(height * 0.04))
    seed[:top_rows, :] = candidate[:top_rows, :]
    for detection in sky_detections:
        x1, y1, x2, y2 = clip_box(detection.box, width, height)
        seed[y1:y2 + 1, x1:x2 + 1] = cv2.bitwise_or(
            seed[y1:y2 + 1, x1:x2 + 1],
            candidate[y1:y2 + 1, x1:x2 + 1],
        )

    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (candidate > 0).astype(np.uint8),
        8,
    )
    min_area = max(30, int(height * width * 0.0008))
    seed_label_ids = {
        int(value)
        for value in np.unique(labels[seed > 0]).tolist()
        if int(value) != 0
    }
    selected_label_ids: List[int] = []
    for label_id in range(1, count):
        overlaps_seed = label_id in seed_label_ids
        component_top = int(stats[label_id, cv2.CC_STAT_TOP])
        component_area = int(stats[label_id, cv2.CC_STAT_AREA])
        # 上端接続は補助条件であり絶対条件ではありません。sky検出枠と重なる
        # 大きな領域も残すため、屋根や指で上端が隠れた写真にも対応します。
        if night_scene:
            # 夜空ではYOLOのsky枠が照明のある建物側へずれることがあります。
            # 上半分が本当に暗いと確認できた場合だけ、上端8%へ接続する暗色領域を
            # 採用します。これにより下部の建物を夜空として拾いにくくします。
            keep_component = component_top <= int(height * 0.08)
        elif sky_detections:
            keep_component = overlaps_seed
        else:
            keep_component = component_top <= int(height * 0.35)
        if component_area >= min_area and keep_component:
            selected_label_ids.append(label_id)

    # 修正前は連結領域ごとに「labels == label_id」という元画像サイズの配列を
    # 作っていたため、細かい雲が多い写真で数十秒かかりました。採用ラベルを
    # 先に集め、np.isinを1回だけ実行すると判定内容を変えず高速化できます。
    selected = np.where(
        np.isin(labels, selected_label_ids),
        255,
        0,
    ).astype(np.uint8)

    selected = _cleanup_stuff_mask(
        selected,
        min_area_ratio=0.0008,
        close_ratio=0.004,
    )
    for mask in exclusion_masks:
        if mask.shape[:2] == (height, width):
            selected[mask > 0] = 0

    if np.count_nonzero(selected) == 0:
        return (
            selected,
            "global_opencv_sky_heuristic",
            "no reliable full-image sky region found",
        )
    return selected, "global_opencv_sky_heuristic", None


def merge_water_objects(
    objects: Sequence[UnityObject],
    image_shape: Sequence[int],
) -> Tuple[List[UnityObject], int]:
    """既に作られたwater候補マスクを1つへ統合し、全品質値を再計算します。

    この関数は自動テストでも使える純粋な統合処理です。cv2.bitwise_orで全候補を
    結合し、近接した切れ目をモルフォロジー処理でつなぎます。将来複数waterを
    保持できるようsource_object_idsとconnected_component_countを残します。
    """

    water_objects = [item for item in objects if item.category == "water"]
    other_objects = [item for item in objects if item.category != "water"]
    if not water_objects:
        return list(objects), 0

    height, width = int(image_shape[0]), int(image_shape[1])
    merged_mask = np.zeros((height, width), dtype=np.uint8)
    raw_names: List[str] = []
    source_ids: List[str] = []
    confidence = 0.0
    total_time = 0.0
    for item in water_objects:
        merged_mask = cv2.bitwise_or(merged_mask, item.mask_result.mask)
        for name in item.raw_names or [item.name]:
            if name not in raw_names:
                raw_names.append(name)
        source_ids.extend(item.source_object_ids or [item.mask_result.object_id])
        confidence = max(confidence, float(item.detected.confidence))
        total_time += item.mask_generation_time_seconds

    merged_mask = _cleanup_stuff_mask(merged_mask)
    fallback = (0, 0, width - 1, height - 1)
    merged_box = box_from_mask(merged_mask, fallback)
    result = make_mask_result(
        merged_mask,
        merged_box,
        "object_0000",
        "merged_water_masks",
    )
    detection = make_detection(
        "water",
        confidence,
        merged_box,
        raw_names=raw_names,
        source="merged_water",
    )
    merged = UnityObject(
        detected=detection,
        mask_result=result,
        name="water",
        category="water",
        region_type="stuff",
        raw_names=raw_names,
        source_object_ids=source_ids,
        merged_instance_count=len(water_objects),
        mask_generation_time_seconds=total_time,
        model_name="opencv_mask_union",
    )
    return other_objects + [merged], max(0, len(water_objects) - 1)


def masks_overlap_ratio(first: np.ndarray, second: np.ndarray) -> float:
    """2マスクの交差画素を、小さい方の面積で割った割合を返します。"""

    first_pixels = first > 0
    second_pixels = second > 0
    intersection = int(np.count_nonzero(first_pixels & second_pixels))
    smaller = min(
        int(np.count_nonzero(first_pixels)),
        int(np.count_nonzero(second_pixels)),
    )
    return intersection / max(1, smaller)


def consolidate_mask_duplicates(
    objects: Sequence[UnityObject],
) -> Tuple[List[UnityObject], int]:
    """マスク生成後に、同じ意味でほぼ同じ領域だけを重複統合します。"""

    kept: List[UnityObject] = []
    merged_count = 0
    for candidate in sorted(
        objects,
        key=lambda item: float(item.detected.confidence),
        reverse=True,
    ):
        duplicate: Optional[UnityObject] = None
        for current in kept:
            if canonical_name_for(candidate.name) != canonical_name_for(current.name):
                continue
            overlap = masks_overlap_ratio(
                candidate.mask_result.mask,
                current.mask_result.mask,
            )
            # 人物・車両は隣接しやすいため90%以上、その他は82%以上の重なりを
            # 要求します。これにより別の車を1台へまとめる危険を減らします。
            threshold = 0.90 if candidate.category in {"person", "vehicle"} else 0.82
            if overlap >= threshold:
                duplicate = current
                break
        if duplicate is None:
            kept.append(candidate)
            continue
        for value in candidate.raw_names:
            if value not in duplicate.raw_names:
                duplicate.raw_names.append(value)
        duplicate.source_object_ids.extend(candidate.source_object_ids)
        duplicate.merged_instance_count += candidate.merged_instance_count
        merged_count += 1
    return kept, merged_count


def renumber_objects(objects: Sequence[UnityObject]) -> List[UnityObject]:
    """最終順序に合わせてobject_idを振り直します。"""

    ordered = sorted(
        objects,
        key=lambda item: (
            0 if item.region_type == "thing" else 1,
            -float(item.detected.confidence),
            item.name,
        ),
    )
    for index, item in enumerate(ordered, start=1):
        item.mask_result.object_id = f"object_{index:04d}"
    return ordered


def json_point(point: Sequence[int]) -> List[int]:
    return [int(point[0]), int(point[1])]


def json_box(box: Sequence[int]) -> Dict[str, int]:
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


def contour_to_json(contour: Iterable[Sequence[int]]) -> List[List[int]]:
    return [json_point(point) for point in contour]


def object_to_json(item: UnityObject) -> Dict[str, Any]:
    """1物体を既存キーを削除しないUnity互換形式へ変換します。"""

    result = item.mask_result
    detected = item.detected
    corners = {
        key: json_point(point)
        for key, point in corners_from_box(result.mask_box).items()
    }
    contour = contour_to_json(result.contour)
    simplified = contour_to_json(result.contour_simplified)
    all_contours = [
        contour_to_json(component)
        for component in result.all_contours
    ]
    center = (
        (result.mask_box[0] + result.mask_box[2]) // 2,
        (result.mask_box[1] + result.mask_box[3]) // 2,
    )
    fallback_reason = getattr(result, "fallback_reason", None)
    mask_source = str(getattr(result, "mask_source", "unknown"))
    is_box_fallback = mask_source.endswith("box_fallback") or "boxes_union_fallback" in mask_source
    return {
        "object_id": result.object_id,
        "name": item.name,
        "category": item.category,
        "canonical_name": canonical_name_for(item.name),
        "confidence": float(detected.confidence),
        "region_type": item.region_type,
        "raw_name": item.raw_names[0] if item.raw_names else item.name,
        "raw_names": list(item.raw_names or [item.name]),
        "source_object_ids": list(item.source_object_ids),
        "merged_instance_count": int(item.merged_instance_count),
        "position_original": {
            "center": json_point(center),
            "detection_box": json_box(result.detection_box),
            "mask_box": json_box(result.mask_box),
        },
        "center": json_point(center),
        "detection_box": json_box(result.detection_box),
        "mask_box": json_box(result.mask_box),
        "four_corners_original": corners,
        "corners": corners,
        "contour_original": contour,
        "contour": contour,
        "contour_simplified_original": simplified,
        "contour_simplified": simplified,
        "all_contours_original": all_contours,
        "binary_mask": {
            "path": result.mask_path,
            "width": int(result.mask.shape[1]),
            "height": int(result.mask.shape[0]),
            "white_pixels_are_object": True,
        },
        "mask_path": result.mask_path,
        "mask_source": mask_source,
        "mask_generation_time_seconds": float(
            item.mask_generation_time_seconds
        ),
        "model_name": item.model_name,
        "mask_quality": {
            "fallback_reason": fallback_reason,
            "is_box_fallback": is_box_fallback,
            "is_exact_contour": not is_box_fallback,
            "segmentation_supported": bool(
                getattr(result, "segmentation_supported", False)
            ),
            "area_pixels": int(result.area_pixels),
            "mask_area_ratio": float(result.mask_area_ratio),
            "box_fill_ratio": float(result.box_fill_ratio),
            "detection_mask_iou": float(result.detection_mask_iou),
            "connected_component_count": int(
                result.connected_component_count
            ),
        },
    }


def build_payload(
    image_path: Path,
    image_shape: Sequence[int],
    detection_mode: str,
    objects: Sequence[UnityObject],
    profiler: StageProfiler,
    model_names: Dict[str, str],
    detection_stats: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """既存キーを維持し、計測値を追加したUnity向けJSON全体を作ります。"""

    height, width = int(image_shape[0]), int(image_shape[1])
    return {
        "schema_version": "unity_objects_optimized_1.0",
        "coordinate_space": "original_image_pixels",
        "coordinate_origin": "top_left",
        "coordinate_unit": "pixel",
        "image": {
            "path": str(image_path),
            "width": width,
            "height": height,
        },
        "detection_mode": detection_mode,
        "processing_time_seconds": float(profiler.times.get("total", 0.0)),
        "processing_stage_times": {
            name: float(profiler.times.get(name, 0.0))
            for name in PROFILE_STAGE_NAMES
        },
        "processing_stage_percentages": profiler.percentages(),
        "bottlenecks_top3": [
            {"stage": name, "seconds": seconds, "percentage": percentage}
            for name, seconds, percentage in profiler.top_bottlenecks()
        ],
        "model_names": dict(model_names),
        "detection_stats": dict(detection_stats or {}),
        "object_count": len(objects),
        "objects": [object_to_json(item) for item in objects],
    }


def remove_stale_outputs(
    mask_dir: Path,
    result_image_path: Optional[Path] = None,
    remove_result_image: bool = False,
) -> None:
    """今回のJSONに存在しない古い出力がUnityに読まれないよう削除します。

    対象は新規版専用の出力フォルダ内に限ります。既存実装のファイルや
    他フォルダには触れません。
    """

    if mask_dir.exists():
        for path in mask_dir.glob("object_*.png"):
            path.unlink()
    if (
        remove_result_image
        and result_image_path is not None
        and result_image_path.exists()
    ):
        result_image_path.unlink()


def format_profile(profiler: StageProfiler) -> str:
    """指定された形式の処理時間集計ログを作ります。"""

    percentages = profiler.percentages()
    lines = ["=== Processing Time Breakdown ==="]
    for name in PROFILE_STAGE_NAMES:
        seconds = profiler.times.get(name, 0.0)
        lines.append(f"{name}: {seconds:.3f}s ({percentages.get(name, 0.0):.1f}%)")
    lines.append("ボトルネック上位3件:")
    for index, (name, seconds, percentage) in enumerate(
        profiler.top_bottlenecks(),
        start=1,
    ):
        lines.append(f"{index}. {name}: {seconds:.3f}s ({percentage:.1f}%)")
    return "\n".join(lines)
