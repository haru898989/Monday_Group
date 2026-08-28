"""Magic Photo Museum: Unity向けUDP送信。

現在のReseiver.csが受け取れるlegacy形式を標準にし、
将来MagicBrain形式へ切り替えられるよう送信処理を分離する。
"""
from __future__ import annotations

import json
import socket
from typing import Any, Iterable, Sequence

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1140


def _legacy_name_and_box(obj: Any) -> tuple[Any, Any]:
    """legacy送信用に物体名と4辺の座標を取り出す。"""
    if isinstance(obj, tuple) and len(obj) == 2:
        detection, mask_result = obj
        return detection.name, mask_result.mask_box

    detection = getattr(obj, "detected", None)
    mask_result = getattr(obj, "mask_result", None)
    if detection is not None and mask_result is not None:
        return detection.name, mask_result.mask_box

    return obj.name, obj.box


def _legacy_payload(
    objects: Iterable[Any],
    cutout_files: Sequence[str] | None = None,
    image_width: int = 0,
    image_height: int = 0,
) -> dict[str, Any]:
    object_list = list(objects)
    cutout_list = list(cutout_files or [])
    rows: list[dict[str, Any]] = []
    for index, obj in enumerate(object_list):
        name, box = _legacy_name_and_box(obj)
        x1, y1, x2, y2 = box
        row = {
            "name": str(name),
            "x1": float(x1),
            "y1": float(y1),
            "x2": float(x2),
            "y2": float(y1),
            "x3": float(x1),
            "y3": float(y2),
            "x4": float(x2),
            "y4": float(y2),
        }
        if cutout_files is not None or image_width or image_height:
            row["cutoutFileName"] = (
                cutout_list[index] if index < len(cutout_list) else ""
            )
        rows.append(row)

    if cutout_files is not None or image_width or image_height:
        return {
            "imageWidth": int(image_width),
            "imageHeight": int(image_height),
            "objects": rows,
        }
    return {"objects": rows}


def build_payload(
    objects: Iterable[Any],
    brain_result: dict[str, Any] | None = None,
    mode: str = "legacy",
    *,
    cutout_files: Sequence[str] | None = None,
    image_width: int = 0,
    image_height: int = 0,
) -> dict[str, Any]:
    """Unityへ送る辞書を作る。

    legacy:
        現在のReseiver.cs互換。
    magic_brain:
        将来、Unity側をMagicBrain JSON対応にした後で使用する。
    """
    if mode == "legacy":
        return _legacy_payload(
            objects,
            cutout_files=cutout_files,
            image_width=image_width,
            image_height=image_height,
        )
    if mode == "magic_brain":
        if brain_result is None:
            raise ValueError("magic_brainモードにはbrain_resultが必要です。")
        return brain_result
    raise ValueError(f"未対応のUDP送信モードです: {mode}")


def send_to_unity(
    objects: Iterable[Any],
    brain_result: dict[str, Any] | None = None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    mode: str = "legacy",
    cutout_files: Sequence[str] | None = None,
    image_width: int = 0,
    image_height: int = 0,
) -> int:
    """JSONをUDPでUnityへ送信し、送信バイト数を返す。"""
    payload = build_payload(
        objects,
        brain_result,
        mode,
        cutout_files=cutout_files,
        image_width=image_width,
        image_height=image_height,
    )
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        return sock.sendto(data, (host, port))
