using System.Collections;
using UnityEngine;

/// <summary>
/// 宝箱をタッチすると、金色の輝き、不気味な紫色の輝き、
/// または小刻みな震えのいずれかをランダムで再生する。
/// </summary>
public class TreasureChestGimmick : MonoBehaviour, GimmickBase
{
    private enum ChestEffect
    {
        Rattle,
        EvilGlow,
        GoldenGlow
    }

    [Header("Random Chances")]
    [SerializeField, Range(0f, 1f)]
    private float rattleProbability = 0.50f;

    [SerializeField, Range(0f, 1f)]
    private float evilGlowProbability = 0.25f;

    [Header("Golden Glow")]
    [SerializeField]
    private float jumpHeight = 0.3f;

    [SerializeField]
    private float openDuration = 0.7f;

    [SerializeField]
    private float rotationAngle = 8f;

    [Header("Evil Glow")]
    [SerializeField]
    private float evilGlowDuration = 1.15f;

    [SerializeField]
    private Color evilColor = new Color(0.55f, 0.08f, 0.95f, 1f);

    [Header("Rattle")]
    [SerializeField]
    private float rattleDuration = 0.95f;

    [SerializeField]
    private float rattleFrequency = 22f;

    [SerializeField]
    private float rattleDistance = 0.055f;

    [SerializeField]
    private float rattleAngle = 4.5f;

    private Renderer targetRenderer;
    private Material targetMaterial;

    private Color originalColor = Color.white;
    private Color originalEmissionColor = Color.black;
    private bool hasOriginalColor;
    private bool hasOriginalEmissionColor;
    private bool originalEmissionEnabled;

    private AudioClip openAudioClip;
    private AudioSource audioSource;

    private Vector3 effectStartLocalPosition;
    private Vector3 effectStartLocalScale;
    private Quaternion effectStartLocalRotation;
    private bool hasEffectStartTransform;
    private bool isPlaying;

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
        if (renderer == null)
        {
            return;
        }

        targetRenderer = renderer;
        targetMaterial = targetRenderer.material;

        if (targetMaterial.HasProperty("_Color"))
        {
            originalColor = targetMaterial.GetColor("_Color");
            hasOriginalColor = true;
        }

