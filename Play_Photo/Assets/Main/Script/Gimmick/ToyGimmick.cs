using System.Collections;
using UnityEngine;

/// <summary>
/// おもちゃをタッチすると小さくピョンと跳ねる
/// </summary>
public class ToyGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float jumpHeight = 0.25f;

    [SerializeField]
    private float jumpDuration = 0.35f;

    private bool isJumping;

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
        if (isJumping)
        {
            return;
        }

        // ★追加：ジャンプするときに音を鳴らす
        if (audioSource != null && audioSource.clip != null)
        {
            audioSource.Play();
        }

        StartCoroutine(Jump());
    }

    private IEnumerator Jump()
    {
        isJumping = true;

        Vector3 startPosition = transform.position;

        float elapsedTime = 0f;

        while (elapsedTime < jumpDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(elapsedTime / jumpDuration);

            // ピョンと跳ねる
            float height =
                Mathf.Sin(rate * Mathf.PI) * jumpHeight;

            transform.position =
                startPosition +
                Vector3.up * height;

            yield return null;
        }

        transform.position = startPosition;

        isJumping = false;

        Debug.Log("おもちゃがジャンプしました。");
    }
}