"""Conservative, auditable mask-quality helpers for MagicPhoto Unity output.

This module does not change detector/model thresholds.  It measures each
already-generated candidate, clips detection-scoped masks to their YOLO box,
removes only tiny disconnected islands, and records why a contour was kept,
repaired, or left as the safe rectangular fallback.
"""

from __future__ import annotations

from collections import Counter
import time
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np

from ml_detector_complete import category_name_for
from object_segmentation import ObjectMaskResult, rebuild_mask_result


Box = Tuple[int, int, int, int]
TARGET_CATEGORIES = {
    "person", "animal", "instrument", "food", "vehicle", "plant", "sky", "water",
}

# タッチ操作では、検出できる最小サイズよりも十分に大きいことが重要です。
# 4つの幾何指標のいずれかが不足した候補はconfidenceによる救済を限定し、
# 複数指標が不足する候補は高confidenceでも除外します。
TOUCH_ELIGIBILITY_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "person": {
        "mask_area_ratio": 0.00100,
        "bbox_area_ratio": 0.00140,
        "bbox_width_ratio": 0.030,
        "bbox_height_ratio": 0.055,
        "minimum_confidence": 0.42,
        "rescue_confidence": 0.72,
    },
    "animal": {
        "mask_area_ratio": 0.00080,
        "bbox_area_ratio": 0.00120,
        "bbox_width_ratio": 0.028,
        "bbox_height_ratio": 0.032,
        "minimum_confidence": 0.40,
        "rescue_confidence": 0.70,
    },
    "instrument": {
        "mask_area_ratio": 0.00070,
        "bbox_area_ratio": 0.00110,
        "bbox_width_ratio": 0.026,
        "bbox_height_ratio": 0.035,
        "minimum_confidence": 0.42,
        "rescue_confidence": 0.72,
    },
    "food": {
        "mask_area_ratio": 0.00055,
        "bbox_area_ratio": 0.00090,
        "bbox_width_ratio": 0.024,
        "bbox_height_ratio": 0.028,
        "minimum_confidence": 0.38,
        "rescue_confidence": 0.68,
    },
    "vehicle": {
        "mask_area_ratio": 0.00100,
        "bbox_area_ratio": 0.00160,
        "bbox_width_ratio": 0.035,
        "bbox_height_ratio": 0.028,
        "minimum_confidence": 0.42,
        "rescue_confidence": 0.72,
    },
}
TOUCH_SIZE_EXEMPT_TARGETS = {"sky", "water", "plant"}
TOUCH_SIZE_PROTECTED_NAMES = {"sun", "moon"}


def target_category_for(name: str, category: Optional[str] = None) -> Optional[str]:
    """Return the requested eight-class view without replacing legacy category."""
    legacy = str(category or category_name_for(name)).strip().lower()
    if legacy in TARGET_CATEGORIES:
        return legacy
    if legacy in {"sun", "moon"}:
        return "sky"
    return None