        if (targetMaterial.HasProperty("_EmissionColor"))
        {
            originalEmissionColor =
                targetMaterial.GetColor("_EmissionColor");

            hasOriginalEmissionColor = true;
            originalEmissionEnabled =
                targetMaterial.IsKeywordEnabled("_EMISSION");
        }
    }

    public void SetAudioClip(AudioClip clip)
    {
        openAudioClip = clip;
    }

    public void ActivateMagic()
    {
        if (isPlaying)
        {
            return;
        }

        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }

        isPlaying = true;
        StartCoroutine(PlayRandomEffect());
    }

    private IEnumerator PlayRandomEffect()
    {
        CaptureTransform();
        RestoreMaterial();

        if (audioSource != null && openAudioClip != null)
        {
            audioSource.PlayOneShot(openAudioClip);
        }

        ChestEffect effect = ChooseRandomEffect();

        switch (effect)
        {
            case ChestEffect.Rattle:
                Debug.Log("宝箱ギミック：カタカタ震える");
                yield return RattleEffect();
                break;

            case ChestEffect.EvilGlow:
                Debug.Log("宝箱ギミック：紫色に怪しく光る");
                yield return EvilGlowEffect();
                break;

            default:
                Debug.Log("宝箱ギミック：金色に光る");
                yield return GoldenGlowEffect();
                break;
        }

        RestoreTransform();
        RestoreMaterial();
        isPlaying = false;
    }

    private ChestEffect ChooseRandomEffect()
    {
        float roll = Random.value;
        float rattleThreshold = Mathf.Clamp01(rattleProbability);
        float evilThreshold = Mathf.Clamp01(
            rattleThreshold + evilGlowProbability
        );

        if (roll < rattleThreshold)
        {
            return ChestEffect.Rattle;
        }

        if (roll < evilThreshold)
        {
            return ChestEffect.EvilGlow;
        }

        return ChestEffect.GoldenGlow;
    }

    private IEnumerator GoldenGlowEffect()
    {
        float duration = Mathf.Max(openDuration, 0.05f);
        float elapsedTime = 0f;
        Color gold = new Color(1f, 0.65f, 0.1f, 1f);

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / duration);
            float envelope = Mathf.Sin(rate * Mathf.PI);
            float angle =
                Mathf.Sin(rate * Mathf.PI * 2f) *
                rotationAngle *
                envelope;

            transform.localPosition =
                effectStartLocalPosition +
                Vector3.up * envelope * jumpHeight;

            transform.localScale =
                effectStartLocalScale * (1f + envelope * 0.18f);

            transform.localRotation =
                effectStartLocalRotation *
                Quaternion.Euler(0f, 0f, angle);

            SetEffectColor(gold, envelope, 0.22f, 2.2f);

            yield return null;
        }
    }

    private IEnumerator EvilGlowEffect()
    {
        float duration = Mathf.Max(evilGlowDuration, 0.05f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / duration);
            float envelope = Mathf.Sin(rate * Mathf.PI);
            float flicker =
                0.72f +
                Mathf.Abs(Mathf.Sin(rate * Mathf.PI * 7f)) * 0.28f;

            float strength = envelope * flicker;
            float angle =
                Mathf.Sin(rate * Mathf.PI * 6f) *
                2.2f *
                envelope;

            transform.localScale =
                effectStartLocalScale * (1f + strength * 0.07f);

            transform.localRotation =
                effectStartLocalRotation *
                Quaternion.Euler(0f, 0f, angle);

            SetEffectColor(
                evilColor,
                strength,
                0.72f,
                2.8f
            );

            yield return null;
        }
    }

    private IEnumerator RattleEffect()
    {
        float duration = Mathf.Max(rattleDuration, 0.05f);
        float frequency = Mathf.Max(rattleFrequency, 1f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(elapsedTime / duration);
            float envelope = Mathf.Sin(rate * Mathf.PI);
            float phase = elapsedTime * frequency * Mathf.PI * 2f;

            float horizontalShake =
                Mathf.Sin(phase) * rattleDistance * envelope;

            float verticalShake =
                Mathf.Sin(phase * 1.65f) *
                rattleDistance *
                0.28f *
                envelope;

            float angle =
                Mathf.Sin(phase * 0.82f) *
                rattleAngle *
                envelope;

            transform.localPosition =
                effectStartLocalPosition +
                new Vector3(horizontalShake, verticalShake, 0f);

            transform.localRotation =
                effectStartLocalRotation *
                Quaternion.Euler(0f, 0f, angle);

            yield return null;
        }
    }

    private void CaptureTransform()
    {
        effectStartLocalPosition = transform.localPosition;
        effectStartLocalScale = transform.localScale;
        effectStartLocalRotation = transform.localRotation;
        hasEffectStartTransform = true;
    }

    private void RestoreTransform()
    {
        if (!hasEffectStartTransform)
        {
            return;
        }

        transform.localPosition = effectStartLocalPosition;
        transform.localScale = effectStartLocalScale;
        transform.localRotation = effectStartLocalRotation;
        hasEffectStartTransform = false;
    }

    private void SetEffectColor(
        Color effectColor,
        float strength,
        float tintAmount,
        float emissionStrength
    )
    {
        if (targetMaterial == null)
        {
            return;
        }

        float safeStrength = Mathf.Clamp01(strength);

        if (hasOriginalColor && targetMaterial.HasProperty("_Color"))
        {
            effectColor.a = originalColor.a;

            targetMaterial.SetColor(
                "_Color",
                Color.Lerp(
                    originalColor,
                    effectColor,
                    safeStrength * tintAmount
                )
            );
        }

        if (targetMaterial.HasProperty("_EmissionColor"))
        {
            targetMaterial.EnableKeyword("_EMISSION");
            targetMaterial.SetColor(
                "_EmissionColor",
                effectColor * safeStrength * emissionStrength
            );
        }
    }

    private void RestoreMaterial()
    {
        if (targetMaterial == null)
        {
            return;
        }

        if (hasOriginalColor && targetMaterial.HasProperty("_Color"))
        {
            targetMaterial.SetColor("_Color", originalColor);
        }

        if (hasOriginalEmissionColor &&
            targetMaterial.HasProperty("_EmissionColor"))
        {
            targetMaterial.SetColor(
                "_EmissionColor",
                originalEmissionColor
            );

            if (originalEmissionEnabled)
            {
                targetMaterial.EnableKeyword("_EMISSION");
            }
            else
            {
                targetMaterial.DisableKeyword("_EMISSION");
            }
        }
    }

    private void OnDisable()
    {
        StopAllCoroutines();
        RestoreTransform();
        RestoreMaterial();
        isPlaying = false;
    }

    private void OnDestroy()
    {
        if (targetMaterial != null)
        {
            Destroy(targetMaterial);
            targetMaterial = null;
        }
    }
}
