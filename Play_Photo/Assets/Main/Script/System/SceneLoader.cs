using System;
using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class SceneLoader : MonoBehaviour
{
    public static SceneLoader Instance { get; private set; }

    [Header("共通フェード設定")]
    [SerializeField] private float fadeInDuration = 1.5f;
    [SerializeField] private float fadeOutDuration = 0.8f;

    private CanvasGroup fadeCanvasGroup;
    private bool isTransitioning;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
    private static void EnsureInstanceExists()
    {
        if (Instance != null)
        {
            return;
        }

        GameObject loaderObject =
            new GameObject("GlobalSceneLoader");

        loaderObject.AddComponent<SceneLoader>();
    }

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;

        // シーンを移動しても、このオブジェクトを削除しない
        DontDestroyOnLoad(gameObject);

        CreateFadeOverlay();
        SceneManager.sceneLoaded += OnSceneLoaded;
    }

    private void OnDestroy()
    {
        if (Instance == this)
        {
            SceneManager.sceneLoaded -= OnSceneLoaded;
            Instance = null;
        }
    }

    private void CreateFadeOverlay()
    {
        GameObject canvasObject =
            new GameObject("SceneFadeCanvas");

        canvasObject.transform.SetParent(transform, false);

        Canvas canvas = canvasObject.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.ScreenSpaceOverlay;
        canvas.overrideSorting = true;
        canvas.sortingOrder = short.MaxValue;

        canvasObject.AddComponent<GraphicRaycaster>();
        fadeCanvasGroup = canvasObject.AddComponent<CanvasGroup>();
        fadeCanvasGroup.alpha = 0f;
        fadeCanvasGroup.interactable = false;
        fadeCanvasGroup.blocksRaycasts = false;

        GameObject blackImageObject =
            new GameObject("BlackFadeImage");

        blackImageObject.transform.SetParent(
            canvasObject.transform,
            false
        );

        RectTransform blackImageRect =
            blackImageObject.AddComponent<RectTransform>();

        blackImageRect.anchorMin = Vector2.zero;
        blackImageRect.anchorMax = Vector2.one;
        blackImageRect.offsetMin = Vector2.zero;
        blackImageRect.offsetMax = Vector2.zero;

        Image blackImage = blackImageObject.AddComponent<Image>();
        blackImage.color = Color.black;
        blackImage.raycastTarget = true;
    }

    private void OnSceneLoaded(Scene scene, LoadSceneMode mode)
    {
        isTransitioning = false;

        if (UsesExistingSceneFade(scene.name))
        {
            SetFadeAlpha(0f, false);
            return;
        }

        StopAllCoroutines();
        SetFadeAlpha(1f, true);
        StartCoroutine(FadeTo(0f, fadeInDuration, false));
    }

    private static bool UsesExistingSceneFade(string sceneName)
    {
        return string.Equals(
                sceneName,
                "Title",
                StringComparison.OrdinalIgnoreCase
            )
            || string.Equals(
                sceneName,
                "LoadingLINE",
                StringComparison.OrdinalIgnoreCase
            );
    }

    /// <summary>
    /// 画面を暗くしてから、ボタンから受け取ったシーンへ遷移する
    /// </summary>
    /// <param name="sceneName"></param>
    public void LoadScene(string sceneName)
    {
        if (string.IsNullOrEmpty(sceneName))
        {
            Debug.LogWarning("シーン名が存在しません");
            return;
        }

        if (isTransitioning)
        {
            return;
        }

        isTransitioning = true;
        StartCoroutine(FadeOutAndLoad(sceneName));
    }

    private IEnumerator FadeOutAndLoad(string sceneName)
    {
        SetFadeAlpha(
            fadeCanvasGroup != null ? fadeCanvasGroup.alpha : 0f,
            true
        );

        yield return FadeTo(1f, fadeOutDuration, true);

        SceneManager.LoadScene(sceneName);
    }

    private IEnumerator FadeTo(
        float targetAlpha,
        float duration,
        bool blockRaycastsAfterFade
    )
    {
        if (fadeCanvasGroup == null)
        {
            yield break;
        }

        float startAlpha = fadeCanvasGroup.alpha;

        if (duration <= 0f)
        {
            SetFadeAlpha(targetAlpha, blockRaycastsAfterFade);
            yield break;
        }

        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.unscaledDeltaTime;

            float t = Mathf.Clamp01(elapsedTime / duration);
            t = Mathf.SmoothStep(0f, 1f, t);

            fadeCanvasGroup.alpha = Mathf.Lerp(
                startAlpha,
                targetAlpha,
                t
            );

            yield return null;
        }

        SetFadeAlpha(targetAlpha, blockRaycastsAfterFade);
    }

    private void SetFadeAlpha(float alpha, bool blockRaycasts)
    {
        if (fadeCanvasGroup == null)
        {
            return;
        }

        fadeCanvasGroup.alpha = alpha;
        fadeCanvasGroup.blocksRaycasts = blockRaycasts;
    }
}
