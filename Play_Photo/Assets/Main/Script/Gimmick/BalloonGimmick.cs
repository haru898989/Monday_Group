using System.Collections;
using UnityEngine;

/// <summary>
/// 風船をタッチすると、左右に揺れながら上昇して最後に破裂する。
/// </summary>
public class BalloonGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float riseDistance = 3f;

    [SerializeField]
    private float riseDuration = 2.5f;

    [SerializeField]
    private float swayAmount = 0.2f;

    [SerializeField]
    private float swaySpeed = 6f;

    private Renderer targetRenderer;

    private AudioClip popAudioClip;
    private AudioSource audioSource;

    private ParticleSystem popEffect;

    private bool isActivated;

    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }

    /// <summary>
    /// Receiverから風船の切り抜きRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }

    /// <summary>
    /// Receiverから破裂音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        popAudioClip = clip;
    }

    /// <summary>
    /// Receiverから破裂エフェクトを受け取る
    /// </summary>
    public void SetPopEffect(ParticleSystem effect)
    {
        popEffect = effect;
    }

    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;
        StartCoroutine(FlyAndPop());
    }

    private IEnumerator FlyAndPop()
    {
        Vector3 startPosition = transform.position;
        Vector3 startScale = transform.localScale;

        float elapsedTime = 0f;

        // 左右に揺れながら上昇
        while (elapsedTime < riseDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / riseDuration
                );

            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );

            float sway =
                Mathf.Sin(
                    elapsedTime * swaySpeed
                )
                * swayAmount;

            transform.position =
                startPosition
                + Vector3.up
                * riseDistance
                * smoothRate
                + Vector3.right
                * sway;

            // 上昇中に少しふわふわ膨らむ
            float pulse =
                1f
                + Mathf.Sin(
                    elapsedTime
                    * swaySpeed
                    * 1.5f
                )
                * 0.03f;

            transform.localScale =
                startScale * pulse;

            yield return null;
        }

        // 割れる直前に一瞬だけ膨らむ
        const float inflateDuration = 0.12f;

        elapsedTime = 0f;

        while (elapsedTime < inflateDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / inflateDuration
                );

            float scaleRate =
                Mathf.Lerp(
                    1f,
                    1.25f,
                    rate
                );

            transform.localScale =
                startScale * scaleRate;

            yield return null;
        }

        // 破裂音
        if (audioSource != null &&
            popAudioClip != null)
        {
            audioSource.PlayOneShot(popAudioClip);
        }

        // 破裂エフェクト
        if (popEffect != null)
        {
            ParticleSystem effect =
                Instantiate(
                    popEffect,
                    transform.position,
                    Quaternion.identity
                );

            effect.Play();

            float effectDestroyTime =
                effect.main.duration
                + effect.main.startLifetime.constantMax;

            Destroy(
                effect.gameObject,
                effectDestroyTime
            );
        }

        // 風船を消す
        HideBalloon();

        // 音が鳴り終わってから削除
        float destroyDelay =
            popAudioClip != null
                ? popAudioClip.length
                : 0.1f;

        Destroy(
            gameObject,
            destroyDelay
        );
    }

    private void HideBalloon()
    {
        if (targetRenderer == null)
        {
            targetRenderer =
                GetComponentInChildren<Renderer>(true);
        }

        if (targetRenderer != null)
        {
            targetRenderer.enabled = false;
        }

        Collider[] colliders =
            GetComponentsInChildren<Collider>(true);

        foreach (Collider targetCollider in colliders)
        {
            targetCollider.enabled = false;
        }
    }
}