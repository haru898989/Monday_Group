"""
Magic Photo Museum - YOLO-World Detector
========================================
YOLO-Worldによる物体検出、クリック判定、日本語パス対応画像読み込み。
"""

from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Optional, Sequence
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
    merged_from_names: Optional[List[str]] = None
    coarse_name: Optional[str] = None
    coarse_confidence: Optional[float] = None
    detail_confidence: Optional[float] = None
    detail_reclassified: bool = False

    def __post_init__(self) -> None:
        if self.original_name is None:
            self.original_name = self.name
        if self.canonical_name is None:
            self.canonical_name = canonical_name_for(self.name)
        if self.sources is None:
            self.sources = [self.source]
        if self.merged_from_names is None:
            self.merged_from_names = [str(self.original_name or self.name)]
        if self.coarse_name is None:
            self.coarse_name = self.name
        if self.coarse_confidence is None:
            self.coarse_confidence = float(self.confidence)

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
        data["category"] = category_name_for(self.name)
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
    "sun": 0.28,
    "moon": 0.30,
    "ferris wheel": 0.18,
    "observation wheel": 0.18,
    "christmas tree": 0.18,
    "decorated christmas tree": 0.18,
    "barbecue grill": 0.20,
    "barbecue meat": 0.18,
    "grilled meat": 0.18,
    "steak": 0.18,
    "watermelon": 0.10,
    "cake": 0.16,
}

# Stage 1 uses broad categories plus a small set of representative labels.
# Abstract YOLO-World prompts such as "animal" alone can miss even a large
# bear, so representative names protect recall without restoring the old
# unbounded all-synonym full-image pass.
COARSE_CATEGORY_NAMES = [
    "person",
    "animal",
    "vehicle",
    "food",
    "furniture",
    "electronics",
    "instrument",
    "building",
    "plant",
]

COARSE_DETECTION_CLASSES = [
    "person",
    "animal", "dog", "cat", "horse", "bear", "bird",
    "vehicle", "car", "bus", "bicycle", "train", "boat",
    "food", "cake", "ice cream", "meat", "grilled meat", "watermelon",
    "furniture", "chair", "table", "barbecue grill",
    "electronics", "phone", "monitor",
    "instrument", "piano", "guitar",
    "building", "ferris wheel",
    "plant", "tree", "christmas tree", "flower",
]

DETAIL_CLASSES_BY_CATEGORY = {
    "person": ["person", "human hand", "hand", "arm", "reflection of person"],
    "animal": [
        "animal", "dog", "cat", "horse", "bear", "bird", "fish", "cow",
        "sheep", "elephant", "giraffe", "zebra",
    ],
    "vehicle": [
        "vehicle", "car", "truck", "van", "bus", "motorcycle", "bicycle",
        "train", "airplane", "boat", "ship",
    ],
    "food": [
        "ice cream", "ice cream cone", "soft serve", "soft serve ice cream",
        "gelato", "cake", "dessert", "food", "dish", "meal", "bread",
        "fruit", "vegetable", "meat", "barbecue meat", "grilled meat",
        "steak", "beef", "watermelon", "drink",
    ],
    "furniture": [
        "furniture", "chair", "bench", "stool", "sofa", "table", "desk",
        "bed", "cabinet",
    ],
    "electronics": [
        "electronics", "monitor", "television", "display", "screen", "laptop",
        "computer", "smartphone", "phone", "tablet",
    ],
    "instrument": [
        "instrument", "piano", "keyboard", "guitar", "violin", "drum",
        "flute", "trumpet", "saxophone",
    ],
    "building": [
        "building", "house", "apartment building", "office building",
        "warehouse", "school", "store", "station", "stadium",
    ],
    "plant": [
        "plant", "tree", "grass", "flower", "bush", "shrub", "vegetation",
        "forest",
    ],
}

DETAIL_CLASS_NAMES = list(dict.fromkeys(
    name
    for names in DETAIL_CLASSES_BY_CATEGORY.values()
    for name in names
))

DETAIL_CONFIDENCE_THRESHOLDS = {
    "animal": 0.22,
    "vehicle": 0.20,
    "food": 0.22,
    "furniture": 0.22,
    "electronics": 0.22,
    "instrument": 0.20,
    "building": 0.22,
    "plant": 0.24,
    "person": 0.20,
}

# Area ratios are intentionally category-aware.  A candidate below these
# values is rejected only when its confidence is also weak; genuinely small
# people, instruments, the sun, and the moon therefore remain eligible.
CATEGORY_MIN_AREA_RATIOS = {
    "person": 0.000020,
    "animal": 0.000035,
    "vehicle": 0.000040,
    "food": 0.000020,
    "instrument": 0.000015,
    "sun": 0.000008,
    "moon": 0.000008,
    "sky": 0.000800,
    "water": 0.000800,
    "ground": 0.000800,
    "plant": 0.000080,
    "building": 0.000100,
    "other": 0.000060,
}

# Minimum dimensions for a practical Unity touch target.  A strong model
# score can rescue a mildly small box, but not a box whose dimensions are
# physically unusable.  Animal/food are deliberately more permissive than
# distant people, vehicles and instruments.
TOUCH_TARGET_THRESHOLDS = {
    "person": (0.00030, 0.012, 0.024, 0.52),
    "vehicle": (0.00028, 0.016, 0.012, 0.50),
    "instrument": (0.00022, 0.014, 0.016, 0.48),
    "animal": (0.00007, 0.007, 0.010, 0.36),
    "food": (0.00006, 0.007, 0.008, 0.36),
    "plant": (0.00012, 0.010, 0.012, 0.42),
    "building": (0.00045, 0.025, 0.025, 0.42),
    "electronics": (0.00008, 0.008, 0.008, 0.40),
    "furniture": (0.00014, 0.010, 0.010, 0.42),
    "other": (0.00014, 0.010, 0.010, 0.45),
}

TOUCH_SIZE_EXEMPT_CATEGORIES = {
    "sun", "moon", "sky", "water", "ground", "plant",
}
# These categories need the actual mask area, so their touch-size decision is
# deferred until after provisional mask generation in analyze_objects_for_unity.
TOUCH_SIZE_DEFERRED_CATEGORIES = {
    "person", "animal", "instrument", "food", "vehicle",
}

