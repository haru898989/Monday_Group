"""
demo_semantic.py
DeepLabV3セマンティックセグメンテーションのデモ。

操作:
  1 : 人の形だけ光らせる
  2 : 背景を暗くして人だけ残す
  3 : 元画像
  q : 終了
"""

import cv2
from semantic_segmentation import SemanticSegmenter

IMAGE_PATH = "sample.jpg"


def main():
    segmenter = SemanticSegmenter()

    img = cv2.imread(IMAGE_PATH)
    if img is None:
        print("sample.jpg が見つかりません。同じフォルダに画像を置いてください。")
        return

    img = segmenter.resize_keep_aspect(img, max_size=1100)

    print("DeepLabV3でセマンティックセグメンテーション中...")
    mask = segmenter.segment_image(img)
    print("完了！")

    mode = 1

    while True:
        if mode == 1:
            display = segmenter.colorize_person(img, mask)
            cv2.putText(display, "Mode 1: person glow", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        elif mode == 2:
            display = segmenter.darken_background_keep_person(img, mask)
            cv2.putText(display, "Mode 2: dark background", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        else:
            display = img.copy()
            cv2.putText(display, "Mode 3: original", (30, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2)

        cv2.imshow("Semantic Segmentation Demo", display)
        key = cv2.waitKey(30)

        if key == ord("1"):
            mode = 1
        elif key == ord("2"):
            mode = 2
        elif key == ord("3"):
            mode = 3
        elif key == ord("q"):
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
