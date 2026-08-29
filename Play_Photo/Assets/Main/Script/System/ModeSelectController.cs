using System.Collections;
using UnityEngine;

public class ModeSelectController : MonoBehaviour
{
    [Header("UI表示演出")]
    [SerializeField] private float uiStartDelay = 1.8f;
    [SerializeField] private float uiFadeInDuration = 1.2f;
    [SerializeField] private float uiFadeOutDuration = 0.5f;

    [Header("選択後のカメラ演出")]
    [SerializeField] private float cameraZoomDistance = 300f;
    [SerializeField] private float cameraZoomDuration = 1.8f;
    [SerializeField] private float fadeOutStartDelay = 0.85f;

    private CanvasGroup uiCanvasGroup;
    private Transform mainCameraTransform;
    private Vector3 cameraStartPosition;
    private bool isTransitioning;

    private void Awake()
    {
        FindSceneReferences();

        if (uiCanvasGroup != null)
        {
            uiCanvasGroup.alpha = 0f;
            SetUIInteraction(false);
        }

        if (mainCameraTransform != null)
        {
            cameraStartPosition = mainCameraTransform.position;
        }
    }

    private void Start()
    {
        if (uiCanvasGroup != null)
        {
            StartCoroutine(FadeInUI());
        }
    }

    private void FindSceneReferences()
    {
        Canvas[] canvases = FindObjectsOfType<Canvas>(true);

        foreach (Canvas canvas in canvases)
        {
            if (canvas.gameObject.scene != gameObject.scene)
            {
                continue;
            }

            uiCanvasGroup = canvas.GetComponent<CanvasGroup>();

            if (uiCanvasGroup == null)
            {
                uiCanvasGroup =
                    canvas.gameObject.AddComponent<CanvasGroup>();
            }

            break;
        }

        Camera mainCamera = Camera.main;
        if (mainCamera != null)
        {
            mainCameraTransform = mainCamera.transform;
        }

        if (uiCanvasGroup == null)
        {
            Debug.LogError(
                "ModeSelectのCanvasが見つかりません。"
            );
        }

        if (mainCameraTransform == null)
        {
            Debug.LogError(
                "ModeSelectのMain Cameraが見つかりません。"
            );
        }
    }

    private IEnumerator FadeInUI()
    {
        yield return new WaitForSecondsRealtime(uiStartDelay);

        yield return FadeCanvasGroup(
            0f,
            1f,
            uiFadeInDuration
        );

        if (!isTransitioning)
        {
            SetUIInteraction(true);
        }
    }

    // 自分の写真を使う
    public void UseMyPhoto()
    {
        BeginTransition("LoadingLINE");
    }

    // 写真を選んで遊ぶ
    public void SelectPreparedPhoto()
    {
        BeginTransition("PhotoSelect");
    }

    private void BeginTransition(string sceneName)
    {
        if (isTransitioning)
        {
            return;
        }

        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            return;
        }

        isTransitioning = true;
        SetUIInteraction(false);
        StartCoroutine(PlayExitSequence());

        // UI消去とカメラ前進を先に少し見せてから、全画面を暗くする。
        // 暗転が完了した時点でSceneLoaderが次のSceneへ移動するため、
        // カメラ演出の完了を待つ必要はない。
        StartCoroutine(StartSceneFadeAfterDelay(sceneName));
    }

    private IEnumerator StartSceneFadeAfterDelay(string sceneName)
    {
        if (fadeOutStartDelay > 0f)
        {
            yield return new WaitForSecondsRealtime(
                fadeOutStartDelay
            );
        }

        SceneLoader.Instance.LoadScene(sceneName);
    }

    private IEnumerator PlayExitSequence()
    {
        float elapsedTime = 0f;

        Vector3 zoomStartPosition =
            mainCameraTransform != null
                ? mainCameraTransform.position
                : cameraStartPosition;

        Vector3 zoomTargetPosition = zoomStartPosition;
        if (mainCameraTransform != null)
        {
            zoomTargetPosition +=
                mainCameraTransform.forward * cameraZoomDistance;
        }

        float startAlpha =
            uiCanvasGroup != null ? uiCanvasGroup.alpha : 1f;

        float sequenceDuration = Mathf.Max(
            cameraZoomDuration,
            uiFadeOutDuration
        );

        while (elapsedTime < sequenceDuration)
        {
            elapsedTime += Time.unscaledDeltaTime;

            if (uiCanvasGroup != null)
            {
                float uiT = uiFadeOutDuration <= 0f
                    ? 1f
                    : Mathf.Clamp01(
                        elapsedTime / uiFadeOutDuration
                    );

                uiT = Mathf.SmoothStep(0f, 1f, uiT);
                uiCanvasGroup.alpha = Mathf.Lerp(
                    startAlpha,
                    0f,
                    uiT
                );
            }

            if (mainCameraTransform != null)
            {
                float cameraT = cameraZoomDuration <= 0f
                    ? 1f
                    : Mathf.Clamp01(
                        elapsedTime / cameraZoomDuration
                    );

                cameraT = Mathf.SmoothStep(0f, 1f, cameraT);
                mainCameraTransform.position = Vector3.Lerp(
                    zoomStartPosition,
                    zoomTargetPosition,
                    cameraT
                );
            }

            yield return null;
        }

        if (uiCanvasGroup != null)
        {
            uiCanvasGroup.alpha = 0f;
        }

        if (mainCameraTransform != null)
        {
            mainCameraTransform.position = zoomTargetPosition;
        }
    }

    private IEnumerator FadeCanvasGroup(
        float startAlpha,
        float targetAlpha,
        float duration
    )
    {
        if (uiCanvasGroup == null)
        {
            yield break;
        }

        if (duration <= 0f)
        {
            uiCanvasGroup.alpha = targetAlpha;
            yield break;
        }

        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.unscaledDeltaTime;

            float t = Mathf.Clamp01(elapsedTime / duration);
            t = Mathf.SmoothStep(0f, 1f, t);

            uiCanvasGroup.alpha = Mathf.Lerp(
                startAlpha,
                targetAlpha,
                t
            );

            yield return null;
        }

        uiCanvasGroup.alpha = targetAlpha;
    }

    private void SetUIInteraction(bool enabled)
    {
        if (uiCanvasGroup == null)
        {
            return;
        }

        uiCanvasGroup.interactable = enabled;
        uiCanvasGroup.blocksRaycasts = enabled;
    }
}
