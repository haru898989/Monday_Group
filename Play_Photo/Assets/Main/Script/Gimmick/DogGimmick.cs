using System.Collections;
using UnityEngine;

/// <summary>
/// 犬をタッチすると、鳴き声に合わせて二度跳ねる。
/// </summary>
public class DogGimmick : MonoBehaviour, GimmickBase
{
    [Header("Crouch")]
    [SerializeField]
    private float crouchDuration = 0.12f;

    [SerializeField]
    private Vector2 crouchScale = new Vector2(1.06f, 0.88f);

    [Header("First Jump")]
    [SerializeField]
    private float firstJumpHeight = 0.38f;

    [SerializeField]
    private float firstJumpDuration = 0.46f;

    [SerializeField]
    private float airTiltAngle = 7f;

    [Header("Landing")]
    [SerializeField]
    private float landingDuration = 0.13f;

    [SerializeField]
    private Vector2 landingScale = new Vector2(1.13f, 0.82f);

    [Header("Second Jump")]
    [SerializeField]
    private float secondJumpHeight = 0.23f;

    [SerializeField]
    private float secondJumpDuration = 0.34f;

    [SerializeField]
    private float settleDuration = 0.18f;

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
                "DogGimmickに渡されたAudioClipがnullです。"
            );
            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"犬の鳴き声を設定しました：{clip.name}"
        );
    }

    public void ActivateMagic()
    {
        if (isPlaying)
        {
            return;
        }

        isPlaying = true;
        StartCoroutine(PlayHappyJump());
    }

    private IEnumerator PlayHappyJump()
    {
        CaptureTransform();

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

        PlayBark();

        yield return Jump(
            firstJumpHeight,
            firstJumpDuration,
            airTiltAngle,
            crouchedScale
        );

        yield return AnimateScale(
            originalLocalScale,
            landedScale,
            landingDuration * 0.45f
        );

        yield return AnimateScale(
            landedScale,
            crouchedScale,
            landingDuration * 0.55f
        );

        yield return Jump(
            secondJumpHeight,
            secondJumpDuration,
            airTiltAngle * 0.65f,
            crouchedScale
        );

        yield return AnimateScale(
            originalLocalScale,
            landedScale,
            landingDuration * 0.45f
        );

        yield return AnimateScale(
            landedScale,
            originalLocalScale,
            settleDuration
        );

        RestoreTransform();
        isPlaying = false;
    }

    private IEnumerator Jump(
        float height,
        float duration,
        float tiltAngle,
        Vector3 startScale
    )
    {
        float safeDuration = Mathf.Max(duration, 0.05f);
        float elapsedTime = 0f;

        while (elapsedTime < safeDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(
                elapsedTime / safeDuration
            );

            float arc = Mathf.Sin(rate * Mathf.PI);
            float tilt =
                Mathf.Sin(rate * Mathf.PI * 2f) *
                tiltAngle *
                arc;

            float stretch = arc * 0.07f;
            Vector3 airScale = new Vector3(
                originalLocalScale.x * (1f - stretch * 0.35f),
                originalLocalScale.y * (1f + stretch),
                originalLocalScale.z
            );

            transform.localPosition =
                originalLocalPosition +
                Vector3.up * arc * height;

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

    private void PlayBark()
    {
        if (audioSource == null || audioSource.clip == null)
        {
            Debug.LogWarning(
                "犬の鳴き声が設定されていません。動きだけ再生します。"
            );
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log(
            $"犬が鳴いて跳ねました：{audioSource.clip.name}"
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
