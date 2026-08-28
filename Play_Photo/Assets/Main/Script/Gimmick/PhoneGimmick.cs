using UnityEngine;

/// <summary>
/// スマホをタッチすると、画面が光って震え続ける。
/// さらに着信音とバイブ音を同時に鳴らす。
/// もう一度タッチすると、発光・振動・音をすべて停止する。
/// </summary>
public class PhoneGimmick : MonoBehaviour, GimmickBase
{
    [Header("発光設定")]

    [SerializeField]
    private Color screenLightColor =
        new Color(
            0.35f,
            0.8f,
            1f,
            1f
        );

    [SerializeField]
    private float emissionStrength = 4f;


    [Header("振動設定")]

    [SerializeField]
    private float vibrationAmount = 0.07f;

    [SerializeField]
    private float vibrationSpeed = 24f;


    private Renderer targetRenderer;
    private Material targetMaterial;

    private Color originalColor = Color.white;
    private Color originalEmissionColor = Color.black;

    private Vector3 originalLocalPosition;

    private bool isPowerOn;

    private float vibrationTimer;


    // 着信音用
    private AudioSource phoneAudioSource;

    // バイブ音用
    private AudioSource vibrationAudioSource;


    private void Awake()
    {
        originalLocalPosition =
            transform.localPosition;
    }


    /// <summary>
    /// Reseiverから着信音とバイブ音を受け取る
    /// </summary>
    public void SetAudioClip(
        AudioClip phoneClip,
        AudioClip vibrationClip
    )
    {
        // 着信音用AudioSourceを取得または追加
        if (phoneAudioSource == null)
        {
            phoneAudioSource =
                gameObject.AddComponent<AudioSource>();
        }

        phoneAudioSource.clip = phoneClip;
        phoneAudioSource.playOnAwake = false;
        phoneAudioSource.loop = true;
        phoneAudioSource.spatialBlend = 0f;


        // バイブ音用AudioSourceを取得または追加
        if (vibrationAudioSource == null)
        {
            vibrationAudioSource =
                gameObject.AddComponent<AudioSource>();
        }

        vibrationAudioSource.clip = vibrationClip;
        vibrationAudioSource.playOnAwake = false;
        vibrationAudioSource.loop = true;
        vibrationAudioSource.spatialBlend = 0f;
    }


    private void Update()
    {
        if (!isPowerOn)
        {
            return;
        }

        vibrationTimer +=
            Time.deltaTime;

        float offsetX =
            Mathf.Sin(
                vibrationTimer
                * vibrationSpeed
            )
            * vibrationAmount;

        float offsetY =
            Mathf.Cos(
                vibrationTimer
                * vibrationSpeed
                * 1.15f
            )
            * vibrationAmount
            * 0.25f;

        transform.localPosition =
            originalLocalPosition
            + new Vector3(
                offsetX,
                offsetY,
                0f
            );
    }


    /// <summary>
    /// Reseiverからスマホの切り抜きRendererを受け取る。
    /// </summary>
    public void SetTargetRenderer(
        Renderer renderer
    )
    {
        targetRenderer =
            renderer;

        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "PhoneGimmickのRendererが設定されていません。"
            );

            return;
        }

        // このスマホ専用のMaterialを取得
        targetMaterial =
            targetRenderer.material;

        if (targetMaterial.HasProperty(
                "_Color"
            ))
        {
            originalColor =
                targetMaterial.GetColor(
                    "_Color"
                );
        }
        else if (
            targetMaterial.HasProperty(
                "_BaseColor"
            )
        )
        {
            originalColor =
                targetMaterial.GetColor(
                    "_BaseColor"
                );
        }

        if (targetMaterial.HasProperty(
                "_EmissionColor"
            ))
        {
            originalEmissionColor =
                targetMaterial.GetColor(
                    "_EmissionColor"
                );
        }

        SetLight(false);
    }


    /// <summary>
    /// スマホをタッチしたときに呼ばれる。
    /// </summary>
    public void ActivateMagic()
    {
        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }

        if (targetMaterial == null)
        {
            Debug.LogWarning(
                "PhoneGimmickのMaterialがありません。"
            );

            return;
        }

        if (isPowerOn)
        {
            TurnOff();
        }
        else
        {
            TurnOn();
        }
    }


    /// <summary>
    /// 発光・振動・音を開始する。
    /// </summary>
    private void TurnOn()
    {
        originalLocalPosition =
            transform.localPosition;

        vibrationTimer = 0f;

        SetLight(true);

        isPowerOn = true;


        // 着信音を再生
        if (phoneAudioSource != null &&
            phoneAudioSource.clip != null)
        {
            phoneAudioSource.Play();
        }


        // バイブ音を再生
        if (vibrationAudioSource != null &&
            vibrationAudioSource.clip != null)
        {
            vibrationAudioSource.Play();
        }
    }


    /// <summary>
    /// 発光・振動・音を停止する。
    /// </summary>
    private void TurnOff()
    {
        isPowerOn = false;

        vibrationTimer = 0f;

        transform.localPosition =
            originalLocalPosition;

        SetLight(false);


        // 着信音を停止
        if (phoneAudioSource != null)
        {
            phoneAudioSource.Stop();
        }


        // バイブ音を停止
        if (vibrationAudioSource != null)
        {
            vibrationAudioSource.Stop();
        }
    }


    /// <summary>
    /// 発光と通常色のON・OFFを切り替える。
    /// </summary>
    private void SetLight(
        bool shouldLight
    )
    {
        if (targetMaterial == null)
        {
            return;
        }

        Color displayColor;

        if (shouldLight)
        {
            displayColor =
                Color.Lerp(
                    originalColor,
                    screenLightColor,
                    0.85f
                );

            displayColor *= 1.4f;

            displayColor.a =
                originalColor.a;
        }
        else
        {
            displayColor =
                originalColor;
        }


        // Standard Shaderなど
        if (targetMaterial.HasProperty(
                "_Color"
            ))
        {
            targetMaterial.SetColor(
                "_Color",
                displayColor
            );
        }


        // URP Litなど
        if (targetMaterial.HasProperty(
                "_BaseColor"
            ))
        {
            targetMaterial.SetColor(
                "_BaseColor",
                displayColor
            );
        }


        // Emission対応Shader
        if (targetMaterial.HasProperty(
                "_EmissionColor"
            ))
        {
            targetMaterial.EnableKeyword(
                "_EMISSION"
            );

            targetMaterial.SetColor(
                "_EmissionColor",
                shouldLight
                    ? screenLightColor
                      * emissionStrength
                    : originalEmissionColor
            );
        }
    }


    private void OnDisable()
    {
        isPowerOn = false;

        vibrationTimer = 0f;

        transform.localPosition =
            originalLocalPosition;

        SetLight(false);


        if (phoneAudioSource != null)
        {
            phoneAudioSource.Stop();
        }

        if (vibrationAudioSource != null)
        {
            vibrationAudioSource.Stop();
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