using System.Collections;
using UnityEngine;

/// <summary>
/// 飛行機をタッチすると真上へ飛ぶ
/// </summary>
public class AirplaneGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float flyHeight = 5f;

    [SerializeField]
    private float flyDuration = 2f;

    private bool isFlying;

    // ★追加
    private AudioSource audioSource;

    // ★追加：Receiverから音源を受け取る
    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();

            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
            }
        }

        audioSource.clip = clip;
        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }

    public void ActivateMagic()
    {
        if (isFlying)
        {
            return;
        }

        // ★追加：飛び始めるときに音を鳴らす
        if (audioSource != null && audioSource.clip != null)
        {
            audioSource.Play();
        }

        StartCoroutine(FlyUp());
    }

    private IEnumerator FlyUp()
    {
        isFlying = true;

        Vector3 startPosition = transform.position;
        Vector3 targetPosition =
            startPosition + Vector3.up * flyHeight;

        float elapsedTime = 0f;

        while (elapsedTime < flyDuration)
        {
            elapsedTime += Time.deltaTime;

            float t = Mathf.SmoothStep(
                0f,
                1f,
                elapsedTime / flyDuration
            );

            transform.position =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    t
                );

            yield return null;
        }

        transform.position = targetPosition;

        isFlying = false;
    }
}