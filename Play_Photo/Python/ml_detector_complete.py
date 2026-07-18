"""
Magic Photo Museum - YOLO-World Detector
========================================
YOLO-Worldによる物体検出、クリック判定、日本語パス対応画像読み込み。
"""

from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Optional
from pathlib import Path
from io import BytesIO
import time

import cv2
import numpy as np
from ultralytics import YOLO

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None


@dataclass
class DetectedObject:
    name: str
    reaction: str
    confidence: float
    box: Tuple[int, int, int, int]
    center: Tuple[int, int]
    source: str = "yolo"
    original_name: Optional[str] = None
    canonical_name: Optional[str] = None
    sources: Optional[List[str]] = None
    auto_reason: Optional[str] = None
    tile_bounds: Optional[Tuple[int, int, int, int]] = None

    def __post_init__(self) -> None:
        if self.original_name is None:
            self.original_name = self.name
        if self.canonical_name is None:
            self.canonical_name = canonical_name_for(self.name)
        if self.sources is None:
            self.sources = [self.source]

    @property
    def box_original(self) -> Tuple[int, int, int, int]:
        return self.box

    @property
    def center_original(self) -> Tuple[int, int]:
        return self.center

    @property
    def top_left(self) -> Tuple[int, int]:
        x1, y1, _, _ = self.box
        return x1, y1

    @property
    def top_right(self) -> Tuple[int, int]:
        _, y1, x2, _ = self.box
        return x2, y1

    @property
    def bottom_right(self) -> Tuple[int, int]:
        _, _, x2, y2 = self.box
        return x2, y2

    @property
    def bottom_left(self) -> Tuple[int, int]:
        x1, _, _, y2 = self.box
        return x1, y2

    @property
    def four_corners_original(self) -> Dict[str, Tuple[int, int]]:
        return {
            "top_left": self.top_left,
            "top_right": self.top_right,
            "bottom_right": self.bottom_right,
            "bottom_left": self.bottom_left,
        }

    def to_dict(self) -> Dict:
        data = asdict(self)
        data["box_original"] = self.box_original
        data["center_original"] = self.center_original
        data["four_corners_original"] = self.four_corners_original
        return data


def imread_unicode(path: str) -> Optional[np.ndarray]:
    """日本語を含むWindowsパスでも読み込める画像読み込み。"""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        if Image is not None and ImageOps is not None:
            with Image.open(BytesIO(data.tobytes())) as pil_img:
                pil_img = ImageOps.exif_transpose(pil_img)
                rgb = pil_img.convert("RGB")
                return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def imwrite_unicode(path: str, image: np.ndarray) -> bool:
    """日本語を含むWindowsパスでも保存できる画像保存。"""
    try:
        suffix = Path(path).suffix.lower() or ".jpg"
        ok, encoded = cv2.imencode(suffix, image)
        if not ok:
            return False
        encoded.tofile(str(path))
        return True
    except Exception:
        return False


DETECTION_PRESETS = {
    "standard": {
        "model_path": "yolov8s-world.pt",
        "confidence": 0.23,
        "image_size": 640,
        "tile_detection": False,
    },
    "accuracy": {
        "model_path": "yolov8m-world.pt",
        "fallback_model_path": "yolov8s-world.pt",
        "confidence": 0.20,
        "image_size": 960,
        "tile_detection": True,
        "tile_size": 960,
        "tile_overlap": 0.25,
    },
    "auto": {
        "model_path": "yolov8s-world.pt",
        "confidence": 0.23,
        "image_size": 640,
        "tile_detection": False,
        "auto_accuracy_image_size": 960,
        "auto_tile_size": 960,
        "auto_tile_overlap": 0.25,
    },
}

CLASS_CONFIDENCE_THRESHOLDS = {
    "person": 0.30,
    "human": 0.30,
    "man": 0.30,
    "woman": 0.30,
    "child": 0.30,
    "car": 0.18,
    "vehicle": 0.18,
    "truck": 0.18,
    "van": 0.18,
    "bus": 0.18,
    "motorcycle": 0.35,
    "bicycle": 0.18,
    "building": 0.20,
    "apartment building": 0.20,
    "office building": 0.20,
    "warehouse": 0.20,
    "house": 0.20,
    "street light": 0.18,
    "utility pole": 0.18,
    "traffic sign": 0.35,
    "road": 0.20,
    "pavement": 0.20,
    "sky": 0.20,
    "mountain": 0.20,
    "water": 0.20,
    "tree": 0.20,
    "plant": 0.20,
    "train": 0.40,
    "city": 0.40,
    "ice cream": 0.20,
    "cone": 0.25,
    "hand": 0.30,
}

TILE_THRESHOLD_EXEMPT_CLASSES = {
    "car", "truck", "van", "bus", "vehicle",
}

BACKGROUND_SINGLETON_CLASSES = {
    "sky", "road", "pavement", "city", "ground", "mountain", "water",
}

