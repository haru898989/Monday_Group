using System.Collections;
using UnityEngine;

/// <summary>
/// 風船をタッチすると、左右に揺れながら上昇して最後に割れる。
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

    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }

    public void SetAudioClip(AudioClip clip)
    {
        popAudioClip = clip;
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

        while (elapsedTime < riseDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / riseDuration);
            float smoothRate = Mathf.SmoothStep(0f, 1f, rate);
            float sway = Mathf.Sin(elapsedTime * swaySpeed) * swayAmount;

            transform.position =
                startPosition
                + Vector3.up * riseDistance * smoothRate
                + Vector3.right * sway;

            float pulse =
                1f + Mathf.Sin(elapsedTime * swaySpeed * 1.5f) * 0.03f;

            transform.localScale = startScale * pulse;

            yield return null;
        }

        if (audioSource != null && popAudioClip != null)
        {
            audioSource.PlayOneShot(popAudioClip);
        }

        // 割れる直前に一瞬膨らませる
        const float popDuration = 0.16f;
        elapsedTime = 0f;

        while (elapsedTime < popDuration)
        {
            elapsedTime += Time.deltaTime;
            float rate = Mathf.Clamp01(elapsedTime / popDuration);

            float scaleRate;

            if (rate < 0.5f)
            {
                scaleRate = Mathf.Lerp(1f, 1.25f, rate * 2f);
            }
            else
            {
                scaleRate = Mathf.Lerp(
                    1.25f,
                    0f,
                    (rate - 0.5f) * 2f
                );
            }

            transform.localScale = startScale * scaleRate;
            yield return null;
        }

        HideBalloon();

        float destroyDelay =
            popAudioClip != null ? popAudioClip.length : 0f;

        Destroy(gameObject, destroyDelay);
    }

    private void HideBalloon()
    {
        if (targetRenderer == null)
        {
            targetRenderer = GetComponentInChildren<Renderer>(true);
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