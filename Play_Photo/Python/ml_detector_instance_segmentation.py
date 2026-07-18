"""Instance-oriented analysis pipeline for Magic Photo."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
import json
import re
import time

import numpy as np

from ml_detector_complete import (
    DetectedObject,
    MagicPhotoDetector,
    imwrite_unicode,
)
from object_segmentation import (
    DeepLabBoxObjectSegmenter,
    ObjectMaskResult,
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
}

INSTANCE_SYNONYM_GROUPS = [
    {"person", "human", "man", "woman", "child"},
    {"vehicle", "car", "truck", "van", "bus"},
    {"monitor", "television", "tv"},
    {"phone", "cell phone"},
    {
        "building",
        "apartment building",
        "office building",
        "warehouse",
        "house",
    },
]


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
            exact_cross_class_duplicate = (
                iou >= 0.85
                and containment >= 0.98
                and center_distance <= 0.06
            )
            if (
                synonym_duplicate
                or same_name_non_vehicle_duplicate
                or exact_cross_class_duplicate
            ):
                duplicate_index = index
                duplicate_metrics = (
                    iou,
                    containment,
                    center_distance,
                )
                break

        if duplicate_index is None:
            kept.append(candidate)
            continue

        current = kept[duplicate_index]
        _merge_detection_sources(current, candidate)
        print(
            "instance duplicate merged: "
            f"kept={current.name} removed={candidate.name} "
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

    if mask_hits:
        return min(
            mask_hits,
            key=lambda item: (
                item.area_pixels,
                -float(item.detected.confidence),
                item.object_id,
            ),
        )
    if fallback_hits:
        return min(
            fallback_hits,
            key=lambda item: (
                item.area_pixels,
                -float(item.detected.confidence),
                item.object_id,
            ),
        )
    return None


def consolidate_overlapping_semantic_masks(
    objects: Sequence[InstanceObject],
    overlap_threshold: float = 0.80,
) -> Tuple[List[InstanceObject], int]:
    """Merge duplicate true masks without using fallback rectangles."""
    kept: List[InstanceObject] = []
    merged_count = 0
    for candidate in sorted(
        objects,
        key=lambda item: item.detected.confidence,
        reverse=True,
    ):
        duplicate: Optional[InstanceObject] = None
        duplicate_overlap = 0.0
        if candidate.mask_result.segmentation_supported:
            candidate_pixels = candidate.mask > 0
            candidate_area = max(
                1,
                int(np.count_nonzero(candidate_pixels)),
            )
            for current in kept:
                if not current.mask_result.segmentation_supported:
                    continue
                if (
                    candidate.detected.canonical_name
                    != current.detected.canonical_name
                ):
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
                if overlap >= overlap_threshold:
                    duplicate = current
                    duplicate_overlap = overlap
                    break

        if duplicate is None:
            kept.append(candidate)
            continue

        _merge_detection_sources(duplicate.detected, candidate.detected)
        merged_count += 1
        print(
            "semantic mask duplicate merged: "
            f"kept={duplicate.detected.name} "
            f"removed={candidate.detected.name} "
            f"intersection_over_smaller={duplicate_overlap:.4f}"
        )

    for index, item in enumerate(kept, start=1):
        item.mask_result.object_id = f"object_{index:04d}"
    return kept, merged_count


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
            instance_consolidated + semantic_mask_consolidated
        )
        detector.last_mode_stats["semantic_mask_consolidated"] = (
            semantic_mask_consolidated
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
            f"{instance_consolidated + semantic_mask_consolidated} "
            f"semantic_mask_consolidated="
            f"{semantic_mask_consolidated} "
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
