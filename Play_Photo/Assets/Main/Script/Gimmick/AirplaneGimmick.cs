using System.Collections;
using UnityEngine;

/// <summary>
/// 飛行機をタッチすると、音を鳴らしながらゆっくり上へ浮かぶギミック
/// </summary>
public class AirplaneGimmick : MonoBehaviour, GimmickBase
{
    [Header("上に飛ぶ距離")]
    [SerializeField]
    private float flyHeight = 5f;

    [Header("飛ぶ時間")]
    [SerializeField]
    private float flyDuration = 4f;

    private AudioSource audioSource;
    private AudioClip airplaneAudioClip;

    private bool isFlying;

    private void Awake()
    {
        // AudioSourceを取得
        audioSource = GetComponent<AudioSource>();

        // なければ自動で追加
        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }

    /// <summary>
    /// Reseiver.csから飛行機の音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        airplaneAudioClip = clip;
    }

    /// <summary>
    /// 飛行機をタップしたときに実行される
    /// </summary>
    public void ActivateMagic()
    {
        // すでに飛んでいる場合は何もしない
        if (isFlying)
        {
            return;
        }

        Debug.Log("飛行機ギミック発動");

        // 飛行音を鳴らす
        if (audioSource != null &&
            airplaneAudioClip != null)
        {
            audioSource.PlayOneShot(
                airplaneAudioClip
            );
        }

        // 現在位置からゆっくり上へ浮かぶ処理を開始
        StartCoroutine(FlyUp());
    }

    /// <summary>
    /// 飛行機をゆっくり上へ移動させる
    /// </summary>
    private IEnumerator FlyUp()
    {
        isFlying = true;

        // 開始位置
        Vector3 startPosition =
            transform.position;

        // 到着位置
        Vector3 targetPosition =
            startPosition +
            Vector3.up * flyHeight;

        float elapsedTime = 0f;

        while (elapsedTime < flyDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / flyDuration
                );

            // 少し自然な動きにする
            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );

            transform.position =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    smoothRate
                );

            yield return null;
        }

        // 最後に位置を確実に合わせる
        transform.position =
            targetPosition;

        isFlying = false;
    }
}
