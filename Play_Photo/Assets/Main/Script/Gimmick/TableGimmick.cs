using System.Collections;
using UnityEngine;

/// <summary>
/// テーブルをタッチするとガタガタ揺れたあと、
/// 重そうに左右どちらかへ移動する。
/// </summary>
public class TableGimmick : MonoBehaviour, GimmickBase
{
    [Header("ガタガタ設定")]
    [SerializeField]
    private float shakeDuration = 0.4f;

    [SerializeField]
    private float shakeAmount = 0.04f;

    [SerializeField]
    private float shakeSpeed = 35f;


    [Header("移動設定")]
    [SerializeField]
    private float moveDistance = 0.8f;

    [SerializeField]
    private float moveDuration = 1.0f;

    [SerializeField]
    private float moveShakeAmount = 0.025f;

    [SerializeField]
    private float moveShakeSpeed = 40f;


    private bool isMoving = false;

    private AudioSource audioSource;


    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1f;
        audioSource.mute = false;
    }


    /// <summary>
    /// Reseiverから音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource == null)
        {
            audioSource =
                GetComponent<AudioSource>();

            if (audioSource == null)
            {
                audioSource =
                    gameObject.AddComponent<AudioSource>();
            }
        }

        if (clip == null)
        {
            Debug.LogWarning(
                "テーブルのAudioClipがnullです。"
            );

            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"テーブルの音声を設定しました：{clip.name}"
        );
    }


    /// <summary>
    /// タッチされたとき
    /// </summary>
    public void ActivateMagic()
    {
        if (isMoving)
        {
            return;
        }

        // 効果音
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.PlayOneShot(
                audioSource.clip
            );
        }

        StartCoroutine(
            TableAction()
        );
    }


    /// <summary>
    /// 全体の動き
    /// </summary>
    private IEnumerator TableAction()
    {
        isMoving = true;

        // ① ガタガタする
        yield return StartCoroutine(
            Shake()
        );

        // ② 横へズズズッと移動
        yield return StartCoroutine(
            Slide()
        );

        isMoving = false;
    }


    /// <summary>
    /// 最初にガタガタ揺れる
    /// </summary>
    private IEnumerator Shake()
    {
        Vector3 startPosition =
            transform.localPosition;

        float elapsedTime = 0f;

        float safeDuration =
            Mathf.Max(
                shakeDuration,
                0.01f
            );

        while (elapsedTime < safeDuration)
        {
            elapsedTime +=
                Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    safeDuration
                );

            // 徐々に揺れを弱くする
            float strength =
                1f - rate;

            float offsetX =
                Mathf.Sin(
                    elapsedTime *
                    shakeSpeed
                )
                *
                shakeAmount
                *
                strength;

            Vector3 position =
                startPosition;

            position.x += offsetX;

            transform.localPosition =
                position;

            yield return null;
        }

        transform.localPosition =
            startPosition;
    }


    /// <summary>
    /// 重そうに横へ移動
    /// </summary>
    private IEnumerator Slide()
    {
        Vector3 startPosition =
            transform.localPosition;

        // 左右どちらへ動くかランダム
        float direction =
            Random.value < 0.5f
            ? -1f
            : 1f;

        Vector3 targetPosition =
            startPosition +
            Vector3.right *
            moveDistance *
            direction;

        float elapsedTime = 0f;

        float safeDuration =
            Mathf.Max(
                moveDuration,
                0.01f
            );

        while (elapsedTime < safeDuration)
        {
            elapsedTime +=
                Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    safeDuration
                );

            // ゆっくり動き始めて
            // ゆっくり止まる
            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );

            Vector3 position =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    smoothRate
                );

            // 移動中に細かくガタガタさせる
            float shake =
                Mathf.Sin(
                    elapsedTime *
                    moveShakeSpeed
                )
                *
                moveShakeAmount;

            position.y += shake;

            transform.localPosition =
                position;

            yield return null;
        }

        transform.localPosition =
            targetPosition;
    }


    private void OnDisable()
    {
        StopAllCoroutines();

        isMoving = false;
    }
}