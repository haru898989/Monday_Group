#!/usr/bin/env python
"""Download the pretrained model files required by MagicPhoto.

Run this once from the project directory after installing requirements.txt:

    python download_models.py

Files are downloaded from their original public model repositories and placed
in the paths expected by the existing MagicPhoto source code.
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


PROJECT_ROOT = Path(__file__).resolve().parent
ONEFORMER_DIR = PROJECT_ROOT / "models" / "oneformer_swin_l"
CLIP_DIR = PROJECT_ROOT / "weights" / "clip"
CLIP_FILE = CLIP_DIR / "ViT-B-32.pt"
TORCH_HOME = PROJECT_ROOT / "weights" / "torch"
DEEPLAB_FILE = TORCH_HOME / "hub" / "checkpoints" / "deeplabv3_resnet50_coco-cd0a2569.pth"
YOLO_FILE = PROJECT_ROOT / "yolov8s-world.pt"

ONEFORMER_REPO = "shi-labs/oneformer_ade20k_swin_large"
ONEFORMER_REQUIRED_FILES = (
    "ade20k_panoptic.json",
    "config.json",
    "merges.txt",
    "preprocessor_config.json",
    "pytorch_model.bin",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "vocab.json",
)


def dependency_error(package: str, _error: ModuleNotFoundError) -> RuntimeError:
    requirements = PROJECT_ROOT / "requirements.txt"
    return RuntimeError(
        f"必要なパッケージ '{package}' がありません。先に次を実行してください:\n"
        f'  {sys.executable} -m pip install -r "{requirements}"'
    )


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def download_oneformer() -> None:
    missing = [name for name in ONEFORMER_REQUIRED_FILES if not (ONEFORMER_DIR / name).is_file()]
    if not missing:
        print(f"[skip] OneFormer: {ONEFORMER_DIR}")
        return

    try:
        from huggingface_hub import snapshot_download
    except ModuleNotFoundError as error:
        raise dependency_error("huggingface-hub", error)

    print(f"[download] OneFormer ({ONEFORMER_REPO})")
    ONEFORMER_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=ONEFORMER_REPO,
        local_dir=ONEFORMER_DIR,
        allow_patterns=list(ONEFORMER_REQUIRED_FILES),
    )

    still_missing = [name for name in ONEFORMER_REQUIRED_FILES if not (ONEFORMER_DIR / name).is_file()]
    if still_missing:
        raise RuntimeError(f"OneFormerの取得が不完全です: {', '.join(still_missing)}")
    print(f"[done] OneFormer: {ONEFORMER_DIR}")


def download_clip() -> None:
    if CLIP_FILE.is_file():
        print(f"[skip] CLIP: {CLIP_FILE}")
        return

    try:
        import clip
    except ModuleNotFoundError as error:
        raise dependency_error("clip", error)

    print("[download] CLIP ViT-B/32")
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    model, _ = clip.load("ViT-B/32", device="cpu", download_root=str(CLIP_DIR))
    del model
    gc.collect()

    if not CLIP_FILE.is_file():
        raise RuntimeError(f"CLIPの保存先を確認できません: {CLIP_FILE}")
    print(f"[done] CLIP: {CLIP_FILE}")


def download_deeplab() -> None:
    if DEEPLAB_FILE.is_file():
        print(f"[skip] DeepLabV3: {DEEPLAB_FILE}")
        return

    # torchvision reads TORCH_HOME when resolving its download/cache path.
    os.environ["TORCH_HOME"] = str(TORCH_HOME)
    try:
        from torchvision.models.segmentation import (
            DeepLabV3_ResNet50_Weights,
            deeplabv3_resnet50,
        )
    except ModuleNotFoundError as error:
        raise dependency_error("torchvision", error)

    print("[download] DeepLabV3 ResNet50")
    model = deeplabv3_resnet50(weights=DeepLabV3_ResNet50_Weights.DEFAULT)
    del model
    gc.collect()

    if not DEEPLAB_FILE.is_file():
        raise RuntimeError(f"DeepLabV3の保存先を確認できません: {DEEPLAB_FILE}")
    print(f"[done] DeepLabV3: {DEEPLAB_FILE}")


def download_yolo() -> None:
    if YOLO_FILE.is_file():
        print(f"[skip] YOLO-World: {YOLO_FILE}")
        return

    try:
        from ultralytics import YOLO
    except ModuleNotFoundError as error:
        raise dependency_error("ultralytics", error)

    print("[download] YOLOv8s-World")
    # Ultralytics saves a named official model in the current directory.
    with working_directory(PROJECT_ROOT):
        model = YOLO(YOLO_FILE.name)
    del model
    gc.collect()

    if not YOLO_FILE.is_file():
        raise RuntimeError(f"YOLO-Worldの保存先を確認できません: {YOLO_FILE}")
    print(f"[done] YOLO-World: {YOLO_FILE}")


DOWNLOADERS = {
    "oneformer": download_oneformer,
    "clip": download_clip,
    "deeplab": download_deeplab,
    "yolo": download_yolo,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MagicPhoto用の学習済みモデルを取得します。")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=tuple(DOWNLOADERS),
        metavar="MODEL",
        help="指定したモデルだけ取得します: oneformer clip deeplab yolo",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected = args.only or list(DOWNLOADERS)

    if sys.version_info >= (3, 14):
        print(
            "[warning] Python 3.14では一部の機械学習パッケージが未対応の可能性があります。"
            "問題が出る場合はPython 3.12を使用してください。"
        )

    print(f"保存先: {PROJECT_ROOT}")
    try:
        for name in selected:
            DOWNLOADERS[name]()
    except Exception as error:
        print(f"[error] {error}", file=sys.stderr)
        return 1

    print("すべての指定モデルを準備できました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
