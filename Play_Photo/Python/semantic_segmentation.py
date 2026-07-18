"""
semantic_segmentation.py
DeepLabV3でセマンティックセグメンテーションするモジュール。
まずは「人(person)の形だけ取得して光らせる」ための土台。
"""

import cv2
import numpy as np
import torch
from torchvision import models, transforms


class SemanticSegmenter:
    CLASS_NAMES = [
        "background", "aeroplane", "bicycle", "bird", "boat",
        "bottle", "bus", "car", "cat", "chair",
        "cow", "diningtable", "dog", "horse", "motorbike",
        "person", "pottedplant", "sheep", "sofa", "train", "tvmonitor"
    ]

    def __init__(self, input_size=520):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.input_size = input_size

        weights = models.segmentation.DeepLabV3_ResNet50_Weights.DEFAULT
        self.model = models.segmentation.deeplabv3_resnet50(weights=weights)
        self.model.to(self.device)
        self.model.eval()

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((input_size, input_size)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])

    def resize_keep_aspect(self, img, max_size=1100):
        h, w = img.shape[:2]
        if max(h, w) <= max_size:
            return img
        scale = max_size / max(h, w)
        return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

    def segment_image(self, img_bgr):
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        input_tensor = self.transform(img_rgb).unsqueeze(0).to(self.device)

        with torch.no_grad():
            output = self.model(input_tensor)["out"][0]

        mask = output.argmax(0).cpu().numpy().astype(np.uint8)

        h, w = img_bgr.shape[:2]
        mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_NEAREST)
        return mask

    def get_class_mask(self, mask, class_name):
        if class_name not in self.CLASS_NAMES:
            raise ValueError(f"未対応クラスです: {class_name}")
        class_id = self.CLASS_NAMES.index(class_name)
        return ((mask == class_id) * 255).astype(np.uint8)

    def colorize_person(self, img_bgr, mask):
        person = self.get_class_mask(mask, "person")
        result = img_bgr.copy()

        glow = cv2.GaussianBlur(person, (41, 41), 0)
        red_layer = np.zeros_like(result)
        red_layer[:, :, 2] = 255

        alpha = (glow.astype(np.float32) / 255.0)[..., None]
        result = (result * (1 - alpha * 0.55) + red_layer * (alpha * 0.55)).astype(np.uint8)

        contours, _ = cv2.findContours(person, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(result, contours, -1, (0, 255, 255), 2)

        return result

    def darken_background_keep_person(self, img_bgr, mask):
        person = self.get_class_mask(mask, "person")
        result = (img_bgr * 0.35).astype(np.uint8)
        result[person > 0] = img_bgr[person > 0]
        return result
