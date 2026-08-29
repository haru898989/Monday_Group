using System.Collections;
using UnityEngine;

/// <summary>
/// 車をタッチすると発進音が鳴り、
/// 左方向へ加速しながら走り去る。
/// </summary>
public class CarGimmick : MonoBehaviour, GimmickBase
{
    // どれくらい左へ進むか
    [SerializeField]
    private float driveDistance = 7f;

    // 走り切るまでの時間
    [SerializeField]
    private float driveDuration = 1.5f;

    private AudioClip carAudioClip;
    private AudioSource audioSource;

    private bool isActivated = false;


    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;

        // 2D音声として再生
        audioSource.spatialBlend = 0f;
    }


    /// <summary>
    /// Receiverから車の発進音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        carAudioClip = clip;
    }


    /// <summary>
    /// 車をタッチしたときに実行
    /// </summary>
    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;

        StartCoroutine(Drive());
    }


    /// <summary>
    /// 車を左方向へ走らせる
    /// </summary>
    private IEnumerator Drive()
    {
        Vector3 startPosition = transform.position;

        // =========================
        // ① 発進音
        // =========================

        if (audioSource != null &&
            carAudioClip != null)
        {
            audioSource.PlayOneShot(
                carAudioClip
            );
        }
        else
        {
            Debug.LogWarning(
                "CarGimmick：Car Audio Clipが設定されていません。"
            );
        }


        // =========================
        // ② 左方向へ発進
        // =========================

        float elapsedTime = 0f;


        while (elapsedTime < driveDuration)
        {
            elapsedTime += Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime / driveDuration
                );


            // 最初はゆっくり、
            // 徐々に加速する
            float moveRate =
                rate * rate;


            transform.position =
                startPosition +
                Vector3.left *
                driveDistance *
                moveRate;


            yield return null;
        }


        // =========================
        // ③ 画面外へ行ったら削除
        // =========================

        Destroy(gameObject);
    }
}