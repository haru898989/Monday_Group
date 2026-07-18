"""Per-object mask generation for Magic Photo.

YOLO detections provide instance boxes. DeepLabV3 provides a semantic class
map. This module combines both without changing either model implementation.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import cv2
import numpy as np

from semantic_segmentation_multi import SemanticSegmenterMulti


Point = Tuple[int, int]
Box = Tuple[int, int, int, int]


YOLO_TO_DEEPLAB: Dict[str, Optional[str]] = {
    "person": "person",
    "human": "person",
    "man": "person",
    "woman": "person",
    "child": "person",
    "face": "person",
    "car": "car",
    "vehicle": "car",
    "truck": "car",
    "van": "car",
    "bus": "bus",
    "train": "train",
    "bicycle": "bicycle",
    "motorcycle": "motorbike",
    "motorbike": "motorbike",
    "bottle": "bottle",
    "chair": "chair",
    "sofa": "sofa",
    "couch": "sofa",
    "monitor": "tvmonitor",
    "television": "tvmonitor",
    "tv": "tvmonitor",
    "potted plant": "pottedplant",
    "plant": "pottedplant",
    "boat": "boat",
    "aeroplane": "aeroplane",
    "airplane": "aeroplane",
    "bird": "bird",
    "cat": "cat",
    "cow": "cow",
    "dog": "dog",
    "horse": "horse",
    "sheep": "sheep",
    "dining table": "diningtable",
    "table": "diningtable",
}


@dataclass
class ObjectMaskResult:
    object_id: str
    mask: np.ndarray
    detection_box: Box
    mask_box: Box
    corners: Dict[str, Point]
    contour: List[Point]
    contour_simplified: List[Point]
    all_contours: List[List[Point]]
    area_pixels: int
    mask_source: str
    segmentation_supported: bool
    model_class_supported: bool
    semantic_class: Optional[str]
    fallback_reason: Optional[str]
    mask_area_ratio: float
    box_fill_ratio: float
    detection_mask_iou: float
    connected_component_count: int
    semantic_candidate_component_count: int
    box_delta: Dict[str, int]
    mask_path: Optional[str] = None


class ObjectMaskProvider(Protocol):
    def segment_object(
        self,
        image: np.ndarray,
        detection,
        object_id: str,
        semantic_mask: Optional[np.ndarray] = None,
    ) -> ObjectMaskResult:
        """Return a full-resolution binary mask for one detected object."""


def _clip_detection_box(box: Sequence[int], width: int, height: int) -> Box:
    """Convert the detector's xyxy box to inclusive pixel coordinates."""
    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1, min(x2, width - 1))
    y2 = max(y1, min(y2, height - 1))
    return x1, y1, x2, y2


def _box_mask(shape: Tuple[int, int], box: Box) -> np.ndarray:
    height, width = shape
    x1, y1, x2, y2 = _clip_detection_box(box, width, height)
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y1:y2 + 1, x1:x2 + 1] = 255
    return mask


def _mask_box(mask: np.ndarray, fallback: Box) -> Box:
    points = cv2.findNonZero(mask)
    if points is None:
        return fallback
    x, y, width, height = cv2.boundingRect(points)
    return x, y, x + width - 1, y + height - 1


def _corners(box: Box) -> Dict[str, Point]:
    x1, y1, x2, y2 = box
    return {
        "top_left": (x1, y1),
        "top_right": (x2, y1),
        "bottom_right": (x2, y2),
        "bottom_left": (x1, y2),
    }


def _contour_points(contour: np.ndarray) -> List[Point]:
    if contour is None or contour.size == 0:
        return []
    return [
        (int(point[0][0]), int(point[0][1]))
        for point in contour
    ]


def _contour_data(
    mask: np.ndarray,
    epsilon_ratio: float,
    max_simplified_points: int,
) -> Tuple[List[Point], List[Point], List[List[Point]]]:
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_NONE,
    )
    if not contours:
        return [], [], []

    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    primary = contours[0]
    perimeter = cv2.arcLength(primary, True)
    active_ratio = max(0.0001, float(epsilon_ratio))
    simplified = primary
    for _ in range(12):
        epsilon = max(0.5, active_ratio * perimeter)
        simplified = cv2.approxPolyDP(primary, epsilon, True)
        if len(simplified) <= max_simplified_points:
            break
        active_ratio *= 1.5
    return (
        _contour_points(primary),
        _contour_points(simplified),
        [_contour_points(item) for item in contours],
    )


