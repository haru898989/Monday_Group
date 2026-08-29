using System;
using System.Collections;
using System.Globalization;
using System.IO;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

[DisallowMultipleComponent]
public class MuseumLoadingPresenter : MonoBehaviour
{
    private static readonly Color GoldColor =
        new Color(1f, 0.72f, 0.18f, 1f);

    private const float CompletionHoldSeconds = 0.35f;
    private const float FadeOutSeconds = 0.65f;

    private CanvasGroup canvasGroup;
    private RawImage titleImage;
    private RawImage stageImage;
    private RawImage elapsedLabelImage;
    private TMP_Text elapsedText;
    private TMP_Text percentText;
    private RectTransform progressFillRect;
    private RectTransform spotlightRect;
    private Texture2D spotlightTexture;

    private string progressFilePath;
    private DateTime loadingStartedUtc;
    private DateTime lastProgressWriteUtc;
    private float loadingStartedTime;
    private float targetProgress;
    private float displayedProgress;
    private string currentStatus = "展示の準備を始めています";
    private string displayedStageImageName;
    private bool viewCreated;
    private bool isHiding;

    private void Awake()
    {
        progressFilePath = Path.GetFullPath(
            Path.Combine(
                Application.dataPath,
                "..",
                "Python",
                "loading_progress.txt"
            )
        );

        CreateView();
    }

    private void OnEnable()
    {
        Show();
    }

    private void Update()
    {
        if (!viewCreated || isHiding)
        {
            return;
        }

        ReadProgressFile();

        displayedProgress = Mathf.MoveTowards(
            displayedProgress,
            targetProgress,
            Time.unscaledDeltaTime * 0.28f
        );

        UpdateProgressVisuals();
        UpdateElapsedTime();
        UpdateSpotlight();
    }

    public void Show()
    {
        if (!viewCreated)
        {
            CreateView();
        }

        StopAllCoroutines();

        isHiding = false;
        loadingStartedUtc = DateTime.UtcNow;
        lastProgressWriteUtc = GetExistingProgressWriteTime();
        loadingStartedTime = Time.unscaledTime;
        targetProgress = 0.01f;
        displayedProgress = 0f;
        currentStatus = "展示の準備を始めています";

        if (canvasGroup != null)
        {
            canvasGroup.alpha = 1f;
            canvasGroup.blocksRaycasts = true;
        }

        UpdateProgressVisuals();
        UpdateElapsedTime();
    }

    private DateTime GetExistingProgressWriteTime()
    {
        try
        {
            return File.Exists(progressFilePath)
                ? File.GetLastWriteTimeUtc(progressFilePath)
                : DateTime.MinValue;
        }
        catch (IOException)
        {
            return DateTime.MinValue;
        }
        catch (UnauthorizedAccessException)
        {
            return DateTime.MinValue;
        }
    }

    public void HideWithCompletion(Action onHidden)
    {
        if (isHiding)
        {
            return;
        }

        isHiding = true;
        targetProgress = 1f;
        displayedProgress = 1f;
        currentStatus = "写真をかざす準備ができました";
        UpdateProgressVisuals();

        StartCoroutine(FinishAndFadeOut(onHidden));
    }

    private IEnumerator FinishAndFadeOut(Action onHidden)
    {
        yield return new WaitForSecondsRealtime(
            CompletionHoldSeconds
        );

        float elapsedTime = 0f;
        float startAlpha =
            canvasGroup != null ? canvasGroup.alpha : 1f;

        while (elapsedTime < FadeOutSeconds)
        {
            elapsedTime += Time.unscaledDeltaTime;

            float t = Mathf.Clamp01(
                elapsedTime / FadeOutSeconds
            );

            t = Mathf.SmoothStep(0f, 1f, t);

            if (canvasGroup != null)
            {
                canvasGroup.alpha = Mathf.Lerp(
                    startAlpha,
                    0f,
                    t
                );
            }

            yield return null;
        }

        if (canvasGroup != null)
        {
            canvasGroup.alpha = 0f;
            canvasGroup.blocksRaycasts = false;
        }

        onHidden?.Invoke();
    }

