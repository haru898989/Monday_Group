using System.Collections;
using System.IO;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
using UnityEngine.Video;

/// <summary>
/// Display 1をタッチ操作用、Display 2を大型表示用として使用する。
/// Mainシーンでは同じカメラ映像をDisplay 2へ表示し、
/// それ以外のシーンでは待機用の動画または画像を表示する。
/// </summary>
public class DualDisplayManager : MonoBehaviour
{
    private static readonly bool EnableSecondDisplay = false;
    private const string PlaySceneName = "Main";

    private static DualDisplayManager instance;

    private Camera sourceCamera;
    private Camera upperDisplayCamera;

    private GameObject standbyRoot;
    private RawImage standbyImage;
    private AspectRatioFitter standbyAspectRatio;
    private GameObject standbyMessage;

    private GameObject playLoadingRoot;
    private bool isPlaySceneActive;
    private bool isPlayLoadingVisible = true;

    private VideoPlayer standbyVideoPlayer;
    private Texture2D standbyTexture;
    private bool standbyMediaLoaded;
    private Coroutine setupCoroutine;


    [RuntimeInitializeOnLoadMethod(
        RuntimeInitializeLoadType.BeforeSceneLoad
    )]
    private static void Initialize()
    {
        if (!EnableSecondDisplay)
        {
            return;
        }

        if (instance != null)
        {
            return;
        }

        GameObject managerObject =
            new GameObject("DualDisplayManager");

        instance =
            managerObject.AddComponent<DualDisplayManager>();
    }


    public static void SetPlayLoadingVisible(bool isVisible)
    {
        if (instance == null)
        {
            return;
        }

        instance.isPlayLoadingVisible = isVisible;
        instance.UpdatePlayLoadingVisibility();
    }


    private void Awake()
    {
        if (instance != null && instance != this)
        {
            Destroy(gameObject);
            return;
        }

        instance = this;
        DontDestroyOnLoad(gameObject);

        if (Display.displays.Length > 1)
        {
            Display.displays[1].Activate();
        }
        else
        {
            Debug.LogWarning(
                "2台目のディスプレイが見つかりません。" +
                "接続後、Windowsの表示設定を拡張にしてください。"
            );
        }

        CreateStandbyView();
        CreatePlayLoadingView();
        LoadStandbyMedia();

        SceneManager.sceneLoaded += OnSceneLoaded;
    }


    private IEnumerator Start()
    {
        yield return null;

        SetupUpperDisplay(
            SceneManager.GetActiveScene().name
        );
    }


    private void OnSceneLoaded(
        Scene scene,
        LoadSceneMode loadSceneMode
    )
    {
        if (setupCoroutine != null)
        {
            StopCoroutine(setupCoroutine);
        }

        setupCoroutine =
            StartCoroutine(
                SetupUpperDisplayNextFrame(scene.name)
            );
    }


    private IEnumerator SetupUpperDisplayNextFrame(
        string sceneName
    )
    {
        yield return null;

        SetupUpperDisplay(sceneName);
        setupCoroutine = null;
    }


    private void SetupUpperDisplay(string sceneName)
    {
        bool isPlayScene =
            sceneName == PlaySceneName;

        isPlaySceneActive = isPlayScene;
        UpdatePlayLoadingVisibility();

        if (standbyRoot != null)
        {
            standbyRoot.SetActive(!isPlayScene);
        }

        if (isPlayScene)
        {
            PauseStandbyVideo();
            CreateUpperDisplayCamera();
        }
        else
        {
            if (!standbyMediaLoaded)
            {
                LoadStandbyMedia();
            }

            if (upperDisplayCamera != null)
            {
                upperDisplayCamera.enabled = false;
            }

            PlayStandbyVideo();
        }
    }


    private void CreateUpperDisplayCamera()
    {
        sourceCamera = FindSourceCamera();

        if (sourceCamera == null)
        {
            Debug.LogWarning(
                "大型ディスプレイへ表示するカメラが" +
                "見つかりません。"
            );
            return;
        }

        if (upperDisplayCamera == null)
        {
            GameObject cameraObject =
                new GameObject("UpperDisplayCamera");

            cameraObject.transform.SetParent(
                transform,
                false
            );

            upperDisplayCamera =
                cameraObject.AddComponent<Camera>();
        }

        CopySourceCamera();
    }


