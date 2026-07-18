"""Magic Photo Museum: Unity向けUDP送信。

現在のReseiver.csが受け取れるlegacy形式を標準にし、
将来MagicBrain形式へ切り替えられるよう送信処理を分離する。
"""
from __future__ import annotations

import json
import socket
from typing import Any, Iterable

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1140


def _legacy_payload(objects: Iterable[Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for obj in objects:
        x1, y1, x2, y2 = obj.box
        rows.append(
            {
                "name": str(obj.name),
                "x1": float(x1),
                "y1": float(y1),
                "x2": float(x2),
                "y2": float(y1),
                "x3": float(x1),
                "y3": float(y2),
                "x4": float(x2),
                "y4": float(y2),
            }
        )
    return {"objects": rows}


def build_payload(
    objects: Iterable[Any],
    brain_result: dict[str, Any] | None = None,
    mode: str = "legacy",
) -> dict[str, Any]:
    """Unityへ送る辞書を作る。

    legacy:
        現在のReseiver.cs互換。
    magic_brain:
        将来、Unity側をMagicBrain JSON対応にした後で使用する。
    """
    if mode == "legacy":
        return _legacy_payload(objects)
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
) -> int:
    """JSONをUDPでUnityへ送信し、送信バイト数を返す。"""
    payload = build_payload(objects, brain_result, mode)
    data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        return sock.sendto(data, (host, port))