AUTO_TILE_ALLOWED_CLASSES = {
    "person", "human", "man", "woman", "child",
    "car", "truck", "van", "bus", "bicycle", "motorcycle",
    "animal", "dog", "cat", "bird", "horse", "rabbit",
    "phone", "cell phone", "bottle", "cup", "traffic sign",
    "ice cream", "cone", "hand",
}

AUTO_TILE_BLOCKED_CLASSES = {
    "sky", "road", "pavement", "city", "building", "office building",
    "apartment building", "warehouse", "wall", "ground", "table",
    "dining table", "tree", "plant", "grass", "mountain", "water",
    "house",
}

CLASS_MAX_AREA_RATIOS = {
    "street light": 0.08,
    "traffic sign": 0.04,
    "person": 0.18,
    "human": 0.18,
    "man": 0.18,
    "woman": 0.18,
    "child": 0.12,
    "motorcycle": 0.10,
    "bicycle": 0.10,
    "car": 0.16,
    "truck": 0.18,
    "van": 0.18,
    "bus": 0.22,
    "phone": 0.08,
    "cell phone": 0.08,
    "bottle": 0.08,
    "cup": 0.08,
    "ice cream": 0.10,
    "cone": 0.08,
    "hand": 0.12,
}

CANONICAL_NAMES = {
    "car": "vehicle",
    "truck": "vehicle",
    "van": "vehicle",
    "bus": "vehicle",
    "vehicle": "vehicle",
    "motorcycle": "vehicle",
    "bicycle": "vehicle",
    "person": "person",
    "human": "person",
    "man": "person",
    "woman": "person",
    "child": "person",
    "building": "building",
    "apartment building": "building",
    "office building": "building",
    "warehouse": "building",
    "house": "building",
    "water": "water",
    "sea": "water",
    "ocean": "water",
    "river": "water",
    "lake": "water",
    "pond": "water",
    "pool": "water",
    "tree": "plant",
    "plant": "plant",
    "flower": "plant",
    "potted plant": "plant",
    "pottedplant": "plant",
}


def canonical_name_for(name: str) -> str:
    return CANONICAL_NAMES.get(name, name)

SYNONYM_GROUPS = [
    ["person", "human", "man", "woman", "child"],
    ["vehicle", "car", "truck", "van", "bus"],
    ["monitor", "television", "tv"],
    ["phone", "cell phone"],
    ["building", "apartment building", "office building", "warehouse", "house"],
    ["water", "sea", "ocean", "river", "lake", "pond", "pool"],
    ["animal", "dog", "cat", "bird", "horse", "rabbit"],
]

CLASS_SPECIFICITY = {
    "vehicle": 0,
    "truck": 2,
    "van": 2,
    "bus": 2,
    "animal": 0,
    "human": 0,
    "person": 1,
    "man": 2,
    "woman": 2,
    "child": 2,
    "car": 2,
    "dog": 2,
    "cat": 2,
    "bird": 2,
    "horse": 2,
    "rabbit": 2,
    "phone": 2,
    "cell phone": 1,
    "monitor": 2,
    "television": 1,
    "tv": 1,
    "house": 2,
    "warehouse": 2,
    "office building": 2,
    "apartment building": 2,
    "building": 1,
}