    private Camera FindSourceCamera()
    {
        Camera mainCamera = Camera.main;

        if (mainCamera != null &&
            mainCamera != upperDisplayCamera)
        {
            return mainCamera;
        }

        foreach (Camera camera in Camera.allCameras)
        {
            if (camera != upperDisplayCamera &&
                camera.targetDisplay == 0)
            {
                return camera;
            }
        }

        return null;
    }


    private void LateUpdate()
    {
        if (upperDisplayCamera == null ||
            !upperDisplayCamera.enabled)
        {
            return;
        }

        if (sourceCamera == null)
        {
            sourceCamera = FindSourceCamera();
        }

        CopySourceCamera();
    }


    private void CopySourceCamera()
    {
        if (sourceCamera == null ||
            upperDisplayCamera == null)
        {
            return;
        }

        upperDisplayCamera.CopyFrom(sourceCamera);
        upperDisplayCamera.transform.SetPositionAndRotation(
            sourceCamera.transform.position,
            sourceCamera.transform.rotation
        );

        upperDisplayCamera.targetTexture = null;
        upperDisplayCamera.targetDisplay = 1;
        upperDisplayCamera.enabled = true;
    }


    private void CreateStandbyView()
    {
        standbyRoot =
            new GameObject("UpperDisplayStandby");

        standbyRoot.transform.SetParent(
            transform,
            false
        );

        Canvas canvas =
            standbyRoot.AddComponent<Canvas>();

        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.targetDisplay = 1;

        GameObject backgroundObject =
            CreateFullScreenObject(
                "Background",
                standbyRoot.transform
            );

        Image backgroundImage =
            backgroundObject.AddComponent<Image>();

        backgroundImage.color =
            new Color(0.04f, 0.08f, 0.14f, 1f);

        GameObject mediaObject =
            CreateFullScreenObject(
                "StandbyMedia",
                standbyRoot.transform
            );

        standbyImage =
            mediaObject.AddComponent<RawImage>();

        standbyImage.color = Color.clear;
        standbyImage.raycastTarget = false;

        standbyAspectRatio =
            mediaObject.AddComponent<AspectRatioFitter>();

        standbyAspectRatio.aspectMode =
            AspectRatioFitter.AspectMode.EnvelopeParent;

        standbyMessage =
            CreateFullScreenObject(
                "StandbyMessage",
                standbyRoot.transform
            );

        Text messageText =
            standbyMessage.AddComponent<Text>();

        messageText.text = "PLAY PHOTO";
        messageText.alignment = TextAnchor.MiddleCenter;
        messageText.fontSize = 72;
        messageText.color = Color.white;
        messageText.raycastTarget = false;
        messageText.font =
            Resources.GetBuiltinResource<Font>(
                "LegacyRuntime.ttf"
            );
    }


    private void CreatePlayLoadingView()
    {
        playLoadingRoot =
            new GameObject("UpperDisplayLoading");

        playLoadingRoot.transform.SetParent(
            transform,
            false
        );

        Canvas canvas =
            playLoadingRoot.AddComponent<Canvas>();

        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.targetDisplay = 1;
        canvas.sortingOrder = 100;

        GameObject backgroundObject =
            CreateFullScreenObject(
                "Background",
                playLoadingRoot.transform
            );

        Image backgroundImage =
            backgroundObject.AddComponent<Image>();

        backgroundImage.color = Color.black;
        backgroundImage.raycastTarget = false;

        GameObject messageObject =
            CreateFullScreenObject(
                "LoadingMessage",
                playLoadingRoot.transform
            );

        Text messageText =
            messageObject.AddComponent<Text>();

        messageText.text = "Loading...";
        messageText.alignment = TextAnchor.MiddleCenter;
        messageText.fontSize = 40;
        messageText.color = Color.white;
        messageText.raycastTarget = false;
        messageText.font =
            Resources.GetBuiltinResource<Font>(
                "LegacyRuntime.ttf"
            );

        playLoadingRoot.SetActive(false);
    }


    private void UpdatePlayLoadingVisibility()
    {
        if (playLoadingRoot != null)
        {
            playLoadingRoot.SetActive(
                isPlaySceneActive &&
                isPlayLoadingVisible
            );
        }
    }


