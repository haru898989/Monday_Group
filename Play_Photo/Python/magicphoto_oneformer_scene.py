"""Offline OneFormer scene segmentation for MagicPhoto's adopted scene path.

The heavy dependencies remain lazy and the fixed, audited sky/water/plant
algorithm is unchanged.  ``analyze_objects_for_unity.py`` is the only formal
caller; the historical PoC runner is not a production entry point.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping
import gc
import hashlib
import json
import os
import time

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parent
LEGACY_MODEL_DIR = Path(
    r"C:\Users\kiich\AppData\Local\MagicPhoto\model_cache\oneformer_swin_l"
)
BUNDLED_MODEL_DIR = PROJECT_ROOT / "models" / "oneformer_swin_l"
DEFAULT_MODEL_DIR = (
    BUNDLED_MODEL_DIR if BUNDLED_MODEL_DIR.is_dir() else LEGACY_MODEL_DIR
)
TREE_CONFIDENCE_THRESHOLD = 0.6
COMPONENT_AREA_RATIO = 0.0001
UNCERTAIN_MARGIN = 0.05
WATER_CLASS_IDS = (21, 26, 60, 128, 109, 113, 104)
PLANT_CLASS_IDS = (4, 9, 17, 29, 72)
SKY_CLASS_ID = 2
TREE_CLASS_ID = 4

# The selection is locked by content rather than path.  This protects renamed
# or copied holdout images as well as the originals.
LOCKED_HOLDOUT_SHA256 = frozenset(
    {
        "f1e1df9a25f68aa6eba7c2ae94073f505c0a82b71ec0ef08f550a467010026aa",
        "d15ac352927f5f0b9b0528e635e2f181e9dcec1579382c5647140b6dcd5fa076",
        "7d34f6ee8cbc76acefac0b11b04a701eabc286e5648f43872f3c40af7cc3ddd5",
        "dc691064356f3c333b06836afe916ce27e69f38b3f8f900004e3892140743fb7",
        "e398c3528a269e9e4b675fdfa3156d39b06b1a30a42be6655c1dd60364b42dcb",
    }
)


class HoldoutImageBlockedError(RuntimeError):
    """Raised before inference when an input belongs to the locked holdout."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_not_locked_holdout(image_path: Path) -> str:
    digest = sha256_file(Path(image_path).resolve())
    if digest in LOCKED_HOLDOUT_SHA256:
        raise HoldoutImageBlockedError(
            "OneFormer test mode is forbidden for this locked holdout image "
            f"until its human ground-truth masks are complete (sha256={digest})."
        )
    return digest


def _load_oneformer_model(model_dir: Path) -> tuple[Any, Any, dict[int, str], dict[str, Any]]:
    """Load the fixed local OneFormer model without importing any PoC module."""

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    from transformers import (
        CLIPTokenizer,
        OneFormerImageProcessor,
        OneFormerForUniversalSegmentation,
        OneFormerProcessor,
    )

    started = time.perf_counter()
    processor_config = json.loads(
        (model_dir / "preprocessor_config.json").read_text(encoding="utf-8")
    )
    for unused_key in (
        "_max_size",
        "image_processor_type",
        "processor_class",
        "metadata",
        "class_names",
        "thing_ids",
        "reduce_labels",
    ):
        processor_config.pop(unused_key, None)
    processor_config["repo_path"] = str(model_dir)
    processor_config["class_info_file"] = "ade20k_panoptic.json"
    image_processor = OneFormerImageProcessor(**processor_config)
    tokenizer = CLIPTokenizer.from_pretrained(model_dir, local_files_only=True)
    processor = OneFormerProcessor(
        image_processor=image_processor,
        tokenizer=tokenizer,
    )
    model = OneFormerForUniversalSegmentation.from_pretrained(
        model_dir,
        local_files_only=True,
    )
    model.eval().to("cpu")
    labels = {int(key): str(value) for key, value in model.config.id2label.items()}
    metadata = {
        "load_seconds": float(time.perf_counter() - started),
        "parameter_count": int(
            sum(parameter.numel() for parameter in model.parameters())
        ),
        "local_model_path": str(model_dir),
        "local_model_bytes": int(
            sum(path.stat().st_size for path in model_dir.rglob("*") if path.is_file())
        ),
    }
    return processor, model, labels, metadata


