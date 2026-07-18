using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;

public class Reseiver : MonoBehaviour
{
    // ========================================
    // UDP通信
    // ========================================

    private UdpClient client;

    [SerializeField]
    private int port = 1140;


    // ========================================
    // タッチ入力
    // ========================================

    private PlayerInput playerInput_;

    [SerializeField]
    private Camera targetCamera;


    // ========================================
    // Unity画面の設定
    // ========================================

    [SerializeField]
    private GameObject loadingPanel;

    // Python側から画像サイズを取得できなかった場合に使用
    [SerializeField]
    private float defaultImageWidth = 346f;

    [SerializeField]
    private float defaultImageHeight = 620f;

    // Unity上で写真を表示している大きさ
    [SerializeField]
    private float worldWidth = 10f;

    [SerializeField]
    private float worldHeight = 10f;

    // 写真の中心位置
    [SerializeField]
    private Vector3 imageCenter = Vector3.zero;

    // ギミックを置くZ座標
    [SerializeField]
    private float objectZ = 0f;


    // ========================================
    // ギミックPrefabの対応表
    // ========================================

    [SerializeField]
    private GimmickPrefabData[] gimmickPrefabs;


    // ========================================
    // 受信データ
    // ========================================

    private ReceivedData latestData;
    private string latestJson;

    // UDP受信スレッドとUnityのメインスレッドで
    // 安全にデータを共有するために使用
    private readonly object dataLock = new object();

    // 現在生成されているギミック
    private readonly List<GameObject> generatedObjects =
        new List<GameObject>();

    // object_idと生成済みギミックを対応させる
    private readonly Dictionary<string, GimmickBase>
        generatedGimmicksById =
            new Dictionary<string, GimmickBase>();


    // ========================================
    // Inspectorで設定するPrefab対応表
    // ========================================

    [Serializable]
    public class GimmickPrefabData
    {
        // Pythonから届く物体名
        // 例：dog、person、chair
        public string objectName;

        // その物体名に対応するPrefab
        public GameObject prefab;
    }


    // ========================================
    // PythonのJSONに対応するクラス
    // ========================================

    [Serializable]
    public class ImageData
    {
        public string path;
        public float width;
        public float height;
    }


    [Serializable]
    public class BoxData
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
    public class PositionOriginal
    {
        public int[] center;

        public BoxData detection_box;
        public BoxData mask_box;
    }


    [Serializable]
    public class FourCornersOriginal
    {
        public int[] top_left;
        public int[] top_right;
        public int[] bottom_right;
        public int[] bottom_left;
    }


    [Serializable]
    public class ObjectData
    {
        // 新しいPython JSON用
        public string object_id;
        public string name;
        public float confidence;

        public PositionOriginal position_original;
        public FourCornersOriginal four_corners_original;

        // 以前のJSON形式にも対応
        public float x1;
        public float y1;

        public float x2;
        public float y2;

        public float x3;
        public float y3;

        public float x4;
        public float y4;
    }


    [Serializable]
    public class ReceivedData
    {
        public string schema_version;

        public ImageData image;

        public int object_count;

        public ObjectData[] objects;
    }


    // ========================================
    // Unity開始時
    // ========================================

    private void Start()
    {
        // 最初はローディング画面を表示
        if (loadingPanel != null)
        {
            loadingPanel.SetActive(true);
        }

        // Cameraが未設定ならMain Cameraを使用
        if (targetCamera == null)
        {
            targetCamera = Camera.main;
        }

        // タッチ入力を有効化
        try
        {
            playerInput_ = new PlayerInput();
            playerInput_.Enable();
        }
        catch (Exception e)
        {
            Debug.LogError(
                $"入力機能の開始に失敗しました：{e.Message}"
            );
        }

        // UDP受信開始
        try
        {
            client = new UdpClient(port);
            client.BeginReceive(ReceiveData, null);

            Debug.Log(
                $"UDP受信を開始しました。ポート番号：{port}"
            );
        }
        catch (Exception e)
        {
            Debug.LogError(
                $"UDPの開始に失敗しました：{e.Message}"
            );
        }
    }


    // ========================================
    // 毎フレーム実行
    // ========================================

    private void Update()
    {
        // Pythonから受信した検出結果を処理
        UpdateDetectedObjects();

        // 今は写真上のUI枠からギミックを実行するため、
        // 以前の3D Collider方式は一旦停止する
        // UpdateTouch();
    }


    // ========================================
    // Pythonの検出結果を処理
    // ========================================