class DeepLabBoxObjectSegmenter:
    """Assign DeepLab semantic pixels to individual YOLO detections."""

    def __init__(
        self,
        semantic_segmenter: SemanticSegmenterMulti,
        epsilon_ratio: float = 0.003,
        minimum_mask_pixels: int = 6,
        minimum_box_coverage: float = 0.002,
        maximum_box_coverage: float = 0.995,
        max_simplified_points: int = 256,
    ) -> None:
        self.semantic_segmenter = semantic_segmenter
        self.epsilon_ratio = float(epsilon_ratio)
        self.minimum_mask_pixels = max(1, int(minimum_mask_pixels))
        self.minimum_box_coverage = max(0.0, float(minimum_box_coverage))
        self.maximum_box_coverage = min(
            1.0,
            max(self.minimum_box_coverage, float(maximum_box_coverage)),
        )
        self.max_simplified_points = max(4, int(max_simplified_points))

    @property
    def supported_semantic_classes(self) -> List[str]:
        return list(self.semantic_segmenter.CLASS_NAMES[1:])

    def semantic_class_for(self, detection_name: str) -> Optional[str]:
        return YOLO_TO_DEEPLAB.get(str(detection_name).strip().lower())

    @staticmethod
    def _component_near_detection(
        candidate: np.ndarray,
        detection_box: Box,
    ) -> Tuple[np.ndarray, int, bool]:
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(
            candidate,
            8,
        )
        if count <= 1:
            return candidate, 0, False

        x1, y1, x2, y2 = detection_box
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        diagonal = max(1.0, float(np.hypot(x2 - x1, y2 - y1)))
        scored_components: List[Tuple[float, int, int]] = []

        for label_id in range(1, count):
            area = int(stats[label_id, cv2.CC_STAT_AREA])
            if area <= 0:
                continue
            component_x, component_y = centroids[label_id]
            distance = np.hypot(
                component_x - center_x,
                component_y - center_y,
            ) / diagonal
            score = distance - min(0.35, np.log1p(area) / 40.0)
            scored_components.append((score, label_id, area))

        component_count = len(scored_components)
        if not scored_components:
            return np.zeros_like(candidate), 0, False
        scored_components.sort()
        best_score, best_label, best_area = scored_components[0]
        total_area = max(1, sum(item[2] for item in scored_components))
        ambiguous = False
        if len(scored_components) >= 2:
            second_score, _, second_area = scored_components[1]
            ambiguous = (
                best_area / total_area >= 0.25
                and second_area / total_area >= 0.25
                and abs(second_score - best_score) <= 0.08
            )

        selected = np.zeros_like(candidate)
        selected[labels == best_label] = 255
        return selected, component_count, ambiguous

    @staticmethod
    def _local_cleanup(mask: np.ndarray, detection_box: Box) -> np.ndarray:
        x1, y1, x2, y2 = detection_box
        box_min_side = max(1, min(x2 - x1 + 1, y2 - y1 + 1))
        kernel_size = 3 if box_min_side >= 12 else 1
        if kernel_size == 1:
            return mask
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (kernel_size, kernel_size),
        )
        return cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    def _build_result(
        self,
        object_id: str,
        mask: np.ndarray,
        detection_box: Box,
        mask_source: str,
        segmentation_supported: bool,
        model_class_supported: bool,
        semantic_class: Optional[str],
        fallback_reason: Optional[str],
        semantic_candidate_component_count: int,
    ) -> ObjectMaskResult:
        final_box = _mask_box(mask, detection_box)
        contour, contour_simplified, all_contours = _contour_data(
            mask,
            self.epsilon_ratio,
            self.max_simplified_points,
        )
        image_area = max(1, mask.shape[0] * mask.shape[1])
        dx1, dy1, dx2, dy2 = detection_box
        mx1, my1, mx2, my2 = final_box
        box_area = max(1, (dx2 - dx1 + 1) * (dy2 - dy1 + 1))
        mask_area = int(np.count_nonzero(mask))
        intersection_mask = np.zeros_like(mask)
        intersection_mask[dy1:dy2 + 1, dx1:dx2 + 1] = 255
        intersection_area = int(
            np.count_nonzero(cv2.bitwise_and(mask, intersection_mask))
        )
        union_area = max(1, box_area + mask_area - intersection_area)
        component_count, _ = cv2.connectedComponents(
            (mask > 0).astype(np.uint8),
            connectivity=8,
        )
        return ObjectMaskResult(
            object_id=object_id,
            mask=mask,
            detection_box=detection_box,
            mask_box=final_box,
            corners=_corners(final_box),
            contour=contour,
            contour_simplified=contour_simplified,
            all_contours=all_contours,
            area_pixels=mask_area,
            mask_source=mask_source,
            segmentation_supported=segmentation_supported,
            model_class_supported=model_class_supported,
            semantic_class=semantic_class,
            fallback_reason=fallback_reason,
            mask_area_ratio=mask_area / image_area,
            box_fill_ratio=mask_area / box_area,
            detection_mask_iou=intersection_area / union_area,
            connected_component_count=max(0, component_count - 1),
            semantic_candidate_component_count=(
                semantic_candidate_component_count
            ),
            box_delta={
                "left": mx1 - dx1,
                "top": my1 - dy1,
                "right": mx2 - dx2,
                "bottom": my2 - dy2,
                "width": (mx2 - mx1 + 1) - (dx2 - dx1 + 1),
                "height": (my2 - my1 + 1) - (dy2 - dy1 + 1),
            },
        )

    def segment_object(
        self,
        image: np.ndarray,
        detection,
        object_id: str,
        semantic_mask: Optional[np.ndarray] = None,
    ) -> ObjectMaskResult:
        if image is None or image.size == 0:
            raise ValueError("image is empty")
        height, width = image.shape[:2]
        detection_box = _clip_detection_box(detection.box, width, height)
        fallback_mask = _box_mask((height, width), detection_box)
        semantic_class = self.semantic_class_for(detection.name)
        model_class_supported = (
            semantic_class is not None
            and semantic_class in self.semantic_segmenter.CLASS_NAMES
        )

        if not model_class_supported or semantic_mask is None:
            return self._build_result(
                object_id,
                fallback_mask,
                detection_box,
                "box_fallback",
                False,
                model_class_supported,
                semantic_class,
                "semantic class not found",
                0,
            )

        class_mask = self.semantic_segmenter.get_class_mask(
            semantic_mask,
            semantic_class,
            clean=False,
        )
        candidate = cv2.bitwise_and(
            class_mask,
            fallback_mask,
        )
        raw_candidate_area = int(np.count_nonzero(candidate))
        if raw_candidate_area == 0:
            return self._build_result(
                object_id,
                fallback_mask,
                detection_box,
                "box_fallback",
                False,
                True,
                semantic_class,
                "empty after crop",
                0,
            )

        candidate = self._local_cleanup(candidate, detection_box)
        candidate, candidate_component_count, ambiguous = (
            self._component_near_detection(candidate, detection_box)
        )

        box_area = max(1, int(np.count_nonzero(fallback_mask)))
        candidate_area = int(np.count_nonzero(candidate))
        candidate_coverage = candidate_area / box_area
        fallback_reason: Optional[str] = None
        if candidate_area == 0:
            fallback_reason = "empty after crop"
        elif ambiguous:
            fallback_reason = "multiple components ambiguous"
        elif candidate_area < self.minimum_mask_pixels:
            fallback_reason = "mask too small"
        elif candidate_coverage < self.minimum_box_coverage:
            fallback_reason = "insufficient overlap"
        elif candidate_coverage > self.maximum_box_coverage:
            fallback_reason = "mask too large"

        if fallback_reason is not None:
            return self._build_result(
                object_id,
                fallback_mask,
                detection_box,
                "box_fallback",
                False,
                True,
                semantic_class,
                fallback_reason,
                candidate_component_count,
            )

        return self._build_result(
            object_id,
            candidate,
            detection_box,
            f"deeplab_voc:{semantic_class}",
            True,
            True,
            semantic_class,
            None,
            candidate_component_count,
        )

    def segment_objects(
        self,
        image: np.ndarray,
        detections: Sequence,
        semantic_mask: Optional[np.ndarray] = None,
    ) -> List[ObjectMaskResult]:
        if semantic_mask is None:
            semantic_mask = self.semantic_segmenter.segment_image(image)
        return [
            self.segment_object(
                image,
                detection,
                f"object_{index:04d}",
                semantic_mask,
            )
            for index, detection in enumerate(detections, start=1)
        ]