def evaluate_touch_eligibility(
    image_shape: Sequence[int],
    detection: object,
    mask_result: ObjectMaskResult,
) -> Dict[str, object]:
    """Evaluate whether an instance is large enough for exhibition touch use."""
    height, width = int(image_shape[0]), int(image_shape[1])
    image_area = max(1, height * width)
    name = str(getattr(detection, "name", "")).strip().lower()
    category = category_name_for(name)
    target_category = target_category_for(name, category)
    confidence = float(getattr(detection, "confidence", 0.0))
    x1, y1, x2, y2 = _clipped_box(
        getattr(detection, "box", mask_result.detection_box),
        width,
        height,
    )
    bbox_width = max(1, x2 - x1 + 1)
    bbox_height = max(1, y2 - y1 + 1)
    metrics = {
        "mask_area_ratio": float(
            np.count_nonzero(mask_result.mask) / image_area
        ),
        "bbox_area_ratio": float(bbox_width * bbox_height / image_area),
        "bbox_width_ratio": float(bbox_width / max(1, width)),
        "bbox_height_ratio": float(bbox_height / max(1, height)),
        "confidence": confidence,
    }
    base = {
        "excluded_from_touch": False,
        "exclusion_reason": None,
        "reason_code": None,
        "name": name,
        "category": category,
        "target_category": target_category,
        **metrics,
    }
    if name in TOUCH_SIZE_PROTECTED_NAMES:
        return {
            **base,
            "decision": "protected_celestial_object",
            "thresholds": None,
            "failed_size_metrics": [],
        }
    if target_category in TOUCH_SIZE_EXEMPT_TARGETS:
        return {
            **base,
            "decision": "scene_region_exempt",
            "thresholds": None,
            "failed_size_metrics": [],
        }
    thresholds = TOUCH_ELIGIBILITY_THRESHOLDS.get(str(target_category))
    if thresholds is None:
        return {
            **base,
            "decision": "not_a_touch_size_category",
            "thresholds": None,
            "failed_size_metrics": [],
        }

    size_keys = (
        "mask_area_ratio",
        "bbox_area_ratio",
        "bbox_width_ratio",
        "bbox_height_ratio",
    )
    failed = [key for key in size_keys if metrics[key] < thresholds[key]]
    hard_failed = [
        key for key in size_keys
        if metrics[key] < thresholds[key] * 0.50
    ]
    low_confidence_marginal = bool(
        confidence < thresholds["minimum_confidence"]
        and any(metrics[key] < thresholds[key] * 1.25 for key in size_keys)
    )
    excluded = bool(
        hard_failed
        or len(failed) >= 2
        or (
            failed
            and confidence < thresholds["rescue_confidence"]
        )
        or low_confidence_marginal
    )
    if excluded:
        reason = (
            "too_small_for_touch: "
            f"category={target_category} failed={','.join(failed) or 'marginal'} "
            f"hard_failed={','.join(hard_failed) or 'none'} "
            f"confidence={confidence:.4f}"
        )
        return {
            **base,
            "excluded_from_touch": True,
            "exclusion_reason": reason,
            "reason_code": "too_small_for_touch",
            "decision": "excluded",
            "thresholds": dict(thresholds),
            "failed_size_metrics": failed,
            "hard_failed_size_metrics": hard_failed,
        }
    return {
        **base,
        "decision": (
            "rescued_by_confidence" if failed else "eligible"
        ),
        "thresholds": dict(thresholds),
        "failed_size_metrics": failed,
        "hard_failed_size_metrics": hard_failed,
    }


def _clipped_box(box: Sequence[int], width: int, height: int) -> Box:
    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(x1, min(width - 1, x2))
    y2 = max(y1, min(height - 1, y2))
    return x1, y1, x2, y2


def _box_mask(shape: Sequence[int], box: Sequence[int]) -> np.ndarray:
    height, width = int(shape[0]), int(shape[1])
    x1, y1, x2, y2 = _clipped_box(box, width, height)
    result = np.zeros((height, width), dtype=np.uint8)
    result[y1:y2 + 1, x1:x2 + 1] = 255
    return result


