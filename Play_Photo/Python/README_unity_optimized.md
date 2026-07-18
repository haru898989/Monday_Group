# Magic Photo Museum Unity向け最適化版

## この版の目的

この版は、写真内の物体をUnityでタッチしたとき、対応する音を正しく選べるように、
物体名、カテゴリー、元画像座標、輪郭、二値マスクをJSONへ保存します。

既存のPythonファイルは変更せず、次の新規ファイルだけで機能を追加しています。

- `analyze_objects_optimized_for_unity.py`: コマンド実行の入口
- `unity_analysis_optimized.py`: water、sky、重複統合、JSON作成の共通処理
- `test_unity_analysis_optimized.py`: AIを使わない回帰テスト

## 処理の流れ

1. 日本語パス対応関数で元画像を読み込みます。
2. YOLO-Worldで具体名、confidence、検出枠を取得します。
3. 高コストなマスク生成より前に、ほぼ同じ検出枠を統合します。
4. 検出をthing、water、skyへ分けます。
5. thingはDeepLabV3/VOCの全画面推論を1回だけ共有してマスク化します。
6. DeepLab非対応thingだけ、検出枠周辺のROIでGrabCutを実行します。
7. water候補は全候補を1回のGrabCutへ渡し、water 1件へ統合します。
8. skyは物体別GrabCutを使わず、元画像全体から1回だけ抽出します。
9. 統合後のマスクから箱、4角、輪郭、面積、品質値を再計算します。
10. 元画像サイズの二値マスク、result.jpg、Unity互換JSONを保存します。

thingは、犬、人物、車のように「1個、2個」と数える独立物体です。
stuffは、空、水、地面のように画像へ連続して広がる領域です。
修正前はstuffもYOLOの小さな四角形ごとに処理していたため、skyが一部分だけになり、
同じ水面がriverとoceanの別オブジェクトになる問題がありました。

## 主なしきい値

- 車両・人物の重複: IoU 0.84以上を基本とします。隣接する別の車や人物を誤統合しないため、通常物体より厳しくしています。
- 完全一致に近い別名候補: IoU 0.90、包含率0.97、中心距離0.06以下、面積類似度0.75以上で統合します。phone、mouse、keyboardなどが同じ箱へ付いた場合に使います。
- `--min-mask-area-ratio`: 初期値0.00035です。これより小さいbox fallbackは、時間のかかるGrabCutを省略します。
- GrabCut対象confidence: 0.22以上です。低confidenceの小物体はbox fallbackを残し、JSONへ理由を記録します。
- skyの室内誤検出防止: YOLOのsky候補がない場合、上部25%の青空色18%以上、上端8%の青空色10%以上を要求します。
- 夜景判定: 上部60%の明度中央値80未満、青色率15%未満です。青い照明を夜空と混同しにくくします。

## Unity向けJSON

トップレベルには、既存互換キーに加えて次を保存します。

- `processing_stage_times`: 各処理段階の秒数
- `processing_stage_percentages`: 全体時間に対する割合
- `bottlenecks_top3`: 上位3つのボトルネック
- `model_names`: 使用したモデルまたは処理方式
- `detection_stats`: 統合前後の検出数

各物体には最低限、次を保存します。

- `object_id`
- `name`
- `category`
- `confidence`
- `region_type`
- `position_original`
- `center`
- `detection_box`
- `mask_box`
- `four_corners_original`
- `contour_original`
- `contour_simplified_original`
- `all_contours_original`
- `binary_mask`
- `mask_quality`
- `raw_names`
- `source_object_ids`
- `merged_instance_count`
- `mask_source`
- `mask_generation_time_seconds`

Unityのタッチ判定では、四角形だけでなく`binary_mask.path`のPNGを使ってください。
白が対象、黒が背景です。JSON座標とマスクは元画像サイズなので、同じ画素座標を使えます。

## 実測結果

環境はWindows、Python 3.12、CPU実行、`yolov8s-world.pt`です。
`yolov8m-world.pt`は存在しないため、accuracyモードもsモデルへfallbackしています。

| 画像・モード | 時間 | 最終物体数 | 主な結果 |
|---|---:|---:|---|
| sample1 現行accuracy | 172.593秒 | 15 | 比較基準 |
| sample1 最適化accuracy | 104.672秒 | 12 | タイルあり、ROI GrabCut、室内skyを除外 |
| sample1 最適化fast | 39.012秒 | 9 | 室内skyを出力せず、box fallback 1件 |
| sample2 海・空 fast | 40.070秒 | 3 | sky 1件、water 1件、ground 1件 |
| sample3 建物・車 fast | 31.875秒 | 21 | 車両15件を別々に保持、マスク重複1件を統合 |
| sample4 夜空・観覧車 fast | 40.388秒 | 7 | 夜空を上端接続領域として抽出 |