def _semantic_probabilities(
    processor: Any,
    model: Any,
    image: Any,
) -> tuple[np.ndarray, dict[int, np.ndarray], dict[str, float | int]]:
    """Run fixed semantic inference and return only adopted scene class scores."""

    import torch

    preprocess_started = time.perf_counter()
    inputs = processor(images=image, task_inputs=["semantic"], return_tensors="pt")
    preprocess_seconds = time.perf_counter() - preprocess_started
    inference_started = time.perf_counter()
    with torch.inference_mode():
        outputs = model(**{key: value.to("cpu") for key, value in inputs.items()})
        class_scores = outputs.class_queries_logits.softmax(dim=-1)[..., :-1]
        mask_scores = outputs.masks_queries_logits.sigmoid()
        scores = torch.einsum("bqc,bqhw->bchw", class_scores, mask_scores)[0]
        probabilities = scores / scores.sum(dim=0, keepdim=True).clamp_min(1e-12)
        predicted = probabilities.argmax(dim=0).to(torch.int16).cpu().numpy()
        selected_ids = {SKY_CLASS_ID, *WATER_CLASS_IDS, *PLANT_CLASS_IDS}
        selected = {
            class_id: probabilities[class_id].to(torch.float32).cpu().numpy()
            for class_id in selected_ids
        }
    timing = {
        "preprocess_seconds": float(preprocess_seconds),
        "model_inference_and_scores_seconds": float(
            time.perf_counter() - inference_started
        ),
        "grid_width": int(predicted.shape[1]),
        "grid_height": int(predicted.shape[0]),
    }
    del outputs, probabilities, inputs
    gc.collect()
    return predicted, selected, timing


