using System.Collections;
using UnityEngine;

/// <summary>
/// 最初のタッチ後、花が右からの風を受けて常に揺れ続ける。
/// 風が吹いている間も、タッチするたび花の色を変更できる。
/// </summary>
public class FlowerGimmick : MonoBehaviour, GimmickBase
{
    [Header("Wind From Right")]
    [SerializeField]
    private float calmWindAngle = 0.7f;

    [SerializeField]
    private float normalWindAngle = 6.5f;

    [SerializeField]
    private float strongWindAngle = 11f;

    [SerializeField, Range(0f, 1f)]
    private float calmWindProbability = 0.25f;

    [SerializeField, Range(0f, 1f)]
    private float strongWindProbability = 0.28f;

    [SerializeField]
    private float minimumWindChangeDuration = 0.65f;

    [SerializeField]
    private float maximumWindChangeDuration = 2.1f;

    [SerializeField]
    private float flutterAngle = 0.65f;

    [SerializeField]
    private float flutterFrequency = 0.75f;

    [Header("Color Change")]
    [SerializeField]
    private float colorChangeDuration = 0.7f;

    private Renderer targetRenderer;
    private Material targetMaterial;
    private Color currentColor = Color.white;

    private Vector3 originalLocalPosition;
    private Vector3 originalLocalScale;
    private Quaternion originalLocalRotation;
    private Vector3 bottomPivotOffset;
    private Vector3 bottomPivotPosition;

