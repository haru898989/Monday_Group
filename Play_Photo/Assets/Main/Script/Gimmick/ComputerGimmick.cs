using System.Collections;
using UnityEngine;

/// <summary>
/// パソコンをタッチするたびに、電源のON・OFFを切り替える。
/// </summary>
public class ComputerGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float startupFlickerInterval = 0.1f;

    [SerializeField]
    private float offFadeDuration = 0.25f;

    private Renderer targetRenderer;
    private Material targetMaterial;
    private Color originalColor = Color.white;

    private AudioClip powerAudioClip;
    private AudioSource audioSource;

    private bool isPowerOn;
    private bool isAnimating;

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

        if (targetRenderer == null)
        {
            return;
        }

        targetMaterial = targetRenderer.material;

        if (targetMaterial.HasProperty("_Color"))
        {
            originalColor = targetMaterial.GetColor("_Color");
        }

        SetVisual(0.55f, 0f);
    }

    public void SetAudioClip(AudioClip clip)
    {
        powerAudioClip = clip;
    }

    public void ActivateMagic()
    {
        if (isAnimating)
        {
            return;
        }

        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }

        if (targetMaterial == null)
        {
            Debug.LogWarning(
                "ComputerGimmickの表示用Rendererがありません。"
            );
            return;
        }

        StartCoroutine(
            isPowerOn ? TurnOff() : TurnOn()
        );
    }

    private IEnumerator TurnOn()
    {
        isAnimating = true;

        PlayPowerSound();

        // 起動時の点滅
        for (int i = 0; i < 3; i++)
        {
            SetVisual(1f, 1.2f);
            yield return new WaitForSeconds(
                startupFlickerInterval
            );

            SetVisual(0.55f, 0f);
            yield return new WaitForSeconds(
                startupFlickerInterval
            );
        }

        SetVisual(1f, 1.5f);

        isPowerOn = true;
        isAnimating = false;
    }

    private IEnumerator TurnOff()
    {
        isAnimating = true;

        PlayPowerSound();

        float elapsedTime = 0f;

        while (elapsedTime < offFadeDuration)
        {
            elapsedTime += Time.deltaTime;
            float rate =
                Mathf.Clamp01(elapsedTime / offFadeDuration);

            float brightness = Mathf.Lerp(1f, 0.55f, rate);
            float emission = Mathf.Lerp(1.5f, 0f, rate);

            SetVisual(brightness, emission);
            yield return null;
        }

        SetVisual(0.55f, 0f);

        isPowerOn = false;
        isAnimating = false;
    }

    private void SetVisual(
        float brightness,
        float emissionStrength
    )
    {
        if (targetMaterial == null)
        {
            return;
        }

        if (targetMaterial.HasProperty("_Color"))
        {
            Color displayColor =
                originalColor * brightness;

            displayColor.a = originalColor.a;

            targetMaterial.SetColor(
                "_Color",
                displayColor
            );
        }

        if (targetMaterial.HasProperty("_EmissionColor"))
        {
            targetMaterial.EnableKeyword("_EMISSION");
            targetMaterial.SetColor(
                "_EmissionColor",
                Color.white * emissionStrength
            );
        }
    }

    private void PlayPowerSound()
    {
        if (audioSource != null && powerAudioClip != null)
        {
            audioSource.PlayOneShot(powerAudioClip);
        }
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