    private GameObject CreateFullScreenObject(
        string objectName,
        Transform parent
    )
    {
        GameObject target =
            new GameObject(
                objectName,
                typeof(RectTransform)
            );

        target.transform.SetParent(parent, false);

        RectTransform rectTransform =
            target.GetComponent<RectTransform>();

        rectTransform.anchorMin = Vector2.zero;
        rectTransform.anchorMax = Vector2.one;
        rectTransform.offsetMin = Vector2.zero;
        rectTransform.offsetMax = Vector2.zero;

        return target;
    }


    private void LoadStandbyMedia()
    {
        string mediaFolder = Path.Combine(
            Application.streamingAssetsPath,
            "UpperDisplay"
        );

        string videoPath = FindMediaFile(
            mediaFolder,
            "standby.mp4",
            "standby.webm",
            "standby.mov"
        );

        if (!string.IsNullOrEmpty(videoPath))
        {
            standbyMediaLoaded = true;

            standbyVideoPlayer =
                gameObject.AddComponent<VideoPlayer>();

            standbyVideoPlayer.playOnAwake = false;
            standbyVideoPlayer.isLooping = true;
            standbyVideoPlayer.renderMode =
                VideoRenderMode.APIOnly;
            standbyVideoPlayer.audioOutputMode =
                VideoAudioOutputMode.None;
            standbyVideoPlayer.url = videoPath;
            standbyVideoPlayer.prepareCompleted +=
                OnStandbyVideoPrepared;
            standbyVideoPlayer.Prepare();
            return;
        }

        string imagePath = FindMediaFile(
            mediaFolder,
            "standby.png",
            "standby.jpg",
            "standby.jpeg"
        );

        if (!string.IsNullOrEmpty(imagePath))
        {
            byte[] imageBytes =
                File.ReadAllBytes(imagePath);

            standbyTexture =
                new Texture2D(
                    2,
                    2,
                    TextureFormat.RGBA32,
                    false
                );

            if (standbyTexture.LoadImage(imageBytes, false))
            {
                standbyMediaLoaded = true;

                SetStandbyTexture(
                    standbyTexture,
                    standbyTexture.width,
                    standbyTexture.height
                );
            }
            else
            {
                Destroy(standbyTexture);
                standbyTexture = null;
            }

            return;
        }

        Debug.Log(
            "大型ディスプレイの待機素材は " +
            mediaFolder +
            " に standby.mp4 または standby.png として" +
            "配置できます。"
        );
    }


    private string FindMediaFile(
        string folderPath,
        params string[] fileNames
    )
    {
        foreach (string fileName in fileNames)
        {
            string filePath =
                Path.Combine(folderPath, fileName);

            if (File.Exists(filePath))
            {
                return filePath;
            }
        }

        return string.Empty;
    }


    private void OnStandbyVideoPrepared(
        VideoPlayer videoPlayer
    )
    {
        SetStandbyTexture(
            videoPlayer.texture,
            (int)videoPlayer.width,
            (int)videoPlayer.height
        );

        PlayStandbyVideo();
    }


    private void SetStandbyTexture(
        Texture texture,
        int width,
        int height
    )
    {
        standbyImage.texture = texture;
        standbyImage.color = Color.white;

        if (width > 0 && height > 0)
        {
            standbyAspectRatio.aspectRatio =
                (float)width / height;
        }

        if (standbyMessage != null)
        {
            standbyMessage.SetActive(false);
        }
    }


    private void PlayStandbyVideo()
    {
        if (standbyRoot != null &&
            standbyRoot.activeInHierarchy &&
            standbyVideoPlayer != null &&
            standbyVideoPlayer.isPrepared)
        {
            standbyVideoPlayer.Play();
        }
    }


    private void PauseStandbyVideo()
    {
        if (standbyVideoPlayer != null &&
            standbyVideoPlayer.isPlaying)
        {
            standbyVideoPlayer.Pause();
        }
    }


    private void OnDestroy()
    {
        if (instance != this)
        {
            return;
        }

        SceneManager.sceneLoaded -= OnSceneLoaded;

        if (standbyVideoPlayer != null)
        {
            standbyVideoPlayer.prepareCompleted -=
                OnStandbyVideoPrepared;
        }

        if (standbyTexture != null)
        {
            Destroy(standbyTexture);
        }

        instance = null;
    }
}