def assess_mask_quality(
    image: np.ndarray,
    mask: np.ndarray,
    detection_box: Sequence[int],
    category: str,
    analysis_scope: str = "detection_box",
    mask_source: str = "",
) -> Dict[str, object]:
    """Measure geometry, components and image-edge support for one mask."""
    binary = ((mask > 0) * 255).astype(np.uint8)
    height, width = binary.shape[:2]
    box_binary = _box_mask(binary.shape, detection_box)
    mask_area = int(np.count_nonzero(binary))
    box_area = max(1, int(np.count_nonzero(box_binary)))
    inside_area = int(np.count_nonzero((binary > 0) & (box_binary > 0)))
    inside_ratio = inside_area / max(1, mask_area)
    fill_ratio = mask_area / box_area

    component_count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (binary > 0).astype(np.uint8), 8
    )
    component_areas = [
        int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, component_count)
    ]
    largest_component_ratio = max(component_areas, default=0) / max(1, mask_area)

    points = cv2.findNonZero(binary)
    if points is None:
        rectangularity = 0.0
        mask_box_area = 0
    else:
        _, _, mask_width, mask_height = cv2.boundingRect(points)
        mask_box_area = max(1, int(mask_width * mask_height))
        rectangularity = mask_area / mask_box_area

    boundary = cv2.morphologyEx(
        binary, cv2.MORPH_GRADIENT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    ) > 0
    boundary_pixels = int(np.count_nonzero(boundary))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_edges = cv2.Canny(gray, 45, 135)
    image_edges = cv2.dilate(
        image_edges,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        iterations=1,
    ) > 0
    boundary_edge_support = (
        float(np.count_nonzero(boundary & image_edges)) / max(1, boundary_pixels)
    )

    scope_is_box = analysis_scope != "full_image"
    failure_reasons: List[str] = []
    if mask_area == 0:
        failure_reasons.append("empty_mask")
    if scope_is_box and inside_ratio < 0.997:
        failure_reasons.append("outside_detection_box")
    if scope_is_box and fill_ratio > 1.01:
        failure_reasons.append("mask_larger_than_detection_box")
    if mask_area and largest_component_ratio < 0.72:
        failure_reasons.append("fragmented_mask")
    if len(component_areas) > 6:
        failure_reasons.append("small_component_noise")
    if (
        scope_is_box
        and str(mask_source) != "box_fallback"
        and rectangularity >= 0.985
        and boundary_edge_support < 0.04
    ):
        failure_reasons.append("rectangle_like_low_boundary_support")

    inside_score = min(1.0, max(0.0, inside_ratio))
    component_score = min(1.0, max(0.0, largest_component_ratio))
    area_score = min(1.0, max(0.0, fill_ratio / 0.12))
    if fill_ratio > 1.0:
        area_score *= max(0.0, 2.0 - fill_ratio)
    edge_score = min(1.0, boundary_edge_support / 0.24)
    source_score = 1.0 if "deeplab" in mask_source else 0.8 if "grabcut" in mask_source else 0.55
    quality_score = (
        0.24 * inside_score
        + 0.24 * component_score
        + 0.18 * area_score
        + 0.24 * edge_score
        + 0.10 * source_score
    )
    return {
        "quality_score": float(max(0.0, min(1.0, quality_score))),
        "status": "needs_review" if failure_reasons else "accepted",
        "failure_reasons": failure_reasons,
        "mask_pixels": mask_area,
        "detection_box_pixels": box_area,
        "inside_detection_box_pixels": inside_area,
        "inside_detection_box_ratio": float(inside_ratio),
        "mask_to_detection_box_ratio": float(fill_ratio),
        "connected_component_count": len(component_areas),
        "largest_component_ratio": float(largest_component_ratio),
        "mask_box_pixels": int(mask_box_area),
        "rectangularity": float(rectangularity),
        "boundary_pixels": boundary_pixels,
        "boundary_edge_support_ratio": float(boundary_edge_support),
        "category": str(category),
        "target_category": target_category_for(category, category),
    }


