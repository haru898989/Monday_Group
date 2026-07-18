"""Magic Photo Museum の画像認識設定。

調整頻度の高いクラス名・閾値・場面ルールを、処理本体から分離して管理する。
値はすべてPython標準型なので、Unity向けJSON生成時にも安全に利用できる。
"""

from __future__ import annotations


# YOLO-Worldへ問い合わせる語彙。既存語彙を維持しつつ、展示で重要な対象を追加する。
CUSTOM_CLASSES: tuple[str, ...] = tuple(
    dict.fromkeys(
        (
            # 人物
            "person", "human", "man", "woman", "child", "face", "hand",
            # 室内
            "table", "chair", "desk", "sofa", "bed", "lamp", "light",
            "ceiling light", "desk lamp", "window", "door", "clock", "mirror", "shelf",
            # 電子機器
            "monitor", "television", "laptop", "computer", "keyboard", "mouse",
            "smartphone", "cell phone", "phone", "speaker", "radio", "camera",
            # 食べ物・飲み物
            "food", "ice cream", "cake", "apple", "banana", "pizza", "bread",
            "drink", "cup", "bottle",
            # 自然・屋外
            "sky", "sun", "moon", "cloud", "tree", "flower", "grass", "mountain",
            "water", "sea", "ocean", "river", "lake", "pond", "pool", "waterfall",
            "building", "house", "tower", "bridge", "castle", "wall", "city", "road",
            # 動物
            "animal", "dog", "cat", "bird", "fish", "horse", "rabbit",
            # 乗り物
            "vehicle", "car", "bicycle", "motorcycle", "bus", "train", "airplane", "boat",
            # 学習・遊び・既存展示対象
            "book", "notebook", "paper", "whiteboard", "mathematical formula",
            "musical instrument", "guitar", "piano", "drum", "microphone",
            "ball", "balloon", "toy", "treasure box", "fireworks", "firework",
            "kettle", "pot", "faucet", "sink", "glass",
        )
    )
)


# モデルの表記揺れを、写真理解で使う代表名へ統合する。
CANONICAL_NAME_MAP: dict[str, str] = {
    "human": "person",
    "man": "person",
    "woman": "person",
    "child": "person",
    "boy": "person",
    "girl": "person",
    "television": "display",
    "tv": "display",
    "monitor": "display",
    "smartphone": "phone",
    "cell phone": "phone",
    "mobile phone": "phone",
    "icecream": "ice cream",
    "firework": "fireworks",
    "ocean": "sea",
    "vehicle": "vehicle",
}


# canonical_nameから写真理解用カテゴリを得るための対応表。
CATEGORY_MAP: dict[str, str] = {
    "person": "human", "face": "human", "hand": "human",
    "table": "furniture", "chair": "furniture", "desk": "furniture",
    "sofa": "furniture", "bed": "furniture", "shelf": "furniture",
    "light": "light", "lamp": "light", "ceiling light": "light", "desk lamp": "light",
    "window": "indoor_fixture", "door": "indoor_fixture", "clock": "indoor_fixture",
    "mirror": "indoor_fixture", "sink": "indoor_fixture", "faucet": "indoor_fixture",
    "kettle": "container", "pot": "container", "glass": "container",
    "display": "electronics", "laptop": "electronics", "computer": "electronics",
    "keyboard": "electronics", "mouse": "electronics", "phone": "electronics",
    "speaker": "electronics", "radio": "electronics", "camera": "electronics",
    "food": "food", "ice cream": "food", "cake": "food", "apple": "food",
    "banana": "food", "pizza": "food", "bread": "food",
    "drink": "drink", "cup": "drink", "bottle": "drink",
    "sky": "nature", "sun": "nature", "moon": "nature", "cloud": "nature",
    "tree": "nature", "flower": "nature", "grass": "nature", "mountain": "nature",
    "water": "water", "sea": "water", "river": "water", "lake": "water",
    "pond": "water", "pool": "water", "waterfall": "water",
    "building": "structure", "house": "structure", "tower": "structure",
    "bridge": "structure", "castle": "structure", "wall": "structure", "city": "structure",
    "road": "transportation_infrastructure",
    "animal": "animal", "dog": "animal", "cat": "animal", "bird": "animal",
    "fish": "animal", "horse": "animal", "rabbit": "animal",
    "vehicle": "vehicle", "car": "vehicle", "bicycle": "vehicle",
    "motorcycle": "vehicle", "bus": "vehicle", "train": "vehicle",
    "airplane": "vehicle", "boat": "vehicle",
    "book": "education", "notebook": "education", "paper": "education",
    "whiteboard": "education", "mathematical formula": "education",
    "musical instrument": "entertainment", "guitar": "entertainment",
    "piano": "entertainment", "drum": "entertainment", "microphone": "entertainment",
    "ball": "entertainment", "balloon": "entertainment", "toy": "entertainment",
    "treasure box": "entertainment", "fireworks": "entertainment",
}


# confidenceは「呼び出し側の全体閾値」と以下のカテゴリ別閾値の高い方を使う。
CONFIDENCE_THRESHOLDS: dict[str, object] = {
    "default": 0.12,
    "by_name": {
        # 遮蔽物や激しい動きがある人物も切り抜き対象として残す。
        "person": 0.15,
        "face": 0.25,
        "hand": 0.20,
        "mouse": 0.12,
        "phone": 0.12,
        "cup": 0.12,
        "bottle": 0.12,
    },
    "by_category": {
        "food": 0.15,
        "animal": 0.16,
        "vehicle": 0.16,
        "electronics": 0.14,
    },
}