sample1のfastモードは、現行版より約77.4%短縮しました。
同じaccuracy設定の最終実測でも約39.4%短縮しました。
精度重視の通常accuracyはタイル検出を残すため、fastより時間がかかります。

実測した主なボトルネックは次のとおりです。

1. `detector_init`: 約22〜65秒。YOLOモデル読み込みとクラス埋め込み作成です。
2. `semantic_inference`: 約3.7〜4.3秒。DeepLabV3のCPU推論です。
3. 通常accuracyでは`grabcut_per_object`と`yolo_tile_detection`、fastでは大きい物体のROI GrabCutです。

## skyとwater

skyは通常の物体別GrabCut対象から外し、画像全体を1回だけ解析します。
昼はYOLOのsky候補とつながる青空、雲、夕焼け候補を採用します。
夜は上半分が十分暗いことを確認し、画像上端へつながる暗色領域を採用します。
建物、人物、車などの既知マスクはskyから差し引きます。

water、sea、ocean、river、lake、pond、pool、stream、canal、waterfallは、
すべて`name="water"`、`category="water"`、`region_type="stuff"`として扱います。
候補マスクを論理和でまとめ、統合後に箱、輪郭、面積、品質値を再計算します。
実画像sample2はwater候補1件からwater 1件になりました。
自動テストではriverとoceanの2候補がwater 1件になることを確認しています。

## 実行方法

### 1. 最初に開くフォルダ

次のフォルダを開いてください。

```text
C:\Users\kiich\OneDrive\magic_photo_complete1
```

### 2. コマンドプロンプト

精度重視で実行する場合:

```bat
cd /d C:\Users\kiich\OneDrive\magic_photo_complete1
.venv\Scripts\python.exe analyze_objects_optimized_for_unity.py sample1.jpg --mode accuracy --profile
```

60秒未満を優先するfastモード:

```bat
cd /d C:\Users\kiich\OneDrive\magic_photo_complete1
.venv\Scripts\python.exe analyze_objects_optimized_for_unity.py sample1.jpg --mode accuracy --fast --profile
```

### 3. PowerShell

精度重視で実行する場合:

```powershell
cd C:\Users\kiich\OneDrive\magic_photo_complete1
.\.venv\Scripts\python.exe .\analyze_objects_optimized_for_unity.py .\sample1.jpg --mode accuracy --profile
```

fastモード:

```powershell
cd C:\Users\kiich\OneDrive\magic_photo_complete1
.\.venv\Scripts\python.exe .\analyze_objects_optimized_for_unity.py .\sample1.jpg --mode accuracy --fast --profile
```

### 4. VS Code

1. VS Codeを起動します。
2. 「ファイル」から「フォルダーを開く」を選び、`C:\Users\kiich\OneDrive\magic_photo_complete1`を開きます。
3. `Ctrl+Shift+P`を押し、「Python: Select Interpreter」を選びます。
4. Pythonインタープリタとして`.venv\Scripts\python.exe`を選びます。
5. 「ターミナル」から「新しいターミナル」を開きます。
6. 次のコマンドを入力します。

```powershell
.\.venv\Scripts\python.exe .\analyze_objects_optimized_for_unity.py .\sample1.jpg --mode accuracy --fast --profile
```

### 5. 入力画像の変更

`sample1.jpg`の部分だけを変更します。

```bat
.venv\Scripts\python.exe analyze_objects_optimized_for_unity.py sample3.jpg --mode accuracy --fast --profile
```

日本語ファイル名や空白を含む名前は、ダブルクォートで囲みます。

```bat
.venv\Scripts\python.exe analyze_objects_optimized_for_unity.py "日本語テスト画像.jpg" --mode accuracy --fast --profile
```

### 6. 保存を省略する高速オプション

JSONだけ必要な場合:

```bat
.venv\Scripts\python.exe analyze_objects_optimized_for_unity.py sample1.jpg --fast --no-result-image --no-save-masks
```

`--no-save-masks`ではUnityの画素単位タッチ判定ができなくなるため、速度測定や
検出名だけを確認するときに限って使用してください。

### 7. 実行後に作成されるファイル

通常は次の場所へ作成します。

- `unity_output_optimized\analysis_result.json`
- `unity_output_optimized\result.jpg`
- `unity_output_optimized\masks\object_0001.png`
- `unity_output_optimized\masks\object_0002.png`

前回実行の古い`object_*.png`は、新しいJSONとの取り違えを防ぐため削除します。
削除対象は新規版専用の`unity_output_optimized\masks`内だけです。

### 8. 実行成功時の表示

次の内容が日本語ログに表示されます。

