using System.Collections;
using UnityEngine;

/// <summary>
/// ソファーをタッチすると、
/// 座られたように沈んでボヨンと戻る。
/// 同時に効果音を再生する。
/// </summary>
public class SofaGimmick : MonoBehaviour, GimmickBase
{
    [Header("沈み込み設定")]
    [SerializeField]
    private float squashAmountY = 0.85f;

    [SerializeField]
    private float stretchAmountX = 1.08f;

    [SerializeField]
    private float squashDuration = 0.18f;


    [Header("戻る設定")]
    [SerializeField]
    private float returnDuration = 0.35f;

    [SerializeField]
    private float bounceAmount = 0.08f;


    private bool isMoving;

    private Vector3 originalScale;

    private Vector3 originalPosition;

    private AudioSource audioSource;


    private void Awake()
    {
        originalScale = transform.localScale;
        originalPosition = transform.localPosition;


        // AudioSourceを取得
        audioSource = GetComponent<AudioSource>();


        // 無ければ自動で追加
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
    /// Reseiverからソファーの音を受け取る
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
                "ソファーのAudioClipがnullです。"
            );

            return;
        }


        audioSource.clip = clip;


        Debug.Log(
            $"ソファーの音声を設定しました：{clip.name}"
        );
    }


    /// <summary>
    /// ソファーをタッチしたとき
    /// </summary>
    public void ActivateMagic()
    {
        if (isMoving)
        {
            return;
        }


        // 効果音を再生
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.PlayOneShot(
                audioSource.clip
            );
        }
        else
        {
            Debug.LogWarning(
                "ソファーの音声が設定されていません。"
            );
        }


        StartCoroutine(
            SofaAction()
        );
    }


    /// <summary>
    /// ソファー全体の動き
    /// </summary>
    private IEnumerator SofaAction()
    {
        isMoving = true;


        // ① むにゅっと沈む
        yield return StartCoroutine(
            Squash()
        );


        // ② ボヨンと戻る
        yield return StartCoroutine(
            ReturnWithBounce()
        );


        // 最終的に元の状態に戻す
        transform.localScale =
            originalScale;

        transform.localPosition =
            originalPosition;


        isMoving = false;
    }


    /// <summary>
    /// 縦に縮み、少し横に広がる
    /// </summary>
    private IEnumerator Squash()
    {
        Vector3 startScale =
            transform.localScale;


        Vector3 targetScale =
            new Vector3(
                originalScale.x *
                stretchAmountX,

                originalScale.y *
                squashAmountY,

                originalScale.z
            );


        Vector3 startPosition =
            transform.localPosition;


        // 少し下方向へ沈ませる
        Vector3 targetPosition =
            originalPosition +
            Vector3.down * 0.08f;


        float elapsedTime = 0f;


        float safeDuration =
            Mathf.Max(
                squashDuration,
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


            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            // サイズ変更
            transform.localScale =
                Vector3.Lerp(
                    startScale,
                    targetScale,
                    smoothRate
                );


            // 少し下へ沈む
            transform.localPosition =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    smoothRate
                );


            yield return null;
        }


        transform.localScale =
            targetScale;

        transform.localPosition =
            targetPosition;
    }


    /// <summary>
    /// ボヨンと跳ねながら元に戻る
    /// </summary>
    private IEnumerator ReturnWithBounce()
    {
        Vector3 startScale =
            transform.localScale;


        Vector3 startPosition =
            transform.localPosition;


        float elapsedTime = 0f;


        float safeDuration =
            Mathf.Max(
                returnDuration,
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


            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            // サイズを元に戻す
            transform.localScale =
                Vector3.Lerp(
                    startScale,
                    originalScale,
                    smoothRate
                );


            // 位置を元に戻す
            Vector3 position =
                Vector3.Lerp(
                    startPosition,
                    originalPosition,
                    smoothRate
                );


            // 戻る途中で少し上へ跳ねる
            float bounce =
                Mathf.Sin(
                    rate *
                    Mathf.PI
                )
                *
                bounceAmount;


            position.y +=
                bounce;


            transform.localPosition =
                position;


            yield return null;
        }


        transform.localScale =
            originalScale;

        transform.localPosition =
            originalPosition;
    }


    /// <summary>
    /// オブジェクトが無効になったとき
    /// </summary>
    private void OnDisable()
    {
        StopAllCoroutines();


        isMoving = false;


        transform.localScale =
            originalScale;

        transform.localPosition =
            originalPosition;
    }
}