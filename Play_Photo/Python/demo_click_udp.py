"""
Magic Photo Museum - ML Click Demo
==================================
ml_detector.py の動作確認用デモ。

今回の版:
- 画面サイズを自動取得
- 画像の縦横比を保ったまま、画面に収まる最大サイズにする
- AI検出・表示・クリック判定を同じ画像座標で統一
- 空と壁は操作対象から除外

実行:
    python demo_click.py
"""
import sys
import os
import shutil
from pathlib import Path
from typing import Any, List, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", SCRIPT_DIR)).resolve()
sys.path.insert(0, str(SCRIPT_DIR))


def configure_packaged_model_paths() -> None:
    """日本語パスを扱えないTorchモデルを英数字パスへ用意する。"""
    source_directory = (
        BUNDLE_DIR / "torch" / "hub" / "checkpoints"
    )
    public_directory = Path(
        os.environ.get("PUBLIC", r"C:\Users\Public")
    )
    cache_root = public_directory / "MagicPhotoModelCache"
    cache_directory = cache_root / "hub" / "checkpoints"
    cache_directory.mkdir(parents=True, exist_ok=True)

    for model_name in (
        "big-lama.pt",
        "deeplabv3_resnet50_coco-cd0a2569.pth",
    ):
        source_path = source_directory / model_name
        target_path = cache_directory / model_name

        if (
            target_path.is_file()
            and target_path.stat().st_size == source_path.stat().st_size
        ):
            continue

        temporary_path = target_path.with_suffix(".tmp")
        shutil.copyfile(source_path, temporary_path)
        os.replace(temporary_path, target_path)

    os.environ["TORCH_HOME"] = str(cache_root)
    os.environ["LAMA_MODEL"] = str(
        cache_directory / "big-lama.pt"
    )


if getattr(sys, "frozen", False):
    configure_packaged_model_paths()

import cv2
import numpy as np
from ml_detector import DetectedObject, MagicPhotoDetector
from eraser_magic import (
    BACKGROUND_CLASSES,
    inpaint_background,
    patch_refine_background,
)
from magic_brain import MagicBrain
from split_objects import create_object_cutouts
from udp_sender import send_to_unity

DATA_DIR = Path(
    os.environ.get(
        "MAGIC_PHOTO_DATA_DIR",
        str(SCRIPT_DIR.parent / "downloaded_images"),
    )
).resolve()
IMAGE_PATH = str(DATA_DIR / "sample.jpg")
WINDOW_NAME = "ML Detector Demo"
SHOW_DEBUG_WINDOW = False

# 現在のReseiver.csに合わせる。将来Unity側を更新したら "magic_brain" に変更可能。
UDP_SEND_MODE = "legacy"
UNITY_HOST = "127.0.0.1"
UNITY_PORT = 1140
CUTOUT_DIR = Path(
    os.environ.get(
        "MAGIC_PHOTO_CUTOUT_DIR",
        str(SCRIPT_DIR / "objects"),
    )
).resolve()
ERASED_BACKGROUND = DATA_DIR / "sample_erased.png"
ANALYSIS_RESULT = Path(
    os.environ.get(
        "MAGIC_PHOTO_ANALYSIS_RESULT",
        str(SCRIPT_DIR / "analysis_result.json"),
    )
).resolve()
YOLO_MODEL_PATH = BUNDLE_DIR / "yolov8s-world.pt"
EXCLUDED_SCENE_CLASSES = {"sky", "wall"}
LARGE_STATIC_BACKGROUND_CLASSES = {
    "desk",
    "table",
    "floor",
    "ground",
    "road",
    "pavement",
}
UNITY_PROGRESS_PREFIX = "UNITY_PROGRESS"
UNITY_PROGRESS_FILE = Path(
    os.environ.get(
        "MAGIC_PHOTO_PROGRESS_FILE",
        str(SCRIPT_DIR / "loading_progress.txt"),
    )
).resolve()


