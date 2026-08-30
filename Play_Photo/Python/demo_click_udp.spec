# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import torch
from PyInstaller.utils.hooks import collect_data_files


python_dir = Path(SPECPATH).resolve()
checkpoint_dir = Path(torch.hub.get_dir()) / "checkpoints"

required_data = [
    (python_dir / "yolov8s-world.pt", "."),
    (
        checkpoint_dir / "deeplabv3_resnet50_coco-cd0a2569.pth",
        "torch/hub/checkpoints",
    ),
    (
        checkpoint_dir / "big-lama.pt",
        "torch/hub/checkpoints",
    ),
]

for source_path, _ in required_data:
    if not source_path.is_file():
        raise SystemExit(f"Required model file was not found: {source_path}")

datas = [(str(source), destination) for source, destination in required_data]
binaries = []
datas += collect_data_files("clip")
datas += collect_data_files("ultralytics")
datas += collect_data_files("simple_lama_inpainting")
hiddenimports = [
    "simple_lama_inpainting.models.model",
    "simple_lama_inpainting.utils.util",
    "torchvision.models.segmentation",
    "ultralytics.models",
    "ultralytics.nn.tasks",
    "ultralytics.utils",
]


a = Analysis(
    [str(python_dir / "demo_click_udp.py")],
    pathex=[str(python_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "IPython",
        "h5py",
        "imageio",
        "jupyter",
        "moviepy",
        "notebook",
        "openpyxl",
        "pandas",
        "pygame",
        "ray",
        "statsmodels",
        "tensorflow",
        "torchdata",
        "triton",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="demo_click_udp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="demo_click_udp",
)
