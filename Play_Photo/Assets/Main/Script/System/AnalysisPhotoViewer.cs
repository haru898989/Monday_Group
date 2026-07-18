using System;
using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

public class AnalysisPhotoViewer : MonoBehaviour
{
    // ========================================
    // JSONに対応するデータクラス
    // ========================================

    [Serializable]
    public class AnalysisResultData
    {
        public string schema_version;
        public AnalysisImageData image;
        public int object_count;
        public DetectedObjectData[] objects;
    }

    [Serializable]
    public class AnalysisImageData
    {
        public string path;
        public int width;
        public int height;
    }

    [Serializable]
    public class DetectedObjectData
    {
        public string object_id;
        public string name;
        public float confidence;

        public DetectedPositionData position_original;
        public DetectedFourCornersData four_corners_original;
    }

    [Serializable]
    public class DetectedPositionData
    {
        public int[] center;

        public DetectedBoxData detection_box;
        public DetectedBoxData mask_box;
    }

    [Serializable]
    public class DetectedBoxData
    {
        public float x;
        public float y;

        public float width;
        public float height;

        public float x1;
        public float y1;

        public float x2;
        public float y2;
    }

    [Serializable]
    public class DetectedFourCornersData
    {
        public int[] top_left;
        public int[] top_right;
        public int[] bottom_right;
        public int[] bottom_left;
    }


    // ========================================
    // 写真表示設定
    // ========================================

    [Header("写真表示")]

    [SerializeField]
    private RawImage photoRawImage;

    [SerializeField]
    private AspectRatioFitter aspectRatioFitter;


    // ========================================
    // JSONファイル設定
    // ========================================

    [Header("JSON設定")]

    [SerializeField]
    private string jsonFilePath =
        @"C:\Users\kouta\OneDrive\ドキュメント\プロコン\Play_Photo\Python\analysis_result.json";

    [SerializeField]
    private float checkInterval = 0.5f;


    // ========================================
    // 検出枠表示設定
    // ========================================

    [Header("検出枠の表示設定")]

    // true：赤い枠を表示
    // false：透明なクリック範囲
    [SerializeField]
    private bool showDetectionBoxes = false;

    [SerializeField]
    private Color debugBoxColor =
        new Color(
            1f,
            0f,
            0f,
            0.25f
        );

    [SerializeField]
    private Color outlineColor = Color.red;

    [SerializeField]
    private Vector2 outlineDistance =
        new Vector2(
            2f,
            -2f
        );


    // ========================================
    // 内部で使用する変数
    // ========================================

    private DateTime lastWriteTime =
        DateTime.MinValue;

    private Texture2D currentTexture;

    private RectTransform boxContainer;

    private Coroutine watchCoroutine;

    private Coroutine drawCoroutine;


    // ========================================
    // Unity開始時
    // ========================================

    private void Start()
    {
        // Inspectorで未設定なら、
        // このオブジェクトからRawImageを探す
        if (photoRawImage == null)
        {
            photoRawImage =
                GetComponent<RawImage>();
        }

        if (photoRawImage == null)
        {
            Debug.LogError(
                "Photo Raw Imageが設定されていません。"
            );

            return;
        }

        // AspectRatioFitterが未設定なら、
        // PhotoRawImageから探す
        if (aspectRatioFitter == null)
        {
            aspectRatioFitter =
                photoRawImage.GetComponent
                    <AspectRatioFitter>();
        }

        CreateBoxContainer();

        watchCoroutine =
            StartCoroutine(
                WatchJsonFile()
            );
    }


    // ========================================
    // 透明なクリック範囲を置く親を作る
    // ========================================

