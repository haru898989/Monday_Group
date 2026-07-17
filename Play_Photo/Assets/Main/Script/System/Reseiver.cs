using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;

public class Reseiver : MonoBehaviour
{
    // UDP通信
    private UdpClient client;
    private readonly int port = 1140;

    // 入力管理
    private PlayerInput playerInput_;

    // 機械学習の座標へ生成するPrefab
    [SerializeField]
    private GameObject objectPrefab;

    // ローディング画面
    [SerializeField]
    private GameObject loadingPanel;

    // Rayを飛ばすカメラ
    [SerializeField]
    private Camera targetCamera;

    // Python側で使用している画像サイズ
    [SerializeField]
    private float imageWidth = 346f;

    [SerializeField]
    private float imageHeight = 620f;

    // Unity上で画像を表示している範囲
    [SerializeField]
    private float worldWidth = 10f;

    [SerializeField]
    private float worldHeight = 10f;

    // Prefabを生成するZ座標
    [SerializeField]
    private float objectZ = 0f;

    // 受信データ
    private ReceivedData latestData;

    // UDP受信スレッドとUnityのメインスレッドで共有するために使用
    private readonly object dataLock = new object();

    // 前回生成したタッチ範囲
    private readonly List<GameObject> generatedObjects =
        new List<GameObject>();


    // Pythonから送られてくる物体情報
    [Serializable]
    public class ObjectData
    {
        public string name;

        public float x1;
        public float y1;

        public float x2;
        public float y2;

        public float x3;
        public float y3;

        public float x4;
        public float y4;
    }


    // Pythonから送られてくるJSON全体
    [Serializable]
    public class ReceivedData
    {
        public ObjectData[] objects;
    }


    private void Start()
    {
        // 最初はローディング画面を表示
        if (loadingPanel != null)
        {
            loadingPanel.SetActive(true);
        }

        // カメラが設定されていなければMain Cameraを使う
        if (targetCamera == null)
        {
            targetCamera = Camera.main;
        }

        // タッチ入力を有効にする
        playerInput_ = new PlayerInput();
        playerInput_.Enable();

        // UDP受信を開始
        try
        {
            client = new UdpClient(port);
            client.BeginReceive(ReceiveData, null);

            Debug.Log($"UDP受信を開始しました。ポート番号：{port}");
        }
        catch (Exception e)
        {
            Debug.LogError($"UDP開始エラー：{e.Message}");
        }
    }


    private void Update()
    {
        // Pythonから届いた座標を処理する
        UpdateDetectedObjects();

        // タッチ・クリックを処理する
        UpdateTouch();
    }


    /// <summary>
    /// Pythonから届いた座標にタッチ用Prefabを生成する
    /// </summary>
    private void UpdateDetectedObjects()
    {
        ReceivedData receivedData = null;

        // 受信データを安全に取り出す
        lock (dataLock)
        {
            if (latestData != null)
            {
                receivedData = latestData;
                latestData = null;
            }
        }

        // 新しいデータがなければ何もしない
        if (receivedData == null)
        {
            return;
        }

        // 受信できたらローディング画面を消す
        if (loadingPanel != null)
        {
            loadingPanel.SetActive(false);
        }

        // 前回生成したタッチ範囲を削除する
        ClearGeneratedObjects();

        if (receivedData.objects == null)
        {
            Debug.LogWarning("objectsのデータがありません。");
            return;
        }

        foreach (ObjectData obj in receivedData.objects)
        {
            CreateTouchObject(obj);
        }
    }


