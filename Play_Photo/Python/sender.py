import socket
import json
import time

# 送信先のIPとポート番号（Unity側と必ず合わせる）
UDP_IP = "127.0.0.1" # ローカルホスト（同じPC内での通信）
UDP_PORT = 1140

# UDP通信用の「ソケット（通信の窓口）」を作成
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

print("UDP送信を開始します...")

try:
    while True:
        # 1. 送りたいデータを辞書型で作る

        data = {
            "objects": [
                {
                    "name": "Cube",
                    "x1": 10,
                    "y1": 20,
                    "x2": 30,
                    "y2": 20,
                    "x3": 10,
                    "y3": 40,
                    "x4": 30,
                    "y4": 40
                },
                {
                    "name": "Sphere",
                    "x1": 50,
                    "y1": 60,
                    "x2": 70,
                    "y2": 60,
                    "x3": 50,
                    "y3": 80,
                    "x4": 70,
                    "y4": 80
                }
            ]
        }

        json_str = json.dumps(data)
        
        sock.sendto(json_str.encode("utf-8"), (UDP_IP, UDP_PORT))

        print(f"送信: {json_str}")

        # 1秒ごとに送信する（実際はループの速度に合わせて調整）
        time.sleep(1) 

except KeyboardInterrupt:
    # Ctrl+C で安全に終了するための処理
    print("終了します")
    sock.close()