class MagicPhotoDetector:
    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence: Optional[float] = None,
        image_size: Optional[int] = None,
        max_display_size: int = 1280,
        detection_mode: str = "standard",
        synonym_iou_threshold: float = 0.72,
        max_low_conf_area_ratio: float = 0.45,
        low_conf_large_threshold: float = 0.38,
        max_full_image_low_conf_area_ratio: float = 0.70,
        full_image_low_conf_threshold: float = 0.55,
        min_box_area_ratio: float = 0.00006,
        min_small_box_confidence: float = 0.24,
        tile_detection: Optional[bool] = None,
        tile_size: Optional[int] = None,
        tile_overlap: Optional[float] = None,
    ):
        self.detection_mode = detection_mode if detection_mode in DETECTION_PRESETS else "standard"
        preset = DETECTION_PRESETS[self.detection_mode]
        selected_model = model_path or str(preset["model_path"])

        if model_path is None and self.detection_mode == "accuracy":
            selected_model = self._select_accuracy_model(preset)

        self.model_path = self._resolve_model_path(selected_model)
        self.confidence = float(confidence if confidence is not None else preset["confidence"])
        self.image_size = int(image_size if image_size is not None else preset["image_size"])
        self.max_display_size = int(max_display_size)
        self.synonym_iou_threshold = float(synonym_iou_threshold)
        self.max_low_conf_area_ratio = float(max_low_conf_area_ratio)
        self.low_conf_large_threshold = float(low_conf_large_threshold)
        self.max_full_image_low_conf_area_ratio = float(max_full_image_low_conf_area_ratio)
        self.full_image_low_conf_threshold = float(full_image_low_conf_threshold)
        self.min_box_area_ratio = float(min_box_area_ratio)
        self.min_small_box_confidence = float(min_small_box_confidence)
        self.tile_detection = bool(
            tile_detection if tile_detection is not None else preset.get("tile_detection", False)
        )
        self.tile_size = int(tile_size if tile_size is not None else preset.get("tile_size", self.image_size))
        self.tile_overlap = float(tile_overlap if tile_overlap is not None else preset.get("tile_overlap", 0.25))
        self.class_confidence_thresholds = {
            name: float(value)
            for name, value in CLASS_CONFIDENCE_THRESHOLDS.items()
        }
        self.small_object_exempt_classes = {
            "person", "human", "man", "woman", "child",
            "car", "truck", "van", "bus", "motorcycle", "bicycle",
            "street light", "utility pole", "traffic sign",
        }
        self.large_region_allowed_classes = {
            "sky", "road", "pavement", "ground", "building",
            "apartment building", "office building", "warehouse", "house",
            "mountain", "water", "sea", "ocean", "river", "lake",
            "pond", "pool", "tree", "plant", "grass",
        }
        self.low_conf_large_classes = {
            "vehicle", "bridge", "city", "wall",
        }
        self.synonym_lookup = self._build_synonym_lookup()
        self.last_raw_detection_count = 0
        self.last_filtered_detection_count = 0
        self.last_final_detection_count = 0
        self.last_processing_time = 0.0
        self.last_mode_stats: Dict[str, object] = {}
        self.last_auto_used_accuracy = False
        self.last_filtered_out: List[Tuple[DetectedObject, str]] = []

        print(
            "YOLO-World mode: "
            f"{self.detection_mode} | model: {self.model_path} | "
            f"base_conf={self.confidence:.2f} | imgsz={self.image_size} | "
            f"tile_detection={self.tile_detection}"
        )
        self.model = YOLO(self.model_path)

        self.custom_classes = [
            "person", "human", "man", "woman", "child", "face",
            "light", "lamp", "ceiling light", "desk lamp",
            "street light", "utility pole", "traffic sign",
            "window", "door", "clock", "mirror",
            "musical instrument", "guitar", "piano", "drum", "microphone",
            "radio", "speaker", "toy", "ball", "balloon",
            "animal", "dog", "cat", "bird", "fish", "horse", "rabbit",
            "book", "notebook", "paper", "mathematical formula", "whiteboard",
            "computer", "laptop", "monitor", "keyboard", "mouse",
            "phone", "cell phone",
            "food", "apple", "banana", "cake", "pizza", "cup", "bottle",
            "ice cream", "cone", "hand",
            "vehicle", "car", "truck", "van", "bus", "train", "bicycle", "motorcycle",
            "sky", "road", "pavement", "ground", "sun", "moon", "cloud",
            "tree", "plant", "grass", "flower", "fireworks",
            "water", "sea", "ocean", "river", "lake", "pond", "pool",
            "waterfall", "building", "apartment building", "office building",
            "warehouse", "house", "tower", "bridge", "castle", "mountain",
            "wall", "city", "treasure box", "kettle", "pot", "faucet",
            "sink", "glass", "firework",
        ]

        self.model.set_classes(self.custom_classes)
        self.reaction_rules = self._build_reaction_rules()
        self.last_objects: List[DetectedObject] = []
        self.last_image: Optional[np.ndarray] = None

    @staticmethod
    def _candidate_model_paths(model_path: str) -> List[Path]:
        path = Path(model_path)
        if path.is_absolute():
            return [path]
        return [
            Path.cwd() / path,
            Path(__file__).resolve().parent / path,
            path,
        ]

    @classmethod
    def _model_exists(cls, model_path: str) -> Optional[Path]:
        for path in cls._candidate_model_paths(model_path):
            if path.exists():
                return path
        return None

    @classmethod
    def _resolve_model_path(cls, model_path: str) -> str:
        found = cls._model_exists(model_path)
        if found is not None:
            return str(found)
        raise FileNotFoundError(
            "YOLO model file was not found. "
            f"Requested '{model_path}'. Place the file next to this script "
            "or set model_path to an existing .pt file."
        )

    @classmethod
    def _select_accuracy_model(cls, preset: Dict[str, object]) -> str:
        preferred = str(preset["model_path"])
        if cls._model_exists(preferred) is not None:
            return preferred

        fallback = str(preset.get("fallback_model_path", "yolov8s-world.pt"))
        if cls._model_exists(fallback) is not None:
            print(
                "Accuracy model is not installed: "
                f"{preferred}. Falling back to {fallback}. "
                "Copy a higher accuracy YOLO-World model here to enable it."
            )
            return fallback

        raise FileNotFoundError(
            "Neither the accuracy model nor the fallback standard model "
            f"was found ({preferred}, {fallback})."
        )

    @staticmethod
    def _build_synonym_lookup() -> Dict[str, str]:
        lookup: Dict[str, str] = {}
        for group in SYNONYM_GROUPS:
            group_id = "|".join(group)
            for name in group:
                lookup[name] = group_id
        return lookup

    @staticmethod
    def _build_reaction_rules() -> Dict[str, str]:
        groups = {
            "human_reaction": ["person", "human", "man", "woman", "child", "face"],
            "toggle_light": ["light", "lamp", "ceiling light", "desk lamp"],
            "play_music": [
                "musical instrument", "guitar", "piano", "drum",
                "microphone", "speaker"
            ],
            "play_radio": ["radio"],
            "animal_sound": [
                "animal", "dog", "cat", "bird", "fish", "horse", "rabbit"
            ],
            "open_book": ["book", "notebook"],
            "solve_or_write": ["paper", "whiteboard"],
            "solve_formula": ["mathematical formula"],
            "start_pc": ["computer", "laptop", "monitor", "keyboard", "mouse"],
            "ring_phone": ["phone", "cell phone"],
            "eat_food": [
                "food", "apple", "banana", "cake", "pizza", "ice cream", "cone"
            ],
            "hand_action": ["hand"],
            "steam_or_fill": ["cup", "bottle"],
            "move_vehicle": [
                "vehicle", "car", "truck", "van", "bus", "train",
                "bicycle", "motorcycle"
            ],
            "fireworks": ["sky", "fireworks", "firework"],
            "day_night_change": ["sun", "moon"],
            "weather_change": ["cloud"],
            "grow_tree": ["tree"],
            "bloom_flower": ["flower"],
            "water_magic": [
                "water", "sea", "ocean", "river", "lake", "pond",
                "pool", "waterfall"
            ],
            "building_magic": [
                "building", "apartment building", "office building",
                "warehouse", "house", "tower", "bridge", "castle", "wall", "city"
            ],
            "road_magic": ["road", "pavement", "ground"],
            "street_magic": ["street light", "utility pole", "traffic sign"],
            "mountain_magic": ["mountain"],
            "break_window": ["window"],
            "open_door": ["door"],
            "spin_clock": ["clock"],
            "magic_mirror": ["mirror"],
            "toy_action": ["toy"],
            "bounce_ball": ["ball"],
            "fly_balloon": ["balloon"],
            "open_treasure": ["treasure box"],
            "steam": ["kettle", "pot"],
            "water_on": ["faucet", "sink"],
            "break_glass": ["glass"],
        }

        rules: Dict[str, str] = {}
        for reaction, names in groups.items():
            for name in names:
                rules[name] = reaction
        return rules

    @staticmethod
    def resize_image_to_fit(
        img: np.ndarray, max_width: int, max_height: int
    ) -> np.ndarray:
        h, w = img.shape[:2]
        max_width = max(100, int(max_width))
        max_height = max(100, int(max_height))
        scale = min(max_width / w, max_height / h, 1.0)

        if scale >= 1.0:
            return img

        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        return cv2.resize(
            img, (new_w, new_h), interpolation=cv2.INTER_AREA
        )

    def load_image_for_screen(
        self,
        image_path: str,
        screen_width: int,
        screen_height: int,
        margin: int = 100,
    ) -> np.ndarray:
        img = imread_unicode(image_path)
        if img is None:
            raise FileNotFoundError(f"画像が見つかりません: {image_path}")

        img = self.resize_image_to_fit(
            img,
            screen_width - margin,
            screen_height - margin,
        )
        self.last_image = img
        return img

    def load_original_image(self, image_path: str) -> np.ndarray:
        img = imread_unicode(image_path)
        if img is None:
            raise FileNotFoundError(f"逕ｻ蜒上′隕九▽縺九ｊ縺ｾ縺帙ｓ: {image_path}")
        self.last_image = img
        return img

    @staticmethod
    def _box_area(item: DetectedObject) -> int:
        x1, y1, x2, y2 = item.box
        return max(0, x2 - x1) * max(0, y2 - y1)

    def _class_threshold(self, name: str, source: str = "yolo") -> float:
        threshold = float(self.class_confidence_thresholds.get(name, self.confidence))
        if source == "yolo_tile":
            threshold += 0.02 if name in TILE_THRESHOLD_EXEMPT_CLASSES else 0.05
        return threshold

    def _inference_confidence(self) -> float:
        values = list(self.class_confidence_thresholds.values()) + [self.confidence]
        return max(0.01, min(values))

    @staticmethod
    def _iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        iw = max(0, ix2 - ix1)
        ih = max(0, iy2 - iy1)
        intersection = iw * ih
        if intersection == 0:
            return 0.0
        area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
        area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
        union = area_a + area_b - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _intersection_over_smaller(
        a: Tuple[int, int, int, int],
        b: Tuple[int, int, int, int],
    ) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1 = max(ax1, bx1)
        iy1 = max(ay1, by1)
        ix2 = min(ax2, bx2)
        iy2 = min(ay2, by2)
        intersection = max(0, ix2 - ix1) * max(0, iy2 - iy1)
        area_a = max(1, (ax2 - ax1) * (ay2 - ay1))
        area_b = max(1, (bx2 - bx1) * (by2 - by1))
        return intersection / min(area_a, area_b)

    @staticmethod
    def _normalized_center_distance(a: DetectedObject, b: DetectedObject) -> float:
        ax, ay = a.center
        bx, by = b.center
        x1 = min(a.box[0], b.box[0])
        y1 = min(a.box[1], b.box[1])
        x2 = max(a.box[2], b.box[2])
        y2 = max(a.box[3], b.box[3])
        diagonal = max(1.0, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5)
        distance = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
        return distance / diagonal

    @staticmethod
    def _size_similarity(a: DetectedObject, b: DetectedObject) -> float:
        area_a = max(1, MagicPhotoDetector._box_area(a))
        area_b = max(1, MagicPhotoDetector._box_area(b))
        return min(area_a, area_b) / max(area_a, area_b)

    @staticmethod
    def _add_sources(target: DetectedObject, source_item: DetectedObject) -> None:
        sources = list(target.sources or [target.source])
        for source in source_item.sources or [source_item.source]:
            if source not in sources:
                sources.append(source)
        target.sources = sources

    @staticmethod
    def _specificity(name: str) -> int:
        return CLASS_SPECIFICITY.get(name, 1)

    def _is_same_synonym_group(self, a: DetectedObject, b: DetectedObject) -> bool:
        group = self.synonym_lookup.get(a.name)
        return group is not None and group == self.synonym_lookup.get(b.name)

    def _is_duplicate_candidate(self, a: DetectedObject, b: DetectedObject) -> bool:
        if canonical_name_for(a.name) != canonical_name_for(b.name):
            return False
        iou = self._iou(a.box, b.box)
        if canonical_name_for(a.name) == "vehicle":
            if iou >= 0.55:
                return True
            containment = self._intersection_over_smaller(a.box, b.box)
            center_distance = self._normalized_center_distance(a, b)
            size_similarity = self._size_similarity(a, b)
            return (
                containment >= 0.78
                and center_distance <= 0.22
                and size_similarity >= 0.45
            )
        if iou >= self.synonym_iou_threshold:
            return True
        containment = self._intersection_over_smaller(a.box, b.box)
        center_distance = self._normalized_center_distance(a, b)
        size_similarity = self._size_similarity(a, b)
        return containment >= 0.88 and center_distance <= 0.18 and size_similarity >= 0.55

    def _choose_duplicate(self, a: DetectedObject, b: DetectedObject) -> DetectedObject:
        specificity_a = self._specificity(a.name)
        specificity_b = self._specificity(b.name)

        if specificity_a != specificity_b:
            if specificity_a > specificity_b and a.confidence >= b.confidence - 0.10:
                return a
            if specificity_b > specificity_a and b.confidence >= a.confidence - 0.10:
                return b

        return a if a.confidence >= b.confidence else b

    def _quality_filter_reason(
        self,
        item: DetectedObject,
        image_area: int,
    ) -> Optional[str]:
        area_ratio = self._box_area(item) / max(1, image_area)

        threshold = self._class_threshold(item.name, item.source)
        if item.confidence + 1e-6 < threshold:
            return f"confidence {item.confidence:.4f} < class_threshold {threshold:.4f}"

        max_area_ratio = CLASS_MAX_AREA_RATIOS.get(item.name)
        if max_area_ratio is not None and area_ratio > max_area_ratio:
            return (
                f"class max area exceeded area_ratio={area_ratio:.4f} "
                f"> max_area_ratio={max_area_ratio:.4f}"
            )

        if (
            item.name not in self.large_region_allowed_classes
            and area_ratio >= self.max_full_image_low_conf_area_ratio
            and item.confidence < self.full_image_low_conf_threshold
        ):
            return f"low-confidence near-full-image box area_ratio={area_ratio:.3f}"

        if (
            item.name in self.low_conf_large_classes
            and area_ratio >= self.max_low_conf_area_ratio
            and item.confidence < self.low_conf_large_threshold
        ):
            return f"low-confidence large box area_ratio={area_ratio:.3f}"

        if (
            item.name not in self.small_object_exempt_classes
            and area_ratio <= self.min_box_area_ratio
            and item.confidence < self.min_small_box_confidence
        ):
            return f"low-confidence tiny box area_ratio={area_ratio:.6f}"

        return None

    def _passes_quality_filters(
        self,
        item: DetectedObject,
        image_area: int,
    ) -> bool:
        return self._quality_filter_reason(item, image_area) is None

    def _filter_detections(
        self,
        detections: List[DetectedObject],
        image_shape: Tuple[int, int, int],
    ) -> List[DetectedObject]:
        h, w = image_shape[:2]
        image_area = h * w
        self.last_filtered_out = []
        quality_filtered: List[DetectedObject] = []
        for item in detections:
            reason = self._quality_filter_reason(item, image_area)
            if reason is None:
                quality_filtered.append(item)
            else:
                self.last_filtered_out.append((item, reason))

        kept: List[DetectedObject] = []
        for candidate in sorted(
            quality_filtered,
            key=lambda item: (self._specificity(item.name), item.confidence),
            reverse=True,
        ):
            replaced = False
            discard = False
            for index, current in enumerate(kept):
                if not (
                    self._is_same_synonym_group(candidate, current)
                    or candidate.name == current.name
                ):
                    continue
                if not self._is_duplicate_candidate(candidate, current):
                    continue

                winner = self._choose_duplicate(candidate, current)
                if winner is candidate:
                    self._add_sources(candidate, current)
                    kept[index] = candidate
                    replaced = True
                    self.last_filtered_out.append((current, f"duplicate merged into {candidate.name}"))
                else:
                    self._add_sources(current, candidate)
                    discard = True
                    self.last_filtered_out.append((candidate, f"duplicate merged into {current.name}"))
                break

            if not replaced and not discard:
                kept.append(candidate)

        kept = self._keep_single_background_regions(kept)
        kept.sort(key=lambda item: item.confidence, reverse=True)
        return kept

    def _keep_single_background_regions(
        self,
        items: List[DetectedObject],
    ) -> List[DetectedObject]:
        best_by_class: Dict[str, DetectedObject] = {}
        output: List[DetectedObject] = []
        for item in items:
            if item.name not in BACKGROUND_SINGLETON_CLASSES:
                output.append(item)
                continue

            current = best_by_class.get(item.name)
            if current is None:
                best_by_class[item.name] = item
                continue

            current_key = (
                current.confidence,
                self._box_area(current),
                1 if current.source == "yolo" else 0,
            )
            item_key = (
                item.confidence,
                self._box_area(item),
                1 if item.source == "yolo" else 0,
            )
            if item_key > current_key:
                self._add_sources(item, current)
                self.last_filtered_out.append((current, f"background singleton kept {item.name}"))
                best_by_class[item.name] = item
            else:
                self._add_sources(current, item)
                self.last_filtered_out.append((item, f"background singleton kept {current.name}"))

        output.extend(best_by_class.values())
        return output

    @staticmethod
    def _format_class_counts(items: List[DetectedObject]) -> str:
        counts: Dict[str, int] = {}
        for item in items:
            counts[item.name] = counts.get(item.name, 0) + 1
        if not counts:
            return "none"
        return ", ".join(
            f"{name}={count}" for name, count in sorted(counts.items())
        )

    def _run_yolo(
        self,
        img: np.ndarray,
        source: str,
        offset: Tuple[int, int] = (0, 0),
        full_shape: Optional[Tuple[int, int, int]] = None,
        tile_bounds: Optional[Tuple[int, int, int, int]] = None,
    ) -> List[DetectedObject]:
        if full_shape is None:
            full_shape = img.shape

        results = self.model(
            img,
            conf=self._inference_confidence(),
            imgsz=self.image_size,
            verbose=False,
        )

        detected: List[DetectedObject] = []
        full_h, full_w = full_shape[:2]
        offset_x, offset_y = offset

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0])
                name = str(self.model.names[class_id])
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                x1 += offset_x
                x2 += offset_x
                y1 += offset_y
                y2 += offset_y

                x1 = max(0, min(x1, full_w - 1))
                y1 = max(0, min(y1, full_h - 1))
                x2 = max(x1 + 1, min(x2, full_w))
                y2 = max(y1 + 1, min(y2, full_h))

                detected.append(
                    DetectedObject(
                        name=name,
                        reaction=self.reaction_rules.get(
                            name, "unknown_magic"
                        ),
                        confidence=confidence,
                        box=(x1, y1, x2, y2),
                        center=((x1 + x2) // 2, (y1 + y2) // 2),
                        source=source,
                        original_name=name,
                        canonical_name=canonical_name_for(name),
                        tile_bounds=tile_bounds,
                    )
                )

        return detected

    def _tile_windows(self, width: int, height: int) -> List[Tuple[int, int, int, int]]:
        tile = max(256, int(self.tile_size))
        overlap = max(0.0, min(self.tile_overlap, 0.8))
        step = max(1, int(tile * (1.0 - overlap)))
        windows: List[Tuple[int, int, int, int]] = []

        y_positions = list(range(0, max(height - tile, 0) + 1, step))
        x_positions = list(range(0, max(width - tile, 0) + 1, step))
        if not y_positions or y_positions[-1] != max(height - tile, 0):
            y_positions.append(max(height - tile, 0))
        if not x_positions or x_positions[-1] != max(width - tile, 0):
            x_positions.append(max(width - tile, 0))

        for y1 in y_positions:
            for x1 in x_positions:
                x2 = min(width, x1 + tile)
                y2 = min(height, y1 + tile)
                windows.append((x1, y1, x2, y2))

        return sorted(set(windows))

    def _auto_should_use_accuracy(
        self,
        img: np.ndarray,
        standard_objects: List[DetectedObject],
    ) -> Tuple[bool, List[str]]:
        h, w = img.shape[:2]
        reasons: List[str] = []
        canonical_counts: Dict[str, int] = {}
        for item in standard_objects:
            canonical_counts[item.canonical_name or canonical_name_for(item.name)] = (
                canonical_counts.get(item.canonical_name or canonical_name_for(item.name), 0) + 1
            )

        if len(standard_objects) < 8:
            reasons.append(f"few detections ({len(standard_objects)} < 8)")
        if canonical_counts.get("vehicle", 0) == 0:
            reasons.append("no vehicle detected")
        if canonical_counts.get("building", 0) == 0:
            reasons.append("no building detected")
        if w * h >= 2_500_000 and len(standard_objects) < 12:
            reasons.append(f"high resolution with modest detections ({w}x{h})")

        return bool(reasons), reasons

    def _is_tile_edge_cut(
        self,
        item: DetectedObject,
        full_shape: Tuple[int, int, int],
        tolerance: int = 3,
    ) -> bool:
        if item.tile_bounds is None:
            return False
        full_h, full_w = full_shape[:2]
        tx1, ty1, tx2, ty2 = item.tile_bounds
        x1, y1, x2, y2 = item.box
        if tx1 > 0 and abs(x1 - tx1) <= tolerance:
            return True
        if ty1 > 0 and abs(y1 - ty1) <= tolerance:
            return True
        if tx2 < full_w and abs(x2 - tx2) <= tolerance:
            return True
        if ty2 < full_h and abs(y2 - ty2) <= tolerance:
            return True
        return False

    def _is_existing_object_match(
        self,
        candidate: DetectedObject,
        existing: DetectedObject,
    ) -> bool:
        if canonical_name_for(candidate.name) != canonical_name_for(existing.name):
            return False
        if self._is_duplicate_candidate(candidate, existing):
            return True
        iou = self._iou(candidate.box, existing.box)
        containment = self._intersection_over_smaller(candidate.box, existing.box)
        center_distance = self._normalized_center_distance(candidate, existing)
        return iou >= 0.25 or (containment >= 0.55 and center_distance <= 0.35)

    def _auto_candidate_reject_reason(
        self,
        candidate: DetectedObject,
        base_objects: List[DetectedObject],
        image_shape: Tuple[int, int, int],
    ) -> Optional[str]:
        if candidate.source != "yolo_tile":
            return "not a tile candidate"
        if candidate.name in AUTO_TILE_BLOCKED_CLASSES:
            return f"blocked auto tile class: {candidate.name}"
        if candidate.name not in AUTO_TILE_ALLOWED_CLASSES:
            return f"class is not auto-add eligible: {candidate.name}"

        quality_reason = self._quality_filter_reason(candidate, image_shape[0] * image_shape[1])
        if quality_reason is not None:
            return quality_reason

        area_ratio = self._box_area(candidate) / max(1, image_shape[0] * image_shape[1])
        if area_ratio > 0.06 and candidate.name not in {"bus", "truck", "van"}:
            return f"auto tile box too large area_ratio={area_ratio:.4f}"
        if area_ratio > 0.14:
            return f"auto tile vehicle/large object too large area_ratio={area_ratio:.4f}"

        if self._is_tile_edge_cut(candidate, image_shape):
            return "tile candidate appears cut by internal tile edge"

        for existing in base_objects:
            if self._is_existing_object_match(candidate, existing):
                return f"already represented by standard {existing.name} box={existing.box}"

        return None

    def _auto_add_tile_candidates(
        self,
        standard_objects: List[DetectedObject],
        tile_raw: List[DetectedObject],
        image_shape: Tuple[int, int, int],
    ) -> Tuple[List[DetectedObject], List[DetectedObject], List[Tuple[DetectedObject, str]]]:
        tile_candidates = self._filter_detections(tile_raw, image_shape)
        accepted: List[DetectedObject] = []
        rejected: List[Tuple[DetectedObject, str]] = []
        current = list(standard_objects)

        for candidate in sorted(tile_candidates, key=lambda item: item.confidence, reverse=True):
            reason = self._auto_candidate_reject_reason(candidate, current, image_shape)
            if reason is not None:
                rejected.append((candidate, reason))
                continue
            candidate.auto_reason = "small object missing from standard"
            candidate.sources = list(candidate.sources or [candidate.source])
            accepted.append(candidate)
            current.append(candidate)

        return tile_candidates, accepted, rejected

    def detect_from_image(self, img: np.ndarray) -> List[DetectedObject]:
        if img is None or img.size == 0:
            raise ValueError("検出対象の画像が空です。")

        started = time.perf_counter()
        detected = self._run_yolo(img, source="yolo", full_shape=img.shape)
        raw_standard_count = len(detected)
        auto_reasons: List[str] = []
        auto_used_accuracy = False
        auto_tile_candidate_count = 0
        auto_added_count = 0
        auto_rejected: List[Tuple[DetectedObject, str]] = []

        if self.detection_mode == "auto":
            standard_filtered = self._filter_detections(detected, img.shape)
            standard_filter_log = list(self.last_filtered_out)
            should_use_accuracy, auto_reasons = self._auto_should_use_accuracy(
                img, standard_filtered
            )
            print(
                "auto standard pass: "
                f"raw={raw_standard_count} filtered={len(standard_filtered)} "
                f"classes={self._format_class_counts(standard_filtered)}"
            )
            if should_use_accuracy:
                auto_used_accuracy = True
                print("auto adds accuracy tiles:", "; ".join(auto_reasons))
                original_image_size = self.image_size
                original_tile_size = self.tile_size
                original_tile_overlap = self.tile_overlap
                tile_raw: List[DetectedObject] = []
                preset = DETECTION_PRESETS["auto"]
                self.image_size = int(preset.get("auto_accuracy_image_size", 960))
                self.tile_size = int(preset.get("auto_tile_size", 960))
                self.tile_overlap = float(preset.get("auto_tile_overlap", 0.25))
                h, w = img.shape[:2]
                windows = self._tile_windows(w, h)
                print(f"tile detections enabled: {len(windows)} tiles")
                for x1, y1, x2, y2 in windows:
                    tile_img = img[y1:y2, x1:x2]
                    tile_raw.extend(
                        self._run_yolo(
                            tile_img,
                            source="yolo_tile",
                            offset=(x1, y1),
                            full_shape=img.shape,
                            tile_bounds=(x1, y1, x2, y2),
                        )
                    )
                self.image_size = original_image_size
                self.tile_size = original_tile_size
                self.tile_overlap = original_tile_overlap
                tile_candidates, accepted, auto_rejected = self._auto_add_tile_candidates(
                    standard_filtered,
                    tile_raw,
                    img.shape,
                )
                tile_filter_log = list(self.last_filtered_out)
                auto_tile_candidate_count = len(tile_candidates)
                auto_added_count = len(accepted)
                detected = list(standard_filtered) + accepted
                self.last_filtered_out = standard_filter_log + tile_filter_log + auto_rejected
            else:
                print("auto keeps standard only")
                detected = standard_filtered
                self.last_filtered_out = standard_filter_log
            print(f"auto standard kept: {len(standard_filtered)}")
            print(f"auto accuracy candidates: {auto_tile_candidate_count}")
            print(f"auto added from accuracy: {auto_added_count}")
            if auto_rejected:
                print("auto rejected candidates:")
                for item, reason in auto_rejected:
                    print(
                        f"  - class={item.name} conf={item.confidence:.4f} "
                        f"source={item.source} box={item.box} reason={reason}"
                    )
            else:
                print("auto rejected candidates: none")

        elif self.tile_detection:
            h, w = img.shape[:2]
            windows = self._tile_windows(w, h)
            print(f"tile detections enabled: {len(windows)} tiles")
            for x1, y1, x2, y2 in windows:
                tile_img = img[y1:y2, x1:x2]
                detected.extend(
                    self._run_yolo(
                        tile_img,
                        source="yolo_tile",
                        offset=(x1, y1),
                        full_shape=img.shape,
                        tile_bounds=(x1, y1, x2, y2),
                    )
                )

        detected.sort(key=lambda item: item.confidence, reverse=True)
        self.last_raw_detection_count = raw_standard_count
        if self.detection_mode != "auto":
            self.last_raw_detection_count = len(detected)
            detected = self._filter_detections(detected, img.shape)
        elif auto_used_accuracy:
            self.last_raw_detection_count = raw_standard_count + len(tile_raw)
        self.last_filtered_detection_count = len(detected)
        self.last_final_detection_count = len(detected)
        self.last_processing_time = time.perf_counter() - started
        self.last_auto_used_accuracy = auto_used_accuracy
        self.last_objects = detected
        self.last_mode_stats = {
            "mode": self.detection_mode,
            "raw": self.last_raw_detection_count,
            "filtered": self.last_filtered_detection_count,
            "final": self.last_final_detection_count,
            "class_counts": self._format_class_counts(detected),
            "processing_time": self.last_processing_time,
            "auto_used_accuracy": auto_used_accuracy,
            "auto_reasons": auto_reasons,
            "auto_standard_kept": len([item for item in detected if item.source == "yolo"]) if self.detection_mode == "auto" else None,
            "auto_accuracy_candidates": auto_tile_candidate_count,
            "auto_added": auto_added_count,
            "auto_rejected": len(auto_rejected),
        }

        print(
            f"{self.detection_mode} summary: "
            f"raw={self.last_raw_detection_count} "
            f"filtered={self.last_filtered_detection_count} "
            f"final={self.last_final_detection_count} "
            f"time={self.last_processing_time:.3f}s"
        )
        print("kept classes:", self._format_class_counts(detected))
        if self.last_filtered_out:
            print("filtered out:")
            for item, reason in self.last_filtered_out:
                print(
                    f"  - class={item.name} conf={item.confidence:.4f} "
                    f"threshold={self._class_threshold(item.name, item.source):.4f} "
                    f"source={item.source} box={item.box} reason={reason}"
                )
        else:
            print("filtered out: none")
        print("\n===== Detected object coordinates (original image basis) =====")

        # Coordinates below are reported in the original image coordinate system.

        for index, item in enumerate(detected, start=1):
            x1, y1, x2, y2 = item.box

            top_left = (x1, y1)
            top_right = (x2, y1)
            bottom_right = (x2, y2)
            bottom_left = (x1, y2)

            print(
                f"\n[{index}] class={item.name} "
                f"canonical={item.canonical_name} "
                f"confidence={item.confidence:.4f} source={item.source}"
            )
            print(f"  left-top     = {top_left}")
            print(f"  right-top    = {top_right}")
            print(f"  right-bottom = {bottom_right}")
            print(f"  left-bottom  = {bottom_left}")
            print(f"  center       = {item.center}")

        return detected
    
