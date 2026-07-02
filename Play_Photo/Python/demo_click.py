"""
Magic Photo Museum - ML Click Demo
==================================
ml_detector.py の動作確認用デモ。

今回の版:
- 画面サイズを自動取得
- 画像の縦横比を保ったまま、画面に収まる最大サイズにする
- AI検出・表示・クリック判定を同じ画像座標で統一
- 人・水・建物・空も認識対象

実行:
    python demo_click.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from ml_detector import MagicPhotoDetector

IMAGE_PATH = "sample.jpg"
WINDOW_NAME = "ML Detector Demo"


def get_screen_size():
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


def draw_objects(img, objects):
    display = img.copy()
    for obj in objects:
        x1, y1, x2, y2 = obj.box
        label = f"{obj.name}:{obj.reaction}"
        cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            display,
            label,
            (x1, max(25, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 255, 0),
            2,
        )
    return display


def main():
    detector = MagicPhotoDetector(confidence=0.12)

    screen_w, screen_h = get_screen_size()
    print(f"画面サイズ: {screen_w} x {screen_h}")

    try:
        # 画面サイズに合わせて、縦横比を保ったまま画像を縮小
        img = detector.load_image_for_screen(IMAGE_PATH, screen_w, screen_h, margin=100)
    except FileNotFoundError:
        print("sample.jpg が見つかりません。同じフォルダに画像を置いてください。")
        return

    h, w = img.shape[:2]
    print(f"表示・AI解析に使う画像サイズ: {w} x {h}")

    print("AIが画像を解析中...")
    # 表示に使う画像そのものをAIに渡す。これで座標が絶対にズレない。
    objects = detector.detect_from_image(img)

    if len(objects) == 0:
        print("AIが物体を見つけられませんでした。unknown領域を作ります。")
        objects = detector.detect_unknown_regions_from_image(img, grid_size=4)
        detector.last_objects = objects

    print("===== 検出結果 =====")
    for obj in objects:
        print(f"{obj.name} / {obj.reaction} / {obj.confidence:.2f} / {obj.box}")

    display = draw_objects(img, objects)

    def on_mouse(event, x, y, flags, param):
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