    private void UpdateDetectedObjects()
    {
        ReceivedData receivedData = null;
        string receivedJson = null;

        lock (dataLock)
        {
            if (latestData != null)
            {
                receivedData = latestData;
                receivedJson = latestJson;

                latestData = null;
                latestJson = null;
            }
        }

        // 新しい受信データがなければ終了
        if (receivedData == null)
        {
            return;
        }

        Debug.Log(
            $"PythonからJSONを受信しました：\n{receivedJson}"
        );

        // 受信できたらLoading画面を消す
        if (loadingPanel != null)
        {
            loadingPanel.SetActive(false);
        }

        // 前回生成したギミックを削除
        ClearGeneratedObjects();

        if (receivedData.objects == null)
        {
            Debug.LogWarning(
                "JSONの中にobjectsがありません。"
            );

            return;
        }

        // JSONに含まれる画像サイズを使用
        float receivedImageWidth = defaultImageWidth;
        float receivedImageHeight = defaultImageHeight;

        if (receivedData.image != null)
        {
            if (receivedData.image.width > 0)
            {
                receivedImageWidth =
                    receivedData.image.width;
            }

            if (receivedData.image.height > 0)
            {
                receivedImageHeight =
                    receivedData.image.height;
            }
        }

        Debug.Log(
            $"画像サイズ：" +
            $"{receivedImageWidth} × {receivedImageHeight}"
        );

        foreach (ObjectData obj in receivedData.objects)
        {
            CreateGimmickObject(
                obj,
                receivedImageWidth,
                receivedImageHeight
            );
        }
    }


    // ========================================
    // 検出位置に対応するギミックを生成
    // ========================================

    private void CreateGimmickObject(
        ObjectData obj,
        float imageWidth,
        float imageHeight
    )
    {
        if (obj == null)
        {
            return;
        }

        if (string.IsNullOrWhiteSpace(obj.name))
        {
            Debug.LogWarning(
                "物体名が空の検出データがありました。"
            );

            return;
        }

        // 検出名に対応するPrefabを取得
        GameObject targetPrefab =
            FindGimmickPrefab(obj.name);

        if (targetPrefab == null)
        {
            Debug.LogWarning(
                $"{obj.name}に対応するPrefabがありません。"
            );

            return;
        }

        // 検出範囲を取得
        if (!TryGetDetectionBox(
                obj,
                out float boxX,
                out float boxY,
                out float boxWidth,
                out float boxHeight))
        {
            Debug.LogWarning(
                $"{obj.name}の座標を取得できませんでした。"
            );

            return;
        }

        if (imageWidth <= 0 || imageHeight <= 0)
        {
            Debug.LogError(
                "画像サイズが正しくありません。"
            );

            return;
        }

        // 検出範囲の中心座標
        float centerX =
            boxX + boxWidth / 2f;

        float centerY =
            boxY + boxHeight / 2f;

        // 画像座標からUnity座標へ変換
        float unityX =
            (centerX / imageWidth - 0.5f)
            * worldWidth;

        // 画像は左上が原点なのでYを反転
        float unityY =
            (0.5f - centerY / imageHeight)
            * worldHeight;

        // 検出範囲の大きさをUnity用へ変換
        float unityWidth =
            boxWidth / imageWidth
            * worldWidth;

        float unityHeight =
            boxHeight / imageHeight
            * worldHeight;

        // 画像の中心位置を加える
        Vector3 generatePosition =
            imageCenter +
            new Vector3(
                unityX,
                unityY,
                objectZ
            );

        // 対応したPrefabを生成
        GameObject generatedObject =
            Instantiate(
                targetPrefab,
                generatePosition,
                Quaternion.identity
            );

        generatedObject.name =
            $"{obj.name}_Gimmick";

        // 検出範囲に合わせてサイズ変更
        generatedObject.transform.localScale =
            new Vector3(
                Mathf.Max(unityWidth, 0.01f),
                Mathf.Max(unityHeight, 0.01f),
                1f
            );

        // ColliderがなければBoxColliderを追加
        Collider targetCollider =
            generatedObject.GetComponentInChildren<Collider>();

        if (targetCollider == null)
        {
            generatedObject.AddComponent<BoxCollider>();

            Debug.LogWarning(
                $"{targetPrefab.name}にColliderがなかったため、" +
                "BoxColliderを自動追加しました。"
            );
        }

        // 生成したPrefabからGimmickBaseを取得
        GimmickBase generatedGimmick =
            generatedObject.GetComponentInChildren<GimmickBase>(
                true
            );

        if (generatedGimmick != null)
        {
            if (!string.IsNullOrWhiteSpace(obj.object_id))
            {
                generatedGimmicksById[obj.object_id] =
                    generatedGimmick;

                Debug.Log(
                    $"ギミックを登録しました：" +
                    $"{obj.name} / {obj.object_id}"
                );
            }
            else
            {
                Debug.LogWarning(
                    $"{obj.name}のobject_idが空です。"
                );
            }
        }
        else
        {
            Debug.LogWarning(
                $"{targetPrefab.name}に、" +
                "GimmickBaseを実装したスクリプトがありません。"
            );
        }

        generatedObjects.Add(generatedObject);

        Debug.Log(
            $"{obj.name}を検出しました。\n" +
            $"Prefab：{targetPrefab.name}\n" +
            $"位置：({unityX}, {unityY})\n" +
            $"大きさ：({unityWidth}, {unityHeight})\n" +
            $"信頼度：{obj.confidence}"
        );
    }