TILE_THRESHOLD_EXEMPT_CLASSES = {
    "person", "animal", "instrument", "car", "truck", "van", "bus", "vehicle",
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
    "person": 0.65,
    "human": 0.65,
    "man": 0.65,
    "woman": 0.65,
    "child": 0.40,
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
    "ice cream": 0.20,
    "ice cream cone": 0.20,
    "soft serve": 0.20,
    "soft serve ice cream": 0.20,
    "cone": 0.14,
    "hand": 0.20,
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
    "boy": "person",
    "girl": "person",
    "adult": "person",
    "people": "person",
    "building": "building",
    "apartment": "building",
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
    "waterfall": "water",
    "water surface": "water",
    "stream": "water",
    "canal": "water",
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
    "tree": "plant",
    "grass": "plant",
    "plant": "plant",
    "flower": "plant",
    "bush": "plant",
    "shrub": "plant",
    "vegetation": "plant",
    "forest": "plant",
    "leaf": "plant",
    "leaves": "plant",
    "potted plant": "plant",
    "pottedplant": "plant",
    "store": "building",
    "shop": "building",
    "school": "building",
    "station": "building",
    "stadium": "building",
    "train": "vehicle",
    "airplane": "vehicle",
    "aeroplane": "vehicle",
    "boat": "vehicle",
    "ship": "vehicle",
    "animal": "animal",
    "wildlife": "animal",
    "large animal": "animal",
    "bear": "animal",
    "fish": "animal",
    "cow": "animal",
    "sheep": "animal",
    "elephant": "animal",
    "giraffe": "animal",
    "zebra": "animal",
    "food": "food",
    "dish": "food",
    "meal": "food",
    "bread": "food",
    "cake": "food",
    "dessert": "food",
    "ice cream": "food",
    "ice cream cone": "food",
    "soft serve": "food",
    "soft serve ice cream": "food",
    "gelato": "food",
    "fruit": "food",
    "vegetable": "food",
    "meat": "food",
    "barbecue meat": "food",
    "grilled meat": "food",
    "steak": "food",
    "beef": "food",
    "watermelon": "food",
    "drink": "food",
    "chair": "furniture",
    "bench": "furniture",
    "stool": "furniture",
    "sofa": "furniture",
    "table": "furniture",
    "desk": "furniture",
    "bed": "furniture",
    "cabinet": "furniture",
    "monitor": "electronics",
    "television": "electronics",
    "display": "electronics",
    "screen": "electronics",
    "laptop": "electronics",
    "computer": "electronics",
    "smartphone": "electronics",
    "phone": "electronics",
    "cell phone": "electronics",
    "tablet": "electronics",
    "piano": "instrument",
    "keyboard": "instrument",
    "guitar": "instrument",
    "violin": "instrument",
    "drum": "instrument",
    "flute": "instrument",
    "trumpet": "instrument",
    "saxophone": "instrument",
    "instrument": "instrument",
    "musical instrument": "instrument",
    "sky": "sky",
    "cloud": "sky",
    "sunset": "sky",
    "sunrise": "sky",
    "night sky": "sky",
    "sun": "sun",
    "moon": "moon",
    "ferris wheel": "building",
    "observation wheel": "building",
    "christmas tree": "plant",
    "decorated christmas tree": "plant",
    "human hand": "hand",
    "hand": "hand",
    "arm": "hand",
    "reflection of person": "reflection",
    "barbecue grill": "barbecue grill",
}


def canonical_name_for(name: str) -> str:
    return CANONICAL_NAMES.get(name, name)


CATEGORY_BY_CANONICAL_NAME = {
    "vehicle": "vehicle",
    "person": "person",
    "building": "building",
    "water": "water",
    "plant": "plant",
    "animal": "animal",
    "dog": "animal",
    "cat": "animal",
    "bird": "animal",
    "cow": "animal",
    "horse": "animal",
    "sheep": "animal",
    "rabbit": "animal",
    "piano": "instrument",
    "keyboard": "instrument",
    "guitar": "instrument",
    "violin": "instrument",
    "drum": "instrument",
    "trumpet": "instrument",
    "saxophone": "instrument",
    "food": "food",
    "furniture": "furniture",
    "electronics": "electronics",
    "instrument": "instrument",
    "sky": "sky",
    "ground": "ground",
    "sun": "sun",
    "moon": "moon",
    "hand": "other",
    "reflection": "other",
    "barbecue grill": "other",
}


def category_name_for(name: str) -> str:
    """Return a stable Unity category while preserving the detected name."""
    normalized = str(name).strip().lower()
    canonical = canonical_name_for(normalized)
    return CATEGORY_BY_CANONICAL_NAME.get(canonical, "other")