    private void ReadProgressFile()
    {
        if (string.IsNullOrWhiteSpace(progressFilePath) ||
            !File.Exists(progressFilePath))
        {
            return;
        }

        try
        {
            DateTime writeTime =
                File.GetLastWriteTimeUtc(progressFilePath);

            if (writeTime <= lastProgressWriteUtc ||
                writeTime < loadingStartedUtc.AddSeconds(-2f))
            {
                return;
            }

            string progressText =
                File.ReadAllText(progressFilePath).Trim();

            string[] parts = progressText.Split(
                new[] { '|' },
                2
            );

            if (parts.Length != 2 ||
                !float.TryParse(
                    parts[0],
                    NumberStyles.Float,
                    CultureInfo.InvariantCulture,
                    out float progress
                ))
            {
                return;
            }

            lastProgressWriteUtc = writeTime;
            targetProgress = Mathf.Max(
                targetProgress,
                Mathf.Clamp01(progress)
            );

            if (!string.IsNullOrWhiteSpace(parts[1]))
            {
                currentStatus = parts[1];
            }
        }
        catch (IOException)
        {
            // Pythonが書き換えている瞬間は次のフレームで再試行する。
        }
        catch (UnauthorizedAccessException)
        {
            // 読み込み権限がない場合もLoading自体は継続する。
        }
    }

    private void UpdateProgressVisuals()
    {
        if (progressFillRect != null)
        {
            Vector2 anchorMax = progressFillRect.anchorMax;
            anchorMax.x = Mathf.Clamp01(displayedProgress);
            progressFillRect.anchorMax = anchorMax;
        }

        if (percentText != null)
        {
            percentText.text =
                Mathf.RoundToInt(displayedProgress * 100f) + "%";
        }

        UpdateStageImage();
    }

    private void UpdateElapsedTime()
    {
        if (elapsedText == null)
        {
            return;
        }

        float elapsedSeconds = Mathf.Max(
            0f,
            Time.unscaledTime - loadingStartedTime
        );

        int minutes = Mathf.FloorToInt(elapsedSeconds / 60f);
        int seconds = Mathf.FloorToInt(elapsedSeconds) % 60;

        elapsedText.text = string.Format(
            "{0:00}:{1:00}",
            minutes,
            seconds
        );
    }

    private void UpdateSpotlight()
    {
        if (spotlightRect == null)
        {
            return;
        }

        RectTransform rootRect = transform as RectTransform;
        float width =
            rootRect != null && rootRect.rect.width > 0f
                ? rootRect.rect.width
                : Screen.width;

        float cycle = Mathf.Repeat(
            Time.unscaledTime,
            3.2f
        ) / 3.2f;

        float x = Mathf.Lerp(
            -width * 0.75f,
            width * 0.75f,
            Mathf.SmoothStep(0f, 1f, cycle)
        );

        spotlightRect.anchoredPosition =
            new Vector2(x, 0f);
    }

