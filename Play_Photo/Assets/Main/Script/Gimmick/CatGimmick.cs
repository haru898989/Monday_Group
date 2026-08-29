using System.Collections;
using UnityEngine;

/// <summary>
/// 猫をタッチすると、鳴き声に合わせて小さく跳ね、
/// 首をかしげながらすり寄るように動く。
/// </summary>
public class CatGimmick : MonoBehaviour, GimmickBase
{
    [Header("Crouch")]
    [SerializeField]
    private float crouchDuration = 0.12f;

    [SerializeField]
    private Vector2 crouchScale = new Vector2(1.05f, 0.90f);

    [Header("Soft Jump")]
    [SerializeField]
    private float jumpHeight = 0.25f;

    [SerializeField]
    private float jumpDuration = 0.42f;

    [SerializeField]
    private float jumpTiltAngle = 4f;

    [Header("Landing")]
    [SerializeField]
    private float landingDuration = 0.14f;

    [SerializeField]
    private Vector2 landingScale = new Vector2(1.10f, 0.86f);

    [Header("Head Tilt And Nuzzle")]
    [SerializeField]
    private float nuzzleDuration = 1.05f;

    [SerializeField]
    private float headTiltAngle = 9f;

    [SerializeField]
    private float nuzzleDistance = 0.07f;

    [SerializeField]
    private float nuzzleScaleAmount = 0.08f;

    private AudioSource audioSource;
    private Vector3 originalLocalPosition;
    private Vector3 originalLocalScale;
    private Quaternion originalLocalRotation;
    private bool hasOriginalTransform;
    private bool isPlaying;

    private void Awake()
    {
        EnsureAudioSource();
    }

    public void SetAudioClip(AudioClip clip)
    {
        EnsureAudioSource();

        if (clip == null)
        {
            Debug.LogWarning(
                "CatGimmickに渡されたAudioClipがnullです。"
            );
            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"猫の鳴き声を設定しました：{clip.name}"
        );
    }

    public void ActivateMagic()
    {
        if (isPlaying)
        {
            return;
        }

        isPlaying = true;
        StartCoroutine(PlayCuteReaction());
    }

    private IEnumerator PlayCuteReaction()
    {
        CaptureTransform();

        float direction = Random.value < 0.5f ? -1f : 1f;

        Vector3 crouchedScale = MultiplyScale(
            originalLocalScale,
            crouchScale
        );

        Vector3 landedScale = MultiplyScale(
            originalLocalScale,
            landingScale
        );

        yield return AnimateScale(
            originalLocalScale,
            crouchedScale,
            crouchDuration
        );

        PlayMeow();
        yield return SoftJump(direction, crouchedScale);

        yield return AnimateScale(
            originalLocalScale,
            landedScale,
            landingDuration * 0.45f
        );

        yield return AnimateScale(
            landedScale,
            originalLocalScale,
            landingDuration * 0.55f
        );

        yield return HeadTiltAndNuzzle(direction);

        RestoreTransform();
        isPlaying = false;
    }

    private IEnumerator SoftJump(
        float direction,
        Vector3 startScale
    )
    {
        float duration = Mathf.Max(jumpDuration, 0.05f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / duration);
            float arc = Mathf.Sin(rate * Mathf.PI);
            float tilt =
                direction *
                Mathf.Sin(rate * Mathf.PI) *
                jumpTiltAngle;

            Vector3 airScale = new Vector3(
                originalLocalScale.x * (1f - arc * 0.025f),
                originalLocalScale.y * (1f + arc * 0.05f),
                originalLocalScale.z
            );

            transform.localPosition =
                originalLocalPosition +
                Vector3.up * arc * jumpHeight;

            transform.localScale = Vector3.Lerp(
                startScale,
                airScale,
                Mathf.SmoothStep(0f, 1f, rate)
            );

            transform.localRotation =
                originalLocalRotation *
                Quaternion.Euler(0f, 0f, tilt);

            yield return null;
        }

        transform.localPosition = originalLocalPosition;
        transform.localScale = originalLocalScale;
        transform.localRotation = originalLocalRotation;
    }

    private IEnumerator HeadTiltAndNuzzle(float direction)
    {
        float duration = Mathf.Max(nuzzleDuration, 0.05f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / duration);
            float envelope = Mathf.Sin(rate * Mathf.PI);
            float gentleSway =
                Mathf.Sin(rate * Mathf.PI * 3f) *
                1.8f *
                envelope;

            float tilt =
                direction * headTiltAngle * envelope +
                gentleSway;

            float approach = envelope * nuzzleScaleAmount;

            transform.localPosition =
                originalLocalPosition +
                new Vector3(
                    direction * nuzzleDistance * envelope,
                    Mathf.Sin(rate * Mathf.PI * 2f) *
                    0.012f *
                    envelope,
                    0f
                );

            transform.localScale = new Vector3(
                originalLocalScale.x * (1f + approach),
                originalLocalScale.y * (1f + approach),
                originalLocalScale.z
            );

            transform.localRotation =
                originalLocalRotation *
                Quaternion.Euler(0f, 0f, tilt);

            yield return null;
        }
    }

    private IEnumerator AnimateScale(
        Vector3 from,
        Vector3 to,
        float duration
    )
    {
        float safeDuration = Mathf.Max(duration, 0.02f);
        float elapsedTime = 0f;

        while (elapsedTime < safeDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.SmoothStep(
                0f,
                1f,
                Mathf.Clamp01(elapsedTime / safeDuration)
            );

            transform.localScale = Vector3.Lerp(from, to, rate);
            yield return null;
        }

        transform.localScale = to;
    }

    private Vector3 MultiplyScale(Vector3 scale, Vector2 multiplier)
    {
        return new Vector3(
            scale.x * multiplier.x,
            scale.y * multiplier.y,
            scale.z
        );
    }

    private void EnsureAudioSource()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1f;
        audioSource.mute = false;
    }

    private void PlayMeow()
    {
        if (audioSource == null || audioSource.clip == null)
        {
            Debug.LogWarning(
                "猫の鳴き声が設定されていません。動きだけ再生します。"
            );
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log(
            $"猫が鳴いてすり寄りました：{audioSource.clip.name}"
        );
    }

    private void CaptureTransform()
    {
        originalLocalPosition = transform.localPosition;
        originalLocalScale = transform.localScale;
        originalLocalRotation = transform.localRotation;
        hasOriginalTransform = true;
    }

    private void RestoreTransform()
    {
        if (!hasOriginalTransform)
        {
            return;
        }

        transform.localPosition = originalLocalPosition;
        transform.localScale = originalLocalScale;
        transform.localRotation = originalLocalRotation;
        hasOriginalTransform = false;
    }

    private void OnDisable()
    {
        StopAllCoroutines();
        RestoreTransform();
        isPlaying = false;
    }
}
