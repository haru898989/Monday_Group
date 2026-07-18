"""
Magic Photo Museum - ML Detector
================================
写真の中の物体をYOLO-Worldで検出し、クリック可能な物体リストとして返す機械学習モジュールです。

今回の版:
- 人・水・建物・空も認識対象に追加
- 画像の縦横比を保ったまま、画面サイズに収まる大きさへ自動リサイズ
- AI検出画像・表示画像・クリック判定座標を同じにする
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, Iterable, List, Optional, Tuple

from recognition_config import (
    CANONICAL_NAME_MAP,
    CATEGORY_MAP,
    CONFIDENCE_THRESHOLDS,
    CONFUSABLE_CLASS_PAIRS,
    CONFUSABLE_IOU_THRESHOLD,
    CUSTOM_CLASSES,
    DUPLICATE_IOU_THRESHOLD,
    PERSON_FILTER,
)


@dataclass
class DetectedObject:
    """AIが検出した物体情報"""
    name: str
    reaction: str
    confidence: float
    box: Tuple[int, int, int, int]
    center: Tuple[int, int]
    # 既存5項目は互換性のため維持し、認識用メタデータを末尾へ追加する。
    canonical_name: str = ""
    original_name: str = ""
    aliases: List[str] = field(default_factory=list)
    category: str = "unknown"

    def __post_init__(self) -> None:
        self.original_name = self.original_name or self.name
        self.canonical_name = self.canonical_name or canonicalize_name(self.name)
        if not self.category or self.category == "unknown":
            self.category = category_for(self.canonical_name)
        self.aliases = _unique_names(
            [self.canonical_name, self.original_name, self.name, *self.aliases]
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _normalized_text(name: Any) -> str:
    """クラス名の大文字小文字・空白・区切り文字を安全に揃える。"""
    text = str(name or "").strip().lower().replace("_", "-")
    text = re.sub(r"\s*-\s*", " ", text)
    return re.sub(r"\s+", " ", text)


def canonicalize_name(name: Any) -> str:
    """YOLOの予測名を写真理解用canonical_nameへ変換する。"""
    normalized = _normalized_text(name)
    return CANONICAL_NAME_MAP.get(normalized, normalized or "unknown")


def category_for(canonical_name: str) -> str:
    """canonical_nameに対応する大分類を返す。未知名はunknownにする。"""
    return CATEGORY_MAP.get(canonical_name, "unknown")


def _unique_names(names: Iterable[Any]) -> List[str]:
    """空要素を除き、入力順を保った重複なしリストを作る。"""
    result: List[str] = []
    for name in names:
        normalized = _normalized_text(name)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def calculate_iou(
    first_box: Tuple[int, int, int, int],
    second_box: Tuple[int, int, int, int],
) -> float:
    """2つのxyxy形式boxのIoUを0.0〜1.0で返す。"""
    ax1, ay1, ax2, ay2 = first_box
    bx1, by1, bx2, by2 = second_box
    intersection_width = max(0, min(ax2, bx2) - max(ax1, bx1))
    intersection_height = max(0, min(ay2, by2) - max(ay1, by1))
    intersection = intersection_width * intersection_height
    first_area = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    second_area = max(0, bx2 - bx1) * max(0, by2 - by1)
    union = first_area + second_area - intersection
    return 0.0 if union <= 0 else max(0.0, min(1.0, intersection / union))


def _confidence_threshold(canonical_name: str, category: str) -> float:
    """名前固有→カテゴリ→defaultの順でconfidence閾値を選ぶ。"""
    by_name = CONFIDENCE_THRESHOLDS.get("by_name", {})
    by_category = CONFIDENCE_THRESHOLDS.get("by_category", {})
    default = float(CONFIDENCE_THRESHOLDS.get("default", 0.12))
    if isinstance(by_name, dict) and canonical_name in by_name:
        return float(by_name[canonical_name])
    if isinstance(by_category, dict) and category in by_category:
        return float(by_category[category])
    return default


def _debug_detection(obj: DetectedObject) -> Dict[str, Any]:
    """後処理debugへ保存する最小限の検出情報を作る。"""
    confidence = _finite_confidence(getattr(obj, "confidence", 0.0))
    try:
        box = list(obj.box)
    except (TypeError, ValueError):
        box = []
    return {
        "original_name": str(getattr(obj, "original_name", "") or getattr(obj, "name", "unknown")),
        "canonical_name": str(getattr(obj, "canonical_name", "") or canonicalize_name(getattr(obj, "name", "unknown"))),
        "confidence": round(confidence, 6),
        "box": box,
    }


def _finite_confidence(value: Any) -> float:
    """confidenceを有限な0.0〜1.0へ安全に変換する。"""
    try:
        confidence = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return max(0.0, min(1.0, confidence)) if math.isfinite(confidence) else 0.0


def _unit_setting(value: Any, default: float) -> float:
    """設定用比率を検証し、不正値では安全な既定値へ戻す。"""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0.0, min(1.0, number)) if math.isfinite(number) else default


def _iou_setting(value: Any, default: float) -> float:
    """IoU閾値は範囲外を丸めず既定値へ戻し、誤統合を防ぐ。"""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return number if math.isfinite(number) and 0.0 < number <= 1.0 else default


def postprocess_detections(
    objects: Optional[Iterable[DetectedObject]],
    image_width: int,
    image_height: int,
    base_confidence: float = 0.12,
    duplicate_iou_threshold: float = DUPLICATE_IOU_THRESHOLD,
    confusable_iou_threshold: float = CONFUSABLE_IOU_THRESHOLD,
) -> Tuple[List[DetectedObject], Dict[str, List[Dict[str, Any]] | List[str]]]:
    """confidence・人物形状・IoUを使い、YOLOの生検出を整理する。

    高confidenceのboxを保持し、統合された元名はaliasesとdebugへ残す。
    """
    debug: Dict[str, List[Dict[str, Any]] | List[str]] = {
        "removed_duplicates": [],
        "removed_low_confidence": [],
        "removed_invalid": [],
        "warnings": [],
    }
    width = max(0, int(image_width))
    height = max(0, int(image_height))
    base_threshold = _unit_setting(
        base_confidence, float(CONFIDENCE_THRESHOLDS.get("default", 0.12))
    )
    duplicate_threshold = _iou_setting(
        duplicate_iou_threshold, DUPLICATE_IOU_THRESHOLD
    )
    confusable_threshold = _iou_setting(
        confusable_iou_threshold, CONFUSABLE_IOU_THRESHOLD
    )
    if width <= 0 or height <= 0:
        debug["warnings"].append("画像サイズが不正なため、全検出を除外しました。")
        return [], debug

    filtered: List[DetectedObject] = []
    image_area = width * height
    sources: Iterable[DetectedObject] = [] if objects is None else objects
    for source in sources:
        confidence = _finite_confidence(source.confidence)

        try:
            x1, y1, x2, y2 = (int(round(float(value))) for value in source.box)
        except (TypeError, ValueError, OverflowError):
            debug["removed_invalid"].append({"name": str(getattr(source, "name", "unknown")), "reason": "invalid_box"})
            continue
        x1, x2 = sorted((max(0, min(width, x1)), max(0, min(width, x2))))
        y1, y2 = sorted((max(0, min(height, y1)), max(0, min(height, y2))))
        if x2 <= x1 or y2 <= y1:
            invalid = _debug_detection(source)
            invalid["reason"] = "empty_box"
            debug["removed_invalid"].append(invalid)
            continue

        original_name = str(source.original_name or source.name or "unknown").strip()
        canonical_name = canonicalize_name(source.canonical_name or original_name)
        category = category_for(canonical_name)
        normalized = replace(
            source,
            confidence=confidence,
            box=(x1, y1, x2, y2),
            center=((x1 + x2) // 2, (y1 + y2) // 2),
            canonical_name=canonical_name,
            original_name=original_name,
            aliases=_unique_names([
                canonical_name,
                original_name,
                *(source.aliases if isinstance(source.aliases, (list, tuple, set)) else []),
            ]),
            category=category,
        )
        threshold = max(base_threshold, _confidence_threshold(canonical_name, category))
        if normalized.confidence < threshold:
            removed = _debug_detection(normalized)
            removed.update({"threshold": round(threshold, 6), "reason": "low_confidence"})
            debug["removed_low_confidence"].append(removed)
            continue

        # faceやhandは全身人物と形が異なるため、この保守的フィルタの対象外にする。
        if canonical_name == "person":
            object_width = x2 - x1
            object_height = y2 - y1
            area_ratio = (object_width * object_height) / image_area
            aspect_ratio = object_width / max(1, object_height)
            tiny = (
                area_ratio < PERSON_FILTER["tiny_area_ratio"]
                and normalized.confidence < PERSON_FILTER["tiny_confidence"]
            )
            implausibly_wide = (
                aspect_ratio > PERSON_FILTER["wide_aspect_ratio"]
                and area_ratio < PERSON_FILTER["wide_max_area_ratio"]
                and normalized.confidence < PERSON_FILTER["wide_max_confidence"]
            )
            if tiny or implausibly_wide:
                removed = _debug_detection(normalized)
                removed.update({"reason": "implausible_person_shape", "area_ratio": round(area_ratio, 8)})
                debug["removed_invalid"].append(removed)
                continue
        filtered.append(normalized)

    filtered.sort(key=lambda item: item.confidence, reverse=True)
    kept: List[DetectedObject] = []
    for candidate in filtered:
        duplicate_index: Optional[int] = None
        duplicate_iou = 0.0
        for index, current in enumerate(kept):
            same_canonical = candidate.canonical_name == current.canonical_name
            confusable = frozenset((candidate.canonical_name, current.canonical_name)) in CONFUSABLE_CLASS_PAIRS
            if not same_canonical and not confusable:
                continue
            iou = calculate_iou(candidate.box, current.box)
            threshold = duplicate_threshold if same_canonical else confusable_threshold
            if iou >= threshold:
                duplicate_index = index
                duplicate_iou = iou
                break

        if duplicate_index is None:
            kept.append(candidate)
            continue

        winner = kept[duplicate_index]
        winner.aliases = _unique_names([*winner.aliases, *candidate.aliases])
        removed = _debug_detection(candidate)
        removed.update(
            {
                "kept_original_name": winner.original_name,
                "kept_canonical_name": winner.canonical_name,
                "iou": round(duplicate_iou, 6),
                "reason": "duplicate",
            }
        )
        debug["removed_duplicates"].append(removed)

    kept.sort(key=lambda item: item.confidence, reverse=True)
    return kept, debug


class MagicPhotoDetector:
    """
    YOLO-Worldを使って、写真内の物体を検出するクラス。
    検出結果は、後続のクリック判定・写真理解で使いやすい形に整形する。
    """

    def __init__(
        self,
        model_path: str = "yolov8s-world.pt",
        confidence: float = 0.12,
        image_size: int = 640,
        max_display_size: int = 1280,
        duplicate_iou_threshold: float = DUPLICATE_IOU_THRESHOLD,
        confusable_iou_threshold: float = CONFUSABLE_IOU_THRESHOLD,
    ):
        # 後処理の単体テストではYOLO/OpenCVを不要にするため、実利用時に読み込む。
        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO
        except ImportError as error:
            raise ImportError(
                "画像検出には requirements.txt の ultralytics/opencv-python/numpy が必要です。"
            ) from error

        self._cv2 = cv2
        self._np = np
        self.model_path = model_path
        self.confidence = _unit_setting(
            confidence, float(CONFIDENCE_THRESHOLDS.get("default", 0.12))
        )
        self.image_size = image_size
        self.max_display_size = max_display_size
        self.duplicate_iou_threshold = _iou_setting(
            duplicate_iou_threshold, DUPLICATE_IOU_THRESHOLD
        )
        self.confusable_iou_threshold = _iou_setting(
            confusable_iou_threshold, CONFUSABLE_IOU_THRESHOLD
        )
        self.model = YOLO(model_path)

        self.custom_classes = list(CUSTOM_CLASSES)

        self.model.set_classes(self.custom_classes)
        self.reaction_rules = self._build_reaction_rules()
        self.last_objects: List[DetectedObject] = []
        self.last_detection_objects: Optional[List[DetectedObject]] = None
        self.last_raw_objects: List[DetectedObject] = []
        self.last_raw_count = 0
        self.last_postprocess_debug: Dict[str, Any] = {
            "removed_duplicates": [],
            "removed_low_confidence": [],
            "removed_invalid": [],
            "warnings": [],
        }
        # 短い別名も用意し、MagicBrainへそのまま渡せるようにする。
        self.last_debug = self.last_postprocess_debug
        self.last_image: Optional[Any] = None
        self.last_loaded_path: Optional[str] = None
        self.last_loaded_mtime_ns: Optional[int] = None
        self.last_loaded_image_id: Optional[int] = None
        self.last_detection_path: Optional[str] = None
        self.last_detection_mtime_ns: Optional[int] = None
        self.last_detection_shape: Optional[Tuple[int, int]] = None

    def _build_reaction_rules(self) -> Dict[str, str]:
        """既存クリックデモとの互換性を保つレガシー反応名の辞書。"""
        return {
            "person": "human_reaction",
            "human": "human_reaction",
            "man": "human_reaction",
            "woman": "human_reaction",
            "child": "human_reaction",
            "face": "human_reaction",

            "light": "toggle_light",
            "lamp": "toggle_light",
            "ceiling light": "toggle_light",
            "desk lamp": "toggle_light",

            "musical instrument": "play_music",
            "guitar": "play_music",
            "piano": "play_music",
            "drum": "play_music",
            "microphone": "play_music",
            "radio": "play_radio",
            "speaker": "play_music",

            "animal": "animal_sound",
            "dog": "animal_sound",
            "cat": "animal_sound",
            "bird": "animal_sound",
            "fish": "animal_sound",
            "horse": "animal_sound",
            "rabbit": "animal_sound",

            "book": "open_book",
            "notebook": "open_book",
            "paper": "solve_or_write",
            "mathematical formula": "solve_formula",
            "whiteboard": "solve_or_write",

            "computer": "start_pc",
            "laptop": "start_pc",
            "monitor": "start_pc",
            "keyboard": "start_pc",
            "mouse": "start_pc",
            "phone": "ring_phone",
            "cell phone": "ring_phone",

            "food": "eat_food",
            "apple": "eat_food",
            "banana": "eat_food",
            "cake": "eat_food",
            "pizza": "eat_food",
            "ice cream": "eat_food",
            "cup": "steam_or_fill",
            "bottle": "steam_or_fill",

            "vehicle": "move_vehicle",
            "car": "move_vehicle",
            "bus": "move_vehicle",
            "train": "move_vehicle",
            "bicycle": "move_vehicle",
            "motorcycle": "move_vehicle",

            "sky": "fireworks",
            "sun": "day_night_change",
            "moon": "day_night_change",
            "cloud": "weather_change",
            "tree": "grow_tree",
            "flower": "bloom_flower",
            "fireworks": "fireworks",
            "firework": "fireworks",
            "water": "water_magic",
            "sea": "water_magic",
            "ocean": "water_magic",
            "river": "water_magic",
            "lake": "water_magic",
            "pond": "water_magic",
            "pool": "water_magic",
            "waterfall": "water_magic",
            "building": "building_magic",
            "house": "building_magic",
            "tower": "building_magic",
            "bridge": "building_magic",
            "castle": "building_magic",
            "wall": "building_magic",
            "city": "building_magic",

            "window": "break_window",
            "door": "open_door",
            "clock": "spin_clock",
            "mirror": "magic_mirror",
            "toy": "toy_action",
            "ball": "bounce_ball",
            "balloon": "fly_balloon",
            "treasure box": "open_treasure",
            "kettle": "steam",
            "pot": "steam",
            "faucet": "water_on",
            "sink": "water_on",
            "glass": "break_glass",
        }

    def resize_image(self, img: Any, max_size: Optional[int] = None) -> Any:
        """
        画像の長辺が max_size を超える場合だけ縮小する。
        縦横比は必ず維持する。
        """
        if max_size is None:
            max_size = self.max_display_size

        h, w = img.shape[:2]
        if max(h, w) <= max_size:
            return img

        scale = max_size / max(h, w)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))
        return self._cv2.resize(img, (new_w, new_h), interpolation=self._cv2.INTER_AREA)

    def resize_image_to_fit(self, img: Any, max_width: int, max_height: int) -> Any:
        """
        画面サイズに合わせて画像を縮小する。
        画面からはみ出さない最大サイズにするが、縦横比は変えない。
        """
        h, w = img.shape[:2]

        # 余白ぶん少し小さくする
        max_width = max(100, int(max_width))
        max_height = max(100, int(max_height))

        scale = min(max_width / w, max_height / h, 1.0)
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        if scale >= 1.0:
            return img

        return self._cv2.resize(img, (new_w, new_h), interpolation=self._cv2.INTER_AREA)

    def load_image(self, image_path: str) -> Any:
        """画像を読み込み、長辺 max_display_size に縮小して返す。"""
        img = self._cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"画像が見つかりません: {image_path}")
        img = self.resize_image(img)
        self.last_image = img
        self._remember_loaded_image(image_path, img)
        return img

    def load_image_for_screen(self, image_path: str, screen_width: int, screen_height: int, margin: int = 80) -> Any:
        """
        画像を読み込み、現在の画面サイズに収まる最大サイズに縮小して返す。
        AI検出・表示・クリック判定をこの画像で統一する。
        """
        img = self._cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"画像が見つかりません: {image_path}")

        fit_w = max(100, screen_width - margin)
        fit_h = max(100, screen_height - margin)
        img = self.resize_image_to_fit(img, fit_w, fit_h)
        self.last_image = img
        self._remember_loaded_image(image_path, img)
        return img

    def _remember_loaded_image(self, image_path: str, img: Any) -> None:
        """直近に読み込んだ画像を、再推論の要否判定用に記録する。"""
        path = os.path.abspath(image_path)
        self.last_loaded_path = path
        self.last_loaded_image_id = id(img)
        try:
            self.last_loaded_mtime_ns = os.stat(path).st_mtime_ns
        except OSError:
            self.last_loaded_mtime_ns = None

    def detect_from_image(self, img: Any) -> List[DetectedObject]:
        """
        すでにリサイズ済みの画像を解析する。
        表示画像と同じ画像を渡すことで、座標ズレを防ぐ。
        """
        results = self.model(img, conf=self.confidence, imgsz=self.image_size)
        detected: List[DetectedObject] = []

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                original_name = str(self.model.names[class_id]).strip()
                name = _normalized_text(original_name)
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                canonical_name = canonicalize_name(name)
                reaction = self.reaction_rules.get(
                    name,
                    self.reaction_rules.get(canonical_name, "unknown_magic"),
                )

                detected.append(
                    DetectedObject(
                        name=name,
                        reaction=reaction,
                        confidence=conf,
                        box=(x1, y1, x2, y2),
                        center=(cx, cy),
                        canonical_name=canonical_name,
                        original_name=original_name,
                        aliases=[canonical_name, name],
                        category=category_for(canonical_name),
                    )
                )

        self.last_raw_objects = detected
        self.last_raw_count = len(detected)
        height, width = img.shape[:2]
        self.last_detection_shape = (height, width)
        if id(img) == self.last_loaded_image_id:
            self.last_detection_path = self.last_loaded_path
            self.last_detection_mtime_ns = self.last_loaded_mtime_ns
        else:
            self.last_detection_path = None
            self.last_detection_mtime_ns = None
        processed, debug = postprocess_detections(
            detected,
            image_width=width,
            image_height=height,
            base_confidence=self.confidence,
            duplicate_iou_threshold=self.duplicate_iou_threshold,
            confusable_iou_threshold=self.confusable_iou_threshold,
        )
        self.last_postprocess_debug = debug
        self.last_debug = debug
        self.last_objects = processed
        self.last_detection_objects = processed
        return processed

    def detect(self, image_path: str) -> List[DetectedObject]:
        """
        画像を解析し、検出した物体を返す。
        従来用。画面サイズに合わせたい場合は demo_click.py のように
        load_image_for_screen() → detect_from_image() を使う。
        """
        img = self.load_image(image_path)
        return self.detect_from_image(img)

    def find_clicked_object(self, x: int, y: int) -> Optional[DetectedObject]:
        """
        クリック座標がどの物体の範囲に入っているかを判定する。
        複数重なった場合は、面積が小さい物体を優先する。
        """
        candidates = []

        for obj in self.last_objects:
            x1, y1, x2, y2 = obj.box
            if x1 <= x <= x2 and y1 <= y <= y2:
                area = (x2 - x1) * (y2 - y1)
                candidates.append((area, obj))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def save_annotated_image(self, image_path: str, output_path: str = "result.jpg") -> None:
        """検出結果を四角で描いた画像を保存する"""
        img = self.load_image(image_path)
        current_shape = tuple(img.shape[:2])
        can_reuse = (
            self.last_detection_objects is not None
            and self.last_objects is self.last_detection_objects
            and self.last_detection_path == self.last_loaded_path
            and self.last_detection_mtime_ns == self.last_loaded_mtime_ns
            and self.last_detection_shape == current_shape
        )
        # 同一ファイル・更新時刻・画像サイズなら既存結果を使い、それ以外だけ再推論する。
        if not can_reuse:
            self.detect_from_image(img)

        for obj in self.last_objects:
            x1, y1, x2, y2 = obj.box
            label = f"{obj.name} {obj.confidence:.2f}"
            self._cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            self._cv2.putText(
                img,
                label,
                (x1, max(25, y1 - 8)),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        self._cv2.imwrite(output_path, img)

    def detect_unknown_regions_from_image(self, img: Any, grid_size: int = 4) -> List[DetectedObject]:
        """リサイズ済み画像をグリッド分割して unknown_magic のクリック領域を作る。"""
        h, w = img.shape[:2]
        unknowns: List[DetectedObject] = []
        if w <= 0 or h <= 0:
            return unknowns

        try:
            requested_grid_size = int(grid_size)
        except (TypeError, ValueError, OverflowError):
            requested_grid_size = 4
        grid_size = max(1, min(requested_grid_size, max(1, w), max(1, h)))

        cell_w = w // grid_size
        cell_h = h // grid_size

        for gy in range(grid_size):
            for gx in range(grid_size):
                x1 = gx * cell_w
                y1 = gy * cell_h
                x2 = w if gx == grid_size - 1 else (gx + 1) * cell_w
                y2 = h if gy == grid_size - 1 else (gy + 1) * cell_h
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                unknowns.append(
                    DetectedObject(
                        name="unknown area",
                        reaction="unknown_magic",
                        confidence=0.0,
                        box=(x1, y1, x2, y2),
                        center=(cx, cy),
                    )
                )

        return unknowns

    def detect_unknown_regions(self, image_path: str, grid_size: int = 4) -> List[DetectedObject]:
        img = self.load_image(image_path)
        return self.detect_unknown_regions_from_image(img, grid_size)


if __name__ == "__main__":
    detector = MagicPhotoDetector()
    image_path = "sample.jpg"

    objects = detector.detect(image_path)

    print("===== 緑の四角の座標一覧 =====")
    for i, obj in enumerate(objects, start=1):
        x1, y1, x2, y2 = obj.box

        print(f"\n[{i}] {obj.name} / {obj.reaction} / 信頼度:{obj.confidence:.2f}")
        print(f"左上     : ({x1}, {y1})")
        print(f"右上     : ({x2}, {y1})")
        print(f"左下     : ({x1}, {y2})")
        print(f"右下     : ({x2}, {y2})")

    detector.save_annotated_image(image_path, "result.jpg")
    print("result.jpg に検出結果を保存しました。")