    private void CreateView()
    {
        if (viewCreated)
        {
            return;
        }

        viewCreated = true;

        canvasGroup = GetComponent<CanvasGroup>();
        if (canvasGroup == null)
        {
            canvasGroup = gameObject.AddComponent<CanvasGroup>();
        }

        Image backgroundImage = GetComponent<Image>();
        if (backgroundImage != null)
        {
            // 実際の写真と額縁を背後に残し、暗い展示室のように見せる。
            backgroundImage.color =
                new Color(0.018f, 0.008f, 0.012f, 0.82f);
        }

        TMP_Text oldLoadingText =
            GetComponentInChildren<TMP_Text>(true);

        if (oldLoadingText != null)
        {
            oldLoadingText.gameObject.SetActive(false);
        }

        titleImage = CreateTextImage(
            "LoadingTitleImage",
            "LoadingText/loading_title",
            new Vector2(0f, -270f),
            new Vector2(1300f, 100f)
        );

        stageImage = CreateTextImage(
            "LoadingStageImage",
            "LoadingText/stage_preparing",
            new Vector2(0f, -330f),
            new Vector2(1300f, 72f)
        );

        CreateProgressBar();

        elapsedLabelImage = CreateTextImage(
            "ElapsedTimeLabelImage",
            "LoadingText/elapsed_label",
            new Vector2(-105f, -425f),
            new Vector2(210f, 52f)
        );

        TMP_FontAsset defaultFont = Resources.Load<TMP_FontAsset>(
            "Fonts & Materials/LiberationSans SDF"
        );

        elapsedText = CreateText("ElapsedTime", defaultFont);
        ConfigureText(
            elapsedText,
            "00:00",
            24f,
            new Color(1f, 0.86f, 0.58f, 1f),
            new Vector2(110f, -425f),
            new Vector2(180f, 50f)
        );

        percentText = CreateText("ProgressPercent", defaultFont);
        ConfigureText(
            percentText,
            "0%",
            24f,
            GoldColor,
            new Vector2(455f, -380f),
            new Vector2(120f, 45f)
        );

        CreateSpotlight();
    }

    private RawImage CreateTextImage(
        string objectName,
        string resourcePath,
        Vector2 position,
        Vector2 size
    )
    {
        GameObject imageObject = new GameObject(objectName);
        imageObject.transform.SetParent(transform, false);

        RectTransform rect =
            imageObject.AddComponent<RectTransform>();

        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.pivot = new Vector2(0.5f, 0.5f);
        rect.anchoredPosition = position;
        rect.sizeDelta = size;

        RawImage image = imageObject.AddComponent<RawImage>();
        image.texture = Resources.Load<Texture2D>(resourcePath);
        image.color = Color.white;
        image.raycastTarget = false;

        return image;
    }

    private void UpdateStageImage()
    {
        if (stageImage == null)
        {
            return;
        }

        string imageName = GetStageImageName(currentStatus);

        if (imageName == displayedStageImageName)
        {
            return;
        }

        Texture2D texture = Resources.Load<Texture2D>(
            "LoadingText/" + imageName
        );

        if (texture != null)
        {
            stageImage.texture = texture;
            displayedStageImageName = imageName;
        }
    }

    private string GetStageImageName(string status)
    {
        switch (status)
        {
            case "写真を受け取っています":
                return "stage_receiving";
            case "写真の中を見ています":
                return "stage_inspecting";
            case "写真の中のものを見つけています":
                return "stage_detecting";
            case "写真をきれいに整えています":
                return "stage_cleaning";
            case "楽しいしかけを準備しています":
                return "stage_gimmicks";
            case "写真をかざっています":
                return "stage_displaying";
            case "写真をかざす準備ができました":
                return "stage_complete";
            default:
                return "stage_preparing";
        }
    }