    /// <summary>
    /// 検出された座標へタッチ用オブジェクトを生成する
    /// </summary>
    private void CreateTouchObject(ObjectData obj)
    {
        if (objectPrefab == null)
        {
            Debug.LogError("Object Prefabが設定されていません。");
            return;
        }

        // 4点の座標から中心を求める
        float centerX = (obj.x1 + obj.x4) / 2f;
        float centerY = (obj.y1 + obj.y4) / 2f;

        // 検出範囲の幅と高さ
        float width = Mathf.Abs(obj.x2 - obj.x1);
        float height = Mathf.Abs(obj.y3 - obj.y1);

        // 画像座標からUnity座標へ変換
        float unityX =
            (centerX / imageWidth - 0.5f) * worldWidth;

        // Python画像は左上が原点なのでY座標を反転
        float unityY =
            (0.5f - centerY / imageHeight) * worldHeight;

        // 検出範囲の大きさをUnity用に変換
        float unityWidth =
            width / imageWidth * worldWidth;

        float unityHeight =
            height / imageHeight * worldHeight;

        // 検出座標にPrefabを生成
        GameObject generatedObject = Instantiate(
            objectPrefab,
            new Vector3(unityX, unityY, objectZ),
            Quaternion.identity
        );

        generatedObject.name = obj.name;

        // 検出範囲に合わせてサイズ変更
        generatedObject.transform.localScale = new Vector3(
            unityWidth,
            unityHeight,
            1f
        );

        // Colliderがなければ自動で追加
        Collider targetCollider =
            generatedObject.GetComponent<Collider>();

        if (targetCollider == null)
        {
            generatedObject.AddComponent<BoxCollider>();
        }

        generatedObjects.Add(generatedObject);

        Debug.Log(
            $"{obj.name}のタッチ範囲を生成しました。" +
            $" 座標：({unityX}, {unityY})"
        );
    }


    /// <summary>
    /// タッチまたはマウスクリックを検出する
    /// </summary>
    private void UpdateTouch()
    {
        if (playerInput_ == null)
        {
            return;
        }

        // タッチ・クリックされた瞬間
        if (!playerInput_.Player.touch.triggered)
        {
            return;
        }

        // マウスやタッチ入力が取得できない場合
        if (Pointer.current == null)
        {
            Debug.LogWarning("Pointerが取得できません。");
            return;
        }

        if (targetCamera == null)
        {
            Debug.LogError("Rayを飛ばすCameraが設定されていません。");
            return;
        }

        // タッチした画面座標
        Vector2 screenPosition =
            Pointer.current.position.ReadValue();

        // カメラからタッチ位置へRayを飛ばす
        Ray ray =
            targetCamera.ScreenPointToRay(screenPosition);

        if (Physics.Raycast(ray, out RaycastHit hit))
        {
            Debug.Log(
                $"タッチしたオブジェクト：{hit.collider.gameObject.name}"
            );

            // Colliderが子オブジェクトに付いていても探せるようにする
            GimmickBase touchGimmick =
                hit.collider.GetComponentInParent<GimmickBase>();

            if (touchGimmick != null)
            {
                touchGimmick.ActivateMagic();
            }
            else
            {
                Debug.LogWarning(
                    $"{hit.collider.gameObject.name}に" +
                    "GimmickBaseを実装したスクリプトがありません。"
                );
            }
        }
    }


    /// <summary>
    /// 前回生成したタッチ範囲を削除する
    /// </summary>
    private void ClearGeneratedObjects()
    {
        foreach (GameObject generatedObject in generatedObjects)
        {
            if (generatedObject != null)
            {
                Destroy(generatedObject);
            }
        }

        generatedObjects.Clear();
    }


    /// <summary>
    /// UDPデータを受信する
    /// </summary>
    private void ReceiveData(IAsyncResult result)
    {
        if (client == null)
        {
            return;
        }

        try
        {
            IPEndPoint ip =
                new IPEndPoint(IPAddress.Any, port);

            byte[] data =
                client.EndReceive(result, ref ip);

            string json =
                Encoding.UTF8.GetString(data);

            ReceivedData receivedData =
                JsonUtility.FromJson<ReceivedData>(json);

            lock (dataLock)
            {
                latestData = receivedData;
            }

            Debug.Log($"受信したJSON：{json}");
        }
        catch (ObjectDisposedException)
        {
            // Unity終了時にUDPが閉じられた場合は何もしない
            return;
        }
        catch (Exception e)
        {
            Debug.LogError($"受信エラー：{e.Message}");
        }

        // 次のデータを待つ
        if (client != null && client.Client != null)
        {
            try
            {
                client.BeginReceive(ReceiveData, null);
            }
            catch (ObjectDisposedException)
            {
                // 終了時なので何もしない
            }
        }
    }


    private void OnDestroy()
    {
        // 入力を無効化
        if (playerInput_ != null)
        {
            playerInput_.Disable();
            playerInput_.Dispose();
            playerInput_ = null;
        }

        // UDPを閉じる
        if (client != null)
        {
            client.Close();
            client = null;

            Debug.Log("UDPポートを閉じました。");
        }

        ClearGeneratedObjects();
    }
}