    private void CreateBoxContainer()
    {
        if (boxContainer != null)
        {
            return;
        }

        GameObject containerObject =
            new GameObject(
                "DetectedBoxContainer",
                typeof(RectTransform)
            );

        containerObject.transform.SetParent(
            photoRawImage.transform,
            false
        );

        boxContainer =
            containerObject.GetComponent<RectTransform>();

        // PhotoRawImage全体に広げる
        boxContainer.anchorMin =
            Vector2.zero;

        boxContainer.anchorMax =
            Vector2.one;

        boxContainer.offsetMin =
            Vector2.zero;

        boxContainer.offsetMax =
            Vector2.zero;

        boxContainer.localScale =
            Vector3.one;

        // 写真より手前に表示
        boxContainer.SetAsLastSibling();
    }


    // ========================================
    // JSONファイルを監視する
    // ========================================

    private IEnumerator WatchJsonFile()
    {
        while (true)
        {
            if (!string.IsNullOrWhiteSpace(
                    jsonFilePath
                ) &&
                File.Exists(jsonFilePath))
            {
                DateTime currentWriteTime =
                    DateTime.MinValue;

                bool writeTimeSucceeded =
                    false;

                try
                {
                    currentWriteTime =
                        File.GetLastWriteTimeUtc(
                            jsonFilePath
                        );

                    writeTimeSucceeded =
                        true;
                }
                catch (Exception e)
                {
                    Debug.LogWarning(
                        "JSONの更新日時を取得できませんでした：" +
                        e.Message
                    );
                }

                // catchの外で読み込み処理を行う
                if (writeTimeSucceeded &&
                    currentWriteTime != lastWriteTime)
                {
                    bool loadSucceeded =
                        LoadJsonAndPhoto();

                    // 正常に読み込めた場合だけ
                    // 更新日時を保存する
                    if (loadSucceeded)
                    {
                        lastWriteTime =
                            currentWriteTime;
                    }
                }
            }

            // yield returnはcatchの外に置く
            yield return new WaitForSeconds(
                Mathf.Max(
                    checkInterval,
                    0.1f
                )
            );
        }
    }


    // ========================================
    // JSONと写真を読み込む
    // ========================================

