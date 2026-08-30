using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.Rendering;
using UnityEngine.Serialization;

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

    private MuseumLoadingPresenter museumLoadingPresenter;
    private bool loadingHideRequested;

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

    // 元画像の縦横比を保って実際に表示する大きさ
    private float displayWorldWidth = 10f;
    private float displayWorldHeight = 10f;

    // Prefabを生成するZ座標
    [SerializeField]
    private float objectZ = 0f;

    // 実行画面の背景として表示する受信画像
    [SerializeField]
    private string backgroundPhotoFileName = "sample.jpg";

    // 当たり判定・切り抜き画像より奥へ配置する
    [SerializeField]
    private float backgroundZOffset = 0.001f;

    private GameObject photoBackground;
    private Texture2D backgroundTexture;
    private Material backgroundMaterial;

    // 写真の大きさへ自動で追従する額縁
    [SerializeField]
    private Sprite photoFrameSprite;

    // カメラから見て写真より少し手前へ配置する
    [SerializeField]
    private float frameZOffset = -0.0005f;

    private GameObject photoFrame;
    private SpriteRenderer photoFrameRenderer;

    // 受信データ
    private ReceivedData latestData;

    // UDP受信スレッドとUnityのメインスレッドで共有するために使用
    private readonly object dataLock = new object();

    // 前回生成したタッチ範囲
    private readonly List<GameObject> generatedObjects =
        new List<GameObject>();

    // 実行時に生成したテクスチャとマテリアル
    private readonly List<UnityEngine.Object> generatedResources =
        new List<UnityEngine.Object>();

    [SerializeField]
    private AudioClip pianoAudioClip;

    [SerializeField]
    private AudioClip dogAudioClip;

    [SerializeField]
    private AudioClip catAudioClip;

    [SerializeField]
    private AudioClip carAudioClip;

    [SerializeField]
    private AudioClip waterAudioClip;

    [SerializeField]
    private AudioClip balloonAudioClip;

    [SerializeField]
    private AudioClip computerAudioClip;

    [SerializeField]
    private AudioClip treasureChestAudioClip;

    [SerializeField]
    private AudioClip clockAudioClip;

    [SerializeField]
    private AudioClip airplaneAudioClip;

    [SerializeField]
    private AudioClip toyAudioClip;

    [SerializeField]
    private AudioClip phoneAudioClip;

    [SerializeField]
    private AudioClip phoneVibrationAudioClip;

    [FormerlySerializedAs("bridgeAudioClip")]
    [SerializeField]
    private AudioClip buildingAudioClip;

    [SerializeField]
    private AudioClip cloudAudioClip;

    [SerializeField]
    private AudioClip carbonatedDrinkAudioClip;

    [SerializeField]
    private AudioClip mountainAudioClip;

    [SerializeField]
    private AudioClip birdAudioClip;

    [SerializeField]
    private AudioClip ballAudioClip;

    [SerializeField]
    private AudioClip humanDanceAudioClip;

    [SerializeField]
    private AudioClip glassBreakAudioClip;

    [SerializeField]
    private AudioClip boatAudioClip;
    
    [SerializeField]
    private AudioClip trainAudioClip;

    [SerializeField]
    private ParticleSystem balloonPopEffect;

    // Pythonから送られてくる物体情報
    [Serializable]
    public class ObjectData
    {
        public string name;
        public string cutoutFileName;

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
        public float imageWidth;
        public float imageHeight;
        public ObjectData[] objects;
    }


    private void Start()
    {
        PrepareMuseumLoadingPresenter();

        // 最初はローディング画面を表示
        SetLoadingVisible(true);

        // カメラが設定されていなければMain Cameraを使う
        if (targetCamera == null)
        {
            targetCamera = Camera.main;
        }

        // シーンに残っている旧ギミックのCubeは表示しない
        HideLegacyGimmickMeshes();

        UpdateDisplayWorldSize(imageWidth, imageHeight);

        // Main Sceneへ移動する前に保存された写真を背景へ表示する
        RefreshPhotoBackground();

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

        float receivedImageWidth =
            receivedData.imageWidth > 0f
                ? receivedData.imageWidth
                : imageWidth;

        float receivedImageHeight =
            receivedData.imageHeight > 0f
                ? receivedData.imageHeight
                : imageHeight;

        // 消しゴムマジック完了後の画像を背景へ反映する
        backgroundPhotoFileName = "sample_erased.png";
        RefreshPhotoBackground(
            receivedImageWidth,
            receivedImageHeight
        );

        // 前回生成したタッチ範囲を削除する
        ClearGeneratedObjects();

        if (receivedData.objects == null)
        {
            Debug.LogWarning("objectsのデータがありません。");
            return;
        }

        foreach (ObjectData obj in receivedData.objects)
        {
            CreateTouchObject(
                obj,
                receivedImageWidth,
                receivedImageHeight
            );
        }
    }


    /// <summary>
    /// 検出された座標へタッチ用オブジェクトを生成する
    /// </summary>
    private void CreateTouchObject(
        ObjectData obj,
        float sourceImageWidth,
        float sourceImageHeight
    )
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
            (centerX / sourceImageWidth - 0.5f)
            * displayWorldWidth;

        // Python画像は左上が原点なのでY座標を反転
        float unityY =
            (0.5f - centerY / sourceImageHeight)
            * displayWorldHeight;

        // 検出範囲の大きさをUnity用に変換
        float unityWidth =
            width / sourceImageWidth * displayWorldWidth;

        float unityHeight =
            height / sourceImageHeight * displayWorldHeight;

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

        // PrefabのCubeは当たり判定だけに使用し、常に透明にする
        HideHitboxRenderers(generatedObject);

        Renderer cutoutRenderer =
            CreateCutoutChild(generatedObject, obj);

        if (cutoutRenderer != null)
        {
            AttachGimmick(
                generatedObject,
                cutoutRenderer,
                obj.name
            );

            // 当たり判定の子要素に切り抜き画像が生成されてからローディングを閉じる
            SetLoadingVisible(false);
        }

        generatedObjects.Add(generatedObject);

        Debug.Log(
            $"{obj.name}のタッチ範囲を生成しました。" +
            $" 座標：({unityX}, {unityY})"
        );
    }


    private void SetLoadingVisible(bool isVisible)
    {
        if (isVisible)
        {
            loadingHideRequested = false;

            if (loadingPanel != null)
            {
                loadingPanel.SetActive(true);

                if (museumLoadingPresenter != null)
                {
                    museumLoadingPresenter.Show();
                }
            }

            DualDisplayManager.SetPlayLoadingVisible(true);
            return;
        }

        if (loadingHideRequested)
        {
            return;
        }

        loadingHideRequested = true;

        if (museumLoadingPresenter != null &&
            loadingPanel != null &&
            loadingPanel.activeInHierarchy)
        {
            museumLoadingPresenter.HideWithCompletion(
                FinishHidingLoadingView
            );
            return;
        }

        FinishHidingLoadingView();
    }

    private void PrepareMuseumLoadingPresenter()
    {
        if (loadingPanel == null)
        {
            return;
        }

        museumLoadingPresenter =
            loadingPanel.GetComponent<MuseumLoadingPresenter>();

        if (museumLoadingPresenter == null)
        {
            museumLoadingPresenter =
                loadingPanel.AddComponent<MuseumLoadingPresenter>();
        }
    }

    private void FinishHidingLoadingView()
    {
        if (loadingPanel != null)
        {
            loadingPanel.SetActive(false);
        }

        DualDisplayManager.SetPlayLoadingVisible(false);
    }


    /// <summary>
    /// 認識した物体名に対応するギミックを動的な当たり判定へ追加する
    /// </summary>
    private void AttachGimmick(
        GameObject target,
        Renderer cutoutRenderer,
        string objectName
    )
    {
        if (target == null || string.IsNullOrWhiteSpace(objectName))
        {
            return;
        }

        string normalizedName =
            objectName.Trim().ToLowerInvariant();

        switch (normalizedName)
        {
            case "person":
            case "human":
                HumanGimmick1 humanGimmick =
                    GetOrAddComponent<HumanGimmick1>(target);

                humanGimmick.SetTargetRenderer(cutoutRenderer);

                humanGimmick.SetAudioClip(
                    humanDanceAudioClip
                );

                break;

            case "cat":
                CatGimmick catGimmick =
                    GetOrAddComponent<CatGimmick>(target);

                catGimmick.SetAudioClip(catAudioClip);
                break;

            case "dog":
                DogGimmick dogGimmick =
                    GetOrAddComponent<DogGimmick>(target);

                dogGimmick.SetAudioClip(dogAudioClip);
                break;

            case "piano":
                InstrumentGimmick InstGimmick =
                    GetOrAddComponent<InstrumentGimmick>(target);
                InstGimmick.SetAudioClip(pianoAudioClip);
                break;

            case "car":
                CarGimmick carGimmick =
                    GetOrAddComponent<CarGimmick>(target);

                carGimmick.SetAudioClip(carAudioClip);
                break;

            case "water":
            case "river":
            case "lake":
            case "pond":
            case "sea":
            case "ocean":
                WaterGimmick waterGimmick =
                    GetOrAddComponent<WaterGimmick>(target);

                waterGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                waterGimmick.SetAudioClip(
                    waterAudioClip
                );

                break;

            case "balloon":
                BalloonGimmick balloonGimmick =
                    GetOrAddComponent<BalloonGimmick>(target);

                balloonGimmick.SetTargetRenderer(cutoutRenderer);
                balloonGimmick.SetAudioClip(balloonAudioClip);
                balloonGimmick.SetPopEffect(balloonPopEffect);

                break;

            case "computer":
            case "laptop":
            case "pc":
                ComputerGimmick computerGimmick =
                    GetOrAddComponent<ComputerGimmick>(target);

                computerGimmick.SetTargetRenderer(cutoutRenderer);
                computerGimmick.SetAudioClip(computerAudioClip);
                break;

            case "treasure box":
            case "treasure_chest":
            case "chest":
                TreasureChestGimmick chestGimmick =
                    GetOrAddComponent<TreasureChestGimmick>(target);

                chestGimmick.SetTargetRenderer(cutoutRenderer);
                chestGimmick.SetAudioClip(treasureChestAudioClip);
                break;

            case "tree":
                TreeGimmick treeGimmick =
                    GetOrAddComponent<TreeGimmick>(target);

                treeGimmick.SetTargetRenderer(
                    cutoutRenderer
                );
                break;

            case "airplane":
            case "plane":
            AirplaneGimmick airplaneGimmick =
            GetOrAddComponent<AirplaneGimmick>(target);
            
            airplaneGimmick.SetAudioClip(airplaneAudioClip);
            break;

            case "toy":
                ToyGimmick toyGimmick =
                    GetOrAddComponent<ToyGimmick>(target);

                toyGimmick.SetAudioClip(toyAudioClip);
                break;

            case "fish":
                FishGlowGimmick fishGimmick =
                    GetOrAddComponent<FishGlowGimmick>(target);

                fishGimmick.SetTargetRenderer(cutoutRenderer);
                break;

            case "flower":
            case "plant":
            case "rose":
            case "sunflower":
            case "daisy":
                FlowerGimmick flowerGimmick =
                    GetOrAddComponent<FlowerGimmick>(target);

                flowerGimmick.SetTargetRenderer(cutoutRenderer);
                break;

            case "cell phone":
            case "mobile phone":
            case "smartphone":
            case "phone":
                PhoneGimmick phoneGimmick =
                    GetOrAddComponent<PhoneGimmick>(target);

                phoneGimmick.SetTargetRenderer(cutoutRenderer);

                phoneGimmick.SetAudioClip(
                    phoneAudioClip,
                    phoneVibrationAudioClip
                );

                break;

            case "ball":
            case "sports ball":
            case "soccer ball":
            case "football":
            case "basketball":
            case "baseball":
            case "tennis ball":
                BallGimmick ballGimmick =
                    GetOrAddComponent<BallGimmick>(target);

                ballGimmick.SetAudioClip(
                    ballAudioClip
                );

                break;


            case "building":
            case "house":
            case "apartment":
            case "apartment building":
            case "office building":
            case "warehouse":
            case "school":
            case "store":
            case "shop":
            case "station":
            case "stadium":
            case "hotel":
            case "skyscraper":
            case "tower":
            case "castle":
            case "palace":
            case "church":
            case "temple":
            case "bridge":
                BuildingGimmick buildingGimmick =
                    GetOrAddComponent<BuildingGimmick>(target);

                buildingGimmick.SetTargetRenderer(cutoutRenderer);

                buildingGimmick.SetAudioClip(
                    buildingAudioClip
                );

                break;

            case "clock":

                if (clockAudioClip == null)
                {
                    Debug.LogError("ReseiverのclockAudioClipがNULLです！");
                }
                else
                {
                    Debug.Log("Reseiverの時計音声：" + clockAudioClip.name);
                }

                ClockGimmick clockGimmick =
                    GetOrAddComponent<ClockGimmick>(target);

                clockGimmick.SetAudioClip(clockAudioClip);

                break;

            case "moon":
                MoonGimmick moonGimmick =
                    GetOrAddComponent<MoonGimmick>(target);

                moonGimmick.SetTargetRenderer(cutoutRenderer);
                break;

            case "cloud":
            case "clouds":
                CloudGimmick cloudGimmick =
                    GetOrAddComponent<CloudGimmick>(target);

                cloudGimmick.SetTargetRenderer(cutoutRenderer);

                cloudGimmick.SetAudioClip(
                    cloudAudioClip
                );

                break;

            case "soda":
            case "soft drink":
            case "cola":
            case "coke":
            case "carbonated drink":
            case "beer":
            case "drink":
            case "cup":
                CarbonatedDrinkGimmick drinkGimmick =
                    GetOrAddComponent<CarbonatedDrinkGimmick>(target);

                drinkGimmick.SetTargetRenderer(cutoutRenderer);

                drinkGimmick.SetAudioClip(
                    carbonatedDrinkAudioClip
                );

                break;

            case "mountain":
            case "volcano":
                MountainGimmick mountainGimmick =
                    GetOrAddComponent<MountainGimmick>(target);

                mountainGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                mountainGimmick.SetAudioClip(
                    mountainAudioClip
                );

                break;

            case "bird":
            case "eagle":
            case "sparrow":
                BirdGimmick birdGimmick =
                    GetOrAddComponent<BirdGimmick>(target);

                birdGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                birdGimmick.SetAudioClip(
                    birdAudioClip
                );

                break;

            case "window":
            case "glass":
                GlassGimmick glassGimmick =
                    GetOrAddComponent<GlassGimmick>(target);

                glassGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                glassGimmick.SetAudioClip(
                    glassBreakAudioClip
                );

                break;
                
            case "boat":
            case "ship":
            case "sailboat":
            case "sailing boat":
            case "motorboat":
            case "speedboat":
            case "ferry":
            case "yacht":
            case "vessel":

                BoatGimmick boatGimmick =
                    GetOrAddComponent<BoatGimmick>(target);

                boatGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                // ★船の音を渡す
                boatGimmick.SetAudioClip(
                    boatAudioClip
                );

                break;
            
            case "train":
            case "railway train":
            case "passenger train":
            case "subway":
            case "metro":
            case "locomotive":

                TrainGimmick trainGimmick =
                    GetOrAddComponent<TrainGimmick>(target);

                trainGimmick.SetTargetRenderer(
                    cutoutRenderer
                );

                trainGimmick.SetAudioClip(
                    trainAudioClip
                );

                break;



        }
    }


    /// <summary>
    /// Componentが未登録の場合だけ追加して返す
    /// </summary>
    private T GetOrAddComponent<T>(GameObject target)
        where T : Component
    {
        T component = target.GetComponent<T>();

        if (component == null)
        {
            component = target.AddComponent<T>();
        }

        return component;
    }


    /// <summary>
    /// シーンへ手動配置されている旧Cubeを無効化する
    /// </summary>
    private void HideLegacyGimmickMeshes()
    {
        MonoBehaviour[] behaviours =
            FindObjectsOfType<MonoBehaviour>(true);

        HashSet<GameObject> handledObjects =
            new HashSet<GameObject>();

        foreach (MonoBehaviour behaviour in behaviours)
        {
            bool isLegacyGimmick = behaviour is GimmickBase;
            bool isOldPlayerController =
                behaviour is PlayerController;

            if (!isLegacyGimmick && !isOldPlayerController)
            {
                continue;
            }

            // Reseiverが入力を処理するため、旧入力処理は重複させない
            if (isOldPlayerController)
            {
                behaviour.enabled = false;
            }

            if (!handledObjects.Add(behaviour.gameObject))
            {
                continue;
            }

            HideHitboxRenderers(behaviour.gameObject);
            DisableColliders(behaviour.gameObject);
        }
    }


    /// <summary>
    /// 当たり判定本体とその既存の子Cubeを非表示にする
    /// </summary>
    private void HideHitboxRenderers(GameObject targetObject)
    {
        MeshRenderer[] renderers =
            targetObject.GetComponentsInChildren<MeshRenderer>(true);

        foreach (MeshRenderer renderer in renderers)
        {
            renderer.enabled = false;
        }
    }


    /// <summary>
    /// 旧Cubeが写真上のクリックを遮らないようにする
    /// </summary>
    private void DisableColliders(GameObject targetObject)
    {
        Collider[] colliders =
            targetObject.GetComponentsInChildren<Collider>(true);

        foreach (Collider targetCollider in colliders)
        {
            targetCollider.enabled = false;
        }
    }


    /// <summary>
    /// worldWidth・worldHeight内へ、元画像の比率を保って収める
    /// </summary>
    private void UpdateDisplayWorldSize(
        float sourceImageWidth,
        float sourceImageHeight
    )
    {
        if (sourceImageWidth <= 0f || sourceImageHeight <= 0f)
        {
            displayWorldWidth = worldWidth;
            displayWorldHeight = worldHeight;
            return;
        }

        float imageAspect =
            sourceImageWidth / sourceImageHeight;

        float availableAspect =
            worldWidth / Mathf.Max(worldHeight, 0.0001f);

        if (imageAspect >= availableAspect)
        {
            displayWorldWidth = worldWidth;
            displayWorldHeight = worldWidth / imageAspect;
        }
        else
        {
            displayWorldHeight = worldHeight;
            displayWorldWidth = worldHeight * imageAspect;
        }
    }


    /// <summary>
    /// 写真と額縁を、元画像の縦横比に合わせた大きさへ更新する
    /// </summary>
    private void UpdatePhotoDisplayTransforms()
    {
        if (photoBackground == null)
        {
            if (photoFrame != null)
            {
                photoFrame.SetActive(false);
            }

            return;
        }

        photoBackground.transform.localScale = new Vector3(
            displayWorldWidth,
            displayWorldHeight,
            1f
        );

        RefreshPhotoFrame();
    }


    /// <summary>
    /// 9スライス額縁を生成し、中央の透明部分を写真サイズへ合わせる
    /// </summary>
    private void RefreshPhotoFrame()
    {
        if (photoFrameSprite == null)
        {
            if (photoFrame != null)
            {
                photoFrame.SetActive(false);
            }

            return;
        }

        if (photoFrame == null)
        {
            photoFrame = new GameObject("RuntimePhotoFrame");
            photoFrameRenderer =
                photoFrame.AddComponent<SpriteRenderer>();
        }

        if (photoFrameRenderer == null)
        {
            photoFrameRenderer =
                photoFrame.GetComponent<SpriteRenderer>();
        }

        photoFrame.SetActive(true);
        photoFrame.transform.position = new Vector3(
            0f,
            0f,
            objectZ + frameZOffset
        );
        photoFrame.transform.rotation = Quaternion.identity;
        photoFrame.transform.localScale = Vector3.one;

        photoFrameRenderer.sprite = photoFrameSprite;
        photoFrameRenderer.drawMode = SpriteDrawMode.Sliced;
        photoFrameRenderer.color = Color.white;

        // Sprite Editorで設定した枠幅をワールド座標へ変換する
        Vector4 spriteBorder = photoFrameSprite.border;
        float pixelsPerUnit = Mathf.Max(
            photoFrameSprite.pixelsPerUnit,
            0.0001f
        );

        float horizontalBorderWorldSize =
            (spriteBorder.x + spriteBorder.z) /
            pixelsPerUnit;

        float verticalBorderWorldSize =
            (spriteBorder.y + spriteBorder.w) /
            pixelsPerUnit;

        // 透明な中央部分が写真と同じ大きさになるよう外寸を決める
        photoFrameRenderer.size = new Vector2(
            displayWorldWidth + horizontalBorderWorldSize,
            displayWorldHeight + verticalBorderWorldSize
        );

        // 背景(-100)より上、認識物体(0以上)より下に描画する
        photoFrameRenderer.sortingOrder = -10;
        photoFrameRenderer.shadowCastingMode =
            ShadowCastingMode.Off;
        photoFrameRenderer.receiveShadows = false;
    }


    /// <summary>
    /// downloaded_imagesの写真を実行画面の背景へ表示する
    /// </summary>
    private void RefreshPhotoBackground(
        float sourceImageWidth = 0f,
        float sourceImageHeight = 0f
    )
    {
        string safeFileName =
            Path.GetFileName(backgroundPhotoFileName);

        string originalPath = Path.Combine(
            MagicPhotoRuntimePaths.DownloadedImagesDirectory,
            safeFileName
        );
        
        string erasedPath = Path.Combine(
            MagicPhotoRuntimePaths.PythonDirectory,
            "eraser_magic_output",
            safeFileName
        );
        
        // 消しゴムマジック後の画像があればそちらを優先
        string photoPath = File.Exists(erasedPath)
        ? erasedPath
        : originalPath;

        if (!File.Exists(photoPath))
        {
            Debug.LogWarning(
                "背景に使用する写真が見つかりません: "
                + photoPath
            );
            return;
        }

        byte[] imageBytes;
        try
        {
            imageBytes = File.ReadAllBytes(photoPath);
        }
        catch (Exception exception)
        {
            Debug.LogWarning(
                "背景写真を読み込めませんでした: "
                + exception.Message
            );
            return;
        }

        Texture2D newTexture = new Texture2D(
            2,
            2,
            TextureFormat.RGBA32,
            false
        );

        if (!newTexture.LoadImage(imageBytes, false))
        {
            Destroy(newTexture);
            Debug.LogWarning(
                "背景写真をTexture2Dへ変換できませんでした: "
                + photoPath
            );
            return;
        }

        UpdateDisplayWorldSize(
            sourceImageWidth > 0f
                ? sourceImageWidth
                : newTexture.width,
            sourceImageHeight > 0f
                ? sourceImageHeight
                : newTexture.height
        );

        Shader shader = Shader.Find("Unlit/Texture");
        if (shader == null)
        {
            shader = Shader.Find(
                "Universal Render Pipeline/Unlit"
            );
        }

        if (shader == null)
        {
            shader = Shader.Find("Standard");
        }

        if (shader == null)
        {
            Destroy(newTexture);
            Debug.LogError(
                "背景写真を表示できるShaderが見つかりません。"
            );
            return;
        }

        Material newMaterial = new Material(shader);
        newMaterial.name = "RuntimePhotoBackgroundMaterial";
        newMaterial.mainTexture = newTexture;

        if (photoBackground == null)
        {
            photoBackground =
                GameObject.CreatePrimitive(PrimitiveType.Quad);

            photoBackground.name = "RuntimePhotoBackground";

            Collider backgroundCollider =
                photoBackground.GetComponent<Collider>();

            if (backgroundCollider != null)
            {
                backgroundCollider.enabled = false;
                Destroy(backgroundCollider);
            }
        }

        photoBackground.transform.position = new Vector3(
            0f,
            0f,
            objectZ + backgroundZOffset
        );
        photoBackground.transform.rotation = Quaternion.identity;
        UpdatePhotoDisplayTransforms();

        Renderer backgroundRenderer =
            photoBackground.GetComponent<Renderer>();

        backgroundRenderer.sharedMaterial = newMaterial;
        backgroundRenderer.shadowCastingMode =
            ShadowCastingMode.Off;
        backgroundRenderer.receiveShadows = false;

        if (backgroundMaterial != null)
        {
            Destroy(backgroundMaterial);
        }

        if (backgroundTexture != null)
        {
            Destroy(backgroundTexture);
        }

        backgroundMaterial = newMaterial;
        backgroundTexture = newTexture;

        Debug.Log("受信した写真を背景へ表示しました: " + photoPath);
    }


    /// <summary>
    /// 背景透明PNGを読み込み、当たり判定の子として表示する
    /// </summary>
    private Renderer CreateCutoutChild(
        GameObject generatedObject,
        ObjectData obj
    )
    {
        if (string.IsNullOrWhiteSpace(obj.cutoutFileName))
        {
            return null;
        }

        string safeFileName =
            Path.GetFileName(obj.cutoutFileName);

        string cutoutPath = Path.Combine(
            MagicPhotoRuntimePaths.CutoutDirectory,
            safeFileName
        );

        if (!File.Exists(cutoutPath))
        {
            Debug.LogWarning(
                "人物切り抜き画像が見つかりません: "
                + cutoutPath
            );
            return null;
        }

        byte[] imageBytes;
        try
        {
            imageBytes = File.ReadAllBytes(cutoutPath);
        }
        catch (Exception exception)
        {
            Debug.LogWarning(
                "人物切り抜き画像を読み込めませんでした: "
                + exception.Message
            );
            return null;
        }

        Texture2D texture = new Texture2D(
            2,
            2,
            TextureFormat.RGBA32,
            false
        );

        if (!texture.LoadImage(imageBytes, false))
        {
            Destroy(texture);
            Debug.LogWarning(
                "人物切り抜き画像をTexture2Dへ変換できませんでした: "
                + cutoutPath
            );
            return null;
        }

        texture.name = safeFileName;
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;

        Material material = CreateCutoutMaterial(texture);
        if (material == null)
        {
            Destroy(texture);
            return null;
        }

        GameObject cutout =
            GameObject.CreatePrimitive(PrimitiveType.Quad);

        cutout.name = "Cutout_" + obj.name;
        cutout.transform.SetParent(
            generatedObject.transform,
            false
        );

        bool isPersonCutout = IsPerson(obj.name);

        cutout.transform.localPosition =
            new Vector3(
                0f,
                0f,
                isPersonCutout ? -0.002f : -0.001f
            );
        cutout.transform.localRotation = Quaternion.identity;
        cutout.transform.localScale = Vector3.one;

        Collider cutoutCollider =
            cutout.GetComponent<Collider>();
        if (cutoutCollider != null)
        {
            cutoutCollider.enabled = false;
            Destroy(cutoutCollider);
        }

        Renderer rootRenderer =
            generatedObject.GetComponent<Renderer>();
        if (rootRenderer != null)
        {
            rootRenderer.enabled = false;
        }

        Renderer cutoutRenderer =
            cutout.GetComponent<Renderer>();
        cutoutRenderer.sharedMaterial = material;
        cutoutRenderer.shadowCastingMode =
            ShadowCastingMode.Off;
        cutoutRenderer.receiveShadows = false;

        // 大きなwall等の切り抜きに人物が隠れないよう、人物を最後に描画する
        if (isPersonCutout)
        {
            cutoutRenderer.sortingOrder = 100;
            material.renderQueue =
                (int)RenderQueue.Transparent + 10;
        }

        generatedResources.Add(texture);
        generatedResources.Add(material);

        return cutoutRenderer;
    }


    /// <summary>
    /// PNGのアルファを保ったまま表示・発光できるマテリアルを作る
    /// </summary>
    private Material CreateCutoutMaterial(Texture2D texture)
    {
        Shader shader = Shader.Find("Standard");
        if (shader == null)
        {
            Debug.LogError(
                "切り抜き表示用のStandard Shaderが見つかりません。"
            );
            return null;
        }

        Material material = new Material(shader);
        material.name = "RuntimeCutoutMaterial";
        material.mainTexture = texture;
        material.SetColor("_Color", Color.white);

        material.SetFloat("_Mode", 3f);
        material.SetInt(
            "_SrcBlend",
            (int)BlendMode.SrcAlpha
        );
        material.SetInt(
            "_DstBlend",
            (int)BlendMode.OneMinusSrcAlpha
        );
        material.SetInt("_ZWrite", 0);
        material.DisableKeyword("_ALPHATEST_ON");
        material.EnableKeyword("_ALPHABLEND_ON");
        material.DisableKeyword("_ALPHAPREMULTIPLY_ON");
        material.renderQueue =
            (int)RenderQueue.Transparent;

        material.EnableKeyword("_EMISSION");
        material.SetColor("_EmissionColor", Color.black);

        return material;
    }


    private bool IsPerson(string objectName)
    {
        if (string.IsNullOrWhiteSpace(objectName))
        {
            return false;
        }

        string normalizedName =
            objectName.Trim().ToLowerInvariant();

        return normalizedName == "person"
            || normalizedName == "human";
    }


    /// <summary>
    /// 写真上のUI当たり判定から、対応する生成済みギミックを発動する
    /// </summary>
    public void ActivateGimmickFromUI(
        string objectId,
        string objectName
    )
    {
        // MagicBrainのobject_idは1始まりなので、同じ順序で生成した
        // オブジェクトを最初に確認する。
        if (int.TryParse(objectId, out int oneBasedIndex))
        {
            int generatedIndex = oneBasedIndex - 1;
            if (generatedIndex >= 0 &&
                generatedIndex < generatedObjects.Count &&
                TryActivateGimmick(
                    generatedObjects[generatedIndex],
                    objectName
                ))
            {
                Debug.Log(
                    $"UIからギミックを実行：" +
                    $"{objectName} / {objectId}"
                );
                return;
            }
        }

        // IDを取得できない旧JSONにも対応するため、物体名で探す。
        foreach (GameObject generatedObject in generatedObjects)
        {
            if (TryActivateGimmick(
                    generatedObject,
                    objectName
                ))
            {
                Debug.Log(
                    $"名前からギミックを実行：{objectName}"
                );
                return;
            }
        }

        Debug.LogWarning(
            $"{objectName}（{objectId}）に対応する" +
            "生成済みギミックが見つかりません。"
        );
    }


    private bool TryActivateGimmick(
        GameObject generatedObject,
        string objectName
    )
    {
        if (generatedObject == null)
        {
            return false;
        }

        string generatedName =
            generatedObject.name?.Trim();
        string expectedName =
            objectName?.Trim();

        bool nameMatches =
            string.IsNullOrWhiteSpace(expectedName) ||
            string.Equals(
                generatedName,
                expectedName,
                StringComparison.OrdinalIgnoreCase
            ) ||
            string.Equals(
                generatedName,
                expectedName + "_Gimmick",
                StringComparison.OrdinalIgnoreCase
            );

        if (!nameMatches)
        {
            return false;
        }

        GimmickBase targetGimmick =
            generatedObject.GetComponentInChildren<GimmickBase>(
                true
            );

        if (targetGimmick == null)
        {
            return false;
        }

        targetGimmick.ActivateMagic();
        return true;
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

        // タッチ位置に重なっているすべてのColliderを取得
        RaycastHit[] hits = Physics.RaycastAll(ray);

        if (hits.Length == 0)
        {
            return;
        }

        GimmickBase selectedGimmick = null;
        Collider selectedCollider = null;

        // 最初は非常に大きな値にしておく
        float smallestArea = float.MaxValue;

        foreach (RaycastHit hit in hits)
        {
            if (hit.collider == null)
            {
                continue;
            }

            // Colliderの親からギミックを取得
            GimmickBase gimmick =
                hit.collider.GetComponentInParent<GimmickBase>();

            if (gimmick == null)
            {
                continue;
            }

            // ★追加
            // タップした場所が切り抜き画像の透明部分なら
            // このオブジェクトは候補から除外する
            if (!IsVisiblePixelHit(hit.collider.gameObject, hit))
            {
                continue;
            }

            Bounds bounds = hit.collider.bounds;

            // Colliderの面積
            float area =
                Mathf.Abs(bounds.size.x * bounds.size.y);

            // 実際に画像が存在する物体の中で
            // 一番小さい当たり判定を優先する
            if (area < smallestArea)
            {
                smallestArea = area;
                selectedGimmick = gimmick;
                selectedCollider = hit.collider;
            }
        }

        // 選ばれた一番手前相当の物体を実行
        if (selectedGimmick != null)
        {
            Debug.Log(
                $"優先してタッチしたオブジェクト：" +
                $"{selectedCollider.gameObject.name}"
            );

            selectedGimmick.ActivateMagic();
        }
        else
        {
            Debug.LogWarning(
                "タッチ位置に実行可能なギミックがありません。"
            );
        }
    }

    /// <summary>
    /// タップ位置が切り抜き画像の
    /// 実際に表示されている部分か判定する
    /// </summary>
    private bool IsVisiblePixelHit(
        GameObject targetObject,
        RaycastHit hit
    )
    {
        if (targetObject == null)
        {
            return false;
        }

        // Cutout_〇〇 という名前のRendererを探す
        Renderer[] renderers =
            targetObject.GetComponentsInChildren<Renderer>(true);

        Renderer cutoutRenderer = null;

        foreach (Renderer renderer in renderers)
        {
            if (renderer.gameObject.name.StartsWith("Cutout_"))
            {
                cutoutRenderer = renderer;
                break;
            }
        }

        // 切り抜き画像がない場合は
        // 従来通りCollider全体を有効とする
        if (cutoutRenderer == null)
        {
            return true;
        }

        Material material = cutoutRenderer.sharedMaterial;

        if (material == null)
        {
            return true;
        }

        Texture2D texture =
            material.mainTexture as Texture2D;

        if (texture == null)
        {
            return true;
        }

        // タップしたワールド座標を
        // オブジェクトのローカル座標へ変換
        Vector3 localPoint =
            targetObject.transform.InverseTransformPoint(
                hit.point
            );

        // Quad / Cubeの中心が0で、
        // 左端=-0.5、右端=0.5なので
        // 0～1のUV座標へ変換
        float u = localPoint.x + 0.5f;
        float v = localPoint.y + 0.5f;

        // 画像範囲外
        if (u < 0f || u > 1f ||
            v < 0f || v > 1f)
        {
            return false;
        }

        Color pixel;

        try
        {
            // タップした位置の画像ピクセルを取得
            pixel = texture.GetPixelBilinear(u, v);
        }
        catch (UnityException)
        {
            // TextureがReadableでなかった場合など
            // タッチ不能になるのを避ける
            return true;
        }

        // alphaがほぼ透明なら
        // この物体を触っていないと判断
        const float alphaThreshold = 0.1f;

        return pixel.a > alphaThreshold;
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

        foreach (UnityEngine.Object resource in generatedResources)
        {
            if (resource != null)
            {
                Destroy(resource);
            }
        }

        generatedResources.Clear();
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

        if (photoBackground != null)
        {
            Destroy(photoBackground);
            photoBackground = null;
        }

        if (backgroundMaterial != null)
        {
            Destroy(backgroundMaterial);
            backgroundMaterial = null;
        }

        if (backgroundTexture != null)
        {
            Destroy(backgroundTexture);
            backgroundTexture = null;
        }

        if (photoFrame != null)
        {
            Destroy(photoFrame);
            photoFrame = null;
            photoFrameRenderer = null;
        }
    }
}