    private void CreateProgressBar()
    {
        GameObject trackObject =
            new GameObject("MuseumProgressTrack");

        trackObject.transform.SetParent(transform, false);

        RectTransform trackRect =
            trackObject.AddComponent<RectTransform>();

        trackRect.anchorMin = new Vector2(0.5f, 0.5f);
        trackRect.anchorMax = new Vector2(0.5f, 0.5f);
        trackRect.pivot = new Vector2(0.5f, 0.5f);
        trackRect.anchoredPosition = new Vector2(0f, -380f);
        trackRect.sizeDelta = new Vector2(820f, 20f);

        Image trackImage = trackObject.AddComponent<Image>();
        trackImage.color = new Color(0.16f, 0.025f, 0.02f, 0.95f);
        trackImage.raycastTarget = false;

        Outline outline = trackObject.AddComponent<Outline>();
        outline.effectColor = new Color(0.85f, 0.48f, 0.08f, 1f);
        outline.effectDistance = new Vector2(2f, -2f);

        GameObject fillObject =
            new GameObject("MuseumProgressFill");

        fillObject.transform.SetParent(trackObject.transform, false);

        progressFillRect =
            fillObject.AddComponent<RectTransform>();

        progressFillRect.anchorMin = Vector2.zero;
        progressFillRect.anchorMax = new Vector2(0f, 1f);
        progressFillRect.pivot = new Vector2(0f, 0.5f);
        progressFillRect.offsetMin = new Vector2(0f, 3f);
        progressFillRect.offsetMax = new Vector2(0f, -3f);

        Image fillImage = fillObject.AddComponent<Image>();
        fillImage.color = GoldColor;
        fillImage.raycastTarget = false;
    }

    private void CreateSpotlight()
    {
        GameObject spotlightObject =
            new GameObject("MovingSpotlight");

        spotlightObject.transform.SetParent(transform, false);
        spotlightObject.transform.SetAsFirstSibling();

        spotlightRect =
            spotlightObject.AddComponent<RectTransform>();

        spotlightRect.anchorMin = new Vector2(0.5f, 0.5f);
        spotlightRect.anchorMax = new Vector2(0.5f, 0.5f);
        spotlightRect.pivot = new Vector2(0.5f, 0.5f);
        spotlightRect.sizeDelta = new Vector2(520f, 1700f);
        spotlightRect.localRotation = Quaternion.Euler(0f, 0f, -10f);

        RawImage spotlightImage =
            spotlightObject.AddComponent<RawImage>();

        spotlightTexture = CreateSpotlightTexture();
        spotlightImage.texture = spotlightTexture;
        spotlightImage.color = new Color(1f, 0.74f, 0.30f, 0.16f);
        spotlightImage.raycastTarget = false;
    }

    private Texture2D CreateSpotlightTexture()
    {
        const int textureWidth = 256;
        Texture2D texture = new Texture2D(
            textureWidth,
            1,
            TextureFormat.RGBA32,
            false
        );

        texture.name = "RuntimeMuseumSpotlight";
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;

        Color[] pixels = new Color[textureWidth];

        for (int index = 0; index < textureWidth; index++)
        {
            float normalized =
                index / (textureWidth - 1f);

            float distanceFromCenter =
                Mathf.Abs(normalized - 0.5f) * 2f;

            float alpha = Mathf.Pow(
                Mathf.Clamp01(1f - distanceFromCenter),
                2.5f
            );

            pixels[index] = new Color(1f, 1f, 1f, alpha);
        }

        texture.SetPixels(pixels);
        texture.Apply(false, true);
        return texture;
    }

    private TMP_Text CreateText(
        string objectName,
        TMP_FontAsset font = null
    )
    {
        GameObject textObject = new GameObject(objectName);
        textObject.transform.SetParent(transform, false);

        TextMeshProUGUI text =
            textObject.AddComponent<TextMeshProUGUI>();

        text.raycastTarget = false;

        if (font != null)
        {
            text.font = font;
        }

        return text;
    }

    private void ConfigureText(
        TMP_Text text,
        string value,
        float fontSize,
        Color color,
        Vector2 position,
        Vector2 size
    )
    {
        if (text == null)
        {
            return;
        }

        text.text = value;
        text.fontSize = fontSize;
        text.color = color;
        text.alignment = TextAlignmentOptions.Center;
        text.enableWordWrapping = false;
        text.raycastTarget = false;

        RectTransform rect = text.rectTransform;
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.pivot = new Vector2(0.5f, 0.5f);
        rect.anchoredPosition = position;
        rect.sizeDelta = size;
    }

    private void OnDestroy()
    {
        if (spotlightTexture != null)
        {
            Destroy(spotlightTexture);
        }
    }
}