    private Coroutine windCoroutine;
    private Coroutine colorChangeCoroutine;
    private float windNoiseSeed;
    private int previousColorIndex = -1;
    private bool hasWindPivot;

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
            currentColor = targetMaterial.GetColor("_Color");
        }
    }

    public void ActivateMagic()
    {
        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }

        if (windCoroutine == null)
        {
            CaptureWindPivot();
            windCoroutine = StartCoroutine(ContinuousWind());
        }

        if (colorChangeCoroutine != null)
        {
            StopCoroutine(colorChangeCoroutine);
        }

        colorChangeCoroutine = StartCoroutine(
            ColorChangeEffect()
        );
    }

    private void CaptureWindPivot()
    {
        originalLocalPosition = transform.localPosition;
        originalLocalScale = transform.localScale;
        originalLocalRotation = transform.localRotation;

        bottomPivotOffset = Vector3.Scale(
            Vector3.down * 0.5f,
            originalLocalScale
        );

        bottomPivotPosition =
            originalLocalPosition +
            originalLocalRotation * bottomPivotOffset;

        windNoiseSeed = Random.Range(0f, 1000f);
        hasWindPivot = true;
    }

    private IEnumerator ContinuousWind()
    {
        float currentAngle = 0f;

        while (true)
        {
            float targetAngle = ChooseNextWindAngle();
            float duration = ChooseWindChangeDuration(targetAngle);
            float startAngle = currentAngle;
            float elapsedTime = 0f;

            while (elapsedTime < duration)
            {
                elapsedTime += Time.deltaTime;

                float rate = Mathf.Clamp01(
                    elapsedTime / duration
                );

                float smoothRate = Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );

                currentAngle = Mathf.Lerp(
                    startAngle,
                    targetAngle,
                    smoothRate
                );

                float flutter = GetWindFlutter(currentAngle);
                ApplyWindRotation(currentAngle + flutter);

                yield return null;
            }

            currentAngle = targetAngle;
        }
    }

    private float ChooseNextWindAngle()
    {
        float roll = Random.value;
        float calmThreshold = Mathf.Clamp01(
            calmWindProbability
        );

        float strongThreshold = Mathf.Clamp01(
            calmThreshold + strongWindProbability
        );

        if (roll < calmThreshold)
        {
            return Random.Range(
                Mathf.Max(0.1f, calmWindAngle * 0.45f),
                Mathf.Max(0.2f, calmWindAngle * 1.7f)
            );
        }

        if (roll < strongThreshold)
        {
            return Random.Range(
                Mathf.Max(normalWindAngle, calmWindAngle),
                Mathf.Max(strongWindAngle, normalWindAngle)
            );
        }

        return Random.Range(
            Mathf.Max(calmWindAngle, 0.2f),
            Mathf.Max(normalWindAngle, calmWindAngle + 0.1f)
        );
    }

    private float ChooseWindChangeDuration(float targetAngle)
    {
        float minimumDuration = Mathf.Max(
            minimumWindChangeDuration,
            0.1f
        );

        float maximumDuration = Mathf.Max(
            maximumWindChangeDuration,
            minimumDuration
        );

        if (targetAngle >= normalWindAngle)
        {
            return Random.Range(
                minimumDuration,
                Mathf.Lerp(minimumDuration, maximumDuration, 0.45f)
            );
        }

        return Random.Range(minimumDuration, maximumDuration);
    }

    private float GetWindFlutter(float currentAngle)
    {
        float noise = Mathf.PerlinNoise(
            windNoiseSeed,
            Time.time * Mathf.Max(flutterFrequency, 0.05f)
        );

        float normalizedNoise = (noise - 0.5f) * 2f;
        float windRate = Mathf.InverseLerp(
            calmWindAngle,
            Mathf.Max(strongWindAngle, calmWindAngle + 0.1f),
            currentAngle
        );

        return normalizedNoise *
            flutterAngle *
            Mathf.Lerp(0.35f, 1f, windRate);
    }

    private void ApplyWindRotation(float angle)
    {
        Quaternion windRotation =
            originalLocalRotation *
            Quaternion.Euler(0f, 0f, angle);

        transform.localRotation = windRotation;

        transform.localPosition =
            bottomPivotPosition -
            windRotation * bottomPivotOffset;
    }

    private IEnumerator ColorChangeEffect()
    {
        if (targetMaterial == null)
        {
            colorChangeCoroutine = null;
            yield break;
        }

        Color startColor = currentColor;
        Color nextColor = GetNextFlowerColor();
        float duration = Mathf.Max(colorChangeDuration, 0.05f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.SmoothStep(
                0f,
                1f,
                Mathf.Clamp01(elapsedTime / duration)
            );

            currentColor = Color.Lerp(
                startColor,
                nextColor,
                rate
            );

            SetMaterialColor(currentColor);
            yield return null;
        }

        currentColor = nextColor;
        SetMaterialColor(currentColor);
        colorChangeCoroutine = null;
    }

    private Color GetNextFlowerColor()
    {
        Color[] flowerColors =
        {
            new Color(1f, 0.35f, 0.55f),
            new Color(1f, 0.85f, 0.15f),
            new Color(0.65f, 0.35f, 1f),
            new Color(1f, 0.25f, 0.2f),
            new Color(0.3f, 0.75f, 1f)
        };

        int selectedColorIndex;

        do
        {
            selectedColorIndex = Random.Range(
                0,
                flowerColors.Length
            );
        }
        while (selectedColorIndex == previousColorIndex);

        previousColorIndex = selectedColorIndex;
        return flowerColors[selectedColorIndex];
    }

    private void SetMaterialColor(Color color)
    {
        if (targetMaterial == null)
        {
            return;
        }

        if (targetMaterial.HasProperty("_Color"))
        {
            targetMaterial.SetColor("_Color", color);
        }

        if (targetMaterial.HasProperty("_EmissionColor"))
        {
            targetMaterial.EnableKeyword("_EMISSION");
            targetMaterial.SetColor(
                "_EmissionColor",
                color * 0.35f
            );
        }
    }

    private void OnDisable()
    {
        if (windCoroutine != null)
        {
            StopCoroutine(windCoroutine);
            windCoroutine = null;
        }

        if (colorChangeCoroutine != null)
        {
            StopCoroutine(colorChangeCoroutine);
            colorChangeCoroutine = null;
        }

        if (hasWindPivot)
        {
            transform.localPosition = originalLocalPosition;
            transform.localRotation = originalLocalRotation;
            hasWindPivot = false;
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