# 同一canonical名と、誤認しやすい別名ペアでは別のIoU閾値を使う。
DUPLICATE_IOU_THRESHOLD = 0.65
CONFUSABLE_IOU_THRESHOLD = 0.85
CONFUSABLE_CLASS_PAIRS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset(("display", "computer")),
        frozenset(("bottle", "pot")),
        frozenset(("bottle", "kettle")),
    }
)


# 人物候補の保守的な妥当性判定。高confidenceや大きな候補は救済する。
PERSON_FILTER: dict[str, float] = {
    "tiny_area_ratio": 0.0003,
    "tiny_confidence": 0.50,
    "wide_aspect_ratio": 3.50,
    "wide_max_area_ratio": 0.015,
    "wide_max_confidence": 0.35,
}


# 位置関係の閾値（画像対角線またはIoUに対する比率）。
RELATION_THRESHOLDS: dict[str, float | int] = {
    "near_distance_ratio": 0.22,
    "far_distance_ratio": 0.60,
    "direction_offset_ratio": 0.12,
    "overlap_iou": 0.10,
    "overlap_smaller_area_ratio": 0.15,
    "containment_ratio": 0.90,
    "direction_min_confidence": 0.30,
    "max_relations": 120,
}


IMPORTANCE_WEIGHTS: dict[str, float] = {
    "confidence": 0.30,
    "area": 0.25,
    "center": 0.20,
    "category": 0.15,
    "relations": 0.10,
}

CATEGORY_IMPORTANCE: dict[str, float] = {
    "human": 1.00,
    "animal": 0.90,
    "food": 0.86,
    "vehicle": 0.82,
    "entertainment": 0.78,
    "electronics": 0.72,
    "nature": 0.68,
    "water": 0.68,
    "drink": 0.64,
    "education": 0.62,
    "furniture": 0.55,
    "light": 0.55,
    "structure": 0.50,
    "indoor_fixture": 0.45,
    "transportation_infrastructure": 0.45,
    "container": 0.40,
    "unknown": 0.20,
}

# person本体と、人物の一部・背景物体を主役判定で区別する。
NAME_IMPORTANCE_OVERRIDES: dict[str, float] = {
    "face": 0.65,
    "hand": 0.35,
    "sky": 0.35,
    "wall": 0.25,
    "road": 0.40,
}

# importanceへ加える関係の強さ。方向・farだけで主役になりすぎないよう抑える。
RELATION_IMPORTANCE_WEIGHTS: dict[str, float] = {
    "holding_candidate": 1.00,
    "using_candidate": 0.85,
    "in_front_of": 0.65,
    "inside": 0.75,
    "contains": 0.75,
    "overlap": 0.70,
    "near": 0.50,
    "left_of": 0.15,
    "right_of": 0.15,
    "above": 0.15,
    "below": 0.15,
    "far": 0.05,
}

RELATION_IMPORTANCE_SATURATION = 2.5


# category/nameの重みから各場面の根拠を集約する。unknownはMagicBrain側で算出する。
SCENE_RULES: dict[str, dict[str, dict[str, float]]] = {
    "indoor": {
        "categories": {"furniture": 0.85, "indoor_fixture": 0.90, "electronics": 0.60, "light": 0.70, "education": 0.45},
        "names": {"ceiling light": 1.00, "desk lamp": 0.90, "window": 0.70, "door": 0.70},
    },
    "outdoor": {
        "categories": {"nature": 0.85, "water": 0.75, "vehicle": 0.40, "structure": 0.35, "transportation_infrastructure": 0.80},
        "names": {"sky": 1.00, "grass": 0.90, "mountain": 1.00, "road": 0.85},
    },
    "home": {
        "categories": {"furniture": 0.65, "light": 0.45, "indoor_fixture": 0.45, "food": 0.25},
        "names": {"bed": 1.00, "sofa": 0.90, "display": 0.75, "house": 0.65},
    },
    "office": {
        "categories": {"electronics": 0.72, "furniture": 0.45, "education": 0.30},
        "names": {"display": 1.00, "computer": 0.95, "laptop": 0.90, "keyboard": 0.85, "desk": 0.80},
    },
    "restaurant": {
        "categories": {"food": 0.80, "drink": 0.72, "furniture": 0.28},
        "names": {"table": 0.60, "cup": 0.65, "plate": 0.75},
    },
    "classroom": {
        "categories": {"education": 0.90, "furniture": 0.35, "electronics": 0.25},
        "names": {"whiteboard": 1.00, "desk": 0.70, "book": 0.70},
    },
    "park": {
        "categories": {"nature": 0.65, "human": 0.18, "animal": 0.25, "entertainment": 0.20},
        "names": {"grass": 0.90, "tree": 0.72, "flower": 0.60, "ball": 0.50},
    },
    "nature": {
        "categories": {"nature": 0.92, "water": 0.80, "animal": 0.38},
        "names": {"mountain": 1.00, "sea": 0.90, "river": 0.90, "sky": 0.60},
    },
    "food_scene": {
        "categories": {"food": 1.00, "drink": 0.55},
        "names": {"ice cream": 1.00, "cake": 0.95, "pizza": 0.95},
    },
    "animal_scene": {
        "categories": {"animal": 1.00},
        "names": {},
    },
    "transportation_scene": {
        "categories": {"vehicle": 1.00, "transportation_infrastructure": 0.75},
        "names": {"train": 1.00, "airplane": 1.00, "road": 0.75},
    },
    "entertainment_scene": {
        "categories": {"entertainment": 0.95, "electronics": 0.18},
        "names": {"camera": 0.60, "speaker": 0.60, "radio": 0.55, "fireworks": 1.00},
    },
    "night_scene": {
        "categories": {"light": 0.45},
        "names": {"moon": 1.00, "fireworks": 0.70, "lamp": 0.45},
    },
}
