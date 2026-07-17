"""
Magic Photo Museum - Custom YOLO Training
=========================================
自分たちで集めた画像データを使って、作品専用の物体検出AIを学習するコード。

事前にRoboflowなどでYOLO形式のデータセットを作り、dataset.yaml を用意してください。

実行例:
    python train_custom_yolo.py
"""

from ultralytics import YOLO


def main():
    # 軽量モデル。精度を上げたい場合は yolov8s.pt や yolov8m.pt に変更。
    model = YOLO("yolov8n.pt")

    model.train(
        data="dataset.yaml",
        epochs=100,
        imgsz=640,
        batch=16,
        patience=20,
        project="runs_magic_photo",
        name="custom_detector",
    )

    print("学習完了。best.pt は runs_magic_photo/custom_detector/weights/best.pt に保存されます。")


if __name__ == "__main__":
    main()
