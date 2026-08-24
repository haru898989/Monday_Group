using System.Collections;
using UnityEngine;

public class TitleFadeIn : MonoBehaviour
{
    [Header("フェードイン設定")]
    [SerializeField] private float fadeDuration = 1.5f;

    [SerializeField] private float startDelay = 0.5f;

    private CanvasGroup canvasGroup;

    private void Awake()
    {
        canvasGroup = GetComponent<CanvasGroup>();

        if (canvasGroup == null)
        {
            Debug.LogError("CanvasGroupが見つかりません。");
            return;
        }

        // 最初は完全に透明
        canvasGroup.alpha = 0f;
    }

    private void Start()
    {
        if (canvasGroup != null)
        {
            StartCoroutine(FadeIn());
        }
    }

    private IEnumerator FadeIn()
    {
        // 最初に少し待つ
        yield return new WaitForSeconds(startDelay);

        float elapsedTime = 0f;

        while (elapsedTime < fadeDuration)
        {
            elapsedTime += Time.deltaTime;

            float t = Mathf.Clamp01(elapsedTime / fadeDuration);

            // 滑らかに表示
            t = Mathf.SmoothStep(0f, 1f, t);

            canvasGroup.alpha = t;

            yield return null;
        }

        canvasGroup.alpha = 1f;
    }
}