- 入力画像パスと元画像サイズ
- 検出モードとfastの有無
- thing、water候補、sky候補の件数
- マスク生成前後の重複統合数
- 各object_id、name、category、confidence
- region_type、mask_source、fallback_reason
- JSON、result.jpg、masksの保存先
- water統合前後の件数
- 各処理時間と割合
- ボトルネック上位3件

## 自動テスト

コマンドプロンプト:

```bat
cd /d C:\Users\kiich\OneDrive\magic_photo_complete1
.venv\Scripts\python.exe -m unittest -v test_unity_analysis_optimized.py
```

PowerShell:

```powershell
cd C:\Users\kiich\OneDrive\magic_photo_complete1
.\.venv\Scripts\python.exe -m unittest -v test_unity_analysis_optimized.py
```

20件のテストで、water統合、sky分離、元画像サイズ、互換JSON、車の重複、
隣接車の非統合、古いマスク削除、保存省略引数、昼夜判定、Python構文を確認します。

## よくあるエラーと対処方法

### python.exeが見つからない

`.venv\Scripts\python.exe`が存在するか確認してください。
現在確認した環境では、`.venv`が参照する元のPython 3.12本体が見つからず、
ランチャーが起動できない状態でした。既存`.venv`を勝手に変更していないため、
実行前にPython 3.12の再導入または新しい仮想環境の作成が必要です。

既存`.venv`を残して新しい環境を作る例:

```bat
cd /d C:\Users\kiich\OneDrive\magic_photo_complete1
py -3.12 -m venv .venv_optimized
.venv_optimized\Scripts\python.exe -m pip install numpy opencv-python pillow torch torchvision ultralytics
.venv_optimized\Scripts\python.exe analyze_objects_optimized_for_unity.py sample1.jpg --fast --profile
```

### 仮想環境がない

Python 3.12をインストールし、上記の`.venv_optimized`作成手順を実行してください。
Python 3.13では一部ライブラリの対応状況が異なる可能性があるため、
既存実装と同じPython 3.12を推奨します。

### 入力画像が見つからない

画像が`C:\Users\kiich\OneDrive\magic_photo_complete1`内にあるか確認します。
別フォルダの場合は絶対パスをダブルクォートで囲んでください。

### モデルファイルが見つからない

`yolov8s-world.pt`がスクリプトと同じフォルダにあるか確認してください。
`yolov8m-world.pt`がなくても、現在はsモデルへfallbackします。

### 必要ライブラリが不足している

エラーに表示された仮想環境へ、`numpy`、`opencv-python`、`pillow`、`torch`、
`torchvision`、`ultralytics`が入っているか確認してください。
この作業では新しいライブラリを自動インストールしていません。

### 日本語パスで読み込めない

画像パスをダブルクォートで囲みます。OneDriveでファイルがオンラインのみの場合は、
エクスプローラーで「このデバイス上で常に保持する」を選び、ローカルへ保存してください。

### メモリ不足

`--fast`、`--mode standard`、`--max-objects 30`を順に試してください。
他のAIアプリや大きな画像を閉じることも有効です。

### CUDAが使えずCPU動作になる

`DeepLabV3 device: cpu`はエラーではありません。CUDA対応GPU、対応ドライバ、
CUDA対応PyTorchが揃っていない場合はCPUで動作します。今回の実測もCPUです。

## 残る精度課題

- OpenCV方式のskyは新しいセマンティックモデルより保守的です。夜空のうち、
  観覧車の細い骨組みで分断された小領域は欠ける場合があります。
- waterはYOLOがwater候補を出さない画像では生成できません。
- DeepLabV3/VOCはsky、water、road、ground、buildingを持たないため、
  楽器や建物はGrabCutまたはbox fallbackになることがあります。
- YOLO-Worldは観覧車をflowerなど別名にする場合があります。マスクが正しくても、
  具体名の誤りは残ります。
- fastモードはタイル検出を省くため、小さい物体の見逃しが増える可能性があります。
- accuracyモードは小物体を拾いやすい一方、CPUでは60秒を超える場合があります。

## 今後さらに精度を上げる方法

sky、water、road、ground、buildingを同時に扱うには、
ADE20K学習済みSegFormer-B0が最も適した追加候補です。
Cityscapesは道路・建物・空には強い一方、汎用waterクラスが不足します。
既存DeepLabV3/VOCはthing向けで、今回必要なstuffの種類が足りません。

SegFormerを採用する場合は`transformers`とモデル重みが追加で必要です。
今回の作業では勝手にインストールしていません。導入候補コマンドは次のとおりです。

```bat
.venv\Scripts\python.exe -m pip install transformers safetensors
```

CPUでも実行できますが、全画面推論時間とモデル初期化時間が増えます。
導入時は現在のOpenCV方式をfallbackとして残し、同じ3枚の実画像で速度と精度を
比較してから既定方式を切り替えるのが安全です。
