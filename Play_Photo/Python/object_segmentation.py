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
    "sky": "sky",
    "cloud": "sky",
    "sunset": "sky",
    "sunrise": "sky",
    "night sky": "sky",
    "water": "water",
    "water surface": "water",
    "sea": "water",
    "ocean": "water",
    "lake": "water",
    "river": "water",
    "pond": "water",
    "stream": "water",
    "canal": "water",
    "pool": "water",
    "swimming pool": "water",
    "fountain": "water",
    "road": "ground",
    "pavement": "ground",
    "sidewalk": "ground",
    "ground": "ground",
    "soil": "ground",
    "sand": "ground",
    "gravel": "ground",
    "floor": "ground",
    "path": "ground",
    "street": "ground",
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
    category: Optional[str] = None
    analysis_scope: str = "detection_box"
    merged_from_names: Optional[List[str]] = None
    merged_object_ids: Optional[List[str]] = None
    quality_score: float = 0.0
    quality_details: Optional[Dict[str, object]] = None
    correction_reasons: Optional[List[str]] = None
    exclusion_reason: Optional[str] = None
    stage_trace: Optional[Dict[str, object]] = None


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


def rebuild_mask_result(
    result: ObjectMaskResult,
    mask: np.ndarray,
    mask_source: Optional[str] = None,
    fallback_reason: Optional[str] = None,
    detection_box: Optional[Box] = None,
    segmentation_supported: Optional[bool] = None,
    analysis_scope: Optional[str] = None,
) -> ObjectMaskResult:
    """既存の結果へ新しいマスクを反映し、座標と品質指標を再計算する。"""
    final_mask = ((mask > 0) * 255).astype(np.uint8)
    if detection_box is not None:
        result.detection_box = detection_box
    result.mask = final_mask
    result.mask_box = _mask_box(final_mask, result.detection_box)
    result.corners = _corners(result.mask_box)
    result.area_pixels = int(np.count_nonzero(final_mask))

    # 輪郭・連結成分は非ゼロ領域だけで計算する。高解像度画像でも、結果は
    # 全画面で計算した場合と同じまま処理時間と一時メモリを抑えられる。
    if result.area_pixels > 0:
        mx1, my1, mx2, my2 = result.mask_box
        mask_region = final_mask[my1:my2 + 1, mx1:mx2 + 1]
        contour, contour_simplified, all_contours = _contour_data(
            mask_region,
            0.002,
            512,
        )

        def offset_points(points: Sequence[Point]) -> List[Point]:
            return [
                (int(point[0]) + mx1, int(point[1]) + my1)
                for point in points
            ]

        result.contour = offset_points(contour)
        result.contour_simplified = offset_points(contour_simplified)
        result.all_contours = [offset_points(item) for item in all_contours]
        component_count, _ = cv2.connectedComponents(
            (mask_region > 0).astype(np.uint8),
            connectivity=8,
        )
        result.connected_component_count = max(0, int(component_count) - 1)
    else:
        result.contour = []
        result.contour_simplified = []
        result.all_contours = []
        result.connected_component_count = 0

    x1, y1, x2, y2 = result.detection_box
    box_area = max(1, (x2 - x1 + 1) * (y2 - y1 + 1))
    intersection_area = int(np.count_nonzero(final_mask[y1:y2 + 1, x1:x2 + 1]))
    union_area = max(1, box_area + result.area_pixels - intersection_area)
    image_area = max(1, final_mask.shape[0] * final_mask.shape[1])
    result.mask_area_ratio = result.area_pixels / image_area
    result.box_fill_ratio = result.area_pixels / box_area
    result.detection_mask_iou = intersection_area / union_area
    mx1, my1, mx2, my2 = result.mask_box
    result.box_delta = {
        "left": mx1 - x1,
        "top": my1 - y1,
        "right": mx2 - x2,
        "bottom": my2 - y2,
        "width": (mx2 - mx1 + 1) - (x2 - x1 + 1),
        "height": (my2 - my1 + 1) - (y2 - y1 + 1),
    }
    if mask_source is not None:
        result.mask_source = mask_source
    result.fallback_reason = fallback_reason
    if segmentation_supported is not None:
        result.segmentation_supported = bool(segmentation_supported)
    if analysis_scope is not None:
        result.analysis_scope = analysis_scope
    return result


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
        self._scene_mask_cache: Dict[str, np.ndarray] = {}

    @property
    def supported_semantic_classes(self) -> List[str]:
        return list(self.semantic_segmenter.CLASS_NAMES[1:])

    def semantic_class_for(self, detection_name: str) -> Optional[str]:
        return YOLO_TO_DEEPLAB.get(str(detection_name).strip().lower())

    def build_scene_result(
        self,
        image: np.ndarray,
        scene_class: str,
        object_id: str,
    ) -> Optional[ObjectMaskResult]:
        """Build one cached full-image background result without GrabCut."""
        normalized = str(scene_class).strip().lower()
        if not self.semantic_segmenter.supports_scene_class(normalized):
            return None
        mask = self._scene_mask_cache.get(normalized)
        if mask is None:
            mask = self.semantic_segmenter.get_scene_class_mask(
                image,
                normalized,
                clean=True,
            )
            self._scene_mask_cache[normalized] = mask
        if int(np.count_nonzero(mask)) < self.minimum_mask_pixels:
            return None
        height, width = image.shape[:2]
        full_box = (0, 0, width - 1, height - 1)
        scene_box = _mask_box(mask, full_box)
        component_count, _ = cv2.connectedComponents(
            (mask > 0).astype(np.uint8),
            connectivity=8,
        )
        return self._build_result(
            object_id,
            mask,
            scene_box,
            f"full_image_scene:{normalized}",
            True,
            True,
            normalized,
            None,
            max(0, int(component_count) - 1),
            "full_image",
        )

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
        scored_components: List[Tuple[float, float, int, int]] = []
        center_label = int(
            labels[
                max(0, min(labels.shape[0] - 1, int(round(center_y)))),
                max(0, min(labels.shape[1] - 1, int(round(center_x)))),
            ]
        )

        for label_id in range(1, count):
            area = int(stats[label_id, cv2.CC_STAT_AREA])
            if area <= 0:
                continue
            component_x, component_y = centroids[label_id]
            distance = np.hypot(
                component_x - center_x,
                component_y - center_y,
            ) / diagonal
            component_left = int(stats[label_id, cv2.CC_STAT_LEFT])
            component_top = int(stats[label_id, cv2.CC_STAT_TOP])
            component_width = int(stats[label_id, cv2.CC_STAT_WIDTH])
            component_height = int(stats[label_id, cv2.CC_STAT_HEIGHT])
            component_right = component_left + component_width - 1
            component_bottom = component_top + component_height - 1
            overlap_width = max(0, min(x2, component_right) - max(x1, component_left) + 1)
            overlap_height = max(0, min(y2, component_bottom) - max(y1, component_top) + 1)
            overlap_ratio = (overlap_width * overlap_height) / max(1, area)
            center_priority = 0.0 if label_id == center_label else 1.0
            scored_components.append(
                (center_priority, distance - overlap_ratio * 0.15, label_id, area)
            )

        component_count = len(scored_components)
        if not scored_components:
            return np.zeros_like(candidate), 0, False
        scored_components.sort()
        best_priority, best_score, best_label, best_area = scored_components[0]
        total_area = max(1, sum(item[3] for item in scored_components))
        ambiguous = False
        if len(scored_components) >= 2:
            second_priority, second_score, _, second_area = scored_components[1]
            ambiguous = (
                best_priority == second_priority
                and best_area / total_area >= 0.25
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
        analysis_scope: str = "detection_box",
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
            analysis_scope=analysis_scope,
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
        scene_class_supported = (
            semantic_class is not None
            and self.semantic_segmenter.supports_scene_class(semantic_class)
        )
        model_class_supported = (
            semantic_class is not None
            and (
                semantic_class in self.semantic_segmenter.CLASS_NAMES
                or scene_class_supported
            )
        )

        if (
            not model_class_supported
            or (semantic_mask is None and not scene_class_supported)
        ):
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

        if scene_class_supported:
            class_mask = self._scene_mask_cache.get(semantic_class)
            if class_mask is None:
                class_mask = self.semantic_segmenter.get_scene_class_mask(
                    image,
                    semantic_class,
                    clean=True,
                )
                self._scene_mask_cache[semantic_class] = class_mask
            scene_component_count = 1
            if semantic_class != "sky":
                class_mask, scene_component_count, _ = self._component_near_detection(
                    class_mask,
                    detection_box,
                )
            if int(np.count_nonzero(class_mask)) < self.minimum_mask_pixels:
                return self._build_result(
                    object_id,
                    fallback_mask,
                    detection_box,
                    "box_fallback",
                    False,
                    True,
                    semantic_class,
                    "full-image scene mask empty",
                    0,
                    "full_image",
                )
            return self._build_result(
                object_id,
                class_mask,
                detection_box,
                f"full_image_scene:{semantic_class}",
                True,
                True,
                semantic_class,
                None,
                scene_component_count,
                "full_image",
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
        self._scene_mask_cache = {}
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
