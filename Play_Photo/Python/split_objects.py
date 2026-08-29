"""
split_objects.py (本家仕様：高画質クロップ＆ペースト版)
YOLOで検出した物体の「周辺だけ」を切り抜いてLaMaに渡すことで、
画像の解像度低下（モザイク化）を完全に防ぐスクリプトです。
"""

import os
import re
from pathlib import Path

import cv2
import numpy as np

from ml_detector import MagicPhotoDetector

IMAGE_PATH = "sample.jpg"
OUTPUT_DIR = "objects"
BOX_RESULT_PATH = "result_boxes.jpg"
ERASED_RESULT_PATH = "erased_result.jpg"

# 背景として広い範囲を覆う検出物は、手前の物体まで巻き込んだ
# 切り抜きになりやすい。これらのマスクから前景物体を除外する。
BACKGROUND_LAYER_CLASSES = {
    "background", "sky", "cloud", "ground", "road", "pavement", "grass",
    "water", "sea", "ocean", "river", "lake", "pond", "mountain", "wall",
    "city",
}

def safe_name(name: str) -> str:
    name = name.strip().lower().replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def reset_cutout_directory(output_dir=OUTPUT_DIR):
    """前回生成した切り抜きPNGだけを削除する。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    for path in output_path.glob("*.png"):
        path.unlink()

    return output_path

def make_object_mask(img, box):
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box

    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)

    bw = x2 - x1
    bh = y2 - y1
    if bw < 5 or bh < 5:
        return None

    mask = np.zeros((h, w), np.uint8)
    rect = (x1, y1, bw, bh)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        obj_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    except Exception:
        obj_mask = np.zeros((h, w), np.uint8)
        obj_mask[y1:y2, x1:x2] = 255

    kernel = np.ones((3, 3), np.uint8)
    obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    return obj_mask


def save_object_png(img, obj_mask, box, output_path):
    """検出矩形を維持したまま、物体以外を透明にしたPNGを保存する。"""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(w, x1))
    y1 = max(0, min(h, y1))
    x2 = max(0, min(w, x2))
    y2 = max(0, min(h, y2))

    if x2 <= x1 or y2 <= y1:
        return False

    crop_img = img[y1:y2, x1:x2]
    crop_mask = obj_mask[y1:y2, x1:x2]

    bgra = cv2.cvtColor(crop_img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = crop_mask

    encoded, buffer = cv2.imencode(".png", bgra)
    if not encoded:
        return False

    Path(output_path).write_bytes(buffer.tobytes())
    return True


def _person_mask_from_semantic_segmentation(img, objects):
    """利用可能ならDeepLabV3で画像全体の人物マスクを1回だけ生成する。"""
    has_person = any(
        str(getattr(obj, "canonical_name", "") or obj.name).lower()
        in {"person", "human"}
        for obj in objects
    )
    if not has_person:
        return None

    try:
        from semantic_segmentation import SemanticSegmenter

        segmenter = SemanticSegmenter(input_size=520)
        semantic_mask = segmenter.segment_image(img)
        return segmenter.get_class_mask(semantic_mask, "person")
    except Exception as error:
        print(
            "人物のセマンティック分割を利用できなかったため、"
            f"GrabCutへ切り替えます: {error}"
        )
        return None


def _mask_inside_box(mask, box):
    """画像全体のマスクから、指定された検出矩形内だけを残す。"""
    h, w = mask.shape[:2]
    x1, y1, x2, y2 = (int(value) for value in box)
    x1 = max(0, min(w, x1))
    y1 = max(0, min(h, y1))
    x2 = max(0, min(w, x2))
    y2 = max(0, min(h, y2))

    if x2 <= x1 or y2 <= y1:
        return None

    result = np.zeros_like(mask)
    result[y1:y2, x1:x2] = mask[y1:y2, x1:x2]
    if np.count_nonzero(result) < 25:
        return None

    kernel = np.ones((3, 3), np.uint8)
    result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel, iterations=1)
    result = cv2.morphologyEx(result, cv2.MORPH_CLOSE, kernel, iterations=2)
    return result


def create_object_cutouts(
    img,
    objects,
    output_dir=OUTPUT_DIR,
    return_masks=False,
):
    """検出物体の背景透明PNGを生成し、物体順にファイル名を返す。"""
    object_list = list(objects)
    output_path = reset_cutout_directory(output_dir)
    cutout_files = ["" for _ in object_list]
    object_masks = [None for _ in object_list]
    person_mask = _person_mask_from_semantic_segmentation(img, object_list)

    # 先に全物体のマスクを作る。背景マスクを保存する前に、後から検出された
    # 飛行機なども含めて、すべての前景物体を差し引けるようにするため。
    for index, obj in enumerate(object_list):
        object_name = str(
            getattr(obj, "canonical_name", "") or obj.name
        ).lower()

        obj_mask = None
        if (
            object_name in {"person", "human"}
            and person_mask is not None
        ):
            obj_mask = _mask_inside_box(person_mask, obj.box)
        if obj_mask is None:
            obj_mask = make_object_mask(img, obj.box)
        if obj_mask is None:
            print(f"{index}: {obj.name} の切り抜きマスクを生成できませんでした。")
            continue

        object_masks[index] = obj_mask

    foreground_mask = np.zeros(img.shape[:2], dtype=np.uint8)
    for index, obj in enumerate(object_list):
        object_name = str(
            getattr(obj, "canonical_name", "") or obj.name
        ).lower()
        obj_mask = object_masks[index]
        if obj_mask is None or object_name in BACKGROUND_LAYER_CLASSES:
            continue
        np.maximum(foreground_mask, obj_mask, out=foreground_mask)

    if np.any(foreground_mask):
        # 輪郭の半透明な残像も背景側へ残さないよう、除外範囲を少しだけ広げる。
        exclusion_kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE,
            (9, 9),
        )
        foreground_exclusion = cv2.dilate(
            foreground_mask,
            exclusion_kernel,
            iterations=1,
        )
    else:
        foreground_exclusion = foreground_mask

    for index, obj in enumerate(object_list):
        object_name = str(
            getattr(obj, "canonical_name", "") or obj.name
        ).lower()
        obj_mask = object_masks[index]
        if obj_mask is None:
            continue

        if object_name in BACKGROUND_LAYER_CLASSES:
            obj_mask = cv2.bitwise_and(
                obj_mask,
                cv2.bitwise_not(foreground_exclusion),
            )
            object_masks[index] = obj_mask

        filename = f"{index}_{safe_name(obj.name)}.png"
        if save_object_png(img, obj_mask, obj.box, output_path / filename):
            cutout_files[index] = filename
            print(f"{index}: 物体切り抜きを保存しました: {filename}")
        else:
            print(f"{index}: 物体切り抜きを保存できませんでした: {filename}")

    if return_masks:
        return cutout_files, object_masks
    return cutout_files

def draw_boxes(img, objects):
    display = img.copy()
    for i, obj in enumerate(objects):
        x1, y1, x2, y2 = obj.box
        label = f"{i}_{obj.name} {obj.confidence:.2f}"
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(display, label, (x1, max(25, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return display

def main():
    if not os.path.exists(IMAGE_PATH):
        print(f"{IMAGE_PATH} が見つかりません。")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 手前のアイスや手を確実に見つけるため、しきい値は低めに設定
    detector = MagicPhotoDetector(confidence=0.15)

    # ★重要: load_image()は表示用に長辺max_display_size(既定1280px)へ縮小してしまう。
    # 縮小後の画像でLaMaを実行すると、そもそも元画像の情報量が失われているため
    # 「グレーのもや」のような低ディテールな結果になりやすい。
    # 検出・インペイントは必ず元解像度の画像で行う（YOLOはimgに合わせた座標でboxを返すので
    # 座標変換は不要）。
    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print(f"{IMAGE_PATH} を読み込めませんでした。")
        return

    print(f"元画像サイズ: {img.shape[1]}x{img.shape[0]} で解析します。")
    print("AIが画像を解析中...")
    objects = detector.detect_from_image(img)

    if len(objects) == 0:
        reset_cutout_directory(OUTPUT_DIR)
        print("物体が見つかりませんでした。")
        return

    cutout_files = create_object_cutouts(img, objects, OUTPUT_DIR)
    saved_count = sum(bool(path) for path in cutout_files)
    print(f"人物切り抜き保存数: {saved_count}")

    print("===== 検出結果 =====")
    total_mask = np.zeros(img.shape[:2], dtype=np.uint8)

    for i, obj in enumerate(objects):
        # 今回は「人（手）」と「アイスクリーム」を消去対象に設定
        target_labels = ["person", "human", "ice cream"]
        if obj.name.lower() not in target_labels:
            continue

        print(f"{i}: {obj.name} を消去対象に追加 / 範囲 {obj.box}")
        obj_mask = make_object_mask(img, obj.box)
        if obj_mask is not None:
            total_mask = cv2.bitwise_or(total_mask, obj_mask)

    # 確認用の枠画像を保存
    result_img = draw_boxes(img, objects)
    cv2.imwrite(BOX_RESULT_PATH, result_img)

    if np.count_nonzero(total_mask) == 0:
        print("消去する対象がマスク化されませんでした。")
        return

    # ==========================================
    # 高画質クロップ＆ペースト処理 (本家仕様)
    # ==========================================
    # ★重要: 以前は「全物体のマスクをまとめて1つの外接矩形」でクロップしていた。
    # 今回のように人物が画面の上下に離れて写っていると、その外接矩形は画像ほぼ全体
    # （高さ2080pxのほぼ全域）に膨れ上がり、巨大な画像をLaMaに渡すことになって
    # 精度が大きく落ち、黒いモザイクのような破綻結果になっていた。
    # → 物体（連結領域）ごとに個別にクロップしてLaMaを実行し、離れた物体同士が
    #   互いに無関係な巨大領域へ引きずられないようにする。
    num_labels, labels_im, stats, _ = cv2.connectedComponentsWithStats(total_mask, connectivity=8)

    print(f"ディープラーニング(LaMa)で背景を予測・構築中... (対象領域: {num_labels - 1}個)")
    from PIL import Image
    from simple_lama_inpainting import SimpleLama

    simple_lama = SimpleLama()
    final_img = img.copy()
    h, w = img.shape[:2]

    for label in range(1, num_labels):  # 0は背景なのでスキップ
        x, y, bw, bh, area = stats[label]
        if area < 25:  # ノイズのような極小領域は無視
            continue

        # この連結領域だけのマスク
        component_mask = np.where(labels_im == label, 255, 0).astype(np.uint8)

        # ★重要: LaMaに「周囲の背景」のヒントを与えるための余白（マージン）。
        # 個々の領域サイズに応じて計算するので、離れた物体に引っ張られて肥大化しない。
        MARGIN = max(150, int(0.6 * max(bw, bh)))

        crop_y1 = max(0, y - MARGIN)
        crop_y2 = min(h, y + bh + MARGIN)
        crop_x1 = max(0, x - MARGIN)
        crop_x2 = min(w, x + bw + MARGIN)

        cropped_img = img[crop_y1:crop_y2, crop_x1:crop_x2]
        cropped_mask = component_mask[crop_y1:crop_y2, crop_x1:crop_x2]

        # 消し残し防止に必要な最小限の膨張のみ行う（過剰な膨張は広範囲の破綻の原因）
        kernel = np.ones((3, 3), np.uint8)
        dilated_cropped_mask = cv2.dilate(cropped_mask, kernel, iterations=3)

        # OpenCVの画像形式をAI用のPIL形式に変換
        img_rgb = cv2.cvtColor(cropped_img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_mask = Image.fromarray(dilated_cropped_mask).convert('L')

        result_pil = simple_lama(pil_img, pil_mask)

        # 処理結果をOpenCV形式に戻す
        result_bgr = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)

        # ★重要: SimpleLamaは内部で画像の縦横を8の倍数にパディングしてから推論するため、
        # 出力サイズが入力クロップよりわずかに大きくなることがある。
        # そのままブレンドするとshape不一致でエラーになるので、元のクロップサイズに切り詰める。
        crop_h, crop_w = cropped_img.shape[:2]
        result_bgr = result_bgr[:crop_h, :crop_w]

        # ==========================================
        # アルファブレンディング（必要な部分だけを型抜きしてフワッと合成）
        # ==========================================
        original_crop = img[crop_y1:crop_y2, crop_x1:crop_x2]

        # 貼り付ける境界線がクッキリしないよう、マスクの輪郭付近だけをぼかす
        blurred_mask = cv2.GaussianBlur(dilated_cropped_mask, (15, 15), 0)
        alpha = blurred_mask.astype(float) / 255.0
        alpha = np.expand_dims(alpha, axis=2)

        blended_crop = (result_bgr * alpha + original_crop * (1.0 - alpha)).astype(np.uint8)
        final_img[crop_y1:crop_y2, crop_x1:crop_x2] = blended_crop

    cv2.imwrite(ERASED_RESULT_PATH, final_img)

    print("-----------------------------")
    print("処理完了！ erased_result.jpg を確認してください。")

if __name__ == "__main__":
    main()