def compare_grabcut_to_box(
    image: np.ndarray,
    grabcut_mask: np.ndarray,
    detection_box: Sequence[int],
    category: str,
) -> Tuple[bool, Dict[str, object]]:
    """Accept GrabCut only when geometry and boundary evidence beat the box."""
    grabcut = assess_mask_quality(
        image, grabcut_mask, detection_box, category,
        analysis_scope="detection_box", mask_source="grabcut_box",
    )
    rectangle = assess_mask_quality(
        image, _box_mask(grabcut_mask.shape, detection_box), detection_box, category,
        analysis_scope="detection_box", mask_source="box_fallback",
    )
    minimum_fill = {
        "person": 0.015,
        "animal": 0.020,
        "instrument": 0.030,
        "food": 0.030,
        "vehicle": 0.045,
        "plant": 0.020,
    }.get(category, 0.030)
    reasons: List[str] = []
    fill_ratio = float(grabcut["mask_to_detection_box_ratio"])
    if fill_ratio < minimum_fill:
        reasons.append("grabcut_too_small")
    if fill_ratio > 0.97:
        reasons.append("grabcut_near_rectangle")
    if float(grabcut["largest_component_ratio"]) < 0.72:
        reasons.append("grabcut_fragmented")
    edge_support = float(grabcut["boundary_edge_support_ratio"])
    rectangle_edge_support = float(rectangle["boundary_edge_support_ratio"])
    edge_improved = edge_support >= max(0.035, rectangle_edge_support + 0.008)
    if not edge_improved:
        reasons.append("grabcut_boundary_not_better_than_box")
    accepted = not reasons
    return accepted, {
        "accepted": accepted,
        "reasons": reasons,
        "grabcut": grabcut,
        "box_fallback": rectangle,
        "quality_score_delta": float(grabcut["quality_score"] - rectangle["quality_score"]),
    }


