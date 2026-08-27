"""Instance-oriented analysis pipeline for Magic Photo."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import json
import re
import time

import cv2
import numpy as np

from ml_detector_complete import (
    DetectedObject,
    MagicPhotoDetector,
    category_name_for,
    imwrite_unicode,
)
from object_segmentation import (
    DeepLabBoxObjectSegmenter,
    ObjectMaskResult,
    rebuild_mask_result,
)
from semantic_segmentation_multi import SemanticSegmenterMulti


INSTANCE_CANONICAL_NAMES = {
    "phone": "phone",
    "cell phone": "phone",
    "monitor": "monitor",
    "television": "monitor",
    "tv": "monitor",
    "animal": "animal",
    "dog": "animal",
    "cat": "animal",
    "bird": "animal",
    "horse": "animal",
    "rabbit": "animal",
    "wildlife": "animal",
    "large animal": "animal",
    "bear": "animal",
    "fish": "animal",
    "cow": "animal",
    "sheep": "animal",
    "elephant": "animal",
    "giraffe": "animal",
    "zebra": "animal",
    "water": "water",
    "sea": "water",
    "ocean": "water",
    "river": "water",
    "lake": "water",
    "pond": "water",
    "pool": "water",
    "waterfall": "water",
}

INSTANCE_SYNONYM_GROUPS = [
    {"person", "human", "man", "woman", "boy", "girl", "child", "adult", "people"},
    {"vehicle", "car", "truck", "van", "bus"},
    {"monitor", "television", "tv", "display", "screen"},
    {"phone", "cell phone", "smartphone"},
    {"water", "sea", "ocean", "river", "lake", "pond", "pool", "waterfall"},
    {
        "building",
        "apartment building",
        "office building",
        "warehouse",
        "house",
    },
    {
        "animal", "wildlife", "large animal", "dog", "cat", "bird",
        "fish", "horse", "rabbit", "cow", "sheep", "bear", "elephant",
        "giraffe", "zebra",
    },
    {
        "instrument", "musical instrument", "piano", "keyboard", "guitar",
        "violin", "drum", "flute", "trumpet", "saxophone",
    },
    {
        "food", "dish", "meal", "bread", "cake", "dessert",
        "ice cream", "ice cream cone", "soft serve",
        "soft serve ice cream", "gelato",
    },
]

FOREGROUND_CATEGORIES = {
    "person", "animal", "food", "vehicle", "instrument", "furniture",
    "electronics", "sun", "moon",
}
MIDGROUND_CATEGORIES = {"building", "plant", "other"}
BACKGROUND_CATEGORIES = {"sky", "water", "ground"}


@dataclass
class InstanceObject:
    detected: DetectedObject
    mask_result: ObjectMaskResult

    @property
    def object_id(self) -> str:
        return self.mask_result.object_id

    @property
    def mask(self) -> np.ndarray:
        return self.mask_result.mask

    @property
    def area_pixels(self) -> int:
        return self.mask_result.area_pixels


@dataclass
class InstanceAnalysis:
    detector: MagicPhotoDetector
    objects: List[InstanceObject]
    semantic_mask: np.ndarray
    result_path: Path
    processing_time: float
    semantic_supported_names: List[str]
    fallback_names: List[str]


def _json_point(point: Tuple[int, int]) -> List[int]:
    return [int(point[0]), int(point[1])]


def _json_box(box: Sequence[int]) -> List[int]:
    return [int(value) for value in box]


def _json_corners(
    corners: Dict[str, Tuple[int, int]],
) -> Dict[str, List[int]]:
    return {
        name: _json_point(point)
        for name, point in corners.items()
    }


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "_", value.strip())
    return cleaned or "image"


def _box_iou(
    first: Tuple[int, int, int, int],
    second: Tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection_width = max(0, min(ax2, bx2) - max(ax1, bx1))
    intersection_height = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = intersection_width * intersection_height
    if intersection <= 0:
        return 0.0
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / (area_a + area_b - intersection)


def _intersection_over_smaller(
    first: Tuple[int, int, int, int],
    second: Tuple[int, int, int, int],
) -> float:
    ax1, ay1, ax2, ay2 = first
    bx1, by1, bx2, by2 = second
    intersection = (
        max(0, min(ax2, bx2) - max(ax1, bx1))
        * max(0, min(ay2, by2) - max(ay1, by1))
    )
    area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
    area_b = max(1, (bx2 - bx1) * (by2 - by1))
    return intersection / min(area_a, area_b)


def _normalized_center_distance(
    first: DetectedObject,
    second: DetectedObject,
) -> float:
    first_width = max(1, first.box[2] - first.box[0])
    first_height = max(1, first.box[3] - first.box[1])
    second_width = max(1, second.box[2] - second.box[0])
    second_height = max(1, second.box[3] - second.box[1])
    scale = max(
        1.0,
        float(
            np.hypot(
                max(first_width, second_width),
                max(first_height, second_height),
            )
        ),
    )
    return float(
        np.hypot(
            first.center[0] - second.center[0],
            first.center[1] - second.center[1],
        )
        / scale
    )


def _same_instance_synonym_group(
    first: DetectedObject,
    second: DetectedObject,
) -> bool:
    first_name = first.name.lower()
    second_name = second.name.lower()
    return any(
        first_name in group and second_name in group
        for group in INSTANCE_SYNONYM_GROUPS
    )


def _merge_detection_sources(
    target: DetectedObject,
    duplicate: DetectedObject,
) -> None:
    sources = list(target.sources or [target.source])
    for source in duplicate.sources or [duplicate.source]:
        if source not in sources:
            sources.append(source)
    target.sources = sources
    names = list(target.merged_from_names or [target.original_name or target.name])
    for name in duplicate.merged_from_names or [duplicate.original_name or duplicate.name]:
        normalized = str(name).strip().lower()
        if normalized and normalized not in names:
            names.append(normalized)
    target.merged_from_names = names


def consolidate_instance_detections(
    detections: Sequence[DetectedObject],
) -> List[DetectedObject]:
    """Remove only near-identical same-meaning boxes."""
    kept: List[DetectedObject] = []
    for candidate in sorted(
        detections,
        key=lambda item: item.confidence,
        reverse=True,
    ):
        candidate.canonical_name = INSTANCE_CANONICAL_NAMES.get(
            candidate.name.lower(),
            candidate.canonical_name,
        )
        duplicate_index: Optional[int] = None
        duplicate_metrics: Optional[Tuple[float, float, float]] = None
        duplicate_reason_code: Optional[str] = None
        for index, current in enumerate(kept):
            iou = _box_iou(candidate.box, current.box)
            containment = _intersection_over_smaller(
                candidate.box,
                current.box,
            )
            center_distance = _normalized_center_distance(
                candidate,
                current,
            )
            synonym_duplicate = (
                _same_instance_synonym_group(candidate, current)
                and (
                    iou >= 0.82
                    or (
                        containment >= 0.94
                        and center_distance <= 0.12
                    )
                )
            )
            same_name_non_vehicle_duplicate = (
                candidate.name == current.name
                and candidate.canonical_name != "vehicle"
                and (
                    iou >= 0.72
                    or (
                        containment >= 0.98
                        and center_distance <= 0.22
                    )
                )
            )
            candidate_area = max(1, (candidate.box[2] - candidate.box[0]) * (candidate.box[3] - candidate.box[1]))
            current_area = max(1, (current.box[2] - current.box[0]) * (current.box[3] - current.box[1]))
            smaller_ratio = min(candidate_area, current_area) / max(candidate_area, current_area)
            same_category_contained_part = (
                category_name_for(candidate.name) == category_name_for(current.name)
                and smaller_ratio <= 0.62
                and containment >= 0.90
                and center_distance <= 0.32
            )
            if (
                synonym_duplicate
                or same_name_non_vehicle_duplicate
                or same_category_contained_part
            ):
                duplicate_index = index
                duplicate_metrics = (
                    iou,
                    containment,
                    center_distance,
                )
                duplicate_reason_code = (
                    "contained_part"
                    if same_category_contained_part
                    else "duplicate_same_object"
                )
                break

        if duplicate_index is None:
            kept.append(candidate)
            continue

        current = kept[duplicate_index]
        candidate_area = max(1, (candidate.box[2] - candidate.box[0]) * (candidate.box[3] - candidate.box[1]))
        current_area = max(1, (current.box[2] - current.box[0]) * (current.box[3] - current.box[1]))
        keep_candidate = False
        if duplicate_metrics[1] >= 0.90:
            larger, smaller = (
                (candidate, current)
                if candidate_area >= current_area
                else (current, candidate)
            )
            keep_candidate = (
                larger is candidate
                and larger.confidence >= smaller.confidence - 0.18
            )
        if keep_candidate:
            _merge_detection_sources(candidate, current)
            kept[duplicate_index] = candidate
            kept_item = candidate
            removed_item = current
        else:
            _merge_detection_sources(current, candidate)
            kept_item = current
            removed_item = candidate
        removed_item.auto_reason = (
            f"{duplicate_reason_code}: post-detection consolidation; "
            f"kept={kept_item.name}"
        )
        print(
            "instance candidate excluded: "
            f"reason_code={duplicate_reason_code} "
            f"kept={kept_item.name} removed={removed_item.name} "
            f"IoU={duplicate_metrics[0]:.4f} "
            f"containment={duplicate_metrics[1]:.4f} "
            f"center_distance={duplicate_metrics[2]:.4f}"
        )
    return kept


def find_clicked_instance(
    objects: Sequence[InstanceObject],
    x: int,
    y: int,
) -> Optional[InstanceObject]:
    """Prefer true mask hits, then use boxes only for fallback objects."""
    mask_hits: List[InstanceObject] = []
    fallback_hits: List[InstanceObject] = []

    for item in objects:
        result = item.mask_result
        height, width = result.mask.shape[:2]
        if result.segmentation_supported:
            if 0 <= x < width and 0 <= y < height and result.mask[y, x] > 0:
                mask_hits.append(item)
            continue

        x1, y1, x2, y2 = result.detection_box
        if x1 <= x <= x2 and y1 <= y <= y2:
            fallback_hits.append(item)

    def click_sort_key(item: InstanceObject) -> Tuple[int, int, float, str]:
        category = category_name_for(item.detected.name)
        if category == "plant" and item.mask_result.mask_area_ratio >= 0.15:
            layer = 2
        elif category in FOREGROUND_CATEGORIES:
            layer = 0
        elif category in MIDGROUND_CATEGORIES:
            layer = 1
        else:
            layer = 2
        return (
            layer,
            item.area_pixels,
            -float(item.detected.confidence),
            item.object_id,
        )

    if mask_hits:
        return min(
            mask_hits,
            key=click_sort_key,
        )
    if fallback_hits:
        return min(
            fallback_hits,
            key=click_sort_key,
        )
    return None


def consolidate_overlapping_semantic_masks(
    objects: Sequence[InstanceObject],
    overlap_threshold: float = 0.80,
) -> Tuple[List[InstanceObject], int]:
    """Merge same-object masks while preserving nearby separate instances."""

    def mask_quality_key(item: InstanceObject) -> Tuple[int, int, float, float]:
        source = str(item.mask_result.mask_source or "").lower()
        if "semantic" in source or "deeplab" in source:
            source_quality = 3
        elif "grabcut" in source:
            source_quality = 2
        else:
            source_quality = 1
        return (
            source_quality,
            int(bool(item.mask_result.model_class_supported)),
            float(item.mask_result.detection_mask_iou),
            float(item.detected.confidence),
        )

    def merge_metadata(
        winner: InstanceObject,
        loser: InstanceObject,
    ) -> None:
        _merge_detection_sources(winner.detected, loser.detected)
        merged_names = list(
            winner.mask_result.merged_from_names
            or winner.detected.merged_from_names
            or [winner.detected.name]
        )
        for name in (
            loser.mask_result.merged_from_names
            or loser.detected.merged_from_names
            or [loser.detected.name]
        ):
            normalized = str(name).strip().lower()
            if normalized and normalized not in merged_names:
                merged_names.append(normalized)
        winner.mask_result.merged_from_names = merged_names
        merged_ids = list(
            winner.mask_result.merged_object_ids
            or [winner.object_id]
        )
        for object_id in (
            loser.mask_result.merged_object_ids
            or [loser.object_id]
        ):
            if object_id not in merged_ids:
                merged_ids.append(object_id)
        winner.mask_result.merged_object_ids = merged_ids

    kept: List[InstanceObject] = []
    merged_count = 0
    for candidate in sorted(
        objects,
        key=lambda item: item.detected.confidence,
        reverse=True,
    ):
        duplicate_index: Optional[int] = None
        duplicate_overlap = 0.0
        duplicate_containment = 0.0
        if candidate.mask_result.segmentation_supported:
            candidate_pixels = candidate.mask > 0
            candidate_area = max(
                1,
                int(np.count_nonzero(candidate_pixels)),
            )
            for index, current in enumerate(kept):
                if not current.mask_result.segmentation_supported:
                    continue
                if (
                    category_name_for(candidate.detected.name)
                    != category_name_for(current.detected.name)
                ):
                    continue
                category = category_name_for(candidate.detected.name)
                same_meaning = (
                    candidate.detected.name == current.detected.name
                    or _same_instance_synonym_group(
                        candidate.detected,
                        current.detected,
                    )
                )
                if not same_meaning:
                    continue
                current_pixels = current.mask > 0
                current_area = max(
                    1,
                    int(np.count_nonzero(current_pixels)),
                )
                intersection = int(
                    np.count_nonzero(candidate_pixels & current_pixels)
                )
                overlap = intersection / min(
                    candidate_area,
                    current_area,
                )
                box_iou = _box_iou(
                    candidate.detected.box,
                    current.detected.box,
                )
                box_containment = _intersection_over_smaller(
                    candidate.detected.box,
                    current.detected.box,
                )
                center_distance = _normalized_center_distance(
                    candidate.detected,
                    current.detected,
                )
                if category == "person":
                    required_overlap = 0.92
                    same_object_geometry = (
                        box_iou >= 0.68
                        or (
                            box_containment >= 0.94
                            and center_distance <= 0.12
                        )
                    )
                elif category == "animal":
                    required_overlap = 0.55
                    same_object_geometry = (
                        box_iou >= 0.20
                        and center_distance <= 0.48
                    )
                else:
                    required_overlap = overlap_threshold
                    same_object_geometry = (
                        box_iou >= 0.25
                        or box_containment >= 0.75
                        or center_distance <= 0.22
                    )
                if overlap >= required_overlap and same_object_geometry:
                    duplicate_index = index
                    duplicate_overlap = overlap
                    duplicate_containment = box_containment
                    break

        if duplicate_index is None:
            kept.append(candidate)
            continue

        current = kept[duplicate_index]
        candidate_area = max(1, int(np.count_nonzero(candidate.mask > 0)))
        current_area = max(1, int(np.count_nonzero(current.mask > 0)))
        larger = candidate if candidate_area >= current_area else current
        smaller = current if larger is candidate else candidate
        highly_contained = (
            duplicate_overlap >= 0.90
            and min(candidate_area, current_area)
            / max(candidate_area, current_area) <= 0.72
        )
        category = category_name_for(candidate.detected.name)
        complementary_animal_masks = (
            category == "animal"
            and 0.55 <= duplicate_overlap < 0.90
        )
        if complementary_animal_masks:
            winner = max(
                (candidate, current),
                key=lambda item: float(item.detected.confidence),
            )
        elif (
            highly_contained
            and mask_quality_key(larger)[:2] >= mask_quality_key(smaller)[:2]
            and larger.detected.confidence >= smaller.detected.confidence - 0.20
        ):
            winner = larger
        else:
            winner = max((candidate, current), key=mask_quality_key)
        loser = current if winner is candidate else candidate
        merge_metadata(winner, loser)
        if complementary_animal_masks:
            union_mask = cv2.bitwise_or(candidate.mask, current.mask)
            ax1, ay1, ax2, ay2 = candidate.detected.box
            bx1, by1, bx2, by2 = current.detected.box
            union_box = (
                min(ax1, bx1),
                min(ay1, by1),
                max(ax2, bx2),
                max(ay2, by2),
            )
            winner.detected.box = union_box
            winner.detected.center = (
                (union_box[0] + union_box[2]) // 2,
                (union_box[1] + union_box[3]) // 2,
            )
            winner.mask_result = rebuild_mask_result(
                winner.mask_result,
                union_mask,
                mask_source=winner.mask_result.mask_source,
                fallback_reason=winner.mask_result.fallback_reason,
                detection_box=union_box,
                segmentation_supported=True,
                analysis_scope=winner.mask_result.analysis_scope,
            )
        loser.detected.auto_reason = (
            "duplicate_same_object: semantic mask overlap; "
            f"kept={winner.detected.name} "
            f"intersection_over_smaller={duplicate_overlap:.4f}"
        )
        if winner is candidate:
            kept[duplicate_index] = candidate
        merged_count += 1
        print(
            "semantic mask candidate excluded: "
            "reason_code=duplicate_same_object "
            f"kept={winner.detected.name} "
            f"removed={loser.detected.name} "
            f"intersection_over_smaller={duplicate_overlap:.4f} "
            f"box_containment={duplicate_containment:.4f}"
        )

    for index, item in enumerate(kept, start=1):
        item.mask_result.object_id = f"object_{index:04d}"
    return kept, merged_count


def resolve_instance_mask_overlaps(
    objects: Sequence[InstanceObject],
) -> Tuple[List[InstanceObject], int, int]:
    """Give every foreground pixel one owner without merging instances."""
    resolved = list(objects)
    masks = [(item.mask > 0).copy() for item in resolved]
    changed = [False] * len(resolved)
    affected_pairs = 0
    removed_overlap_pixels = 0
    priority = {
        "food": 0,
        "person": 1,
        "animal": 1,
        "vehicle": 1,
        "instrument": 1,
        "electronics": 2,
        "furniture": 3,
        "building": 4,
        "plant": 4,
        "other": 4,
    }

    def normalized_distance(
        item: InstanceObject,
        xs: np.ndarray,
        ys: np.ndarray,
    ) -> np.ndarray:
        x1, y1, x2, y2 = item.detected.box
        center_x = (x1 + x2) * 0.5
        center_y = (y1 + y2) * 0.5
        width = max(1.0, float(x2 - x1))
        height = max(1.0, float(y2 - y1))
        return ((xs - center_x) / width) ** 2 + ((ys - center_y) / height) ** 2

    for first_index in range(len(resolved)):
        for second_index in range(first_index + 1, len(resolved)):
            first_box = resolved[first_index].mask_result.mask_box
            second_box = resolved[second_index].mask_result.mask_box
            overlap_x1 = max(int(first_box[0]), int(second_box[0]))
            overlap_y1 = max(int(first_box[1]), int(second_box[1]))
            overlap_x2 = min(int(first_box[2]), int(second_box[2]))
            overlap_y2 = min(int(first_box[3]), int(second_box[3]))
            if overlap_x1 > overlap_x2 or overlap_y1 > overlap_y2:
                continue
            overlap_slice = np.s_[
                overlap_y1:overlap_y2 + 1,
                overlap_x1:overlap_x2 + 1,
            ]
            first_region = masks[first_index][overlap_slice]
            second_region = masks[second_index][overlap_slice]
            overlap = first_region & second_region
            overlap_count = int(np.count_nonzero(overlap))
            if overlap_count == 0:
                continue
            first = resolved[first_index]
            second = resolved[second_index]
            first_category = category_name_for(first.detected.name)
            second_category = category_name_for(second.detected.name)
            affected_pairs += 1
            removed_overlap_pixels += overlap_count
            if first_category != second_category:
                first_name = str(first.detected.name).strip().lower()
                second_name = str(second.detected.name).strip().lower()
                first_priority = priority.get(first_category, 5)
                second_priority = priority.get(second_category, 5)
                if first_name in {
                    "christmas tree",
                    "decorated christmas tree",
                }:
                    first_priority = 3
                if second_name in {
                    "christmas tree",
                    "decorated christmas tree",
                }:
                    second_priority = 3
                if first_priority < second_priority:
                    second_region[overlap] = False
                    changed[second_index] = True
                    continue
                if second_priority < first_priority:
                    first_region[overlap] = False
                    changed[first_index] = True
                    continue

            ys, xs = np.where(overlap)
            global_xs = xs + overlap_x1
            global_ys = ys + overlap_y1
            first_distance = normalized_distance(first, global_xs, global_ys)
            second_distance = normalized_distance(second, global_xs, global_ys)
            first_loses = first_distance > second_distance
            ties = first_distance == second_distance
            if np.any(ties):
                first_loses[ties] = (
                    first.detected.confidence < second.detected.confidence
                )
            if np.any(first_loses):
                first_region[ys[first_loses], xs[first_loses]] = False
                changed[first_index] = True
            second_loses = ~first_loses
            if np.any(second_loses):
                second_region[ys[second_loses], xs[second_loses]] = False
                changed[second_index] = True

    for index, item in enumerate(resolved):
        if not changed[index]:
            continue
        item.mask_result = rebuild_mask_result(
            item.mask_result,
            masks[index].astype(np.uint8) * 255,
            mask_source=item.mask_result.mask_source,
            fallback_reason=item.mask_result.fallback_reason,
            detection_box=item.mask_result.detection_box,
            segmentation_supported=item.mask_result.segmentation_supported,
            analysis_scope=item.mask_result.analysis_scope,
        )
    return resolved, affected_pairs, removed_overlap_pixels


def consolidate_objects_by_category(
    objects: Sequence[InstanceObject],
    categories: Sequence[str] = ("water",),
) -> Tuple[List[InstanceObject], int]:
    """指定カテゴリの複数検出を1件へまとめ、マスクの和集合を保持する。"""
    target_categories = {
        str(category).strip().lower()
        for category in categories
    }

    def masks_represent_same_region(
        first: InstanceObject,
        second: InstanceObject,
    ) -> bool:
        first_pixels = first.mask > 0
        second_pixels = second.mask > 0
        first_area = max(1, int(np.count_nonzero(first_pixels)))
        second_area = max(1, int(np.count_nonzero(second_pixels)))
        intersection = int(np.count_nonzero(first_pixels & second_pixels))
        union = max(1, first_area + second_area - intersection)
        if intersection / min(first_area, second_area) >= 0.45:
            return True
        if intersection / union >= 0.30:
            return True
        if _box_iou(first.mask_result.mask_box, second.mask_result.mask_box) >= 0.25:
            return True

        height, width = first.mask.shape[:2]
        gap = max(1, int(round(min(height, width) * 0.006)))
        ax1, ay1, ax2, ay2 = first.mask_result.mask_box
        bx1, by1, bx2, by2 = second.mask_result.mask_box
        x_overlap = min(ax2, bx2) - max(ax1, bx1) >= 0
        y_overlap = min(ay2, by2) - max(ay1, by1) >= 0
        if not (x_overlap or y_overlap):
            return False
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (gap * 2 + 1, gap * 2 + 1),
        )
        dilated = cv2.dilate(first.mask, kernel, iterations=1) > 0
        return bool(np.any(dilated & second_pixels))

    result = list(objects)
    merged_count = 0
    for item in result:
        item.mask_result.category = category_name_for(item.detected.name)

    for category in target_categories:
        members = [
            item
            for item in result
            if category_name_for(item.detected.name) == category
        ]
        clusters: List[List[InstanceObject]] = []
        for member in members:
            matching = [
                cluster
                for cluster in clusters
                if any(masks_represent_same_region(member, other) for other in cluster)
            ]
            if not matching:
                clusters.append([member])
                continue
            primary_cluster = matching[0]
            primary_cluster.append(member)
            for extra_cluster in matching[1:]:
                primary_cluster.extend(extra_cluster)
                clusters.remove(extra_cluster)

        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            primary = max(cluster, key=lambda item: float(item.detected.confidence))
            union_mask = np.zeros_like(primary.mask, dtype=np.uint8)
            source_ids: List[str] = []
            source_names: List[str] = []
            for item in cluster:
                union_mask = np.maximum(union_mask, item.mask)
                for object_id in item.mask_result.merged_object_ids or [item.object_id]:
                    if object_id not in source_ids:
                        source_ids.append(object_id)
                for name in (
                    item.mask_result.merged_from_names
                    or item.detected.merged_from_names
                    or [item.detected.name]
                ):
                    normalized = str(name).strip().lower()
                    if normalized and normalized not in source_names:
                        source_names.append(normalized)

            detection_box = (
                min(item.mask_result.detection_box[0] for item in cluster),
                min(item.mask_result.detection_box[1] for item in cluster),
                max(item.mask_result.detection_box[2] for item in cluster),
                max(item.mask_result.detection_box[3] for item in cluster),
            )
            supported = any(item.mask_result.segmentation_supported for item in cluster)
            rebuild_mask_result(
                primary.mask_result,
                union_mask,
                mask_source=f"category_union:{category}",
                fallback_reason=(
                    None if supported else "category union contains fallback masks only"
                ),
                detection_box=detection_box,
                segmentation_supported=supported,
                analysis_scope="connected_category_union",
            )
            primary.mask_result.merged_object_ids = source_ids
            primary.mask_result.merged_from_names = source_names
            primary.mask_result.category = category
            primary.detected.name = category
            primary.detected.canonical_name = category
            for item in cluster:
                if item is not primary:
                    _merge_detection_sources(primary.detected, item.detected)
                    result.remove(item)
            merged_count += len(cluster) - 1

    for index, item in enumerate(result, start=1):
        item.mask_result.object_id = f"object_{index:04d}"
    return result, merged_count


class InstanceSegmentationPipeline:
    def __init__(
        self,
        detection_mode: str = "standard",
        semantic_segmenter: Optional[SemanticSegmenterMulti] = None,
        epsilon_ratio: float = 0.003,
        output_root: Optional[Path] = None,
    ) -> None:
        self.detection_mode = (
            detection_mode
            if detection_mode in {"standard", "accuracy", "auto"}
            else "standard"
        )
        self.semantic_segmenter = (
            semantic_segmenter
            if semantic_segmenter is not None
            else SemanticSegmenterMulti(input_size=640)
        )
        self.object_segmenter = DeepLabBoxObjectSegmenter(
            self.semantic_segmenter,
            epsilon_ratio=epsilon_ratio,
        )
        self.output_root = (
            Path(output_root).resolve()
            if output_root is not None
            else Path(__file__).resolve().parent
        )

    def _save_masks(
        self,
        image_path: Path,
        objects: Sequence[InstanceObject],
    ) -> None:
        folder_name = (
            f"{_safe_path_part(image_path.stem)}_{self.detection_mode}"
        )
        mask_dir = self.output_root / "masks" / folder_name
        mask_dir.mkdir(parents=True, exist_ok=True)
        expected_names = {
            f"{item.object_id}.png"
            for item in objects
        }
        for stale_path in mask_dir.glob("object_*.png"):
            if stale_path.name not in expected_names:
                stale_path.unlink()

        for item in objects:
            filename = f"{item.object_id}.png"
            absolute_path = mask_dir / filename
            if not imwrite_unicode(str(absolute_path), item.mask):
                raise OSError(f"Could not save mask: {absolute_path}")
            item.mask_result.mask_path = absolute_path.relative_to(
                self.output_root
            ).as_posix()

    @staticmethod
    def _object_to_json(item: InstanceObject) -> Dict[str, object]:
        detected = item.detected
        result = item.mask_result
        sources = list(detected.sources or [detected.source])
        if result.segmentation_supported and "semantic" not in sources:
            sources.append("semantic")

        legacy_corners = {
            key: _json_point(value)
            for key, value in detected.four_corners_original.items()
        }
        return {
            "object_id": result.object_id,
            "name": detected.name,
            "category": result.category or category_name_for(detected.name),
            "canonical_name": detected.canonical_name,
            "original_name": detected.original_name,
            "confidence": float(detected.confidence),
            "reaction": detected.reaction,
            "source": detected.source,
            "sources": sources,
            "auto_reason": detected.auto_reason,
            "detection_box": _json_box(result.detection_box),
            "mask_box": _json_box(result.mask_box),
            "corners": _json_corners(result.corners),
            "contour": [
                _json_point(point) for point in result.contour
            ],
            "contour_simplified": [
                _json_point(point)
                for point in result.contour_simplified
            ],
            "all_contours": [
                [_json_point(point) for point in contour]
                for contour in result.all_contours
            ],
            "area_pixels": int(result.area_pixels),
            "mask_source": result.mask_source,
            "analysis_scope": result.analysis_scope,
            "merged_from_names": list(result.merged_from_names or []),
            "merged_object_ids": list(result.merged_object_ids or []),
            "segmentation_supported": bool(
                result.segmentation_supported
            ),
            "model_class_supported": bool(
                result.model_class_supported
            ),
            "semantic_class": result.semantic_class,
            "fallback_reason": result.fallback_reason,
            "mask_area_ratio": float(result.mask_area_ratio),
            "box_fill_ratio": float(result.box_fill_ratio),
            "detection_mask_iou": float(result.detection_mask_iou),
            "connected_component_count": int(
                result.connected_component_count
            ),
            "semantic_candidate_component_count": int(
                result.semantic_candidate_component_count
            ),
            "box_delta": dict(result.box_delta),
            "contour_simplified_point_count": len(
                result.contour_simplified
            ),
            "mask_path": result.mask_path,
            # Unity/legacy compatibility fields.
            "x1": int(result.detection_box[0]),
            "y1": int(result.detection_box[1]),
            "x2": int(result.detection_box[2]),
            "y2": int(result.detection_box[3]),
            "box_original": _json_box(detected.box_original),
            "four_corners_original": legacy_corners,
            "center_original": _json_point(detected.center_original),
        }

    def _save_json(
        self,
        image_path: Path,
        original_shape: Tuple[int, int, int],
        display_size: Tuple[int, int],
        objects: Sequence[InstanceObject],
        detector: MagicPhotoDetector,
        processing_time: float,
        output_json_path: Path,
        semantic_mask: np.ndarray,
    ) -> Path:
        original_height, original_width = original_shape[:2]
        display_width, display_height = display_size
        present_classes = self.semantic_segmenter.present_class_ids(
            semantic_mask,
            include_background=False,
        )
        payload = {
            "schema_version": "2.0",
            "image_path": str(image_path),
            "coordinate_space": "original_image_pixels",
            "coordinate_convention": (
                "detection_box/mask_box are inclusive xyxy pixel indices; "
                "box_original is the legacy detector value"
            ),
            "original_width": original_width,
            "original_height": original_height,
            "display_width": display_width,
            "display_height": display_height,
            "display_scale_x": display_width / original_width,
            "display_scale_y": display_height / original_height,
            "detection_mode": self.detection_mode,
            "processing_time_seconds": processing_time,
            "detection_stats": dict(detector.last_mode_stats),
            "semantic_classes_present": [
                {
                    "class_id": int(class_id),
                    "name": name,
                    "area_pixels": int(pixel_count),
                }
                for class_id, name, pixel_count in present_classes
            ],
            "objects": [
                self._object_to_json(item)
                for item in objects
            ],
        }
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_json_path

    def analyze(
        self,
        image: np.ndarray,
        image_path: Path,
        display_size: Optional[Tuple[int, int]] = None,
        output_json_path: Optional[Path] = None,
        semantic_mask: Optional[np.ndarray] = None,
    ) -> InstanceAnalysis:
        if image is None or image.size == 0:
            raise ValueError("image is empty")
        started = time.perf_counter()
        detector = MagicPhotoDetector(
            detection_mode=self.detection_mode,
        )
        detector_objects = detector.detect_from_image(image)
        detections = consolidate_instance_detections(
            detector_objects
        )
        instance_consolidated = len(detector_objects) - len(detections)

        if semantic_mask is None:
            semantic_mask = self.semantic_segmenter.segment_image(image)
        if semantic_mask.shape[:2] != image.shape[:2]:
            raise RuntimeError(
                "semantic mask must match the original image size"
            )

        mask_results = self.object_segmenter.segment_objects(
            image,
            detections,
            semantic_mask=semantic_mask,
        )
        objects = [
            InstanceObject(detected=detection, mask_result=mask_result)
            for detection, mask_result in zip(detections, mask_results)
        ]
        objects, semantic_mask_consolidated = (
            consolidate_overlapping_semantic_masks(objects)
        )
        objects, category_consolidated = consolidate_objects_by_category(
            objects,
            categories=("water",),
        )
        self._save_masks(Path(image_path), objects)

        if display_size is None:
            display_size = (image.shape[1], image.shape[0])
        if output_json_path is None:
            output_json_path = self.output_root / "analysis_result.json"
        else:
            output_json_path = Path(output_json_path)

        processing_time = time.perf_counter() - started
        semantic_supported_names = sorted({
            item.detected.name
            for item in objects
            if item.mask_result.segmentation_supported
        })
        fallback_names = sorted({
            item.detected.name
            for item in objects
            if not item.mask_result.segmentation_supported
        })
        detector.last_final_detection_count = len(objects)
        detector.last_mode_stats["final"] = len(objects)
        detector.last_mode_stats["mask_supported"] = sum(
            item.mask_result.segmentation_supported
            for item in objects
        )
        detector.last_mode_stats["box_fallback"] = sum(
            not item.mask_result.segmentation_supported
            for item in objects
        )
        detector.last_mode_stats["instance_consolidated"] = (
            instance_consolidated
            + semantic_mask_consolidated
            + category_consolidated
        )
        detector.last_mode_stats["semantic_mask_consolidated"] = (
            semantic_mask_consolidated
        )
        detector.last_mode_stats["category_consolidated"] = (
            category_consolidated
        )
        detector.last_mode_stats["mask_supported_ratio"] = (
            detector.last_mode_stats["mask_supported"] / max(1, len(objects))
        )
        detector.last_mode_stats["pipeline_processing_time"] = (
            processing_time
        )
        result_path = self._save_json(
            Path(image_path),
            image.shape,
            display_size,
            objects,
            detector,
            processing_time,
            output_json_path,
            semantic_mask,
        )

        print(
            f"instance summary: mode={self.detection_mode} "
            f"objects={len(objects)} "
            f"semantic_masks="
            f"{detector.last_mode_stats['mask_supported']} "
            f"box_fallback="
            f"{detector.last_mode_stats['box_fallback']} "
            f"mask_supported_ratio="
            f"{detector.last_mode_stats['mask_supported_ratio']:.4f} "
            f"instance_consolidated="
            f"{instance_consolidated + semantic_mask_consolidated + category_consolidated} "
            f"semantic_mask_consolidated="
            f"{semantic_mask_consolidated} "
            f"category_consolidated={category_consolidated} "
            f"time={processing_time:.3f}s"
        )
        print(
            "DeepLab masks used for detected classes: "
            + (", ".join(semantic_supported_names) or "none")
        )
        print(
            "box_fallback detected classes: "
            + (", ".join(fallback_names) or "none")
        )
        print(f"analysis JSON saved: {result_path}")

        for item in objects:
            result = item.mask_result
            print(
                f"{item.object_id} class={item.detected.name} "
                f"confidence={item.detected.confidence:.4f} "
                f"detection_box={result.detection_box} "
                f"mask_box={result.mask_box} "
                f"box_delta={result.box_delta} "
                f"area={result.area_pixels} "
                f"mask_area_ratio={result.mask_area_ratio:.6f} "
                f"box_fill_ratio={result.box_fill_ratio:.6f} "
                f"detection_mask_iou={result.detection_mask_iou:.6f} "
                f"components={result.connected_component_count} "
                f"semantic_candidates="
                f"{result.semantic_candidate_component_count} "
                f"mask_source={result.mask_source} "
                f"fallback_reason={result.fallback_reason or 'none'}"
            )

        return InstanceAnalysis(
            detector=detector,
            objects=objects,
            semantic_mask=semantic_mask,
            result_path=result_path,
            processing_time=processing_time,
            semantic_supported_names=semantic_supported_names,
            fallback_names=fallback_names,
        )