    // ========================================
    // JSONから検出範囲を取得
    // ========================================

    private bool TryGetDetectionBox(
        ObjectData obj,
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

        // 1. mask_boxを優先して使用
        if (obj.position_original != null &&
            obj.position_original.mask_box != null)
        {
            BoxData box =
                obj.position_original.mask_box;

            if (box.width > 0 &&
                box.height > 0)
            {
                x = box.x;
                y = box.y;
                width = box.width;
                height = box.height;

                return true;
            }
        }

        // 2. mask_boxがなければdetection_boxを使用
        if (obj.position_original != null &&
            obj.position_original.detection_box != null)
        {
            BoxData box =
                obj.position_original.detection_box;

            if (box.width > 0 &&
                box.height > 0)
            {
                x = box.x;
                y = box.y;
                width = box.width;
                height = box.height;

                return true;
            }
        }

        // 3. 4角座標を使用
        if (obj.four_corners_original != null)
        {
            int[] topLeft =
                obj.four_corners_original.top_left;

            int[] bottomRight =
                obj.four_corners_original.bottom_right;

            if (IsValidPoint(topLeft) &&
                IsValidPoint(bottomRight))
            {
                x = topLeft[0];
                y = topLeft[1];

                width =
                    Mathf.Abs(
                        bottomRight[0] - topLeft[0]
                    );

                height =
                    Mathf.Abs(
                        bottomRight[1] - topLeft[1]
                    );

                if (width > 0 && height > 0)
                {
                    return true;
                }
            }
        }

        // 4. 以前のx1～y4形式を使用
        float minX = Mathf.Min(
            obj.x1,
            obj.x2,
            obj.x3,
            obj.x4
        );

        float maxX = Mathf.Max(
            obj.x1,
            obj.x2,
            obj.x3,
            obj.x4
        );

        float minY = Mathf.Min(
            obj.y1,
            obj.y2,
            obj.y3,
            obj.y4
        );

        float maxY = Mathf.Max(
            obj.y1,
            obj.y2,
            obj.y3,
            obj.y4
        );

        float oldWidth = maxX - minX;
        float oldHeight = maxY - minY;

        if (oldWidth > 0 &&
            oldHeight > 0)
        {
            x = minX;
            y = minY;
            width = oldWidth;
            height = oldHeight;

            return true;
        }

        return false;
    }


    private bool IsValidPoint(int[] point)
    {
        return point != null &&
               point.Length >= 2;
    }


    // ========================================
    // 名前に対応するPrefabを探す
    // ========================================

    private GameObject FindGimmickPrefab(
        string objectName
    )
    {
        if (gimmickPrefabs == null)
        {
            return null;
        }

        foreach (
            GimmickPrefabData data
            in gimmickPrefabs
        )
        {
            if (data == null ||
                data.prefab == null)
            {
                continue;
            }

            if (string.Equals(
                    data.objectName?.Trim(),
                    objectName.Trim(),
                    StringComparison.OrdinalIgnoreCase))
            {
                return data.prefab;
            }
        }

        return null;
    }


    // ========================================
    // UIの赤い枠からギミックを実行
    // ========================================

    public void ActivateGimmickFromUI(
        string objectId,
        string objectName
    )
    {
        // object_idから対応するギミックを探す
        if (!string.IsNullOrWhiteSpace(objectId) &&
            generatedGimmicksById.TryGetValue(
                objectId,
                out GimmickBase targetGimmick
            ) &&
            targetGimmick != null)
        {
            Debug.Log(
                $"UIからギミックを実行：" +
                $"{objectName} / {objectId}"
            );

            targetGimmick.ActivateMagic();
            return;
        }

        // object_idで見つからなかった場合は、
        // 生成したオブジェクト名から探す
        foreach (
            GameObject generatedObject
            in generatedObjects
        )
        {
            if (generatedObject == null)
            {
                continue;
            }

            string expectedName =
                objectName + "_Gimmick";

            if (!string.Equals(
                    generatedObject.name,
                    expectedName,
                    StringComparison.OrdinalIgnoreCase))
            {
                continue;
            }

            GimmickBase fallbackGimmick =
                generatedObject
                    .GetComponentInChildren<GimmickBase>(
                        true
                    );

            if (fallbackGimmick != null)
            {
                Debug.Log(
                    $"名前からギミックを実行：" +
                    objectName
                );

                fallbackGimmick.ActivateMagic();
                return;
            }
        }

        Debug.LogWarning(
            $"{objectName}（{objectId}）に対応する" +
            "生成済みギミックが見つかりません。"
        );
    }