def report_progress(progress: float, message: str) -> None:
    """UnityのLoading画面へ実処理の段階を通知する。"""
    clamped_progress = max(0.0, min(1.0, float(progress)))
    progress_text = f"{clamped_progress:.3f}|{message}"

    try:
        temporary_path = UNITY_PROGRESS_FILE.with_suffix(".tmp")
        temporary_path.write_text(progress_text, encoding="utf-8")
        os.replace(temporary_path, UNITY_PROGRESS_FILE)
    except OSError as error:
        print(f"進捗ファイルを更新できませんでした: {error}", flush=True)

    print(
        f"{UNITY_PROGRESS_PREFIX}|{progress_text}",
        flush=True,
    )


def _normalized_object_name(obj: DetectedObject) -> str:
    return str(
        getattr(obj, "canonical_name", "")
        or getattr(obj, "name", "")
    ).strip().lower()


def _box_area(box: Sequence[float]) -> float:
    x1, y1, x2, y2 = box
    return max(0.0, float(x2) - float(x1)) * max(
        0.0,
        float(y2) - float(y1),
    )


def _box_intersection(a: Sequence[float], b: Sequence[float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    width = max(0.0, min(float(ax2), float(bx2)) - max(float(ax1), float(bx1)))
    height = max(0.0, min(float(ay2), float(by2)) - max(float(ay1), float(by1)))
    return width * height


def _box_iou(a: Sequence[float], b: Sequence[float]) -> float:
    intersection = _box_intersection(a, b)
    if intersection <= 0.0:
        return 0.0

    union = _box_area(a) + _box_area(b) - intersection
    return intersection / union if union > 0.0 else 0.0


def _intersection_over_smaller(
    a: Sequence[float],
    b: Sequence[float],
) -> float:
    smaller_area = min(_box_area(a), _box_area(b))
    if smaller_area <= 0.0:
        return 0.0
    return _box_intersection(a, b) / smaller_area


def remove_overlapping_detections(
    objects: Sequence[DetectedObject],
    image_width: int,
    image_height: int,
) -> Tuple[List[DetectedObject], int]:
    """切り抜き前に明らかな重複枠と巨大な集合枠を除外する。"""
    candidates = list(objects)
    if len(candidates) <= 1:
        return candidates, 0

    suppressed = set()
    image_area = max(1.0, float(image_width * image_height))

    # 机や床を写真全体ほど大きな「物体」として検出することがある。
    # これを切り抜くと巨大なマスクの生成・背景修復が走り、前景のスマホなどとは
    # 無関係にロードが大幅に長くなるため、静的背景に限って除外する。
    for index, candidate in enumerate(candidates):
        candidate_name = _normalized_object_name(candidate)
        candidate_area_ratio = _box_area(candidate.box) / image_area

        if (
            candidate_name in LARGE_STATIC_BACKGROUND_CLASSES
            and candidate_area_ratio >= 0.70
        ):
            suppressed.add(index)
            print(
                "巨大な静的背景を除外: "
                f"{candidate.name} box={candidate.box} "
                f"/ image_area={candidate_area_ratio:.3f}"
            )

    ranked_indices = sorted(
        range(len(candidates)),
        key=lambda index: (
            -float(getattr(candidates[index], "confidence", 0.0)),
            _box_area(candidates[index].box),
        ),
    )

    # ほぼ同一の枠は、名前が異なる競合判定も含めて信頼度の高い方だけを残す。
    # 同じ種類では少しずれた重複枠も除外するが、離れた複数物体は残す。
    for order, kept_index in enumerate(ranked_indices):
        if kept_index in suppressed:
            continue

        kept = candidates[kept_index]
        kept_name = _normalized_object_name(kept)

        for candidate_index in ranked_indices[order + 1:]:
            if candidate_index in suppressed:
                continue

            candidate = candidates[candidate_index]
            iou = _box_iou(kept.box, candidate.box)
            same_name = (
                kept_name == _normalized_object_name(candidate)
            )

            if iou >= 0.90 or (same_name and iou >= 0.68):
                suppressed.add(candidate_index)
                print(
                    "重複検出を除外: "
                    f"{candidate.name} box={candidate.box} "
                    f"/ kept={kept.name} iou={iou:.3f}"
                )

    # 花畑などでは、個々の花に加えて写真全体を覆うflower枠が残ることがある。
    # 同じ種類の小さな枠を2個以上ほぼ完全に包む巨大枠は、集合的な重複として除く。
    for container_index, container in enumerate(candidates):
        if container_index in suppressed:
            continue

        container_area = _box_area(container.box)
        container_area_ratio = container_area / image_area
        if container_area_ratio < 0.42:
            continue

        container_name = _normalized_object_name(container)
        contained_count = 0

        for child_index, child in enumerate(candidates):
            if (
                child_index == container_index
                or child_index in suppressed
                or container_name != _normalized_object_name(child)
            ):
                continue

            child_area = _box_area(child.box)
            if child_area >= container_area * 0.45:
                continue

            if _intersection_over_smaller(container.box, child.box) >= 0.90:
                contained_count += 1

        if contained_count >= 2:
            suppressed.add(container_index)
            print(
                "巨大な集合重複を除外: "
                f"{container.name} box={container.box} "
                f"/ image_area={container_area_ratio:.3f} "
                f"/ contained={contained_count}"
            )

    filtered = [
        item
        for index, item in enumerate(candidates)
        if index not in suppressed
    ]

    return filtered, len(suppressed)


def create_erased_background(
    img: Any,
    objects: Sequence[DetectedObject],
    object_masks: Sequence[Any],
) -> None:
    """切り抜き生成時のマスクを再利用して背景を補完する。"""
    height, width = img.shape[:2]
    erase_mask = np.zeros((height, width), dtype=np.uint8)
    person_mask = np.zeros_like(erase_mask)

    for index, obj in enumerate(objects):
        object_name = str(
            getattr(obj, "canonical_name", "") or obj.name
        ).lower()
        if object_name in BACKGROUND_CLASSES:
            continue

        obj_mask = object_masks[index] if index < len(object_masks) else None
        if obj_mask is None or obj_mask.shape != erase_mask.shape:
            continue

        np.maximum(erase_mask, obj_mask, out=erase_mask)
        if object_name in {"person", "human"}:
            np.maximum(person_mask, obj_mask, out=person_mask)

    if np.any(erase_mask):
        close_kernel = np.ones((7, 7), dtype=np.uint8)
        erase_mask = cv2.morphologyEx(
            erase_mask,
            cv2.MORPH_CLOSE,
            close_kernel,
        )
        expand_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (21, 21),
        )
        erase_mask = cv2.dilate(erase_mask, expand_kernel, iterations=1)
        result = inpaint_background(img, erase_mask, 5.0, "lama", 4)

        if np.any(person_mask):
            cleanup_kernel = cv2.getStructuringElement(
                cv2.MORPH_ELLIPSE,
                (49, 49),
            )
            cleanup_mask = cv2.dilate(
                person_mask,
                cleanup_kernel,
                iterations=1,
            )
            result = inpaint_background(result, cleanup_mask, 5.0, "lama", 2)
            result = patch_refine_background(result, cleanup_mask)
    else:
        result = img
        print("消去対象がないため、元画像を消去済み背景として使用します。")

    ERASED_BACKGROUND.parent.mkdir(parents=True, exist_ok=True)
    encoded, buffer = cv2.imencode(".png", result)
    if not encoded:
        raise OSError("消去済み背景を保存できませんでした。")
    ERASED_BACKGROUND.write_bytes(buffer.tobytes())


def get_screen_size() -> tuple[int, int]:
    """Windowsでもだいたい動く画面サイズ取得。失敗したら1280x720。"""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        w = root.winfo_screenwidth()
        h = root.winfo_screenheight()
        root.destroy()
        return w, h
    except Exception:
        return 1280, 720


def draw_objects(img: Any, objects: Sequence[DetectedObject]) -> Any:
    display = img.copy()
    for obj in objects:
        x1, y1, x2, y2 = obj.box
        label = f"{obj.name}:{obj.reaction}"
        #四角
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
        #ラベル
        cv2.putText(
            display,
            label,
            (x1, max(25, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
        )
        # 左上
        cv2.circle(display, (x1, y1), 4, (0, 0, 255), -1)
        cv2.putText(display, f"({x1},{y1})", (x1, y1+18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0), 1)

        # 右上
        cv2.circle(display, (x2, y1), 4, (0, 0, 255), -1)
        cv2.putText(display, f"({x2},{y1})", (x2-70, y1+18),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0), 1)

        # 左下
        cv2.circle(display, (x1, y2), 4, (0, 0, 255), -1)
        cv2.putText(display, f"({x1},{y2})", (x1, y2-8),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0), 1)

        # 右下
        cv2.circle(display, (x2, y2), 4, (0, 0, 255), -1)
        cv2.putText(display, f"({x2},{y2})", (x2-70, y2-8),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,255,0), 1)
    return display


