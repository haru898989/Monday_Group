from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    ImageMessageContent
)
import os
import datetime

app = Flask(__name__)

# ==========================================
# 1. LINEの認証情報（ここで設定します）
# ==========================================
# 先ほど取得したトークンとシークレットをここに貼り付けます
LINE_CHANNEL_ACCESS_TOKEN = '9PbWhZ2weqIUHgdneN38OrGC9giGBUx4y6KpIeNeqphMeQR6fif+lgceVxjmDGluM+g1QMM3+8n8Ou9zW7Nn6MhQ3o4x+9o/FU05jocHgZMpWDUIln/JIl2SPfm3fHQnheJ7Z1eck+Eyq+umGYxcrQdB04t89/1O/w1cDnyilFU='
LINE_CHANNEL_SECRET = 'cfbe0fce2f1d4a8c07120653baf377fd'

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# 画像を保存するフォルダを作成
SAVE_DIR = "downloaded_images"
os.makedirs(SAVE_DIR, exist_ok=True)

# ==========================================
# 2. LINEからの通信を受け取る窓口
# ==========================================
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("署名エラー：LINEの認証情報が間違っている可能性があります。")
        abort(400)

    return 'OK'

# ==========================================
# 3. 「画像」が送られてきた時の処理
# ==========================================
@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):
    print("写真が送られてきました！")
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_blob_api = MessagingApiBlob(api_client)
        
        # ユーザーにメッセージを返す
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text="写真を受け取りました！魔法をかけています...🪄")]
            )
        )

        # 画像をダウンロードして保存
        message_id = event.message.id
        message_content = line_bot_blob_api.get_message_content(message_id)
        
        now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        file_path = os.path.join(SAVE_DIR, f"photo_{now}.jpg")
        
        with open(file_path, 'wb') as fd:
            fd.write(message_content)
                
        print(f"画像を保存しました: {file_path}")

if __name__ == "__main__":
    print("LINE Botサーバーが起動しました！(ポート5000)")
    app.run(port=5000)