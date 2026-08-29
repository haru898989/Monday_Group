using System.Collections;
using UnityEngine;

/// <summary>
/// 山をタッチすると、揺れながら赤くなって膨らみ、
/// 噴火前のような激しい動きをしたあと元に戻る。
/// </summary>
public class MountainGimmick : MonoBehaviour, GimmickBase
{
    // =========================
    // 前兆の揺れ
    // =========================

    [SerializeField]
    private float preShakeDuration = 1.0f;

    [SerializeField]
    private float preShakeAmount = 0.06f;

    [SerializeField]
    private float preShakeSpeed = 24f;


    // =========================
    // 強い揺れ
    // =========================

    [SerializeField]
    private float strongShakeDuration = 1.0f;

    [SerializeField]
    private float strongShakeAmount = 0.12f;


    // =========================
    // 山の変形
    // =========================

    [SerializeField]
    private float growScale = 1.15f;

    [SerializeField]
    private float growDuration = 0.4f;

    [SerializeField]
    private float returnDuration = 0.9f;


    // =========================
    // 内部変数
    // =========================

    private Renderer targetRenderer;

    private AudioClip eruptionAudioClip;
    private AudioSource audioSource;

    private bool isActivated = false;


    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }


    /// <summary>
    /// Receiverから山のRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// Receiverから噴火音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        eruptionAudioClip = clip;
    }


    /// <summary>
    /// タッチされた時
    /// </summary>
    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;

        StartCoroutine(MountainEffect());
    }


    /// <summary>
    /// 山ギミック本体
    /// </summary>
    private IEnumerator MountainEffect()
    {
        if (targetRenderer == null)
        {
            targetRenderer =
                GetComponentInChildren<Renderer>(true);
        }

        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "MountainGimmick：山のRendererがありません。"
            );

            isActivated = false;
            yield break;
        }


        Vector3 originalPosition =
            transform.position;

        Vector3 originalScale =
            transform.localScale;


        Material material =
            targetRenderer.material;

        Color originalColor =
            material.color;


        Color hotColor =
            new Color(
                1f,
                0.35f,
                0.15f,
                originalColor.a
            );


        Vector3 enlargedScale =
            originalScale * growScale;


        // =========================
        // ① 小さく揺れ始める
        // =========================

        float elapsedTime = 0f;


        while (elapsedTime < preShakeDuration)
        {
            elapsedTime += Time.deltaTime;


            float power =
                Mathf.Clamp01(
                    elapsedTime / preShakeDuration
                );


            float shakeX =
                Mathf.Sin(
                    elapsedTime * preShakeSpeed
                )
                * preShakeAmount
                * power;


            float shakeY =
                Random.Range(
                    -preShakeAmount,
                    preShakeAmount
                )
                * 0.25f
                * power;


            transform.position =
                originalPosition +
                new Vector3(
                    shakeX,
                    shakeY,
                    0f
                );


            yield return null;
        }


        transform.position =
            originalPosition;


        // =========================
        // ② 膨らみながら赤くなる
        // =========================

        elapsedTime = 0f;


        while (elapsedTime < growDuration)
        {
            elapsedTime += Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime / growDuration
                );


            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            transform.localScale =
                Vector3.Lerp(
                    originalScale,
                    enlargedScale,
                    smoothRate
                );


            material.color =
                Color.Lerp(
                    originalColor,
                    hotColor,
                    smoothRate
                );


            yield return null;
        }


        transform.localScale =
            enlargedScale;

        material.color =
            hotColor;


        // =========================
        // ③ 噴火音
        // =========================

        if (audioSource != null &&
            eruptionAudioClip != null)
        {
            audioSource.PlayOneShot(
                eruptionAudioClip
            );
        }


        // =========================
        // ④ 激しく揺れる
        // =========================

        elapsedTime = 0f;


        while (elapsedTime < strongShakeDuration)
        {
            elapsedTime += Time.deltaTime;


            float shakeX =
                Random.Range(
                    -strongShakeAmount,
                    strongShakeAmount
                );


            float shakeY =
                Random.Range(
                    -strongShakeAmount,
                    strongShakeAmount
                )
                * 0.5f;


            transform.position =
                originalPosition +
                new Vector3(
                    shakeX,
                    shakeY,
                    0f
                );


            // 少し脈打つ
            float pulse =
                1f +
                Mathf.Sin(
                    elapsedTime * 18f
                ) * 0.03f;


            transform.localScale =
                enlargedScale * pulse;


            yield return null;
        }


        transform.position =
            originalPosition;

        transform.localScale =
            enlargedScale;


        // 少し余韻
        yield return new WaitForSeconds(0.3f);


        // =========================
        // ⑤ 元の状態へ戻る
        // =========================

        elapsedTime = 0f;


        while (elapsedTime < returnDuration)
        {
            elapsedTime += Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime / returnDuration
                );


            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            transform.localScale =
                Vector3.Lerp(
                    enlargedScale,
                    originalScale,
                    smoothRate
                );


            material.color =
                Color.Lerp(
                    hotColor,
                    originalColor,
                    smoothRate
                );


            yield return null;
        }


        transform.position =
            originalPosition;

        transform.localScale =
            originalScale;

        material.color =
            originalColor;


        isActivated = false;


        Debug.Log(
            "MountainGimmick：山ギミック終了"
        );
    }
}