def main() -> None:
    report_progress(0.03, "展示の準備を始めています")
    detector = MagicPhotoDetector(
        model_path=str(YOLO_MODEL_PATH),
        confidence=0.12,
    )

    screen_w, screen_h = get_screen_size()
    print(f"画面サイズ: {screen_w} x {screen_h}")

    try:
        report_progress(0.08, "写真を受け取っています")
        # 画面サイズに合わせて、縦横比を保ったまま画像を縮小
        img = detector.load_image_for_screen(IMAGE_PATH, screen_w, screen_h, margin=100)
    except FileNotFoundError:
        print("sample.jpg が見つかりません。同じフォルダに画像を置いてください。")
        return

    h, w = img.shape[:2]
    print(f"表示・AI解析に使う画像サイズ: {w} x {h}")

    report_progress(0.18, "写真の中を見ています")
    print("AIが画像を解析中...")
    # 表示に使う画像そのものをAIに渡す。これで座標が絶対にズレない。
    detected_objects = detector.detect_from_image(img)
    had_detection_before_exclusion = len(detected_objects) > 0

    # skyとwallは写真の広範囲を覆う背景であり、タッチ対象や切り抜きとして
    # 重ねると前景物体の残像・色むらの原因になるため、以降の処理へ渡さない。
    detected_before_scene_exclusion = len(detected_objects)
    detected_objects = [
        obj
        for obj in detected_objects
        if str(
            getattr(obj, "canonical_name", "") or obj.name
        ).strip().lower() not in EXCLUDED_SCENE_CLASSES
    ]
    excluded_scene_count = (
        detected_before_scene_exclusion - len(detected_objects)
    )

    detected_objects, duplicate_count = remove_overlapping_detections(
        detected_objects,
        w,
        h,
    )
    detector.last_objects = detected_objects

    print(
        f"検出数: raw={detector.last_raw_count}, "
        f"後処理後={len(detected_objects)}, "
        f"背景除外(sky/wall)={excluded_scene_count}, "
        f"重複除外={duplicate_count}"
    )

    # unknownグリッドは従来のクリック用フォールバック。写真理解JSONには含めない。
    if not had_detection_before_exclusion:
        print("AIが物体を見つけられませんでした。unknown領域を作ります。")
        objects = detector.detect_unknown_regions_from_image(img, grid_size=4)
        detector.last_objects = objects
    else:
        objects = detected_objects

    report_progress(0.46, "写真の中のものを見つけています")
    cutout_files, object_masks = create_object_cutouts(
        img,
        objects,
        CUTOUT_DIR,
        return_masks=True,
    )

    # 消去済み背景が完成してからUnityへ座標を送る
    report_progress(0.68, "写真をきれいに整えています")
    create_erased_background(img, objects, object_masks)

    report_progress(0.86, "楽しいしかけを準備しています")
    brain_result = MagicBrain().analyze(
        detected_objects,
        image_width=w,
        image_height=h,
        image_path=IMAGE_PATH,
        debug=detector.last_debug,
    )
    output_path = MagicBrain.save_json(
        brain_result,
        str(ANALYSIS_RESULT),
    )

    # UDP送信は専用モジュールへ分離。現在はReseiver.cs互換形式で送る。
    try:
        report_progress(0.96, "写真をかざっています")
        sent_bytes = send_to_unity(
            objects,
            brain_result,
            host=UNITY_HOST,
            port=UNITY_PORT,
            mode=UDP_SEND_MODE,
            cutout_files=cutout_files,
            image_width=w,
            image_height=h,
        )
        print(
            f"UnityへUDP送信しました: {UNITY_HOST}:{UNITY_PORT} "
            f"/ mode={UDP_SEND_MODE} / {sent_bytes} bytes"
        )
        report_progress(1.0, "写真をかざす準備ができました")
    except (OSError, TypeError, ValueError) as error:
        # Unityが起動していなくても、画像認識デモ自体は続行する。
        print(f"UnityへのUDP送信に失敗しました: {error}")

    print("===== 重複・低信頼度除去後の物体 =====")
    if brain_result["objects"]:
        for item in brain_result["objects"]:
            print(
                f"id={item['object_id']} / {item['canonical_name']} "
                f"(original={item['original_name']}) / {item['confidence']:.2f} / {item['box']}"
            )
    else:
        print("なし")

    print("===== 主役候補（上位3件） =====")
    if brain_result["main_objects"]:
        for item in brain_result["main_objects"]:
            print(f"id={item['object_id']} / {item['name']} / importance={item['importance']:.4f}")
    else:
        print("なし")

    print(f"primary_scene: {brain_result['scene']['primary']}")
    print("scene_scores 上位3件:")
    scene_top3 = sorted(
        brain_result["scene"]["scores"].items(), key=lambda item: item[1], reverse=True
    )[:3]
    for scene_name, score in scene_top3:
        print(f"  {scene_name}: {score:.4f}")

    person_ids = {
        item["object_id"] for item in brain_result["objects"]
        if item["canonical_name"] == "person"
    }
    object_names = {
        item["object_id"]: item["canonical_name"] for item in brain_result["objects"]
    }
    person_relation_types = {
        "holding_candidate", "using_candidate", "in_front_of",
        "near", "overlap", "inside", "contains",
    }
    person_relations = []
    for relation in brain_result["relations"]:
        subject_id = relation["subject_id"]
        object_id = relation["object_id"]
        involves_person = subject_id in person_ids or object_id in person_ids
        has_non_person = (
            object_names.get(subject_id) != "person"
            or object_names.get(object_id) != "person"
        )
        if involves_person and has_non_person and relation["type"] in person_relation_types:
            person_relations.append(relation)
    print("===== 人物と物体の関係 =====")
    if person_relations:
        for relation in person_relations:
            print(
                f"{relation['subject_id']} -> {relation['object_id']} / "
                f"{relation['type']} / score={relation['score']:.4f}"
            )
    else:
        print("なし")
    print(f"JSON保存先: {Path(output_path).resolve()}")

    if not SHOW_DEBUG_WINDOW:
        print("Unity向け解析が完了したため、Python処理を終了します。")
        return

    display = draw_objects(img, objects)

    def on_mouse(event: int, x: int, y: int, flags: int, param: Any) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            obj = detector.find_clicked_object(x, y)
            if obj is None:
                print(f"クリック位置 ({x}, {y}) には検出物体がありません。")
            else:
                print("-----------------------------")
                print(f"クリック位置: ({x}, {y})")
                print(f"物体名: {obj.name}")
                print(f"反応: {obj.reaction}")
                print(f"信頼度: {obj.confidence:.2f}")
                print(f"範囲: {obj.box}")

    # AUTOSIZEにすることで、画像をウィンドウ側で無理に引き伸ばさない
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(WINDOW_NAME, on_mouse)

    while True:
        cv2.imshow(WINDOW_NAME, display)
        key = cv2.waitKey(30)
        if key == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