    private bool LoadJsonAndPhoto()
    {
        if (!File.Exists(jsonFilePath))
        {
            Debug.LogWarning(
                "analysis_result.jsonが見つかりません：" +
                jsonFilePath
            );

            return false;
        }

        string json;

        try
        {
            json =
                File.ReadAllText(
                    jsonFilePath
                );
        }
        catch (Exception e)
        {
            Debug.LogWarning(
                "JSONを読み込めませんでした：" +
                e.Message
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(json))
        {
            Debug.LogWarning(
                "JSONの中身が空です。"
            );

            return false;
        }

        AnalysisResultData result;

        try
        {
            result =
                JsonUtility.FromJson
                    <AnalysisResultData>(
                        json
                    );
        }
        catch (Exception e)
        {
            Debug.LogWarning(
                "JSONの変換に失敗しました：" +
                e.Message
            );

            return false;
        }

        if (result == null)
        {
            Debug.LogWarning(
                "JSONをデータへ変換できませんでした。"
            );

            return false;
        }

        if (result.image == null)
        {
            Debug.LogWarning(
                "JSONの中にimage情報がありません。"
            );

            return false;
        }

        if (string.IsNullOrWhiteSpace(
                result.image.path
            ))
        {
            Debug.LogWarning(
                "JSONのimage.pathが空です。"
            );

            return false;
        }

        if (!File.Exists(result.image.path))
        {
            Debug.LogError(
                "写真ファイルが見つかりません：" +
                result.image.path
            );

            return false;
        }

        byte[] imageBytes;

        try
        {
            imageBytes =
                File.ReadAllBytes(
                    result.image.path
                );
        }
        catch (Exception e)
        {
            Debug.LogError(
                "写真を読み込めませんでした：" +
                e.Message
            );

            return false;
        }

        Texture2D newTexture =
            new Texture2D(
                2,
                2,
                TextureFormat.RGBA32,
                false
            );

        bool textureLoadSucceeded =
            newTexture.LoadImage(
                imageBytes
            );

        if (!textureLoadSucceeded)
        {
            Destroy(newTexture);

            Debug.LogError(
                "写真をTexture2Dへ変換できませんでした。"
            );

            return false;
        }

        // 前の写真を削除
        if (currentTexture != null)
        {
            photoRawImage.texture =
                null;

            Destroy(currentTexture);
        }

        currentTexture =
            newTexture;

        photoRawImage.texture =
            currentTexture;

        photoRawImage.color =
            Color.white;


        // ========================================
        // 写真の縦横比を設定
        // ========================================

        float imageWidth =
            result.image.width > 0
                ? result.image.width
                : currentTexture.width;

        float imageHeight =
            result.image.height > 0
                ? result.image.height
                : currentTexture.height;

        if (aspectRatioFitter != null &&
            imageHeight > 0f)
        {
            aspectRatioFitter.aspectRatio =
                imageWidth / imageHeight;
        }

        Debug.Log(
            "写真を表示しました：" +
            result.image.path
        );

        int detectedCount =
            result.objects != null
                ? result.objects.Length
                : 0;

        Debug.Log(
            "検出された物体数：" +
            detectedCount
        );


        // ========================================
        // 検出範囲を作り直す
        // ========================================

        if (drawCoroutine != null)
        {
            StopCoroutine(drawCoroutine);

            drawCoroutine =
                null;
        }

        drawCoroutine =
            StartCoroutine(
                DrawBoxesNextFrame(
                    result
                )
            );

        return true;
    }


    // ========================================
    // UIサイズ反映後に検出範囲を描画
    // ========================================

    private IEnumerator DrawBoxesNextFrame(
        AnalysisResultData result
    )
    {
        // AspectRatioFitterの反映を待つ
        yield return null;

        Canvas.ForceUpdateCanvases();

        if (photoRawImage != null)
        {
            LayoutRebuilder
                .ForceRebuildLayoutImmediate(
                    photoRawImage.rectTransform
                );
        }

        ClearBoxes();

        if (result == null ||
            result.objects == null ||
            result.image == null)
        {
            drawCoroutine =
                null;

            yield break;
        }

        int imageWidth =
            result.image.width;

        int imageHeight =
            result.image.height;

        if (imageWidth <= 0)
        {
            imageWidth =
                currentTexture != null
                    ? currentTexture.width
                    : 1;
        }

        if (imageHeight <= 0)
        {
            imageHeight =
                currentTexture != null
                    ? currentTexture.height
                    : 1;
        }

        foreach (
            DetectedObjectData detectedObject
            in result.objects
        )
        {
            CreateDetectedBox(
                detectedObject,
                imageWidth,
                imageHeight
            );
        }

        drawCoroutine =
            null;
    }


    // ========================================
    // 1つの検出範囲を作成
    // ========================================

    private void CreateDetectedBox(
        DetectedObjectData detectedObject,
        int imageWidth,
        int imageHeight
    )
    {
        if (detectedObject == null)
        {
            return;
        }

        if (!TryGetDetectionBox(
                detectedObject,
                out float boxX,
                out float boxY,
                out float boxWidth,
                out float boxHeight))
        {
            Debug.LogWarning(
                detectedObject.name +
                "の検出範囲を取得できませんでした。"
            );

            return;
        }

        if (imageWidth <= 0 ||
            imageHeight <= 0)
        {
            Debug.LogError(
                "元画像のサイズが正しくありません。"
            );

            return;
        }

        if (boxContainer == null)
        {
            CreateBoxContainer();
        }

        if (boxContainer == null)
        {
            return;
        }

        float photoWidth =
            boxContainer.rect.width;

        float photoHeight =
            boxContainer.rect.height;

        if (photoWidth <= 0f ||
            photoHeight <= 0f)
        {
            Debug.LogWarning(
                "写真表示領域の大きさが0です。"
            );

            return;
        }


        // ========================================
        // 元画像座標からUI座標へ変換
        // ========================================

        float centerX =
            boxX +
            boxWidth / 2f;

        float centerY =
            boxY +
            boxHeight / 2f;

        float uiX =
            (
                centerX / imageWidth -
                0.5f
            ) *
            photoWidth;

        // 画像は左上が原点なのでYを反転
        float uiY =
            (
                0.5f -
                centerY / imageHeight
            ) *
            photoHeight;

        float uiWidth =
            boxWidth /
            imageWidth *
            photoWidth;

        float uiHeight =
            boxHeight /
            imageHeight *
            photoHeight;


        // ========================================
        // クリック範囲を作成
        // ========================================

        string safeObjectName =
            string.IsNullOrWhiteSpace(
                detectedObject.name
            )
                ? "Unknown"
                : detectedObject.name;

        string safeObjectId =
            string.IsNullOrWhiteSpace(
                detectedObject.object_id
            )
                ? "NoId"
                : detectedObject.object_id;

        GameObject boxObject =
            new GameObject(
                "DetectedBox_" +
                safeObjectName +
                "_" +
                safeObjectId,
                typeof(RectTransform),
                typeof(Image)
            );

        boxObject.transform.SetParent(
            boxContainer,
            false
        );

        RectTransform boxRect =
            boxObject.GetComponent<RectTransform>();

        boxRect.anchorMin =
            new Vector2(
                0.5f,
                0.5f
            );

        boxRect.anchorMax =
            new Vector2(
                0.5f,
                0.5f
            );

        boxRect.pivot =
            new Vector2(
                0.5f,
                0.5f
            );

        boxRect.anchoredPosition =
            new Vector2(
                uiX,
                uiY
            );

        boxRect.sizeDelta =
            new Vector2(
                Mathf.Max(
                    uiWidth,
                    1f
                ),
                Mathf.Max(
                    uiHeight,
                    1f
                )
            );

        boxRect.localScale =
            Vector3.one;


        // ========================================
        // 枠の見た目
        // ========================================

        Image boxImage =
            boxObject.GetComponent<Image>();

        if (showDetectionBoxes)
        {
            // 動作確認用の赤い枠
            boxImage.color =
                debugBoxColor;
        }
        else
        {
            // 透明なクリック範囲
            boxImage.color =
                new Color(
                    1f,
                    1f,
                    1f,
                    0f
                );
        }

        // 透明でもクリック可能にする
        boxImage.raycastTarget =
            true;


        // ========================================
        // 赤い外枠
        // ========================================

        Outline outline =
            boxObject.AddComponent<Outline>();

        outline.effectColor =
            outlineColor;

        outline.effectDistance =
            outlineDistance;

        outline.useGraphicAlpha =
            false;

        outline.enabled =
            showDetectionBoxes;


        // ========================================
        // クリック処理
        // ========================================

        DetectedBoxClick boxClick =
            boxObject.AddComponent
                <DetectedBoxClick>();

        boxClick.Initialize(
            detectedObject.name,
            detectedObject.object_id,
            detectedObject.confidence
        );

        Debug.Log(
            "クリック範囲を作成：" +
            detectedObject.name +
            " / X=" +
            boxX +
            " Y=" +
            boxY +
            " 幅=" +
            boxWidth +
            " 高さ=" +
            boxHeight +
            " / 枠表示=" +
            showDetectionBoxes
        );
    }


    // ========================================
    // JSONから検出範囲を取得
    // ========================================

    private bool TryGetDetectionBox(
        DetectedObjectData detectedObject,
        out float x,
        out float y,
        out float width,
        out float height
    )
    {
        x = 0f;
        y = 0f;
        width = 0f;
        height = 0f;

        if (detectedObject == null)
        {
            return false;
        }

        // mask_boxを優先
        if (detectedObject.position_original != null &&
            detectedObject.position_original.mask_box != null)
        {
            DetectedBoxData maskBox =
                detectedObject
                    .position_original
                    .mask_box;

            if (maskBox.width > 0f &&
                maskBox.height > 0f)
            {
                x = maskBox.x;
                y = maskBox.y;
                width = maskBox.width;
                height = maskBox.height;

                return true;
            }
        }

        // mask_boxがなければdetection_box
        if (detectedObject.position_original != null &&
            detectedObject.position_original.detection_box != null)
        {
            DetectedBoxData detectionBox =
                detectedObject
                    .position_original
                    .detection_box;

            if (detectionBox.width > 0f &&
                detectionBox.height > 0f)
            {
                x = detectionBox.x;
                y = detectionBox.y;
                width = detectionBox.width;
                height = detectionBox.height;

                return true;
            }
        }

        // 最後に四隅の座標を使用
        if (detectedObject.four_corners_original != null)
        {
            int[] topLeft =
                detectedObject
                    .four_corners_original
                    .top_left;

            int[] bottomRight =
                detectedObject
                    .four_corners_original
                    .bottom_right;

            if (topLeft != null &&
                topLeft.Length >= 2 &&
                bottomRight != null &&
                bottomRight.Length >= 2)
            {
                x = topLeft[0];
                y = topLeft[1];

                width =
                    Mathf.Abs(
                        bottomRight[0] -
                        topLeft[0]
                    );

                height =
                    Mathf.Abs(
                        bottomRight[1] -
                        topLeft[1]
                    );

                return width > 0f &&
                       height > 0f;
            }
        }

        return false;
    }


    // ========================================
    // 前回のクリック範囲を削除
    // ========================================

    private void ClearBoxes()
    {
        if (boxContainer == null)
        {
            return;
        }

        for (
            int i =
                boxContainer.childCount - 1;
            i >= 0;
            i--
        )
        {
            Transform child =
                boxContainer.GetChild(i);

            if (child == null)
            {
                continue;
            }

            // Destroyはフレーム終了時なので、
            // 先に無効化してクリックを止める
            child.gameObject.SetActive(
                false
            );

            Destroy(
                child.gameObject
            );
        }
    }


    // ========================================
    // 枠の表示・非表示を変更
    // ========================================

    public void SetDetectionBoxesVisible(
        bool isVisible
    )
    {
        showDetectionBoxes =
            isVisible;

        if (boxContainer == null)
        {
            return;
        }

        for (
            int i = 0;
            i < boxContainer.childCount;
            i++
        )
        {
            Transform child =
                boxContainer.GetChild(i);

            if (child == null)
            {
                continue;
            }

            Image boxImage =
                child.GetComponent<Image>();

            Outline outline =
                child.GetComponent<Outline>();

            if (boxImage != null)
            {
                if (showDetectionBoxes)
                {
                    boxImage.color =
                        debugBoxColor;
                }
                else
                {
                    boxImage.color =
                        new Color(
                            1f,
                            1f,
                            1f,
                            0f
                        );
                }

                // 枠が透明でもクリック可能
                boxImage.raycastTarget =
                    true;
            }

            if (outline != null)
            {
                outline.enabled =
                    showDetectionBoxes;
            }
        }
    }


    // ========================================
    // Inspectorの値を調整したとき
    // ========================================

    private void OnValidate()
    {
        checkInterval =
            Mathf.Max(
                checkInterval,
                0.1f
            );

        if (Application.isPlaying)
        {
            SetDetectionBoxesVisible(
                showDetectionBoxes
            );
        }
    }


    // ========================================
    // 終了処理
    // ========================================

    private void OnDestroy()
    {
        if (watchCoroutine != null)
        {
            StopCoroutine(
                watchCoroutine
            );

            watchCoroutine =
                null;
        }

        if (drawCoroutine != null)
        {
            StopCoroutine(
                drawCoroutine
            );

            drawCoroutine =
                null;
        }

        ClearBoxes();

        if (currentTexture != null)
        {
            if (photoRawImage != null)
            {
                photoRawImage.texture =
                    null;
            }

            Destroy(
                currentTexture
            );

            currentTexture =
                null;
        }
    }
}