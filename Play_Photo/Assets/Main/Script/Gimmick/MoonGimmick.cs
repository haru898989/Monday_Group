using UnityEngine;

/// <summary>
/// 月をタッチすると、
/// ほんのり青白く光りながら
/// ゆっくり明るくなったり暗くなったりする。
///
/// もう一度タッチすると発光を停止し、
/// 元の見た目に戻る。
/// </summary>
public class MoonGimmick : MonoBehaviour, GimmickBase
{
    [Header("発光設定")]

    [SerializeField]
    private Color moonLightColor =
        new Color(
            0.72f,
            0.82f,
            0.95f,
            1f
        );

    // 一番暗いときの発光強度
    [SerializeField]
    private float minimumBrightness = 0.15f;

    // 一番明るいときの発光強度
    [SerializeField]
    private float maximumBrightness = 1.0f;

    // 明暗の変化速度
    [SerializeField]
    private float glowSpeed = 0.8f;

    // 元画像に青白い色を混ぜる割合
    // 小さいほど元の写真の色を残す
    [SerializeField]
    [Range(0f, 1f)]
    private float colorBlendAmount = 0.18f;


    private Renderer targetRenderer;
    private Material targetMaterial;

    private Color originalColor = Color.white;
    private Color originalEmissionColor = Color.black;

    private bool isGlowing;

    private float glowTimer;


    /// <summary>
    /// Reseiverから月の切り抜きRendererを受け取る。
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
                "MoonGimmickのRendererが設定されていません。"
            );

            return;
        }

        // 他の物体へ影響しないよう、
        // 月専用のMaterialを取得する
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


        RestoreOriginalVisual();
    }


    private void Update()
    {
        if (!isGlowing)
        {
            return;
        }

        if (targetMaterial == null)
        {
            return;
        }


        glowTimer +=
            Time.deltaTime
            * glowSpeed;


        /*
         * 0～1の間をゆっくり往復する。
         *
         * 明るい
         * ↓
         * 暗い
         * ↓
         * 明るい
         *
         * を繰り返す。
         */
        float wave =
            (
                Mathf.Sin(
                    glowTimer
                )
                + 1f
            )
            / 2f;


        float brightness =
            Mathf.Lerp(
                minimumBrightness,
                maximumBrightness,
                wave
            );


        SetMoonBrightness(
            brightness
        );
    }


    /// <summary>
    /// 月をタッチしたときに呼ばれる。
    /// </summary>
    public void ActivateMagic()
    {
        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren
                    <Renderer>(true)
            );
        }


        if (targetMaterial == null)
        {
            Debug.LogWarning(
                "MoonGimmickのMaterialがありません。"
            );

            return;
        }


        if (isGlowing)
        {
            TurnOff();
        }
        else
        {
            TurnOn();
        }
    }


    /// <summary>
    /// 月の発光を開始する。
    /// </summary>
    private void TurnOn()
    {
        glowTimer = 0f;

        isGlowing = true;
    }


    /// <summary>
    /// 月の発光を停止して、
    /// 元の色へ戻す。
    /// </summary>
    private void TurnOff()
    {
        isGlowing = false;

        glowTimer = 0f;

        RestoreOriginalVisual();
    }


    /// <summary>
    /// 月の明るさを変更する。
    /// 白くなりすぎないよう、
    /// 元画像の色を強く残す。
    /// </summary>
    private void SetMoonBrightness(
        float brightness
    )
    {
        if (targetMaterial == null)
        {
            return;
        }


        /*
         * 元画像の色に、
         * 青白い色をほんの少しだけ混ぜる。
         *
         * colorBlendAmountを小さくしているので、
         * 前のように真っ白になりにくい。
         */
        Color displayColor =
            Color.Lerp(
                originalColor,
                moonLightColor,
                colorBlendAmount
            );


        displayColor.a =
            originalColor.a;


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


        /*
         * 発光はかなり弱め。
         * maximumBrightnessも1.0なので
         * 白飛びしにくい。
         */
        if (targetMaterial.HasProperty(
                "_EmissionColor"
            ))
        {
            targetMaterial.EnableKeyword(
                "_EMISSION"
            );

            targetMaterial.SetColor(
                "_EmissionColor",
                moonLightColor
                * brightness
            );
        }
    }


    /// <summary>
    /// 月を元の見た目へ戻す。
    /// </summary>
    private void RestoreOriginalVisual()
    {
        if (targetMaterial == null)
        {
            return;
        }


        if (targetMaterial.HasProperty(
                "_Color"
            ))
        {
            targetMaterial.SetColor(
                "_Color",
                originalColor
            );
        }


        if (targetMaterial.HasProperty(
                "_BaseColor"
            ))
        {
            targetMaterial.SetColor(
                "_BaseColor",
                originalColor
            );
        }


        if (targetMaterial.HasProperty(
                "_EmissionColor"
            ))
        {
            targetMaterial.EnableKeyword(
                "_EMISSION"
            );

            targetMaterial.SetColor(
                "_EmissionColor",
                originalEmissionColor
            );
        }
    }


    private void OnDisable()
    {
        isGlowing = false;

        glowTimer = 0f;

        RestoreOriginalVisual();
    }


    private void OnDestroy()
    {
        if (targetMaterial != null)
        {
            RestoreOriginalVisual();

            Destroy(
                targetMaterial
            );

            targetMaterial = null;
        }
    }
}