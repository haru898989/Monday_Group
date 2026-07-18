"""
Unity向け・物体検出 + UDP送信
--------------------------------
必要なファイル:
- このファイル
- ml_detector.py
- 解析画像（例: sample.jpg）

実行例:
python analyze_objects_for_unity.py sample.jpg --mode accuracy
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path

import cv2
import numpy as np

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from ml_detector import MagicPhotoDetector


UNITY_IP = "127.0.0.1"
UNITY_PORT = 1140


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="画像を解析して、物体名と座標をUnityへUDP送信します。"
    )
    parser.add_argument("image_path", help="解析する画像ファイル")
    parser.add_argument(
        "--mode",
        choices=("standard", "accuracy", "auto"),
        default="accuracy",
        help="互換用の引数です。",
    )
    return parser.parse_args()


def resolve_image_path(image_path_text: str) -> Path:
    image_path = Path(image_path_text)
    if not image_path.is_absolute():
        image_path = CURRENT_DIR / image_path
    return image_path.resolve()


def imread_unicode(path: Path):
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except Exception:
        return None


def create_detector(mode: str) -> MagicPhotoDetector:
    if mode == "accuracy":
        confidence = 0.20
    elif mode == "standard":
        confidence = 0.30
    else:
        confidence = 0.20

    return MagicPhotoDetector(confidence=confidence)


def build_payload(objects, image_path: Path, width: int, height: int) -> dict:
    unity_objects = []

    for index, obj in enumerate(objects):
        x1, y1, x2, y2 = (int(value) for value in obj.box)

        box_width = max(1, x2 - x1)
        box_height = max(1, y2 - y1)

        unity_objects.append(
            {
                "object_id": f"object_{index:03d}",
                "name": str(obj.name),
                "confidence": float(obj.confidence),
                "position_original": {
                    "center": [
                        int((x1 + x2) / 2),
                        int((y1 + y2) / 2),
                    ],
                    "detection_box": {
                        "x": x1,
                        "y": y1,
                        "width": box_width,
                        "height": box_height,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                    "mask_box": {
                        "x": x1,
                        "y": y1,
                        "width": box_width,
                        "height": box_height,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                    },
                },
                "four_corners_original": {
                    "top_left": [x1, y1],
                    "top_right": [x2, y1],
                    "bottom_right": [x2, y2],
                    "bottom_left": [x1, y2],
                },
            }
        )

    return {
        "schema_version": "unity_objects_1.0",
        "image": {
            "path": str(image_path),
            "width": int(width),
            "height": int(height),
        },
        "object_count": len(unity_objects),
        "objects": unity_objects,
    }


def send_to_unity(payload: dict) -> None:
    json_text = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    encoded = json_text.encode("utf-8")

    if len(encoded) > 60000:
        raise ValueError(
            f"UDP送信データが大きすぎます: {len(encoded)} bytes"
        )

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(encoded, (UNITY_IP, UNITY_PORT))

    print(
        f"UnityへUDP送信しました: "
        f"{payload['object_count']}個 / "
        f"{len(encoded)} bytes / "
        f"{UNITY_IP}:{UNITY_PORT}",
        flush=True,
    )


def main() -> None:
    args = parse_args()
    image_path = resolve_image_path(args.image_path)

    print("analyze_objects_for_unity.pyを開始しました", flush=True)
    print(f"入力画像: {image_path}", flush=True)
    print(f"検出モード: {args.mode}", flush=True)

    if not image_path.exists():
        raise FileNotFoundError(
            f"解析画像が見つかりません: {image_path}"
        )

    image = imread_unicode(image_path)

    if image is None or image.size == 0:
        raise ValueError(
            f"画像を読み込めませんでした: {image_path}"
        )

    height, width = image.shape[:2]
    print(
        f"入力画像サイズ: width={width}, height={height}",
        flush=True,
    )

    detector = create_detector(args.mode)

    print("AIが画像を解析中です...", flush=True)
    objects = detector.detect_from_image(image)

    print(f"検出物体数: {len(objects)}", flush=True)

    for obj in objects:
        print(
            f"- name={obj.name}, "
            f"confidence={obj.confidence:.3f}, "
            f"box={obj.box}",
            flush=True,
        )

    payload = build_payload(
        objects,
        image_path,
        width,
        height,
    )

    json_path = CURRENT_DIR / "analysis_result.json"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON保存先: {json_path}", flush=True)

    send_to_unity(payload)


if __name__ == "__main__":
    main()
