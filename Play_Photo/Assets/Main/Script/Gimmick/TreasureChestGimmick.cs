using System.Collections;
using UnityEngine;

/// <summary>
/// 宝箱をタッチすると、跳ねて開いたように動き、金色に発光する。
/// 1回だけ発動する。
/// </summary>
public class TreasureChestGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float jumpHeight = 0.3f;

    [SerializeField]
    private float openDuration = 0.7f;

    [SerializeField]
    private float rotationAngle = 8f;

    private Renderer targetRenderer;
    private Material targetMaterial;
    private Color originalColor = Color.white;

    private AudioClip openAudioClip;
    private AudioSource audioSource;

    private bool isOpened;

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
    }

    public void SetAudioClip(AudioClip clip)
    {
        openAudioClip = clip;
    }

    public void ActivateMagic()
    {
        if (isOpened)
        {
            return;
        }

        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }

        isOpened = true;
        StartCoroutine(OpenChest());
    }

    private IEnumerator OpenChest()
    {
        Vector3 startPosition = transform.position;
        Vector3 startScale = transform.localScale;
        Quaternion startRotation = transform.rotation;

        if (audioSource != null && openAudioClip != null)
        {
            audioSource.PlayOneShot(openAudioClip);
        }

        float elapsedTime = 0f;

        while (elapsedTime < openDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(elapsedTime / openDuration);

            float bounce = Mathf.Sin(rate * Mathf.PI);
            float scaleRate = 1f + bounce * 0.18f;
            float angle =
                Mathf.Sin(rate * Mathf.PI) * rotationAngle;

            transform.position =
                startPosition + Vector3.up * bounce * jumpHeight;

            transform.localScale =
                startScale * scaleRate;

            transform.rotation =
                startRotation
                * Quaternion.Euler(0f, 0f, -angle);

            SetGlow(bounce * 2f);

            yield return null;
        }

        transform.position = startPosition;
        transform.localScale = startScale;
        transform.rotation = startRotation;

        // 開いた後は金色の光を残す
        SetGlow(1.4f);
    }

    private void SetGlow(float strength)
    {
        if (targetMaterial == null)
        {
            return;
        }

        if (targetMaterial.HasProperty("_Color"))
        {
            targetMaterial.SetColor(
                "_Color",
                originalColor
            );
        }

        if (targetMaterial.HasProperty("_EmissionColor"))
        {
            targetMaterial.EnableKeyword("_EMISSION");

            Color gold =
                new Color(1f, 0.65f, 0.1f);

            targetMaterial.SetColor(
                "_EmissionColor",
                gold * strength
            );
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