def _component_filter(mask: np.ndarray) -> tuple[np.ndarray, dict[str, int | float]]:
    binary = (mask > 0).astype(np.uint8)
    minimum = max(1, int(round(binary.size * COMPONENT_AREA_RATIO)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    output = np.zeros_like(binary)
    removed = 0
    for component_id in range(1, count):
        if int(stats[component_id, cv2.CC_STAT_AREA]) >= minimum:
            output[labels == component_id] = 1
        else:
            removed += 1
    return output, {
        "minimum_pixels": minimum,
        "components_before": max(0, int(count) - 1),
        "components_after": max(0, int(count) - 1 - removed),
        "removed_components": int(removed),
    }


def _resize_binary(mask: np.ndarray, width: int, height: int) -> np.ndarray:
    resized = cv2.resize(
        mask.astype(np.uint8),
        (int(width), int(height)),
        interpolation=cv2.INTER_NEAREST,
    )
    return (resized > 0).astype(np.uint8)


def _mean_probability(probability: np.ndarray, mask: np.ndarray) -> float:
    values = probability[mask > 0]
    return float(values.mean()) if values.size else 0.0


def run_fixed_oneformer_scene(
    image_bgr: np.ndarray,
    image_path: Path,
    model_dir: Path | None = None,
) -> dict[str, Any]:
    """Return fixed sky/water/plant masks without learned or color rescue.

    The input image must already have passed ``assert_not_locked_holdout``.  It
    is checked again here so direct callers cannot bypass the selection lock.
    """

    source_sha256 = assert_not_locked_holdout(image_path)
    selected_model_dir = Path(model_dir or DEFAULT_MODEL_DIR).resolve()
    if not selected_model_dir.is_dir():
        raise FileNotFoundError(f"local OneFormer model not found: {selected_model_dir}")

    # Lazy imports keep fallback runs independent of the heavy runtime and the
    # offline flags in ``_load_oneformer_model`` prevent network access.
    from PIL import Image
    # Transformers constructs OneFormer's training loss even for inference and
    # normally requires SciPy for Hungarian matching.  MagicPhoto never passes
    # training labels in this mode, so the loss is never evaluated.  Keep the
    # runtime download-free by bypassing only that constructor-time check; all
    # inference operations and weights are unchanged.
    import transformers.models.oneformer.modeling_oneformer as oneformer_modeling

    started = time.perf_counter()
    previous_requires_backends = oneformer_modeling.requires_backends

    def inference_only_requires_backends(obj: object, backends: list[str]) -> None:
        if list(backends) == ["scipy"]:
            return
        previous_requires_backends(obj, backends)

    oneformer_modeling.requires_backends = inference_only_requires_backends
    try:
        processor, model, labels, load_metadata = _load_oneformer_model(
            selected_model_dir
        )
    finally:
        oneformer_modeling.requires_backends = previous_requires_backends
    model_loaded = time.perf_counter()
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    predicted, probabilities, inference_timing = _semantic_probabilities(
        processor,
        model,
        pil_image,
    )

    raw_sky = predicted == SKY_CLASS_ID
    raw_water = np.isin(predicted, WATER_CLASS_IDS)
    raw_plant = np.isin(predicted, PLANT_CLASS_IDS)

    water_probability = np.sum(
        np.stack([probabilities[class_id] for class_id in WATER_CLASS_IDS]), axis=0
    )
    sky_probability = probabilities[SKY_CLASS_ID]
    competition = raw_sky | raw_water
    difference = sky_probability - water_probability
    uncertain = competition & (np.abs(difference) < UNCERTAIN_MARGIN)
    sky_grid = competition & ~uncertain & (difference >= 0)
    water_grid = competition & ~uncertain & (difference < 0)

    # Only tree pixels already predicted by OneFormer are thresholded.  Other
    # plant classes remain unchanged; no HSV/Lab/color/texture rescue is used.
    plant_grid = raw_plant.copy()
    low_tree = (predicted == TREE_CLASS_ID) & (
        probabilities[TREE_CLASS_ID] < TREE_CONFIDENCE_THRESHOLD
    )
    plant_grid[low_tree] = False

    height, width = image_bgr.shape[:2]
    grids = {"sky": sky_grid, "water": water_grid, "plant": plant_grid}
    masks: dict[str, np.ndarray] = {}
    category_details: dict[str, dict[str, Any]] = {}
    for category, grid in grids.items():
        original = _resize_binary(grid, width, height)
        filtered, component_stats = _component_filter(original)
        masks[category] = (filtered * 255).astype(np.uint8)
        if category == "sky":
            category_probability = sky_probability
        elif category == "water":
            category_probability = water_probability
        else:
            selected_probability = np.zeros_like(sky_probability)
            for class_id in PLANT_CLASS_IDS:
                pixels = predicted == class_id
                selected_probability[pixels] = probabilities[class_id][pixels]
            category_probability = selected_probability
        category_details[category] = {
            "area_pixels": int(np.count_nonzero(filtered)),
            "area_ratio": float(np.count_nonzero(filtered) / max(1, filtered.size)),
            "mean_confidence_grid": _mean_probability(category_probability, grid),
            "component_filter": component_stats,
        }

    class_details = []
    for class_id in (SKY_CLASS_ID, *WATER_CLASS_IDS, *PLANT_CLASS_IDS):
        class_grid = predicted == class_id
        class_details.append(
            {
                "source_class_id": int(class_id),
                "source_class": str(labels.get(class_id, f"class_{class_id}")),
                "mean_confidence": _mean_probability(probabilities[class_id], class_grid),
                "grid_area_ratio": float(class_grid.mean()),
                "magicphoto_category": (
                    "sky" if class_id == SKY_CLASS_ID
                    else "water" if class_id in WATER_CLASS_IDS
                    else "plant"
                ),
            }
        )

    return {
        "masks": masks,
        "source_sha256": source_sha256,
        "model_dir": str(selected_model_dir),
        "model_id": "shi-labs/oneformer_ade20k_swin_large",
        "pretrained_dataset": "ADE20K",
        "tree_confidence_threshold": TREE_CONFIDENCE_THRESHOLD,
        "component_area_ratio": COMPONENT_AREA_RATIO,
        "uncertain_margin": UNCERTAIN_MARGIN,
        "color_texture_rescue_used": False,
        "additional_training_used": False,
        "scipy_training_loss_check_bypassed_for_inference_only": True,
        "water_class_ids": list(WATER_CLASS_IDS),
        "plant_class_ids": list(PLANT_CLASS_IDS),
        "class_details": class_details,
        "category_details": category_details,
        "uncertain_area_ratio": float(uncertain.mean()),
        "timing_seconds": {
            "model_load": float(model_loaded - started),
            "preprocess": float(inference_timing["preprocess_seconds"]),
            "inference_and_scores": float(
                inference_timing["model_inference_and_scores_seconds"]
            ),
            "total": float(time.perf_counter() - started),
        },
        "model_metadata": load_metadata,
    }
