"""
Magic Photo Museum - ML Detector
================================
写真の中の物体をYOLO-Worldで検出し、クリック可能な物体リストとして返す機械学習モジュールです。

今回の版:
- 人・水・建物・空も認識対象に追加
- 画像の縦横比を保ったまま、画面サイズに収まる大きさへ自動リサイズ
- AI検出画像・表示画像・クリック判定座標を同じにする
"""

from dataclasses import dataclass, asdict
from typing import List, Tuple, Dict, Optional

import cv2
import numpy as np
from ultralytics import YOLO


@dataclass
class DetectedObject:
    """AIが検出した物体情報"""
    name: str
    reaction: str
    confidence: float
    box: Tuple[int, int, int, int]
    center: Tuple[int, int]

    def to_dict(self) -> Dict:
        return asdict(self)


class MagicPhotoDetector:
    """
    YOLO-Worldを使って、写真内の物体を検出するクラス。
    検出結果は、後続のクリック判定・演出処理で使いやすい形に整形する。
    """

    def __init__(
        self,
        model_path: str = "yolov8s-world.pt",
        confidence: float = 0.12,
        image_size: int = 640,
        max_display_size: int = 1280,
    ):
        self.model_path = model_path
        self.confidence = confidence
        self.image_size = image_size
        self.max_display_size = max_display_size
        self.model = YOLO(model_path)

        # コンテスト作品用：写真内で反応させたい候補物体
        self.custom_classes = [
            # 人
            "person", "human", "man", "woman", "child", "face",

            # 光・部屋
            "light", "lamp", "ceiling light", "desk lamp",
            "window", "door", "clock", "mirror",

            # 音・遊び
            "musical instrument", "guitar", "piano", "drum", "microphone",
            "radio", "speaker", "toy", "ball", "balloon",

            # 生き物
            "animal", "dog", "cat", "bird", "fish", "horse", "rabbit",

            # 読み物・学習
            "book", "notebook", "paper", "mathematical formula", "whiteboard",

            # 電子機器
            "computer", "laptop", "monitor", "keyboard", "mouse", "phone", "cell phone",

            # 食べ物
            "food", "apple", "banana", "cake", "pizza", "cup", "bottle", "ice cream",

            # 乗り物
            "vehicle", "car", "bus", "train", "bicycle", "motorcycle",

            # 自然・外
            "sky", "sun", "moon", "cloud", "tree", "flower", "fireworks",
            "water", "sea", "ocean", "river", "lake", "pond", "pool", "waterfall",
            "building", "house", "tower", "bridge", "castle", "wall", "city",

            # 企画専用で探したいもの
            "treasure box", "kettle", "pot", "faucet", "sink", "glass", "firework",
        ]

        self.model.set_classes(self.custom_classes)
        self.reaction_rules = self._build_reaction_rules()
        self.last_objects: List[DetectedObject] = []
        self.last_image: Optional[np.ndarray] = None

    def _build_reaction_rules(self) -> Dict[str, str]:
        """検出名から演出カテゴリへ変換する辞書"""
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

    def resize_image(self, img: np.ndarray, max_size: Optional[int] = None) -> np.ndarray:
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
        new_w = int(w * scale)
        new_h = int(h * scale)
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def resize_image_to_fit(self, img: np.ndarray, max_width: int, max_height: int) -> np.ndarray:
        """
        画面サイズに合わせて画像を縮小する。
        画面からはみ出さない最大サイズにするが、縦横比は変えない。
        """
        h, w = img.shape[:2]

        # 余白ぶん少し小さくする
        max_width = max(100, int(max_width))
        max_height = max(100, int(max_height))

        scale = min(max_width / w, max_height / h, 1.0)
        new_w = int(w * scale)
        new_h = int(h * scale)

        if scale >= 1.0:
            return img

        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def load_image(self, image_path: str) -> np.ndarray:
        """画像を読み込み、長辺 max_display_size に縮小して返す。"""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"画像が見つかりません: {image_path}")
        img = self.resize_image(img)
        self.last_image = img
        return img

    def load_image_for_screen(self, image_path: str, screen_width: int, screen_height: int, margin: int = 80) -> np.ndarray:
        """
        画像を読み込み、現在の画面サイズに収まる最大サイズに縮小して返す。
        AI検出・表示・クリック判定をこの画像で統一する。
        """
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"画像が見つかりません: {image_path}")

        fit_w = max(100, screen_width - margin)
        fit_h = max(100, screen_height - margin)
        img = self.resize_image_to_fit(img, fit_w, fit_h)
        self.last_image = img
        return img

    def detect_from_image(self, img: np.ndarray) -> List[DetectedObject]:
        """
        すでにリサイズ済みの画像を解析する。
        表示画像と同じ画像を渡すことで、座標ズレを防ぐ。
        """
        results = self.model(img, conf=self.confidence, imgsz=self.image_size)
        detected: List[DetectedObject] = []

        for result in results:
            for box in result.boxes:
                class_id = int(box.cls[0])
                name = self.model.names[class_id]
                conf = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                reaction = self.reaction_rules.get(name, "unknown_magic")

                detected.append(
                    DetectedObject(
                        name=name,
                        reaction=reaction,
                        confidence=conf,
                        box=(x1, y1, x2, y2),
                        center=(cx, cy),
                    )
                )

        detected.sort(key=lambda obj: obj.confidence, reverse=True)
        self.last_objects = detected
        return detected

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

        if not self.last_objects:
            self.detect_from_image(img)

        for obj in self.last_objects:
            x1, y1, x2, y2 = obj.box
            label = f"{obj.name} {obj.confidence:.2f}"
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(
                img,
                label,
                (x1, max(25, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )

        cv2.imwrite(output_path, img)

    def detect_unknown_regions_from_image(self, img: np.ndarray, grid_size: int = 4) -> List[DetectedObject]:
        """リサイズ済み画像をグリッド分割して unknown_magic のクリック領域を作る。"""
        h, w = img.shape[:2]
        unknowns: List[DetectedObject] = []

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

    print("===== AI検出結果 =====")
    for obj in objects:
        print(obj.to_dict())

    detector.save_annotated_image(image_path, "result.jpg")
    print("result.jpg に検出結果を保存しました。")