SYNONYM_GROUPS = [
    ["person", "human", "man", "woman", "boy", "girl", "child", "adult", "people"],
    ["vehicle", "car", "truck", "van", "bus"],
    ["monitor", "television", "tv", "display", "screen"],
    ["phone", "cell phone", "smartphone"],
    ["building", "apartment building", "office building", "warehouse", "house"],
    ["water", "sea", "ocean", "river", "lake", "pond", "pool", "waterfall"],
    ["animal", "wildlife", "large animal", "dog", "cat", "bird", "fish", "horse", "rabbit", "cow", "sheep", "bear", "elephant", "giraffe", "zebra"],
    ["instrument", "musical instrument", "piano", "keyboard", "guitar", "violin", "drum", "flute", "trumpet", "saxophone"],
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
            "ferris wheel", "observation wheel",
            "christmas tree", "decorated christmas tree",
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
        # These branches were evaluation experiments, not production policy.
        # The formal entrypoint also sets them to False explicitly so a future
        # caller cannot accidentally reconnect them by changing defaults here.
        self.enable_focused_food_pass = False
        self.enable_dominant_food_background_suppression = False

        print(
            "YOLO-World mode: "
            f"{self.detection_mode} | model: {self.model_path} | "
            f"base_conf={self.confidence:.2f} | imgsz={self.image_size} | "
            f"tile_detection={self.tile_detection}"
        )
        self.model = YOLO(self.model_path)

        self.custom_classes = list(COARSE_DETECTION_CLASSES)
        self.coarse_classes = list(COARSE_DETECTION_CLASSES)
        self.detail_classes_by_category = {
            category: list(names)
            for category, names in DETAIL_CLASSES_BY_CATEGORY.items()
        }
        self._active_classes = list(self.coarse_classes)
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
        names = list(target.merged_from_names or [target.original_name or target.name])
        for name in source_item.merged_from_names or [source_item.original_name or source_item.name]:
            normalized = str(name).strip().lower()
            if normalized and normalized not in names:
                names.append(normalized)
        target.merged_from_names = names

    @staticmethod
    def _specificity(name: str) -> int:
        normalized = str(name).strip().lower()
        category = category_name_for(normalized)
        if normalized == category or normalized in COARSE_CATEGORY_NAMES:
            return 0
        return CLASS_SPECIFICITY.get(normalized, 2)

    def _is_same_synonym_group(self, a: DetectedObject, b: DetectedObject) -> bool:
        group = self.synonym_lookup.get(a.name)
        return group is not None and group == self.synonym_lookup.get(b.name)

    def _is_duplicate_candidate(self, a: DetectedObject, b: DetectedObject) -> bool:
        if canonical_name_for(a.name) != canonical_name_for(b.name):
            return False
        iou = self._iou(a.box, b.box)
        canonical = canonical_name_for(a.name)
        if canonical == "person":
            if iou >= 0.74:
                return True
            containment = self._intersection_over_smaller(a.box, b.box)
            center_distance = self._normalized_center_distance(a, b)
            size_similarity = self._size_similarity(a, b)
            return (
                containment >= 0.92
                and center_distance <= 0.14
                and size_similarity >= 0.62
            )
        if canonical == "vehicle":
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
        containment = self._intersection_over_smaller(a.box, b.box)
        center_distance = self._normalized_center_distance(a, b)
        area_a = self._box_area(a)
        area_b = self._box_area(b)
        if containment >= 0.90 and center_distance <= 0.22:
            larger, smaller = (a, b) if area_a >= area_b else (b, a)
            if larger.confidence >= smaller.confidence - 0.18:
                return larger

        specificity_a = self._specificity(a.name)
        specificity_b = self._specificity(b.name)

        if specificity_a != specificity_b:
            if specificity_a > specificity_b and a.confidence >= b.confidence - 0.18:
                return a
            if specificity_b > specificity_a and b.confidence >= a.confidence - 0.18:
                return b

        return a if a.confidence >= b.confidence else b

    def _remove_contained_parts(
        self,
        detections: List[DetectedObject],
    ) -> Tuple[List[DetectedObject], List[Tuple[DetectedObject, str]]]:
        """Remove same-category fragments contained in a fuller candidate."""
        kept: List[DetectedObject] = []
        removed: List[Tuple[DetectedObject, str]] = []
        for candidate in sorted(
            detections,
            key=lambda item: (self._box_area(item), item.confidence),
            reverse=True,
        ):
            candidate_area = max(1, self._box_area(candidate))
            matched_full: Optional[DetectedObject] = None
            matched_containment = 0.0
            for full in kept:
                if canonical_name_for(candidate.name) != canonical_name_for(full.name):
                    continue
                full_area = max(1, self._box_area(full))
                if candidate_area / full_area > 0.62:
                    continue
                containment = self._intersection_over_smaller(
                    candidate.box,
                    full.box,
                )
                center_distance = self._normalized_center_distance(candidate, full)
                category = category_name_for(candidate.name)
                center_limit = 0.32 if category in {"person", "animal", "food"} else 0.24
                if (
                    containment >= 0.90
                    and center_distance <= center_limit
                    and full.confidence >= candidate.confidence - 0.18
                ):
                    matched_full = full
                    matched_containment = containment
                    break
            if matched_full is None:
                kept.append(candidate)
                continue
            self._add_sources(matched_full, candidate)
            removed.append((
                candidate,
                "contained_part: "
                f"contained_by={matched_full.name} "
                f"intersection_over_smaller={matched_containment:.4f}",
            ))
        return kept, removed

    def _quality_filter_reason(
        self,
        item: DetectedObject,
        image_area: int,
        image_shape: Optional[Tuple[int, int, int]] = None,
    ) -> Optional[str]:
        area_ratio = self._box_area(item) / max(1, image_area)

        threshold = self._class_threshold(item.name, item.source)
        if item.confidence + 1e-6 < threshold:
            return f"low_confidence: {item.confidence:.4f} < class_threshold {threshold:.4f}"

        category = category_name_for(item.name)
        if (
            image_shape is not None
            and category not in TOUCH_SIZE_EXEMPT_CATEGORIES
            and category not in TOUCH_SIZE_DEFERRED_CATEGORIES
        ):
            height, width = image_shape[:2]
            x1, y1, x2, y2 = item.box
            width_ratio = max(0, x2 - x1) / max(1, width)
            height_ratio = max(0, y2 - y1) / max(1, height)
            min_area, min_width, min_height, rescue_confidence = (
                TOUCH_TARGET_THRESHOLDS.get(
                    category,
                    TOUCH_TARGET_THRESHOLDS["other"],
                )
            )
            hard_too_small = (
                area_ratio < min_area * 0.40
                or width_ratio < min_width * 0.55
                or height_ratio < min_height * 0.55
            )
            soft_too_small = (
                area_ratio < min_area
                or width_ratio < min_width
                or height_ratio < min_height
            )
            if hard_too_small or (
                soft_too_small and item.confidence < rescue_confidence
            ):
                return (
                    "too_small: "
                    f"category={category} area_ratio={area_ratio:.6f} "
                    f"width_ratio={width_ratio:.5f} height_ratio={height_ratio:.5f} "
                    f"confidence={item.confidence:.4f}"
                )
        if (
            category == "furniture"
            and area_ratio > 0.12
            and item.confidence < 0.38
        ):
            return (
                "low_confidence: oversized furniture candidate "
                f"area_ratio={area_ratio:.4f}"
            )
        minimum_area_ratio = CATEGORY_MIN_AREA_RATIOS.get(
            category,
            self.min_box_area_ratio,
        )
        weak_small_confidence = max(threshold + 0.10, self.min_small_box_confidence)
        if (
            category not in TOUCH_SIZE_EXEMPT_CATEGORIES
            and category not in TOUCH_SIZE_DEFERRED_CATEGORIES
            and area_ratio < minimum_area_ratio
            and item.confidence < weak_small_confidence
        ):
            return (
                f"too_small: low-confidence tiny {category} area_ratio={area_ratio:.6f} "
                f"< minimum_area_ratio={minimum_area_ratio:.6f}"
            )

        max_area_ratio = CLASS_MAX_AREA_RATIOS.get(item.name)
        if max_area_ratio is not None and area_ratio > max_area_ratio:
            return (
                f"low_confidence: class max area exceeded area_ratio={area_ratio:.4f} "
                f"> max_area_ratio={max_area_ratio:.4f}"
            )

        if (
            item.name not in self.large_region_allowed_classes
            and area_ratio >= self.max_full_image_low_conf_area_ratio
            and item.confidence < self.full_image_low_conf_threshold
        ):
            return f"low_confidence: near-full-image box area_ratio={area_ratio:.3f}"

        if (
            item.name in self.low_conf_large_classes
            and area_ratio >= self.max_low_conf_area_ratio
            and item.confidence < self.low_conf_large_threshold
        ):
            return f"low_confidence: large box area_ratio={area_ratio:.3f}"

        if (
            item.name not in self.small_object_exempt_classes
            and category not in TOUCH_SIZE_EXEMPT_CATEGORIES
            and category not in TOUCH_SIZE_DEFERRED_CATEGORIES
            and area_ratio <= self.min_box_area_ratio
            and item.confidence < self.min_small_box_confidence
        ):
            return f"too_small: low-confidence tiny box area_ratio={area_ratio:.6f}"

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
            reason = None
            if item.source == "yolo_tile" and self._is_tile_edge_cut(
                item,
                image_shape,
                tolerance=4,
            ):
                reason = "tile_boundary: candidate is cut by an internal tile edge"
            if reason is None:
                reason = self._quality_filter_reason(item, image_area, image_shape)
            if reason is None:
                quality_filtered.append(item)
            else:
                self.last_filtered_out.append((item, reason))

        quality_filtered, contained_removed = self._remove_contained_parts(
            quality_filtered
        )
        self.last_filtered_out.extend(contained_removed)

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
                    self.last_filtered_out.append((
                        current,
                        f"duplicate_same_object: merged into {candidate.name}",
                    ))
                else:
                    self._add_sources(current, candidate)
                    discard = True
                    self.last_filtered_out.append((
                        candidate,
                        f"duplicate_same_object: merged into {current.name}",
                    ))
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
                self.last_filtered_out.append((
                    current,
                    f"duplicate_same_object: background singleton kept {item.name}",
                ))
                best_by_class[item.name] = item
            else:
                self._add_sources(current, item)
                self.last_filtered_out.append((
                    item,
                    f"duplicate_same_object: background singleton kept {current.name}",
                ))

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

    @staticmethod
    def _exclusion_reason_code(reason: str) -> str:
        known = {
            "too_small",
            "low_confidence",
            "contained_part",
            "duplicate_same_object",
            "tile_boundary",
            "crowd_limit",
            "background_noninteractive",
            "misclassified_part",
        }
        prefix = str(reason).split(":", 1)[0].strip()
        if prefix in known:
            return prefix
        if "duplicate" in reason or "already represented" in reason:
            return "duplicate_same_object"
        if "tile" in reason:
            return "tile_boundary"
        if "confidence" in reason:
            return "low_confidence"
        return "other_filter"

    def _build_exclusion_debug(
        self,
        image_shape: Tuple[int, int, int],
    ) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
        height, width = image_shape[:2]
        image_area = max(1, height * width)
        events: List[Dict[str, object]] = []
        counts: Dict[str, int] = {}
        seen = set()
        for item, reason in self.last_filtered_out:
            code = self._exclusion_reason_code(reason)
            key = (item.name, item.box, item.source, code)
            if key in seen:
                continue
            seen.add(key)
            x1, y1, x2, y2 = item.box
            event = {
                "reason_code": code,
                "reason": str(reason),
                "name": str(item.name),
                "category": category_name_for(item.name),
                "confidence": float(item.confidence),
                "source": str(item.source),
                "box": [int(x1), int(y1), int(x2), int(y2)],
                "bbox_area_ratio": float(self._box_area(item) / image_area),
                "bbox_width_ratio": float(max(0, x2 - x1) / max(1, width)),
                "bbox_height_ratio": float(max(0, y2 - y1) / max(1, height)),
            }
            events.append(event)
            counts[code] = counts.get(code, 0) + 1
        return events, counts

    def _set_model_classes(self, class_names: List[str]) -> None:
        """Change YOLO-World prompts only when the requested set changed."""
        normalized = list(dict.fromkeys(str(name).strip().lower() for name in class_names))
        if normalized == self._active_classes:
            return
        self.model.set_classes(normalized)
        self._active_classes = normalized

    def _suppress_tiny_crowd_candidates(
        self,
        detections: List[DetectedObject],
        image_shape: Tuple[int, int, int],
    ) -> Tuple[List[DetectedObject], List[Tuple[DetectedObject, str]]]:
        """Cap only weak, tiny crowd boxes while retaining meaningful instances."""
        image_area = max(1, image_shape[0] * image_shape[1])
        people = [item for item in detections if category_name_for(item.name) == "person"]
        if len(people) <= 14:
            return detections, []

        ranked = list(people)
        ranked.sort(
            key=lambda item: (
                1 if self._box_area(item) / image_area >= 0.00020 else 0,
                1 if item.confidence >= 0.48 else 0,
                item.confidence * np.sqrt(max(1, self._box_area(item))),
                item.confidence,
            ),
            reverse=True,
        )
        selected_people = ranked[:14]
        selected_ids = {id(item) for item in selected_people}
        removed = [
            (item, "crowd_limit: weak tiny crowd candidate suppressed before mask generation")
            for item in people
            if id(item) not in selected_ids
        ]
        kept = [
            item for item in detections
            if category_name_for(item.name) != "person" or id(item) in selected_ids
        ]
        kept.sort(key=lambda item: item.confidence, reverse=True)
        return kept, removed

    def _apply_supporting_label_evidence(
        self,
        detections: List[DetectedObject],
    ) -> int:
        """Use rejected overlapping detail labels without restoring their boxes."""
        reclassified = 0
        rejected = [item for item, _ in self.last_filtered_out]
        preferred_food_names = {
            "ice cream", "ice cream cone", "soft serve",
            "soft serve ice cream", "gelato",
        }
        for item in detections:
            if category_name_for(item.name) != "food":
                continue
            supporting = []
            for other in rejected:
                if str(other.name).strip().lower() not in preferred_food_names:
                    continue
                iou = self._iou(item.box, other.box)
                containment = self._intersection_over_smaller(item.box, other.box)
                center_distance = self._normalized_center_distance(item, other)
                if (
                    other.confidence >= max(0.28, item.confidence - 0.08)
                    and (
                        iou >= 0.20
                        or containment >= 0.45
                        or center_distance <= 0.20
                    )
                ):
                    supporting.append(other)
            if not supporting:
                continue
            best = max(supporting, key=lambda candidate: candidate.confidence)
            previous_name = item.name
            item.name = best.name
            item.original_name = best.name
            item.canonical_name = canonical_name_for(best.name)
            item.detail_confidence = float(best.confidence)
            item.detail_reclassified = True
            item.confidence = float(np.sqrt(item.confidence * best.confidence))
            item.reaction = self.reaction_rules.get(best.name, item.reaction)
            item.merged_from_names = list(dict.fromkeys(
                list(item.merged_from_names or [previous_name]) + [best.name]
            ))
            reclassified += 1
        return reclassified

    def _detect_focused_food_candidates(
        self,
        image: np.ndarray,
    ) -> Tuple[List[DetectedObject], Dict[str, object]]:
        """Run one narrow food pass when the coarse pass found no food."""
        started = time.perf_counter()
        prompts = ["watermelon", "ice cream", "cake"]
        accepted: List[DetectedObject] = []
        try:
            self._set_model_classes(prompts)
            results = self.model(
                image,
                conf=0.05,
                imgsz=max(800, min(960, int(self.image_size))),
                verbose=False,
            )
            if results and results[0].boxes is not None:
                thresholds = {
                    "watermelon": 0.10,
                    "ice cream": 0.16,
                    "cake": 0.16,
                    "pizza": 0.14,
                }
                height, width = image.shape[:2]
                for box in results[0].boxes:
                    class_id = int(box.cls[0])
                    name = str(self.model.names[class_id]).strip().lower()
                    confidence = float(box.conf[0])
                    if confidence < thresholds.get(name, 0.16):
                        continue
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    x1 = max(0, min(width - 1, x1))
                    y1 = max(0, min(height - 1, y1))
                    x2 = max(x1 + 1, min(width, x2))
                    y2 = max(y1 + 1, min(height, y2))
                    accepted.append(DetectedObject(
                        name=name,
                        reaction=self.reaction_rules.get(name, "eat_food"),
                        confidence=confidence,
                        box=(x1, y1, x2, y2),
                        center=((x1 + x2) // 2, (y1 + y2) // 2),
                        source="yolo_food_focus",
                        original_name=name,
                        canonical_name=canonical_name_for(name),
                    ))
        except Exception as exc:
            return [], {
                "used": True,
                "candidate_count": 0,
                "error": type(exc).__name__,
                "processing_time": float(time.perf_counter() - started),
            }
        finally:
            self._set_model_classes(self.coarse_classes)
        return accepted, {
            "used": True,
            "candidate_count": len(accepted),
            "processing_time": float(time.perf_counter() - started),
            "prompts": prompts,
        }

    def _reclassify_barbecue_context(
        self,
        image: np.ndarray,
        detections: List[DetectedObject],
    ) -> int:
        """Recognize a meat-covered tabletop grill without keeping furniture."""
        changed = 0
        for item in detections:
            if str(item.name).strip().lower() not in {"table", "desk"}:
                continue
            x1, y1, x2, y2 = item.box
            if y1 < int(image.shape[0] * 0.52):
                continue
            roi_bottom = y1 + max(1, int(round((y2 - y1) * 0.50)))
            roi = image[y1:roi_bottom, x1:x2]
            if roi.size == 0:
                continue
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            hue, saturation, value = cv2.split(hsv)
            reddish = (
                ((hue <= 28) | (hue >= 165))
                & (saturation >= 55)
                & (value >= 35)
                & (value <= 245)
            ).astype(np.uint8)
            reddish = cv2.morphologyEx(
                reddish,
                cv2.MORPH_OPEN,
                np.ones((3, 3), dtype=np.uint8),
            )
            count, _, stats, _ = cv2.connectedComponentsWithStats(reddish, 8)
            roi_area = max(1, reddish.size)
            piece_count = sum(
                1
                for component_id in range(1, count)
                if roi_area * 0.0002
                <= int(stats[component_id, cv2.CC_STAT_AREA])
                <= roi_area * 0.04
            )
            red_ratio = float(np.count_nonzero(reddish)) / roi_area
            if piece_count < 25 or not 0.10 <= red_ratio <= 0.65:
                continue
            previous_name = str(item.name)
            item.name = "barbecue meat"
            item.original_name = "barbecue meat"
            item.canonical_name = canonical_name_for(item.name)
            item.detail_reclassified = True
            item.detail_confidence = max(0.32, float(item.confidence))
            item.confidence = max(0.32, float(item.confidence))
            item.reaction = self.reaction_rules.get(item.name, "eat_food")
            item.merged_from_names = list(dict.fromkeys(
                list(item.merged_from_names or [previous_name]) + [item.name]
            ))
            supporting_food = [
                other
                for other in detections
                if other is not item
                and category_name_for(other.name) == "food"
                and (
                    self._intersection_over_smaller(item.box, other.box) >= 0.70
                    or self._iou(item.box, other.box) >= 0.20
                )
                and self._normalized_center_distance(item, other) <= 0.35
            ]
            if supporting_food:
                best = max(supporting_food, key=lambda other: other.confidence)
                item.box = best.box
                item.center = best.center
                item.confidence = max(item.confidence, best.confidence, 0.32)
                best.name = "barbecue meat"
                best.original_name = "barbecue meat"
                best.canonical_name = canonical_name_for(best.name)
                best.detail_reclassified = True
                best.detail_confidence = max(0.31, float(best.confidence))
                best.confidence = max(0.31, float(best.confidence))
                best.reaction = self.reaction_rules.get(best.name, "eat_food")
            changed += 1
        return changed

    def _suppress_secondary_background_candidates(
        self,
        detections: List[DetectedObject],
        image_shape: Tuple[int, int, int],
    ) -> Tuple[List[DetectedObject], List[Tuple[DetectedObject, str]]]:
        """Drop visually secondary objects behind a dominant close-up food item."""
        height, width = image_shape[:2]
        image_area = max(1, height * width)
        food_candidates = [
            item
            for item in detections
            if category_name_for(item.name) == "food"
            and self._box_area(item) / image_area >= 0.06
            and (item.box[2] - item.box[0]) / max(1, width) >= 0.25
            and item.center[1] >= int(height * 0.40)
        ]
        dominant_food = max(
            food_candidates,
            key=lambda item: self._box_area(item) * item.confidence,
            default=None,
        )
        kept: List[DetectedObject] = []
        removed: List[Tuple[DetectedObject, str]] = []
        hand_candidates = [
            item
            for item in detections
            if canonical_name_for(item.name) == "hand"
        ]
        for item in detections:
            normalized = str(item.name).strip().lower()
            if normalized == "reflection of person":
                removed.append((
                    item,
                    "background_noninteractive: reflected person is not a touch target",
                ))
                continue
            if category_name_for(item.name) == "person" and any(
                self._intersection_over_smaller(item.box, hand.box) >= 0.55
                and self._normalized_center_distance(item, hand) <= 0.30
                for hand in hand_candidates
            ):
                removed.append((
                    item,
                    "misclassified_part: person box is explained by a hand candidate",
                ))
                continue
            is_secondary = False
            if dominant_food is not None and item is not dominant_food:
                category = category_name_for(item.name)
                is_secondary = (
                    category in {"person", "electronics", "furniture"}
                    and item.box[3] <= dominant_food.box[1] + int(height * 0.02)
                    and item.center[1] < dominant_food.center[1]
                    and self._box_area(item) <= self._box_area(dominant_food) * 1.10
                    and item.confidence < 0.90
                )
            if is_secondary:
                removed.append((
                    item,
                    "background_noninteractive: behind dominant foreground food",
                ))
            else:
                kept.append(item)
        return kept, removed

    def reclassify_crops(
        self,
        image: np.ndarray,
        detections: List[DetectedObject],
        max_candidates: int = 18,
    ) -> Tuple[List[DetectedObject], Dict[str, object]]:
        """Reclassify selected coarse boxes with narrow per-category prompts.

        Crops in the same category are inferred as one batch.  No new box is
        created here: stage 2 only assigns a more specific name to a stage-1
        instance, which prevents crop detections from multiplying objects.
        """
        started = time.perf_counter()
        if image is None or image.size == 0 or not detections:
            return detections, {
                "candidate_count": 0,
                "reclassified_count": 0,
                "processing_time": 0.0,
                "category_batches": 0,
            }

        height, width = image.shape[:2]
        image_area = max(1, height * width)
        eligible = [
            item for item in detections
            if category_name_for(item.name) in self.detail_classes_by_category
            and item.source != "clip_landmark"
            and (
                item.name in COARSE_CATEGORY_NAMES
                or float(item.confidence) < 0.34
                or category_name_for(item.name) == "food"
                or (
                    category_name_for(item.name) == "person"
                    and self._box_area(item) / image_area >= 0.01
                )
            )
        ]
        eligible.sort(
            key=lambda item: (
                1 if item.name in COARSE_CATEGORY_NAMES else 0,
                1 if category_name_for(item.name) in {"animal", "food", "instrument", "electronics"} else 0,
                -abs(float(item.confidence) - 0.35),
                min(0.20, self._box_area(item) / image_area),
            ),
            reverse=True,
        )
        selected = eligible[:max(0, int(max_candidates))]
        grouped: Dict[str, List[Tuple[DetectedObject, np.ndarray]]] = {}
        crop_cache: Dict[Tuple[str, Tuple[int, int, int, int]], np.ndarray] = {}
        for item in selected:
            category = category_name_for(item.name)
            x1, y1, x2, y2 = item.box
            pad_x = max(2, int(round((x2 - x1) * 0.08)))
            pad_y = max(2, int(round((y2 - y1) * 0.08)))
            crop_box = (
                max(0, x1 - pad_x),
                max(0, y1 - pad_y),
                min(width, x2 + pad_x),
                min(height, y2 + pad_y),
            )
            cache_key = (category, crop_box)
            crop = crop_cache.get(cache_key)
            if crop is None:
                cx1, cy1, cx2, cy2 = crop_box
                crop = image[cy1:cy2, cx1:cx2].copy()
                crop_cache[cache_key] = crop
            if crop.size:
                grouped.setdefault(category, []).append((item, crop))

        reclassified_count = 0
        category_batches = 0
        failures: List[str] = []
        try:
            for category, pairs in grouped.items():
                prompts = self.detail_classes_by_category[category]
                self._set_model_classes(prompts)
                category_batches += 1
                try:
                    results = self.model(
                        [crop for _, crop in pairs],
                        conf=0.05,
                        imgsz=min(480, max(320, self.image_size // 2)),
                        verbose=False,
                    )
                except Exception as exc:
                    failures.append(f"{category}: {type(exc).__name__}")
                    continue

                for (item, crop), result in zip(pairs, results):
                    if result.boxes is None or len(result.boxes) == 0:
                        continue
                    crop_h, crop_w = crop.shape[:2]
                    crop_area = max(1, crop_h * crop_w)
                    best_name: Optional[str] = None
                    best_confidence = 0.0
                    best_score = -1.0
                    for box in result.boxes:
                        class_id = int(box.cls[0])
                        name = str(self.model.names[class_id]).strip().lower()
                        person_part = (
                            category == "person"
                            and name in {
                                "human hand", "hand", "arm",
                                "reflection of person",
                            }
                        )
                        if category_name_for(name) != category and not person_part:
                            continue
                        confidence = float(box.conf[0])
                        bx1, by1, bx2, by2 = map(float, box.xyxy[0].tolist())
                        contains_center = (
                            bx1 <= crop_w * 0.5 <= bx2
                            and by1 <= crop_h * 0.5 <= by2
                        )
                        box_ratio = max(0.0, bx2 - bx1) * max(0.0, by2 - by1) / crop_area
                        score = confidence + (0.08 if contains_center else 0.0) + min(0.05, box_ratio * 0.05)
                        if name not in COARSE_CATEGORY_NAMES:
                            score += 0.035
                        if person_part:
                            score += 0.070
                        if score > best_score:
                            best_score = score
                            best_name = name
                            best_confidence = confidence

                    threshold = DETAIL_CONFIDENCE_THRESHOLDS.get(category, 0.22)
                    if (
                        best_name is None
                        or best_name in COARSE_CATEGORY_NAMES
                        or best_confidence < threshold
                    ):
                        continue
                    coarse_name = str(item.coarse_name or item.name)
                    item.name = best_name
                    item.original_name = best_name
                    item.canonical_name = canonical_name_for(best_name)
                    item.detail_confidence = float(best_confidence)
                    item.detail_reclassified = True
                    item.confidence = float(
                        np.sqrt(max(0.0, float(item.coarse_confidence or item.confidence)) * best_confidence)
                    )
                    item.reaction = self.reaction_rules.get(best_name, item.reaction)
                    item.merged_from_names = list(dict.fromkeys(
                        list(item.merged_from_names or [coarse_name]) + [best_name]
                    ))
                    reclassified_count += 1
        finally:
            self._set_model_classes(self.coarse_classes)

        elapsed = time.perf_counter() - started
        return detections, {
            "candidate_count": len(selected),
            "reclassified_count": reclassified_count,
            "processing_time": float(elapsed),
            "category_batches": category_batches,
            "failures": failures,
        }

    def detect_sun_moon_candidates(
        self,
        image: np.ndarray,
        sky_mask: np.ndarray,
    ) -> Tuple[List[DetectedObject], Dict[str, object]]:
        """Find sky light blobs and keep only CLIP-model sun/moon proposals."""
        started = time.perf_counter()
        if image is None or image.size == 0 or sky_mask is None:
            return [], {"candidate_count": 0, "processing_time": 0.0, "skipped": True}
        sky = (sky_mask > 0).astype(np.uint8)
        sky_ratio = float(np.count_nonzero(sky)) / max(1, sky.size)
        if sky_ratio < 0.003:
            return [], {
                "candidate_count": 0,
                "processing_time": time.perf_counter() - started,
                "skipped": True,
                "reason": "sky mask too small",
                "sky_ratio": sky_ratio,
            }

        height, width = image.shape[:2]
        image_area = max(1, height * width)
        radius = max(3, int(round(min(image.shape[:2]) * 0.02)))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
        expanded = cv2.dilate(sky * 255, kernel, iterations=1)

        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        bright = (
            (hsv[:, :, 2] >= 245)
            & (expanded > 0)
        ).astype(np.uint8)
        bright[int(height * 0.92):, :] = 0
        bright = cv2.morphologyEx(
            bright,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
        )
        count, labels, stats, _ = cv2.connectedComponentsWithStats(bright, 8)
        proposals: List[Tuple[int, int, int, int, float]] = []
        minimum_area = max(6, int(image_area * 0.000003))
        maximum_area = max(minimum_area + 1, int(image_area * 0.025))
        for label_id in range(1, count):
            area = int(stats[label_id, cv2.CC_STAT_AREA])
            if not minimum_area <= area <= maximum_area:
                continue
            x = int(stats[label_id, cv2.CC_STAT_LEFT])
            y = int(stats[label_id, cv2.CC_STAT_TOP])
            box_width = int(stats[label_id, cv2.CC_STAT_WIDTH])
            box_height = int(stats[label_id, cv2.CC_STAT_HEIGHT])
            aspect = box_width / max(1, box_height)
            fill = area / max(1, box_width * box_height)
            if not 0.28 <= aspect <= 3.6 or fill < 0.18:
                continue
            pad = max(4, int(round(max(box_width, box_height) * 0.55)))
            box = (
                max(0, x - pad),
                max(0, y - pad),
                min(width, x + box_width + pad),
                min(height, y + box_height + pad),
            )
            mean_value = float(np.mean(hsv[:, :, 2][labels == label_id]))
            proposals.append((*box, mean_value + fill * 35.0))

        proposals.sort(key=lambda item: item[4], reverse=True)
        unique: List[Tuple[int, int, int, int, float]] = []
        for proposal in proposals:
            if any(self._iou(proposal[:4], existing[:4]) >= 0.55 for existing in unique):
                continue
            unique.append(proposal)
            if len(unique) >= 4:
                break
        if not unique or Image is None:
            return [], {
                "candidate_count": 0,
                "visual_proposal_count": len(unique),
                "processing_time": float(time.perf_counter() - started),
                "skipped": True,
                "reason": "no sky light proposals",
                "sky_ratio": sky_ratio,
            }

        try:
            import clip
            import torch

            clip_path = Path(__file__).resolve().parent / "weights" / "clip" / "ViT-B-32.pt"
            if not clip_path.exists():
                raise FileNotFoundError(str(clip_path))
            if not hasattr(self, "_clip_sky_model"):
                self._clip_sky_model, self._clip_sky_preprocess = clip.load(
                    str(clip_path),
                    device="cpu",
                    jit=False,
                )
                self._clip_sky_model.eval()
            prompts = [
                "a photo of the sun in the sky",
                "a photo of the moon in the sky",
                "an indoor lamp or artificial light",
                "a bright reflection on water",
                "a clock face",
            ]
            crops = []
            for x1, y1, x2, y2, _ in unique:
                rgb = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
                crops.append(self._clip_sky_preprocess(Image.fromarray(rgb)))
            with torch.inference_mode():
                image_input = torch.stack(crops)
                text_input = clip.tokenize(prompts)
                logits, _ = self._clip_sky_model(image_input, text_input)
                probabilities = logits.softmax(dim=-1).cpu().numpy()
        except Exception as exc:
            return [], {
                "candidate_count": 0,
                "visual_proposal_count": len(unique),
                "processing_time": float(time.perf_counter() - started),
                "skipped": True,
                "reason": f"CLIP unavailable: {type(exc).__name__}",
                "sky_ratio": sky_ratio,
            }

        candidates: List[DetectedObject] = []
        model_details: List[Dict[str, object]] = []
        for proposal, scores in zip(unique, probabilities):
            best_index = int(np.argmax(scores))
            best_score = float(scores[best_index])
            distractor_score = float(np.max(scores[2:]))
            x1, y1, x2, y2, _ = proposal
            value_crop = hsv[y1:y2, x1:x2, 2]
            crop_h, crop_w = value_crop.shape[:2]
            core = value_crop[
                crop_h // 4:max(crop_h // 4 + 1, crop_h * 3 // 4),
                crop_w // 4:max(crop_w // 4 + 1, crop_w * 3 // 4),
            ]
            border_mask = np.ones(value_crop.shape, dtype=bool)
            border_mask[
                crop_h // 4:max(crop_h // 4 + 1, crop_h * 3 // 4),
                crop_w // 4:max(crop_w // 4 + 1, crop_w * 3 // 4),
            ] = False
            border_values = value_crop[border_mask]
            core_brightness = float(np.mean(core)) if core.size else 0.0
            border_brightness = float(np.mean(border_values)) if border_values.size else core_brightness
            proposal_contrast = core_brightness - border_brightness
            accepted = (
                best_index in {0, 1}
                and best_score >= 0.30
                and best_score >= distractor_score + 0.04
                and (proposal_contrast >= 4.0 or core_brightness >= 248.0)
            )
            name = "sun" if best_index == 0 else "moon"
            model_details.append({
                "name": name,
                "accepted": bool(accepted),
                "model_confidence": best_score,
                "distractor_confidence": distractor_score,
                "core_brightness": core_brightness,
                "proposal_contrast": float(proposal_contrast),
                "box": [x1, y1, x2, y2],
            })
            if not accepted:
                continue
            candidates.append(DetectedObject(
                name=name,
                reaction=self.reaction_rules.get(name, "day_night_change"),
                confidence=best_score,
                box=(x1, y1, x2, y2),
                center=((x1 + x2) // 2, (y1 + y2) // 2),
                source="clip_sky",
                original_name=name,
                canonical_name=name,
            ))
        raw_model_candidate_count = len(candidates)
        candidates.sort(key=lambda item: float(item.confidence), reverse=True)
        candidates = candidates[:1]
        return candidates, {
            "candidate_count": len(candidates),
            "model_accepted_before_singleton": raw_model_candidate_count,
            "visual_proposal_count": len(unique),
            "processing_time": float(time.perf_counter() - started),
            "skipped": False,
            "sky_ratio": sky_ratio,
            "model": "CLIP ViT-B/32 (local existing weight)",
            "details": model_details,
        }

    def _detect_night_landmark_candidates(
        self,
        image: np.ndarray,
        existing: Sequence[DetectedObject],
    ) -> Tuple[List[DetectedObject], Dict[str, object]]:
        """Run one narrow landmark pass only for sparse dark scenes."""
        started = time.perf_counter()
        height, width = image.shape[:2]
        image_area = max(1, height * width)
        mean_brightness = float(
            np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2HSV)[:, :, 2])
        )
        large_existing = sum(
            1
            for item in existing
            if self._box_area(item) / image_area >= 0.08
        )
        should_run = (
            mean_brightness <= 115.0
            and large_existing == 0
            and len(existing) <= 8
        )
        if not should_run:
            return [], {
                "used": False,
                "candidate_count": 0,
                "processing_time": float(time.perf_counter() - started),
                "mean_brightness": mean_brightness,
                "reason": "scene does not require landmark pass",
            }
        prompts = [
            "ferris wheel",
            "observation wheel",
            "christmas tree",
            "decorated christmas tree",
        ]
        try:
            self._set_model_classes(prompts)
            candidates = self._run_yolo(
                image,
                source="yolo_landmark",
                full_shape=image.shape,
            )
        finally:
            self._set_model_classes(self.coarse_classes)
        clip_details: List[Dict[str, object]] = []
        if not candidates and Image is not None:
            proposal_boxes = [
                (0, 0, width, height),
                (0, 0, width, int(height * 0.86)),
                (0, int(height * 0.12), int(width * 0.86), height),
                (0, 0, int(width * 0.86), int(height * 0.86)),
                (0, int(height * 0.34), int(width * 0.72), height),
                (
                    int(width * 0.12), int(height * 0.34),
                    int(width * 0.74), height,
                ),
            ]
            window_width = int(width * 0.68)
            window_height = int(height * 0.68)
            for y1 in (0, height - window_height):
                for x1 in (0, width - window_width):
                    proposal_boxes.append((
                        x1,
                        y1,
                        x1 + window_width,
                        y1 + window_height,
                    ))
            proposal_boxes = list(dict.fromkeys(proposal_boxes))
            clip_prompts = [
                "a large ferris wheel at an amusement park at night",
                "a decorated christmas tree with lights",
                "fireworks in the night sky",
                "an empty dark night sky",
                "people near shops and buildings",
                "a building at night",
            ]
            try:
                import clip
                import torch

                clip_path = (
                    Path(__file__).resolve().parent
                    / "weights" / "clip" / "ViT-B-32.pt"
                )
                if not clip_path.exists():
                    raise FileNotFoundError(str(clip_path))
                if not hasattr(self, "_clip_landmark_model"):
                    (
                        self._clip_landmark_model,
                        self._clip_landmark_preprocess,
                    ) = clip.load(str(clip_path), device="cpu", jit=False)
                    self._clip_landmark_model.eval()
                crop_tensors = []
                for x1, y1, x2, y2 in proposal_boxes:
                    rgb = cv2.cvtColor(
                        image[y1:y2, x1:x2],
                        cv2.COLOR_BGR2RGB,
                    )
                    crop_tensors.append(
                        self._clip_landmark_preprocess(Image.fromarray(rgb))
                    )
                with torch.inference_mode():
                    logits, _ = self._clip_landmark_model(
                        torch.stack(crop_tensors),
                        clip.tokenize(clip_prompts),
                    )
                    probabilities = logits.softmax(dim=-1).cpu().numpy()
                for class_index, name in (
                    (0, "ferris wheel"),
                    (1, "christmas tree"),
                ):
                    best_proposal_index = int(
                        np.argmax(probabilities[:, class_index])
                    )
                    scores = probabilities[best_proposal_index]
                    best_class = int(np.argmax(scores))
                    confidence = float(scores[class_index])
                    distractor = float(np.max(scores[2:]))
                    box = proposal_boxes[best_proposal_index]
                    accepted = bool(
                        best_class == class_index
                        and confidence >= 0.32
                        and confidence >= distractor + 0.05
                    )
                    clip_details.append({
                        "name": name,
                        "accepted": accepted,
                        "confidence": confidence,
                        "distractor_confidence": distractor,
                        "box": [int(value) for value in box],
                    })
                    if not accepted:
                        continue
                    x1, y1, x2, y2 = box
                    candidate_center = ((x1 + x2) // 2, (y1 + y2) // 2)
                    if name == "ferris wheel":
                        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                        scale = min(1.0, 700.0 / max(height, width))
                        if scale < 1.0:
                            gray = cv2.resize(
                                gray,
                                None,
                                fx=scale,
                                fy=scale,
                                interpolation=cv2.INTER_AREA,
                            )
                        gray = cv2.GaussianBlur(gray, (9, 9), 1.5)
                        circles = cv2.HoughCircles(
                            gray,
                            cv2.HOUGH_GRADIENT,
                            dp=1.2,
                            minDist=max(40, int(min(gray.shape) * 0.20)),
                            param1=100,
                            param2=35,
                            minRadius=max(20, int(min(gray.shape) * 0.22)),
                            maxRadius=max(24, int(min(gray.shape) * 0.52)),
                        )
                        if circles is not None and circles.size:
                            circle_x, circle_y, circle_radius = circles[0][0]
                            circle_x = float(circle_x) / scale
                            circle_y = float(circle_y) / scale
                            circle_radius = float(circle_radius) / scale * 1.04
                            x1 = max(0, int(round(circle_x - circle_radius)))
                            y1 = max(0, int(round(circle_y - circle_radius)))
                            x2 = min(width, int(round(circle_x + circle_radius)))
                            y2 = min(height, int(round(circle_y + circle_radius)))
                            candidate_center = (
                                int(round(circle_x)),
                                int(round(circle_y)),
                            )
                    elif name == "christmas tree":
                        horizontal_inset = int(round((x2 - x1) * 0.10))
                        x1 = max(0, x1 + horizontal_inset)
                        x2 = min(width, x2 - horizontal_inset)
                    box = (x1, y1, x2, y2)
                    candidates.append(DetectedObject(
                        name=name,
                        reaction=self.reaction_rules.get(
                            name,
                            "unknown_magic",
                        ),
                        confidence=confidence,
                        box=box,
                        center=candidate_center,
                        source="clip_landmark",
                        original_name=name,
                        canonical_name=canonical_name_for(name),
                    ))
            except Exception as exc:
                clip_details.append({
                    "accepted": False,
                    "error": type(exc).__name__,
                })
        return candidates, {
            "used": True,
            "candidate_count": len(candidates),
            "processing_time": float(time.perf_counter() - started),
            "mean_brightness": mean_brightness,
            "prompts": prompts,
            "clip_fallback_used": not bool(candidates) or bool(clip_details),
            "clip_details": clip_details,
        }

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
        image_area = w * h
        if len(standard_objects) <= 2:
            reasons.append(f"very few detections ({len(standard_objects)} <= 2)")
        if image_area >= 2_500_000 and len(standard_objects) < 10:
            reasons.append(f"high resolution with modest detections ({w}x{h})")
        elif image_area >= 1_500_000 and len(standard_objects) < 5:
            reasons.append(f"large image with few detections ({w}x{h})")

        return bool(reasons), reasons

    def _accuracy_should_use_tiles(
        self,
        img: np.ndarray,
        standard_objects: List[DetectedObject],
    ) -> Tuple[bool, List[str]]:
        """Use the expensive full tile pass only when it can add useful detail."""
        h, w = img.shape[:2]
        image_area = h * w
        reasons: List[str] = []
        if image_area >= 3_000_000:
            reasons.append(f"high resolution ({w}x{h})")
        if len(standard_objects) <= 2:
            reasons.append(f"very few initial detections ({len(standard_objects)})")
        elif image_area >= 1_500_000 and len(standard_objects) < 6:
            reasons.append(
                f"large image with sparse initial detections ({len(standard_objects)})"
            )
        small_candidate_count = sum(
            1
            for item in standard_objects
            if self._box_area(item) / max(1, image_area) < 0.002
        )
        if image_area >= 1_500_000 and small_candidate_count >= 4:
            reasons.append(f"many small-object candidates ({small_candidate_count})")
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

        quality_reason = self._quality_filter_reason(
            candidate,
            image_shape[0] * image_shape[1],
            image_shape,
        )
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
        full_detection_started = time.perf_counter()
        detected = self._run_yolo(img, source="yolo", full_shape=img.shape)
        full_detection_time = time.perf_counter() - full_detection_started
        additional_detection_time = 0.0
        focused_food_stats: Dict[str, object] = {
            "used": False,
            "candidate_count": 0,
            "processing_time": 0.0,
        }
        if self.enable_focused_food_pass:
            focused_food, focused_food_stats = self._detect_focused_food_candidates(img)
            detected.extend(focused_food)
            additional_detection_time += float(
                focused_food_stats.get("processing_time", 0.0)
            )
        else:
            focused_food_stats["reason"] = "disabled_not_formally_adopted"
        raw_standard_count = len(detected)
        auto_reasons: List[str] = []
        auto_used_accuracy = False
        auto_tile_candidate_count = 0
        auto_added_count = 0
        auto_rejected: List[Tuple[DetectedObject, str]] = []
        tile_analysis_used = False
        tile_reasons: List[str] = []
        landmark_stats: Dict[str, object] = {
            "used": False,
            "candidate_count": 0,
            "processing_time": 0.0,
        }

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
                tile_analysis_used = True
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
                additional_started = time.perf_counter()
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
                additional_detection_time += time.perf_counter() - additional_started
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
            standard_filtered = self._filter_detections(detected, img.shape)
            standard_filter_log = list(self.last_filtered_out)
            tile_analysis_used, tile_reasons = self._accuracy_should_use_tiles(
                img,
                standard_filtered,
            )
            detected = list(standard_filtered)
            if tile_analysis_used:
                h, w = img.shape[:2]
                windows = self._tile_windows(w, h)
                print(
                    f"accuracy tile detections enabled: {len(windows)} tiles; "
                    + "; ".join(tile_reasons)
                )
                additional_started = time.perf_counter()
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
                additional_detection_time += time.perf_counter() - additional_started
            else:
                print("accuracy tile detections skipped: initial pass is sufficient")
            self.last_filtered_out = standard_filter_log

        landmark_reference = [
            item for item in detected if item.source == "yolo"
        ]
        landmark_candidates, landmark_stats = (
            self._detect_night_landmark_candidates(
                img,
                landmark_reference,
            )
        )
        detected.extend(landmark_candidates)
        additional_detection_time += float(
            landmark_stats.get("processing_time", 0.0)
        )

        detected.sort(key=lambda item: item.confidence, reverse=True)
        self.last_raw_detection_count = raw_standard_count
        if self.detection_mode != "auto":
            self.last_raw_detection_count = len(detected)
            preliminary_filter_log = list(self.last_filtered_out)
            detected = self._filter_detections(detected, img.shape)
            self.last_filtered_out = (
                preliminary_filter_log + list(self.last_filtered_out)
            )
        elif auto_used_accuracy:
            self.last_raw_detection_count = raw_standard_count + len(tile_raw)
        initial_filter_log = list(self.last_filtered_out)
        bbox_filtered_count = len(detected)
        detected, crowd_removed = self._suppress_tiny_crowd_candidates(
            detected,
            img.shape,
        )
        self.last_filtered_out = initial_filter_log + crowd_removed
        pre_reclassification_count = len(detected)
        detected, crop_stats = self.reclassify_crops(img, detected)
        supporting_label_reclassified_count = (
            self._apply_supporting_label_evidence(detected)
        )
        barbecue_context_reclassified_count = (
            self._reclassify_barbecue_context(img, detected)
        )
        if self.enable_dominant_food_background_suppression:
            detected, secondary_background_removed = (
                self._suppress_secondary_background_candidates(
                    detected,
                    img.shape,
                )
            )
        else:
            secondary_background_removed = []
        self.last_filtered_out.extend(secondary_background_removed)
        final_filter_log = list(self.last_filtered_out)
        detected = self._filter_detections(detected, img.shape)
        self.last_filtered_out = final_filter_log + list(self.last_filtered_out)
        self.last_filtered_detection_count = len(detected)
        self.last_final_detection_count = len(detected)
        self.last_processing_time = time.perf_counter() - started
        self.last_auto_used_accuracy = auto_used_accuracy
        self.last_objects = detected
        exclusion_events, exclusion_reason_counts = self._build_exclusion_debug(
            img.shape
        )
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
            "tile_analysis_used": tile_analysis_used,
            "tile_reasons": tile_reasons or auto_reasons,
            "landmark_analysis": landmark_stats,
            "full_detection_time": full_detection_time,
            "additional_detection_time": additional_detection_time,
            "primary_candidate_count": raw_standard_count,
            "initial_candidate_count": self.last_raw_detection_count,
            "initial_excluded_count": max(0, self.last_raw_detection_count - bbox_filtered_count),
            "bbox_deduplicated_count": max(0, self.last_raw_detection_count - bbox_filtered_count),
            "crowd_suppressed_count": len(crowd_removed),
            "pre_reclassification_count": pre_reclassification_count,
            "crop_reclassification_candidate_count": int(crop_stats["candidate_count"]),
            "crop_reclassified_count": int(crop_stats["reclassified_count"]),
            "crop_reclassification_batches": int(crop_stats["category_batches"]),
            "crop_reclassification_time": float(crop_stats["processing_time"]),
            "crop_reclassification_failures": list(crop_stats.get("failures", [])),
            "supporting_label_reclassified_count": int(
                supporting_label_reclassified_count
            ),
            "barbecue_context_reclassified_count": int(
                barbecue_context_reclassified_count
            ),
            "focused_food_analysis": focused_food_stats,
            "secondary_background_suppressed_count": len(
                secondary_background_removed
            ),
            "pre_mask_candidate_count": len(detected),
            "excluded_before_mask_count": max(0, self.last_raw_detection_count - len(detected)),
            "excluded_candidates": exclusion_events,
            "exclusion_reason_counts": exclusion_reason_counts,
            "contained_part_count": int(
                exclusion_reason_counts.get("contained_part", 0)
            ),
            "duplicate_same_object_count": int(
                exclusion_reason_counts.get("duplicate_same_object", 0)
            ),
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
                    f"source={item.source} box={item.box} "
                    f"reason_code={self._exclusion_reason_code(reason)} "
                    f"reason={reason}"
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
    