    // ========================================
    // 以前の3Dタッチ・クリック処理
    // 現在はUpdateから呼んでいない
    // ========================================

    private void UpdateTouch()
    {
        if (playerInput_ == null)
        {
            return;
        }

        // タッチまたはクリックされた瞬間だけ処理
        if (!playerInput_.Player.touch.triggered)
        {
            return;
        }

        if (Pointer.current == null)
        {
            Debug.LogWarning(
                "Pointerを取得できませんでした。"
            );

            return;
        }

        if (targetCamera == null)
        {
            Debug.LogError(
                "Target Cameraが設定されていません。"
            );

            return;
        }

        // タッチ・クリックした画面座標
        Vector2 screenPosition =
            Pointer.current.position.ReadValue();

        // カメラからタッチ位置へRayを飛ばす
        Ray ray =
            targetCamera.ScreenPointToRay(
                screenPosition
            );

        if (Physics.Raycast(
                ray,
                out RaycastHit hit,
                Mathf.Infinity))
        {
            Debug.Log(
                $"タッチしたオブジェクト：" +
                $"{hit.collider.gameObject.name}"
            );

            // Colliderが子にあっても親から探す
            GimmickBase touchGimmick =
                hit.collider
                   .GetComponentInParent<GimmickBase>();

            if (touchGimmick != null)
            {
                touchGimmick.ActivateMagic();
            }
            else
            {
                Debug.LogWarning(
                    $"{hit.collider.gameObject.name}に、" +
                    "GimmickBaseを実装したスクリプトがありません。"
                );
            }
        }
        else
        {
            Debug.Log(
                "タッチした場所にColliderはありません。"
            );
        }
    }


    // ========================================
    // 前回生成したギミックを削除
    // ========================================

    private void ClearGeneratedObjects()
    {
        foreach (
            GameObject generatedObject
            in generatedObjects
        )
        {
            if (generatedObject != null)
            {
                Destroy(generatedObject);
            }
        }

        generatedObjects.Clear();
        generatedGimmicksById.Clear();
    }


    // ========================================
    // UDP受信処理
    // ========================================

    private void ReceiveData(
        IAsyncResult result
    )
    {
        if (client == null)
        {
            return;
        }

        try
        {
            IPEndPoint ip =
                new IPEndPoint(
                    IPAddress.Any,
                    port
                );

            byte[] data =
                client.EndReceive(
                    result,
                    ref ip
                );

            string json =
                Encoding.UTF8.GetString(data);

            ReceivedData receivedData =
                JsonUtility.FromJson<ReceivedData>(
                    json
                );

            if (receivedData == null)
            {
                throw new Exception(
                    "JSONをReceivedDataへ変換できませんでした。"
                );
            }

            lock (dataLock)
            {
                latestData = receivedData;
                latestJson = json;
            }
        }
        catch (ObjectDisposedException)
        {
            // Unity終了時にポートが閉じられた
            return;
        }
        catch (SocketException e)
        {
            Debug.LogError(
                $"UDP受信エラー：{e.Message}"
            );
        }
        catch (Exception e)
        {
            Debug.LogError(
                $"受信データ処理エラー：{e.Message}"
            );
        }

        // 次のデータを待つ
        if (client != null)
        {
            try
            {
                client.BeginReceive(
                    ReceiveData,
                    null
                );
            }
            catch (ObjectDisposedException)
            {
                // Unity終了中なので何もしない
            }
            catch (SocketException)
            {
                // ポート終了中なので何もしない
            }
        }
    }


    // ========================================
    // 終了処理
    // ========================================

    private void OnDestroy()
    {
        // 入力を停止
        if (playerInput_ != null)
        {
            playerInput_.Disable();
            playerInput_.Dispose();
            playerInput_ = null;
        }

        // UDPポートを閉じる
        if (client != null)
        {
            client.Close();
            client = null;

            Debug.Log(
                "UDPポートを閉じました。"
            );
        }

        ClearGeneratedObjects();
    }
}