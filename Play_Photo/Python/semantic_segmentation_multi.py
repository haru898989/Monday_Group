import cv2
import numpy as np
import torch
from torchvision import models, transforms


class SemanticSegmenterMulti:
    """DeepLabV3による複数クラス対応セマンティックセグメンテーション。"""

    CLASS_NAMES = [
        "background", "aeroplane", "bicycle", "bird", "boat",
        "bottle", "bus", "car", "cat", "chair",
        "cow", "diningtable", "dog", "horse", "motorbike",
        "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"
    ]
    SCENE_CLASS_NAMES = ("sky", "water", "ground", "plant")

    # OpenCVはBGR。クラスごとに見分けやすい固定色を設定。
    COLORS = np.array([
        [0, 0, 0], [255, 120, 0], [255, 0, 180], [0, 220, 255],
        [255, 170, 0], [100, 210, 255], [0, 120, 255], [0, 0, 255],
        [255, 0, 255], [40, 180, 255], [80, 170, 80], [180, 120, 60],
        [0, 255, 255], [120, 80, 255], [255, 80, 0], [0, 255, 0],
        [0, 180, 0], [150, 150, 255], [220, 100, 180], [255, 255, 0],
        [255, 255, 255]
    ], dtype=np.uint8)

    def __init__(self, input_size=640, min_component_ratio=0.0008):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.input_size = int(input_size)
        self.min_component_ratio = float(min_component_ratio)

        weights = models.segmentation.DeepLabV3_ResNet50_Weights.DEFAULT
        self.model = models.segmentation.deeplabv3_resnet50(weights=weights)
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((self.input_size, self.input_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        print(f"DeepLabV3 device: {self.device}")

    def segment_image(self, img_bgr):
        if img_bgr is None or img_bgr.size == 0:
            raise ValueError("入力画像が空です。")

        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        x = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            output = self.model(x)["out"][0]

        semantic_mask = output.argmax(0).cpu().numpy().astype(np.uint8)
        h, w = img_bgr.shape[:2]
        final_mask = cv2.resize(
            semantic_mask, (w, h), interpolation=cv2.INTER_NEAREST
        )
        if final_mask.shape[:2] != (h, w):
            raise RuntimeError("DeepLab final mask size does not match the original image.")
        return final_mask

    def get_class_id(self, class_name):
        if class_name not in self.CLASS_NAMES:
            raise ValueError(f"未対応クラスです: {class_name}")
        return self.CLASS_NAMES.index(class_name)

    def get_class_mask(self, semantic_mask, class_name_or_id, clean=True):
        if isinstance(class_name_or_id, str):
            class_id = self.get_class_id(class_name_or_id)
        else:
            class_id = int(class_name_or_id)

        mask = ((semantic_mask == class_id) * 255).astype(np.uint8)
        return self.clean_mask(mask) if clean else mask

    def supports_scene_class(self, class_name):
        """VOC外だが全画像から補助推定できる背景クラスかを返す。"""
        return str(class_name).strip().lower() in self.SCENE_CLASS_NAMES

    def get_scene_class_mask(self, img_bgr, class_name, clean=True):
        """検出枠で切らず、元画像全体から背景クラスのマスクを作る。

        現在のDeepLabV3/VOCにないsky/water/groundを、位置条件を伴う
        保守的なHSV候補として推定する。最終的な物体割当では検出枠に
        近い連結成分だけを選ぶ。
        """
        if img_bgr is None or img_bgr.size == 0:
            raise ValueError("入力画像が空です。")

        normalized_name = str(class_name).strip().lower()
        if normalized_name not in self.SCENE_CLASS_NAMES:
            raise ValueError(f"全画像推定に未対応のクラスです: {class_name}")

        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        hue, saturation, value = cv2.split(hsv)
        height, width = hue.shape
        if normalized_name == "sky":
            blue = (
                (hue >= 85)
                & (hue <= 135)
                & (saturation >= 35)
                & (value >= 55)
            )
            bright_cloud = (saturation <= 55) & (value >= 155)
            candidate = (blue | bright_cloud).astype(np.uint8)
            candidate[int(height * 0.90):, :] = 0
        elif normalized_name == "water":
            blue_water = (
                (hue >= 75)
                & (hue <= 125)
                & (saturation >= 12)
                & (value >= 35)
                & (value <= 235)
            )
            # Distant sea is often grey because of haze or backlight.  Position
            # and the later sky/foreground subtraction constrain this broader
            # low-saturation candidate more safely than hue alone.
            neutral_water = (
                (saturation <= 58)
                & (value >= 45)
                & (value <= 215)
            )
            candidate = (blue_water | neutral_water).astype(np.uint8)
            candidate[:int(height * 0.12), :] = 0
            candidate[int(height * 0.90):, :] = 0
        elif normalized_name == "ground":
            brown = (
                (hue >= 5)
                & (hue <= 35)
                & (saturation >= 20)
                & (value >= 25)
                & (value <= 220)
            )
            neutral = (
                (saturation <= 50)
                & (value >= 35)
                & (value <= 185)
            )
            candidate = (brown | neutral).astype(np.uint8)
            candidate[:int(height * 0.42), :] = 0
        else:
            candidate = (
                (hue >= 32)
                & (hue <= 92)
                & (saturation >= 38)
                & (value >= 28)
                & (value <= 235)
            ).astype(np.uint8)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(
            candidate,
            8,
        )
        selected = np.zeros((height, width), dtype=np.uint8)
        top_band = max(1, int(height * 0.08))
        bottom_band = int(height * 0.88)
        minimum_area = max(20, int(height * width * 0.0005))
        for label_id in range(1, count):
            component_top = int(stats[label_id, cv2.CC_STAT_TOP])
            component_height = int(stats[label_id, cv2.CC_STAT_HEIGHT])
            component_bottom = component_top + component_height
            component_area = int(stats[label_id, cv2.CC_STAT_AREA])
            if component_area < minimum_area:
                continue
            if normalized_name == "sky" and component_top <= top_band:
                selected[labels == label_id] = 255
            elif normalized_name == "water":
                selected[labels == label_id] = 255
            elif normalized_name == "ground" and component_bottom >= bottom_band:
                selected[labels == label_id] = 255
            elif normalized_name == "plant":
                selected[labels == label_id] = 255

        if clean and np.count_nonzero(selected) > 0:
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            selected = cv2.morphologyEx(
                selected,
                cv2.MORPH_CLOSE,
                kernel,
                iterations=1,
            )
        return selected

    def clean_mask(self, mask):
        """小さなノイズを除去し、穴や切れ目を軽く補正する。"""
        h, w = mask.shape[:2]
        if np.count_nonzero(mask) == 0:
            return mask.copy()

        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
        open_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel, iterations=1)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, open_kernel, iterations=1)

        count, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned, 8)
        result = np.zeros_like(cleaned)
        min_area = max(30, int(h * w * self.min_component_ratio))

        for label_id in range(1, count):
            if stats[label_id, cv2.CC_STAT_AREA] >= min_area:
                result[labels == label_id] = 255
        return result

    def present_class_ids(self, semantic_mask, include_background=False):
        ids, counts = np.unique(semantic_mask, return_counts=True)
        pairs = sorted(zip(ids.tolist(), counts.tolist()), key=lambda x: x[1], reverse=True)
        result = []
        for class_id, pixel_count in pairs:
            if class_id == 0 and not include_background:
                continue
            if 0 <= class_id < len(self.CLASS_NAMES):
                result.append((class_id, self.CLASS_NAMES[class_id], pixel_count))
        return result

    def class_at(self, semantic_mask, x, y):
        h, w = semantic_mask.shape[:2]
        if not (0 <= x < w and 0 <= y < h):
            return 0, "background"
        class_id = int(semantic_mask[y, x])
        return class_id, self.CLASS_NAMES[class_id]

    def colorize(self, semantic_mask, img=None, alpha=0.55):
        color_mask = self.COLORS[semantic_mask]
        if img is None:
            return color_mask
        return cv2.addWeighted(img, 1.0 - alpha, color_mask, alpha, 0)

    def draw_legend(self, image, class_ids):
        result = image.copy()
        x0, y0 = 18, 72
        row_h = 28
        max_rows = max(1, (result.shape[0] - y0 - 15) // row_h)

        for row, class_id in enumerate(class_ids[:max_rows]):
            y = y0 + row * row_h
            color = tuple(int(v) for v in self.COLORS[class_id])
            cv2.rectangle(result, (x0, y - 16), (x0 + 20, y + 4), color, -1)
            cv2.rectangle(result, (x0, y - 16), (x0 + 20, y + 4), (255, 255, 255), 1)
            cv2.putText(
                result, self.CLASS_NAMES[class_id], (x0 + 30, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2,
                cv2.LINE_AA
            )
        return result

    def glow(self, img, mask, color=(0, 255, 255)):
        result = img.copy()
        glow = cv2.GaussianBlur(mask, (51, 51), 0)
        layer = np.zeros_like(result)
        layer[:] = color
        alpha = (glow.astype(np.float32) / 255.0)[..., None] * 0.58
        result = (result * (1 - alpha) + layer * alpha).clip(0, 255).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result, contours, -1, color, 3)
        return result

    @staticmethod
    def spotlight(img, mask):
        background = (img.astype(np.float32) * 0.20).astype(np.uint8)
        soft = cv2.GaussianBlur(mask, (21, 21), 0)
        alpha = (soft.astype(np.float32) / 255.0)[..., None]
        return (background * (1 - alpha) + img * alpha).clip(0, 255).astype(np.uint8)

    def mask_preview(self, semantic_mask, selected_id=None):
        if selected_id is None:
            return self.COLORS[semantic_mask]
        mask = self.get_class_mask(semantic_mask, selected_id)
        color = np.zeros((*mask.shape, 3), dtype=np.uint8)
        color[mask > 0] = self.COLORS[selected_id]
        return color
