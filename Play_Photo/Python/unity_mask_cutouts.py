"""正式解析マスクから、既存Unity向けの透過PNGを生成する。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Sequence

import cv2
import numpy as np


Box = tuple[int, int, int, int]
GENERATED_CUTOUT_PATTERN = "unity_object_*.png"


@dataclass(frozen=True)
class MaskCutoutSource:
    """1物体分の、Unity表示名・マスク範囲・正式マスク。"""

    name: str
    box: Box
    mask: np.ndarray


@dataclass(frozen=True)
class UnityUdpObject:
    """udp_sender.pyのlegacy形式が必要とする最小情報。"""

    name: str
    box: Box


def _safe_name(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_")
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", normalized).strip("_")
    return safe or "object"


def _clip_inclusive_box(box: Sequence[int], width: int, height: int) -> Box:
    if width <= 0 or height <= 0:
        raise ValueError("切り抜き元画像の幅と高さは1以上である必要があります。")

    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(width - 1, x1))
    y1 = max(0, min(height - 1, y1))
    x2 = max(0, min(width - 1, x2))
    y2 = max(0, min(height - 1, y2))
    if x2 < x1 or y2 < y1:
        raise ValueError(f"切り抜き範囲が不正です: {(x1, y1, x2, y2)}")
    return x1, y1, x2, y2


def create_rgba_cutouts_from_masks(
    image: np.ndarray,
    sources: Sequence[MaskCutoutSource],
    output_dir: Path,
) -> tuple[list[UnityUdpObject], list[str]]:
    """元画像の色と正式マスクの透明度を合成してUnity用PNGを保存する。

    戻り値の物体とファイル名は常に同じ順序です。UDP座標とPNGの切り抜き範囲には
    同じ ``box`` を使うため、Unity上での位置と表示サイズが一致します。
    """

    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("切り抜き元画像はBGRの3チャンネル画像である必要があります。")

    height, width = image.shape[:2]
    output_dir.mkdir(parents=True, exist_ok=True)
    for stale_path in output_dir.glob(GENERATED_CUTOUT_PATTERN):
        stale_path.unlink()

    udp_objects: list[UnityUdpObject] = []
    cutout_files: list[str] = []

    for index, source in enumerate(sources, start=1):
        mask = np.asarray(source.mask)
        if mask.ndim == 3:
            mask = mask[:, :, 0]
        if mask.shape != (height, width):
            raise ValueError(
                f"{source.name} のマスクサイズ {mask.shape} が"
                f"元画像サイズ {(height, width)} と一致しません。"
            )

        box = _clip_inclusive_box(source.box, width, height)
        x1, y1, x2, y2 = box
        crop_image = image[y1:y2 + 1, x1:x2 + 1]
        crop_alpha = np.where(
            mask[y1:y2 + 1, x1:x2 + 1] > 0,
            255,
            0,
        ).astype(np.uint8)

        udp_objects.append(UnityUdpObject(name=str(source.name), box=box))
        if not np.any(crop_alpha):
            cutout_files.append("")
            continue

        rgba_cutout = cv2.cvtColor(crop_image, cv2.COLOR_BGR2BGRA)
        rgba_cutout[:, :, 3] = crop_alpha
        filename = (
            f"unity_object_{index:04d}_{_safe_name(str(source.name))}.png"
        )
        encoded, buffer = cv2.imencode(".png", rgba_cutout)
        if not encoded:
            raise OSError(f"透過切り抜きPNGを作成できませんでした: {filename}")
        (output_dir / filename).write_bytes(buffer.tobytes())
        cutout_files.append(filename)

    return udp_objects, cutout_files
