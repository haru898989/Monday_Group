"""
split_objects.py
写真をAIで検出して、物体ごとに objects フォルダへ切り出して保存するコード。

使い方:
    python split_objects.py

必要ファイル:
    split_objects.py
    ml_detector.py
    sample.jpg

出力:
    objects/0_person.png のように、背景透明PNGで物体ごとに保存
    result_boxes.jpg に検出枠つき画像を保存
"""

import os
import re
import cv2
import numpy as np
from ml_detector import MagicPhotoDetector

IMAGE_PATH = "sample.jpg"
OUTPUT_DIR = "objects"
BOX_RESULT_PATH = "result_boxes.jpg"


def safe_name(name: str) -> str:
    """ファイル名に使えない文字を _ に変える"""
    name = name.strip().lower().replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name)


def make_object_mask(img, box):
    """
    GrabCutで四角の中から物体っぽい部分だけを取り出すマスクを作る。
    YOLOの四角だけで切るより、背景が少し透明になりやすい。
    """
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box

    # 画像範囲内に補正
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)

    bw = x2 - x1
    bh = y2 - y1
    if bw < 5 or bh < 5:
        return None

    # GrabCut用マスク
    mask = np.zeros((h, w), np.uint8)
    rect = (x1, y1, bw, bh)
    bgd_model = np.zeros((1, 65), np.float64)
    fgd_model = np.zeros((1, 65), np.float64)

    try:
        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
        obj_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype("uint8")
    except Exception:
        # GrabCutが失敗したら四角全体を物体として扱う
        obj_mask = np.zeros((h, w), np.uint8)
        obj_mask[y1:y2, x1:x2] = 255

    # 少しだけマスクを整える
    kernel = np.ones((3, 3), np.uint8)
    obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    obj_mask = cv2.morphologyEx(obj_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

    return obj_mask


def save_object_png(img, obj_mask, box, output_path):
    """物体部分だけを背景透明PNGとして保存する"""
    h, w = img.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(w - 1, x2)
    y2 = min(h - 1, y2)

    crop_img = img[y1:y2, x1:x2]
    crop_mask = obj_mask[y1:y2, x1:x2]

    # BGR → BGRA にして、Aにマスクを入れる
    bgra = cv2.cvtColor(crop_img, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = crop_mask

    cv2.imwrite(output_path, bgra)


def draw_boxes(img, objects):
    """検出確認用の枠つき画像を作る"""
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
        print(f"{IMAGE_PATH} が見つかりません。同じフォルダに画像を置いてください。")
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    detector = MagicPhotoDetector(confidence=0.12)

    # demo_click.pyと同じ考え方で、読み込み画像とAI解析画像を統一
    img = detector.load_image(IMAGE_PATH)

    print("AIが画像を解析中...")
    objects = detector.detect_from_image(img)

    if len(objects) == 0:
        print("物体が見つかりませんでした。")
        return

    print("===== 検出結果 =====")

    saved_count = 0
    for i, obj in enumerate(objects):
        print(f"{i}: {obj.name} / 信頼度 {obj.confidence:.2f} / 範囲 {obj.box}")

        obj_mask = make_object_mask(img, obj.box)
        if obj_mask is None:
            continue

        filename = f"{i}_{safe_name(obj.name)}.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        save_object_png(img, obj_mask, obj.box, output_path)
        saved_count += 1

    result_img = draw_boxes(img, objects)
    cv2.imwrite(BOX_RESULT_PATH, result_img)

    print("-----------------------------")
    print(f"保存完了: {saved_count} 個")
    print(f"物体画像: {OUTPUT_DIR} フォルダ")
    print(f"検出確認画像: {BOX_RESULT_PATH}")


if __name__ == "__main__":
    main()
