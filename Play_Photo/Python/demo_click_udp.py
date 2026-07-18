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
from pathlib import Path
from typing import Any, Sequence
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from ml_detector import DetectedObject, MagicPhotoDetector
from magic_brain import MagicBrain
from udp_sender import send_to_unity

IMAGE_PATH = "../downloaded_images/sample.jpg"
WINDOW_NAME = "ML Detector Demo"

# 現在のReseiver.csに合わせる。将来Unity側を更新したら "magic_brain" に変更可能。
UDP_SEND_MODE = "legacy"
UNITY_HOST = "127.0.0.1"
UNITY_PORT = 1140


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
    detected_objects = detector.detect_from_image(img)
    print(f"検出数: raw={detector.last_raw_count}, 後処理後={len(detected_objects)}")

    # unknownグリッドは従来のクリック用フォールバック。写真理解JSONには含めない。
    if len(detected_objects) == 0:
        print("AIが物体を見つけられませんでした。unknown領域を作ります。")
        objects = detector.detect_unknown_regions_from_image(img, grid_size=4)
        detector.last_objects = objects
    else:
        objects = detected_objects

    brain_result = MagicBrain().analyze(
        detected_objects,
        image_width=w,
        image_height=h,
        image_path=IMAGE_PATH,
        debug=detector.last_debug,
    )
    output_path = MagicBrain.save_json(brain_result, "analysis_result.json")

    # UDP送信は専用モジュールへ分離。現在はReseiver.cs互換形式で送る。
    try:
        sent_bytes = send_to_unity(
            objects,
            brain_result,
            host=UNITY_HOST,
            port=UNITY_PORT,
            mode=UDP_SEND_MODE,
        )
        print(
            f"UnityへUDP送信しました: {UNITY_HOST}:{UNITY_PORT} "
            f"/ mode={UDP_SEND_MODE} / {sent_bytes} bytes"
        )
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
