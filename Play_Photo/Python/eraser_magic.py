"""AI detection/segmentation based object removal (eraser magic).

``analyze_objects_for_unity.py`` の正式解析を使って物体とマスクを取得し、
選択した物体の領域を背景補完します。入力画像は上書きせず、出力は固定先へ更新します。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
from pathlib import Path
from typing import Iterable, Sequence

import cv2
import numpy as np

from analyze_objects_for_unity import (
    DEFAULT_SCENE_SEGMENTATION,
    analyze_image,
    make_output_paths,
    try_grabcut_mask,
    update_mask_result_from_mask,
)
from ml_detector_complete import imread_unicode, imwrite_unicode


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PERSON_CLASSES = {"person", "human", "man", "woman", "child"}
PERSON_PART_CLASSES = DEFAULT_PERSON_CLASSES | {"face", "hand"}
BACKGROUND_CLASSES = {
    "background", "sky", "cloud", "ground", "road", "pavement", "grass",
    "water", "sea", "ocean", "river", "lake", "pond", "mountain", "wall",
    "city",
}


def parse_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def resolve_path(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else SCRIPT_DIR / path).resolve()


def clear_output_files(directory: Path, protected_path: Path) -> None:
    """前回出力したファイルを削除し、入力画像だけは必ず保護します。"""
    directory.mkdir(parents=True, exist_ok=True)
    protected = protected_path.resolve()
    for path in directory.iterdir():
        if path.is_file() and path.resolve() != protected:
            path.unlink()


def ensure_inpaint_backend(method: str) -> None:
    """Fail before model detection when an optional backend is unavailable."""
    if method != "lama":
        return
    if importlib.util.find_spec("simple_lama_inpainting") is None:
        raise SystemExit(
            "ERROR: simple-lama-inpainting is not installed in this Python.\n"
            "For Python 3.14, run this command first:\n"
            "  python -m pip install simple-lama-inpainting==0.1.2 --no-deps\n"
            "Then run eraser_magic.py again."
        )


def select_objects(
    objects: Sequence,
    classes: set[str],
    object_ids: set[str],
    remove_all: bool,
    include_background: bool,
) -> list:
    selected = []
    for item in objects:
        detected_names = {
            str(item.detected.name).lower(),
            str(item.detected.canonical_name).lower(),
            str(item.detected.original_name).lower(),
        }
        is_background = bool(BACKGROUND_CLASSES & detected_names)
        all_match = remove_all and (include_background or not is_background)
        if all_match or item.object_id in object_ids or classes & detected_names:
            selected.append(item)
    return selected


def refine_selected_fallback_masks(image: np.ndarray, selected: Sequence) -> None:
    """Estimate outlines for selected fallback boxes on a reduced image."""
    height, width = image.shape[:2]
    max_side = max(height, width)
    scale = min(1.0, 720.0 / max(1, max_side))
    if scale < 1.0:
        work = cv2.resize(
            image,
            (max(2, round(width * scale)), max(2, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        work = image

    for item in selected:
        result = item.mask_result
        if result.mask_source != "box_fallback":
            continue
        x1, y1, x2, y2 = result.detection_box
        scaled_box = (
            round(x1 * scale),
            round(y1 * scale),
            round(x2 * scale),
            round(y2 * scale),
        )
        estimated = try_grabcut_mask(work, scaled_box)
        if estimated is None:
            continue
        if estimated.shape != (height, width):
            estimated = cv2.resize(
                estimated, (width, height), interpolation=cv2.INTER_NEAREST
            )
        update_mask_result_from_mask(
            result,
            estimated,
            "grabcut_scaled_box",
            "deeplab unsupported; outline estimated by scaled grabcut",
        )


def refine_selected_masks_with_sam(
    image: np.ndarray,
    selected: Sequence,
    model_name: str,
) -> int:
    """Replace coarse YOLO/DeepLab masks with SAM2 prompted masks."""
    if not selected or not model_name:
        return 0
    try:
        from ultralytics import SAM
    except ImportError:
        print("SAM2 unavailable; keeping DeepLab/GrabCut masks.")
        return 0

    boxes = [list(item.mask_result.detection_box) for item in selected]
    try:
        sam = SAM(model_name)
        predictions = sam(image, bboxes=boxes, verbose=False)
    except Exception as exc:
        print(f"SAM2 failed; keeping existing masks: {exc}")
        return 0
    if not predictions or predictions[0].masks is None:
        return 0

    masks = predictions[0].masks.data.cpu().numpy()
    if len(masks) != len(selected):
        print(
            f"SAM2 mask count mismatch ({len(masks)} != {len(selected)}); "
            "keeping existing masks."
        )
        return 0

    height, width = image.shape[:2]
    updated = 0
    for item, predicted in zip(selected, masks):
        binary = np.where(predicted > 0.5, 255, 0).astype(np.uint8)
        if binary.shape != (height, width):
            binary = cv2.resize(
                binary, (width, height), interpolation=cv2.INTER_NEAREST
            )
        if np.count_nonzero(binary) < 12:
            continue
        update_mask_result_from_mask(
            item.mask_result,
            binary,
            f"sam2:{model_name}",
            None,
        )
        updated += 1
    print(f"SAM2 refined masks: {updated}/{len(selected)}")
    return updated


def combine_and_expand_masks(
    selected: Iterable,
    image_shape: tuple[int, ...],
    expansion: int,
    close_size: int,
) -> tuple[np.ndarray, list[dict[str, object]]]:
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    details: list[dict[str, object]] = []
    for item in selected:
        object_mask = np.where(item.mask > 0, 255, 0).astype(np.uint8)
        mask = cv2.bitwise_or(mask, object_mask)
        details.append({
            "object_id": item.object_id,
            "name": item.detected.name,
            "canonical_name": item.detected.canonical_name,
            "confidence": float(item.detected.confidence),
            "mask_source": item.mask_result.mask_source,
            "area_pixels": int(np.count_nonzero(object_mask)),
        })

    if close_size > 0:
        size = close_size if close_size % 2 == 1 else close_size + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    if expansion > 0:
        size = expansion * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        mask = cv2.dilate(mask, kernel, iterations=1)
    return mask, details


def build_person_cleanup_mask(
    selected: Sequence,
    image_shape: tuple[int, ...],
    expansion: int,
) -> np.ndarray:
    """Build a wider second-pass mask around people and visible body parts."""
    cleanup = np.zeros(image_shape[:2], dtype=np.uint8)
    for item in selected:
        names = {
            str(item.detected.name).lower(),
            str(item.detected.canonical_name).lower(),
            str(item.detected.original_name).lower(),
        }
        if not (names & PERSON_PART_CLASSES):
            continue
        cleanup = cv2.bitwise_or(
            cleanup,
            np.where(item.mask > 0, 255, 0).astype(np.uint8),
        )
    if expansion > 0 and np.any(cleanup):
        size = expansion * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
        cleanup = cv2.dilate(cleanup, kernel, iterations=1)
    return cleanup


def patch_refine_background(
    image: np.ndarray,
    cleanup_mask: np.ndarray,
) -> np.ndarray:
    """Copy coherent sharp patches from valid surroundings with Shift-Map."""
    xphoto = getattr(cv2, "xphoto", None)
    if xphoto is None or not hasattr(xphoto, "inpaint"):
        print(
            "Shift-Map patch refinement unavailable "
            "(opencv-contrib xphoto is not installed)."
        )
        return image
    if not np.any(cleanup_mask):
        return image

    # xphoto uses the opposite convention: non-zero means a valid/source pixel.
    valid_mask = np.where(cleanup_mask > 0, 0, 255).astype(np.uint8)
    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    try:
        patched_lab = np.empty_like(lab)
        inpaint_result = xphoto.inpaint(
            lab,
            valid_mask,
            patched_lab,
            xphoto.INPAINT_SHIFTMAP,
        )
        if inpaint_result is not None:
            patched_lab = inpaint_result
        if patched_lab is None or patched_lab.shape != lab.shape:
            return image
        patched = cv2.cvtColor(patched_lab, cv2.COLOR_LAB2BGR)
    except Exception as exc:
        print(f"Shift-Map patch refinement skipped: {exc}")
        return image

    result = image.copy()
    result[cleanup_mask > 0] = patched[cleanup_mask > 0]
    print("Shift-Map copied sharp surrounding patches into person areas.")
    return result


def safe_filename(value: str) -> str:
    text = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_"
        for char in str(value).strip()
    )
    return text.strip("_") or "object"


def save_color_cutouts(
    image: np.ndarray,
    selected: Sequence,
    output_dir: Path,
) -> dict[str, str]:
    """Save every selected object as a cropped, full-color transparent PNG."""
    cutout_dir = output_dir / "cutouts"
    cutout_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, str] = {}

    for item in selected:
        alpha = np.where(item.mask > 0, 255, 0).astype(np.uint8)
        points = cv2.findNonZero(alpha)
        if points is None:
            continue
        x, y, width, height = cv2.boundingRect(points)
        color_crop = image[y:y + height, x:x + width]
        alpha_crop = alpha[y:y + height, x:x + width]
        cutout = cv2.cvtColor(color_crop, cv2.COLOR_BGR2BGRA)
        cutout[:, :, 3] = alpha_crop
        filename = (
            f"{item.object_id}_{safe_filename(item.detected.name)}.png"
        )
        path = cutout_dir / filename
        if not imwrite_unicode(str(path), cutout):
            raise OSError(f"Could not save color cutout: {path}")
        saved[item.object_id] = str(path)
    return saved


def inpaint_background(
    image: np.ndarray,
    mask: np.ndarray,
    radius: float,
    method: str,
    lama_passes: int = 4,
) -> np.ndarray:
    """Reconstruct masked pixels and softly blend their boundary."""
    if method == "lama":
        try:
            from PIL import Image
            from simple_lama_inpainting import SimpleLama
        except ImportError as exc:
            raise RuntimeError(
                "LaMa背景生成に必要なパッケージがありません。"
                "同じPython環境で `pip install simple-lama-inpainting` を実行してください。"
            ) from exc

        source_height, source_width = image.shape[:2]
        lama = SimpleLama()
        working = image.copy()
        remaining = np.where(mask > 0, 255, 0).astype(np.uint8)
        pass_count = max(1, int(lama_passes))

        for pass_index in range(pass_count):
            print(f"LaMa progressive pass: {pass_index + 1}/{pass_count}")
            rgb = cv2.cvtColor(working, cv2.COLOR_BGR2RGB)
            generated_pil = lama(
                Image.fromarray(rgb),
                Image.fromarray(remaining).convert("L"),
            )
            generated_rgb = np.asarray(generated_pil.convert("RGB"))
            generated_height, generated_width = generated_rgb.shape[:2]
            if (
                generated_height >= source_height
                and generated_width >= source_width
            ):
                generated_rgb = generated_rgb[:source_height, :source_width]
            elif generated_rgb.shape[:2] != (source_height, source_width):
                generated_rgb = cv2.resize(
                    generated_rgb,
                    (source_width, source_height),
                    interpolation=cv2.INTER_CUBIC,
                )
            generated = cv2.cvtColor(generated_rgb, cv2.COLOR_RGB2BGR)

            if pass_index == pass_count - 1:
                fill_region = remaining > 0
            else:
                distance = cv2.distanceTransform(
                    remaining, cv2.DIST_L2, cv2.DIST_MASK_PRECISE
                )
                maximum_distance = float(distance.max())
                if maximum_distance <= 1.0:
                    fill_region = remaining > 0
                else:
                    passes_left = pass_count - pass_index
                    band_width = max(6.0, maximum_distance / passes_left)
                    fill_region = (remaining > 0) & (distance <= band_width)

            working[fill_region] = generated[fill_region]
            remaining[fill_region] = 0
            if not np.any(remaining):
                break

        generated = working
        # Transfer real high-frequency texture from the surrounding source into
        # the generated area. LaMa predicts the large background structure;
        # this pass restores local soil/grass/water detail instead of blurring it.
        source_float = image.astype(np.float32)
        source_base = cv2.GaussianBlur(source_float, (0, 0), sigmaX=2.0)
        source_detail = source_float - source_base
        encoded_detail = np.clip(source_detail + 128.0, 0, 255).astype(np.uint8)
        propagated_detail = cv2.inpaint(
            encoded_detail,
            mask,
            3.0,
            cv2.INPAINT_TELEA,
        ).astype(np.float32) - 128.0
        detailed = np.clip(
            generated.astype(np.float32) + propagated_detail * 0.72,
            0,
            255,
        ).astype(np.uint8)

        # Keep the source pixel-perfect outside the mask. The expanded mask
        # already covers object-edge remnants, so no blurred alpha blend is used.
        result = image.copy()
        result[mask > 0] = detailed[mask > 0]
        return result

    flag = cv2.INPAINT_TELEA if method == "telea" else cv2.INPAINT_NS
    reconstructed = cv2.inpaint(image, mask, max(1.0, radius), flag)

    # A second, complementary pass reduces directional streaks on wider holes.
    second_flag = cv2.INPAINT_NS if flag == cv2.INPAINT_TELEA else cv2.INPAINT_TELEA
    second = cv2.inpaint(reconstructed, mask, max(1.0, radius * 0.65), second_flag)
    reconstructed = cv2.addWeighted(reconstructed, 0.55, second, 0.45, 0)

    # Feather only the replacement boundary; pixels outside the mask remain intact.
    soft_mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(0.8, radius * 0.35))
    alpha = (soft_mask.astype(np.float32) / 255.0)[..., None]
    return np.clip(
        image.astype(np.float32) * (1.0 - alpha)
        + reconstructed.astype(np.float32) * alpha,
        0,
        255,
    ).astype(np.uint8)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YOLO/DeepLabで検出した物体を消し、背景を補完します。"
    )
    parser.add_argument("image", help="入力画像（例: sample.jpg）")
    parser.add_argument("--output-dir", default="eraser_magic_output")
    parser.add_argument(
        "--classes",
        default=",".join(sorted(DEFAULT_PERSON_CLASSES)),
        help="消すクラス名。カンマ区切り（初期値: 人物系）",
    )
    parser.add_argument("--object-ids", default="", help="object_0001等をカンマ区切り")
    parser.add_argument("--all", action="store_true", help="検出した全物体を消す")
    parser.add_argument(
        "--include-background",
        action="store_true",
        help="--all使用時に地面・空・水面などの背景領域も含める（通常は非推奨）",
    )
    parser.add_argument("--mode", choices=("standard", "accuracy", "auto"), default="standard")
    parser.add_argument(
        "--scene-segmentation",
        choices=(DEFAULT_SCENE_SEGMENTATION, "existing"),
        default=DEFAULT_SCENE_SEGMENTATION,
        help="analyze_objects_for_unity.pyで使うscene処理",
    )
    parser.add_argument(
        "--oneformer-fallback",
        choices=("existing", "error"),
        default="existing",
        help="OneFormerを使えない場合の動作",
    )
    parser.add_argument(
        "--oneformer-model-dir",
        default=None,
        help="ローカルOneFormerモデルフォルダ（通常は指定不要）",
    )
    parser.add_argument("--expand", type=int, default=10, help="マスクを外側へ広げるpx数")
    parser.add_argument("--close-size", type=int, default=7, help="マスク内の小さな穴を閉じるサイズ")
    parser.add_argument("--radius", type=float, default=5.0, help="背景補完の探索半径")
    parser.add_argument(
        "--method",
        choices=("lama", "telea", "ns"),
        default="lama",
        help="背景補完方式。大きな消去領域にはlamaを推奨（初期値: lama）",
    )
    parser.add_argument(
        "--lama-passes",
        type=int,
        default=4,
        help="LaMaを外周から段階生成する回数。品質優先は4～6（初期値: 4）",
    )
    parser.add_argument(
        "--sam-model",
        default="sam2.1_t.pt",
        help="輪郭精密化に使うSAM2モデル（初期値: sam2.1_t.pt）",
    )
    parser.add_argument(
        "--no-sam",
        action="store_true",
        help="SAM2輪郭精密化を無効にする",
    )
    parser.add_argument(
        "--person-cleanup-expand",
        type=int,
        default=24,
        help="人物残像を再補完する追加範囲px（初期値: 24）",
    )
    parser.add_argument(
        "--no-person-cleanup",
        action="store_true",
        help="人物領域のLaMa第2補完を無効にする",
    )
    parser.add_argument(
        "--no-patch-refine",
        action="store_true",
        help="周辺実画像からのShift-Mapパッチ転写を無効にする",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    ensure_inpaint_backend(args.method)
    started = time.perf_counter()
    image_path = resolve_path(args.image)
    output_dir = resolve_path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    analysis_dir = output_dir / "analysis"
    analysis_paths = make_output_paths(
        str(analysis_dir),
        "analysis_result.json",
        "result.jpg",
    )
    cutout_dir = output_dir / "cutouts"
    clear_output_files(analysis_paths.mask_dir, image_path)
    clear_output_files(cutout_dir, image_path)

    image = imread_unicode(str(image_path))
    if image is None or image.size == 0:
        raise FileNotFoundError(f"画像を読み込めません: {image_path}")

    # 正式なUnity向け解析を実行し、その採用済み検出・マスクを消去処理でも使います。
    analysis = analyze_image(
        image_path=image_path,
        detection_mode=args.mode,
        paths=analysis_paths,
        scene_segmentation=args.scene_segmentation,
        oneformer_fallback=args.oneformer_fallback,
        oneformer_model_dir=args.oneformer_model_dir,
    )

    selected = select_objects(
        analysis.objects,
        parse_csv(args.classes),
        parse_csv(args.object_ids),
        args.all,
        args.include_background,
    )
    if not selected:
        detected = ", ".join(
            f"{item.object_id}:{item.detected.name}" for item in analysis.objects
        ) or "なし"
        raise RuntimeError(
            "消去対象が見つかりません。--classes、--object-ids、または --all を確認してください。"
            f" 検出結果: {detected}"
        )

    if not args.no_sam:
        refine_selected_masks_with_sam(image, selected, args.sam_model)

    # If SAM2 is disabled or failed, remaining box masks use lightweight GrabCut.
    refine_selected_fallback_masks(image, selected)
    cutout_paths = save_color_cutouts(image, selected, output_dir)

    mask, removed = combine_and_expand_masks(
        selected,
        image.shape,
        max(0, args.expand),
        max(0, args.close_size),
    )
    for item in removed:
        item["color_cutout"] = cutout_paths.get(str(item["object_id"]))
    result = inpaint_background(
        image, mask, args.radius, args.method, args.lama_passes
    )
    person_cleanup_mask = build_person_cleanup_mask(
        selected,
        image.shape,
        max(0, args.person_cleanup_expand),
    )
    if (
        args.method == "lama"
        and not args.no_person_cleanup
        and np.any(person_cleanup_mask)
    ):
        print("LaMa person-overlap cleanup pass")
        result = inpaint_background(
            result,
            person_cleanup_mask,
            args.radius,
            args.method,
            max(2, args.lama_passes // 2),
        )
    if not args.no_patch_refine and np.any(person_cleanup_mask):
        result = patch_refine_background(result, person_cleanup_mask)

    result_path = output_dir / f"{image_path.stem}_erased.png"
    mask_path = output_dir / f"{image_path.stem}_erase_mask.png"
    if not imwrite_unicode(str(result_path), result):
        raise OSError(f"結果画像を保存できません: {result_path}")
    if not imwrite_unicode(str(mask_path), mask):
        raise OSError(f"マスクを保存できません: {mask_path}")

    metadata = {
        "source_image": str(image_path),
        "source_image_overwritten": False,
        "result_image": str(result_path),
        "erase_mask": str(mask_path),
        "analysis_entrypoint": "analyze_objects_for_unity.py",
        "analysis_json": str(analysis.paths.json_path),
        "analysis_result_image": str(analysis.paths.result_image_path),
        "analysis_mask_dir": str(analysis.paths.mask_dir),
        "detection_mode": args.mode,
        "inpaint_method": args.method,
        "inpaint_radius": args.radius,
        "lama_progressive_passes": args.lama_passes,
        "sam_model": None if args.no_sam else args.sam_model,
        "person_cleanup_expansion_pixels": (
            0 if args.no_person_cleanup else max(0, args.person_cleanup_expand)
        ),
        "patch_refinement_enabled": not args.no_patch_refine,
        "mask_expansion_pixels": max(0, args.expand),
        "removed_objects": removed,
        "processing_time_seconds": time.perf_counter() - started,
    }
    metadata_path = output_dir / "eraser_magic_result.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"消去した物体数: {len(selected)}")
    for item in selected:
        print(f"- {item.object_id}: {item.detected.name}")
    print(f"結果画像: {result_path}")
    print(f"消去マスク: {mask_path}")
    print(f"処理情報: {metadata_path}")


if __name__ == "__main__":
    main()