def refine_person_boundaries(
    image: np.ndarray,
    detections: Sequence[object],
    mask_results: Sequence[ObjectMaskResult],
    enabled: bool = True,
    maximum_side: int = 256,
) -> Dict[str, object]:
    """Snap accepted DeepLab person edges to local colour boundaries.

    DeepLab remains the foreground seed.  GrabCut may only make a small,
    strongly-overlapping correction, which protects thin arms/legs and keeps
    the quantitative person gate meaningful.
    """
    started = time.perf_counter()
    analysis: Dict[str, object] = {
        "enabled": bool(enabled),
        "candidate_count": 0,
        "accepted_count": 0,
        "rejected_count": 0,
        "changed_pixels": 0,
        "reason_counts": {},
        "maximum_working_side": int(maximum_side),
    }
    if not enabled:
        analysis["processing_time_seconds"] = 0.0
        return analysis

    reason_counts: Counter[str] = Counter()
    height, width = image.shape[:2]
    for detection, result in zip(detections, mask_results):
        category = category_name_for(detection.name)
        if category != "person" or "deeplab" not in str(result.mask_source).lower():
            continue
        analysis["candidate_count"] = int(analysis["candidate_count"]) + 1
        x1, y1, x2, y2 = _clipped_box(result.detection_box, width, height)
        crop = image[y1:y2 + 1, x1:x2 + 1]
        old_crop = (result.mask[y1:y2 + 1, x1:x2 + 1] > 0).astype(np.uint8)
        if crop.size == 0 or int(np.count_nonzero(old_crop)) < 20:
            reason_counts["person_seed_too_small"] += 1
            analysis["rejected_count"] = int(analysis["rejected_count"]) + 1
            continue

        scale = min(1.0, float(maximum_side) / max(crop.shape[:2]))
        work_size = (
            max(2, int(round(crop.shape[1] * scale))),
            max(2, int(round(crop.shape[0] * scale))),
        )
        work_image = cv2.resize(crop, work_size, interpolation=cv2.INTER_AREA)
        seed = (
            cv2.resize(old_crop, work_size, interpolation=cv2.INTER_NEAREST) > 0
        ).astype(np.uint8)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        definite_foreground = cv2.erode(seed, kernel, iterations=2)
        probable_region = cv2.dilate(seed, kernel, iterations=2)
        if not np.count_nonzero(definite_foreground):
            reason_counts["person_seed_has_no_safe_core"] += 1
            analysis["rejected_count"] = int(analysis["rejected_count"]) + 1
            continue

        grabcut_labels = np.full(seed.shape, cv2.GC_BGD, dtype=np.uint8)
        grabcut_labels[probable_region > 0] = cv2.GC_PR_BGD
        grabcut_labels[seed > 0] = cv2.GC_PR_FGD
        grabcut_labels[definite_foreground > 0] = cv2.GC_FGD
        try:
            cv2.grabCut(
                work_image,
                grabcut_labels,
                None,
                np.zeros((1, 65), dtype=np.float64),
                np.zeros((1, 65), dtype=np.float64),
                1,
                cv2.GC_INIT_WITH_MASK,
            )
        except cv2.error:
            reason_counts["person_guided_grabcut_failed"] += 1
            analysis["rejected_count"] = int(analysis["rejected_count"]) + 1
            continue

        refined_crop = np.isin(
            grabcut_labels, (cv2.GC_FGD, cv2.GC_PR_FGD)
        ).astype(np.uint8)
        refined_crop = cv2.resize(
            refined_crop,
            (crop.shape[1], crop.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        ) > 0
        old_pixels = old_crop > 0
        old_area = max(1, int(np.count_nonzero(old_pixels)))
        new_area = int(np.count_nonzero(refined_crop))
        intersection = int(np.count_nonzero(old_pixels & refined_crop))
        union = max(1, int(np.count_nonzero(old_pixels | refined_crop)))
        area_ratio = new_area / old_area
        seed_iou = intersection / union
        rejection_reasons = []
        if not 0.82 <= area_ratio <= 1.12:
            rejection_reasons.append("person_boundary_area_change_unsafe")
        if seed_iou < 0.82:
            rejection_reasons.append("person_boundary_seed_agreement_low")
        if new_area < 20:
            rejection_reasons.append("person_boundary_result_too_small")
        if rejection_reasons:
            reason_counts.update(rejection_reasons)
            analysis["rejected_count"] = int(analysis["rejected_count"]) + 1
            continue

        refined = np.zeros_like(result.mask, dtype=np.uint8)
        refined[y1:y2 + 1, x1:x2 + 1] = refined_crop.astype(np.uint8) * 255
        changed_pixels = int(np.count_nonzero((refined > 0) != (result.mask > 0)))
        if changed_pixels == 0:
            reason_counts["person_boundary_unchanged"] += 1
            continue
        corrections = list(result.correction_reasons or [])
        corrections.append(
            "person_boundary_guided_grabcut:"
            f"seed_iou={seed_iou:.4f},area_ratio={area_ratio:.4f}"
        )
        rebuild_mask_result(
            result,
            refined,
            mask_source=f"{result.mask_source}+guided_grabcut",
            fallback_reason=result.fallback_reason,
            detection_box=result.detection_box,
            segmentation_supported=result.segmentation_supported,
            analysis_scope=result.analysis_scope,
        )
        result.correction_reasons = corrections
        analysis["accepted_count"] = int(analysis["accepted_count"]) + 1
        analysis["changed_pixels"] = int(analysis["changed_pixels"]) + changed_pixels

    analysis["reason_counts"] = dict(reason_counts)
    analysis["processing_time_seconds"] = float(time.perf_counter() - started)
    return analysis


def _remove_micro_components(mask: np.ndarray, category: str) -> Tuple[np.ndarray, int]:
    binary = ((mask > 0) * 255).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(
        (binary > 0).astype(np.uint8), 8
    )
    if count <= 2:
        return binary, 0
    areas = [int(stats[index, cv2.CC_STAT_AREA]) for index in range(1, count)]
    largest = max(areas, default=0)
    ratio = 0.003 if category == "person" else 0.012
    minimum = max(4, int(round(largest * ratio)))
    cleaned = np.zeros_like(binary)
    removed = 0
    for index, area in enumerate(areas, start=1):
        if area >= minimum:
            cleaned[labels == index] = 255
        else:
            removed += area
    return cleaned, removed


def postprocess_mask_results(
    image: np.ndarray,
    detections: Sequence[object],
    mask_results: Sequence[ObjectMaskResult],
    apply_repairs: bool = True,
) -> Dict[str, object]:
    """Conservatively repair masks and attach per-stage audit information."""
    corrected = 0
    outside_removed = 0
    islands_removed = 0
    quality_failures: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    target_counts: Counter[str] = Counter()
    excluded_records: List[Dict[str, object]] = []

    for detection, result in zip(detections, mask_results):
        category = category_name_for(detection.name)
        corrections = list(result.correction_reasons or [])
        original = ((result.mask > 0) * 255).astype(np.uint8)
        repaired = original.copy()
        if apply_repairs and result.analysis_scope != "full_image":
            box_binary = _box_mask(repaired.shape, result.detection_box)
            removed = int(np.count_nonzero((repaired > 0) & (box_binary == 0)))
            if removed:
                repaired[box_binary == 0] = 0
                outside_removed += removed
                corrections.append(f"clipped_to_detection_box:{removed}_pixels")
            # The current person path is the quantitative baseline.  Do not
            # alter its connected components without passing the person gate;
            # only the already-required hard clip to the candidate box applies.
            if category == "person":
                removed_islands = 0
            else:
                repaired, removed_islands = _remove_micro_components(repaired, category)
            if removed_islands:
                islands_removed += removed_islands
                corrections.append(f"removed_micro_components:{removed_islands}_pixels")
        if not np.array_equal(original, repaired) and np.count_nonzero(repaired):
            rebuild_mask_result(
                result, repaired,
                mask_source=result.mask_source,
                fallback_reason=result.fallback_reason,
                detection_box=result.detection_box,
                segmentation_supported=result.segmentation_supported,
                analysis_scope=result.analysis_scope,
            )
            corrected += 1

        quality = assess_mask_quality(
            image, result.mask, result.detection_box, category,
            result.analysis_scope, result.mask_source,
        )
        for reason in quality["failure_reasons"]:
            quality_failures[str(reason)] += 1
        result.quality_score = float(quality["quality_score"])
        result.quality_details = quality
        result.correction_reasons = corrections
        if int(quality["mask_pixels"]) == 0 and category != "person":
            result.exclusion_reason = "empty_after_overlap_resolution"
            excluded_records.append({
                "stage": "mask_generation",
                "object_id": result.object_id,
                "name": str(detection.name),
                "category": category,
                "reason_code": "empty_after_overlap_resolution",
                "reason": "mask has no foreground pixels after instance overlap resolution",
                "action": "excluded",
            })
        result.stage_trace = {
            "detection": {
                "status": "accepted",
                "source": str(getattr(detection, "source", "unknown")),
                "sources": list(getattr(detection, "sources", None) or []),
                "confidence": float(getattr(detection, "confidence", 0.0)),
                "merged_from_names": list(
                    getattr(detection, "merged_from_names", None) or []
                ),
            },
            "classification": {
                "status": (
                    "detail_reclassified"
                    if bool(getattr(detection, "detail_reclassified", False))
                    else "coarse_or_direct"
                ),
                "legacy_category": category,
                "target_category": target_category_for(detection.name, category),
                "coarse_name": str(getattr(detection, "coarse_name", detection.name)),
                "final_name": str(detection.name),
                "detail_confidence": getattr(detection, "detail_confidence", None),
            },
            "mask_generation": {
                "status": (
                    "excluded"
                    if result.exclusion_reason
                    else
                    "fallback" if result.mask_source == "box_fallback"
                    else "repaired" if corrections else str(quality["status"])
                ),
                "mask_source": str(result.mask_source),
                "fallback_reason": result.fallback_reason,
                "correction_reasons": corrections,
                "quality_failure_reasons": list(quality["failure_reasons"]),
            },
        }
        source_counts[str(result.mask_source)] += 1
        target = target_category_for(detection.name, category)
        target_counts[str(target or "out_of_scope")] += 1

    return {
        "policy_applied": bool(apply_repairs),
        "processed_object_count": len(mask_results),
        "corrected_object_count": int(corrected),
        "outside_detection_box_pixels_removed": int(outside_removed),
        "micro_component_pixels_removed": int(islands_removed),
        "mask_source_counts": dict(source_counts),
        "target_category_counts": dict(target_counts),
        "quality_failure_reason_counts": dict(quality_failures),
        "excluded_object_count": len(excluded_records),
        "excluded_objects": excluded_records,
    }
