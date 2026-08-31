using System.Collections;
using UnityEngine;

/// <summary>
/// 魚をタップすると高速でピチピチ暴れる。
/// 回転だけでなく、伸縮を組み合わせて
/// 魚の体がしなるように見せる。
/// </summary>
public class FishGlowGimmick : MonoBehaviour, GimmickBase
{
    [Header("ピチピチ設定")]

    // 全体のピチピチ時間
    [SerializeField]
    private float shakeTime = 0.8f;

    // 左右に傾く角度
    [SerializeField]
    private float shakeAngle = 16f;

    // ピチピチ速度
    [SerializeField]
    private float shakeSpeed = 45f;


    [Header("体のくねり")]

    // 横方向の伸縮量
    [SerializeField]
    private float bodyBendAmount = 0.10f;

    // 縦方向の伸縮量
    [SerializeField]
    private float bodySquashAmount = 0.05f;

    // 伸縮速度
    [SerializeField]
    private float bodyBendSpeed = 45f;


    [Header("跳ねる動き")]

    // 跳ねる高さ
    [SerializeField]
    private float jumpHeight = 0.07f;

    // 跳ねる速度
    [SerializeField]
    private float jumpSpeed = 30f;


    [Header("横移動")]

    // 左右への移動量
    [SerializeField]
    private float sideMoveAmount = 0.025f;


    private bool isActivated = false;

    private Quaternion originalRotation;
    private Vector3 originalPosition;
    private Vector3 originalScale;

    private AudioSource audioSource;


    private void Awake()
    {
        originalRotation =
            transform.localRotation;

        originalPosition =
            transform.localPosition;

        originalScale =
            transform.localScale;


        // AudioSourceを取得
        audioSource =
            GetComponent<AudioSource>();

        // 無ければ追加
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
    /// Reseiver.csから呼ばれるため残している
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
    }


    /// <summary>
    /// Reseiverから魚の音を受け取る
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

            audioSource.playOnAwake = false;
            audioSource.loop = false;
            audioSource.spatialBlend = 0f;
            audioSource.volume = 1f;
            audioSource.mute = false;
        }


        if (clip == null)
        {
            Debug.LogWarning(
                "魚のAudioClipがnullです。"
            );

            return;
        }


        audioSource.clip = clip;

        Debug.Log(
            $"魚の音声を設定しました：{clip.name}"
        );
    }


    /// <summary>
    /// タッチされたとき
    /// </summary>
    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }


        isActivated = true;


        // 現在の状態を保存
        originalRotation =
            transform.localRotation;

        originalPosition =
            transform.localPosition;

        originalScale =
            transform.localScale;


        // 音を再生
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.PlayOneShot(
                audioSource.clip
            );
        }


        StartCoroutine(
            FishFlop()
        );
    }


    /// <summary>
    /// 魚のピチピチ動作
    /// </summary>
    private IEnumerator FishFlop()
    {
        float elapsedTime = 0f;


        while (elapsedTime < shakeTime)
        {
            elapsedTime +=
                Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    shakeTime
                );


            /*
             * 最初は激しく、
             * 最後だけ少し弱くする。
             *
             * 前のコードより
             * 弱くなるタイミングを遅くしている。
             */
            float strength =
                Mathf.Lerp(
                    1f,
                    0.25f,
                    rate * rate
                );


            // =====================================
            // ① 高速左右回転
            // =====================================

            float wave =
                Mathf.Sin(
                    elapsedTime *
                    shakeSpeed
                );


            float angle =
                wave *
                shakeAngle *
                strength;


            transform.localRotation =
                originalRotation *
                Quaternion.Euler(
                    0f,
                    0f,
                    angle
                );


            // =====================================
            // ② 魚の体を伸縮
            // =====================================

            /*
             * 回転とは少しタイミングをずらす。
             *
             * これによって
             * 「魚全体が板みたいに回転」
             * している感じを減らす。
             */

            float bodyWave =
                Mathf.Sin(
                    elapsedTime *
                    bodyBendSpeed +
                    1.2f
                );


            float scaleX =
                1f +
                bodyWave *
                bodyBendAmount *
                strength;


            float scaleY =
                1f -
                Mathf.Abs(bodyWave) *
                bodySquashAmount *
                strength;


            Vector3 newScale =
                originalScale;


            newScale.x =
                originalScale.x *
                scaleX;


            newScale.y =
                originalScale.y *
                scaleY;


            transform.localScale =
                newScale;


            // =====================================
            // ③ 高速で上下に跳ねる
            // =====================================

            float jump =
                Mathf.Abs(
                    Mathf.Sin(
                        elapsedTime *
                        jumpSpeed
                    )
                )
                *
                jumpHeight *
                strength;


            // =====================================
            // ④ 左右にも少しズレる
            // =====================================

            float side =
                Mathf.Sin(
                    elapsedTime *
                    shakeSpeed *
                    0.7f
                )
                *
                sideMoveAmount *
                strength;


            Vector3 position =
                originalPosition;


            position.x += side;
            position.y += jump;


            transform.localPosition =
                position;


            yield return null;
        }


        // =====================================
        // 元の状態へ戻す
        // =====================================

        transform.localPosition =
            originalPosition;

        transform.localRotation =
            originalRotation;

        transform.localScale =
            originalScale;


        isActivated = false;
    }


    private void OnDisable()
    {
        StopAllCoroutines();

        isActivated = false;

        transform.localPosition =
            originalPosition;

        transform.localRotation =
            originalRotation;

        transform.localScale =
            originalScale;
    }
}