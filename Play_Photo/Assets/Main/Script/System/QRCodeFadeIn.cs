using System.Collections;
using UnityEngine;
using UnityEngine.UI;

public class QRCodeFadeIn : MonoBehaviour
{
    [Header("暗くする画像")]
    [SerializeField] private Image backgroundImage;
    [SerializeField] private Image qrCodeImage;

    [Header("明るくなるまでの設定")]
    [SerializeField] private float startDelay = 0.2f;
    [SerializeField] private float fadeDuration = 1.5f;

    [Header("最初の暗さ")]
    [Range(0f, 1f)]
    [SerializeField] private float startBrightness = 0f;

    private void Awake()
    {
        SetBrightness(startBrightness);
    }

    private void Start()
    {
        StartCoroutine(BrightenImages());
    }

    private IEnumerator BrightenImages()
    {
        // 最初は暗い状態を少し維持
        yield return new WaitForSeconds(startDelay);

        float elapsedTime = 0f;

        while (elapsedTime < fadeDuration)
        {
            elapsedTime += Time.deltaTime;

            float t = Mathf.Clamp01(
                elapsedTime / fadeDuration
            );

            t = Mathf.SmoothStep(0f, 1f, t);

            float brightness = Mathf.Lerp(
                startBrightness,
                1f,
                t
            );

            SetBrightness(brightness);

            yield return null;
        }

        // 最後は元の明るさ
        SetBrightness(1f);
    }

    private void SetBrightness(float brightness)
    {
        Color color = new Color(
            brightness,
            brightness,
            brightness,
            1f
        );

        if (backgroundImage != null)
        {
            backgroundImage.color = color;
        }

        if (qrCodeImage != null)
        {
            qrCodeImage.color = color;
        }
    }
}