using System.Collections;
using UnityEngine;

/// <summary>
/// 花をタッチすると、次の2種類からランダムで1つ発動する。
/// 1. ゆっくり左右に揺れる
/// 2. 色が変わり、次の色変更までその色を維持する
///
/// 同じ演出は連続しない。
/// </summary>
public class FlowerGimmick : MonoBehaviour, GimmickBase
{
    [Header("揺れる演出")]

    // 揺れる時間
    [SerializeField]
    private float swayDuration = 2.2f;

    // 最大の傾き
    [SerializeField]
    private float swayAngle = 8f;

    // 揺れる回数
    [SerializeField]
    private float swayCount = 1.5f;


    [Header("色変更演出")]

    // 色が切り替わるまでの時間
    [SerializeField]
    private float colorChangeDuration = 0.7f;


    private Renderer targetRenderer;
    private Material targetMaterial;

    private Color currentColor = Color.white;

    private bool isAnimating;

    // 同じ演出が連続しないように記録
    // 0：揺れる
    // 1：色が変わる
    private int previousEffect = -1;

    // 同じ色が続かないように記録
    private int previousColorIndex = -1;


    /// <summary>
    /// Reseiverから、写真の切り抜きRendererを設定する。
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        if (targetRenderer == null)
        {
            return;
        }

        // 他のオブジェクトのMaterialへ影響しないよう、
        // この花専用のMaterialを取得する
        targetMaterial = targetRenderer.material;

        if (targetMaterial.HasProperty("_Color"))
        {
            currentColor =
                targetMaterial.GetColor("_Color");
        }
    }


    /// <summary>
    /// 花をクリックしたときに呼ばれる。
    /// </summary>
    public void ActivateMagic()
    {
        // 演出中の連打は受け付けない
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

        int selectedEffect;

        do
        {
            selectedEffect =
                Random.Range(0, 2);
        }
        while (selectedEffect == previousEffect);

        previousEffect = selectedEffect;

        switch (selectedEffect)
        {
            // ゆっくり揺れる
            case 0:
                StartCoroutine(SwayEffect());
                break;

            // 色が変わる
            case 1:
                StartCoroutine(ColorChangeEffect());
                break;
        }
    }


    /// <summary>
    /// 花をゆっくり左右に揺らす。
    /// </summary>
    private IEnumerator SwayEffect()
    {
        isAnimating = true;

        Quaternion startRotation =
            transform.localRotation;

        float elapsedTime = 0f;

        while (elapsedTime < swayDuration)
        {
            elapsedTime += Time.deltaTime;

            float progress =
                Mathf.Clamp01(
                    elapsedTime / swayDuration
                );

            /*
             * swayCount回分だけ、ゆっくり左右へ往復する。
             *
             * SmoothStepを使って開始と終了を滑らかにし、
             * 最後は自然に元の角度へ戻す。
             */
            float smoothProgress =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    progress
                );

            float fadeOut =
                Mathf.Sin(
                    progress * Mathf.PI
                );

            float angle =
                Mathf.Sin(
                    smoothProgress
                    * swayCount
                    * Mathf.PI
                    * 2f
                )
                * swayAngle
                * fadeOut;

            transform.localRotation =
                startRotation
                * Quaternion.Euler(
                    0f,
                    0f,
                    angle
                );

            yield return null;
        }

        transform.localRotation =
            startRotation;

        isAnimating = false;
    }


    /// <summary>
    /// 花の色を徐々に変更する。
    /// 変更後は、次に色変更が選ばれるまでその色を維持する。
    /// </summary>
    private IEnumerator ColorChangeEffect()
    {
        isAnimating = true;

        if (targetMaterial == null)
        {
            isAnimating = false;
            yield break;
        }

        Color nextColor =
            GetNextFlowerColor();

        Color startColor =
            currentColor;

        float elapsedTime = 0f;

        while (elapsedTime < colorChangeDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / colorChangeDuration
                );

            // 色の変化を滑らかにする
            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );

            Color changingColor =
                Color.Lerp(
                    startColor,
                    nextColor,
                    smoothRate
                );

            SetMaterialColor(
                changingColor
            );

            yield return null;
        }

        // 変更後の色を保存し、元には戻さない
        currentColor =
            nextColor;

        SetMaterialColor(
            currentColor
        );

        isAnimating = false;
    }


    /// <summary>
    /// 前回とは異なる花の色を返す。
    /// </summary>
    private Color GetNextFlowerColor()
    {
        Color[] flowerColors =
        {
            new Color(1f, 0.35f, 0.55f),  // ピンク
            new Color(1f, 0.85f, 0.15f),  // 黄色
            new Color(0.65f, 0.35f, 1f),  // 紫
            new Color(1f, 0.25f, 0.2f),   // 赤
            new Color(0.3f, 0.75f, 1f)    // 水色
        };

        int selectedColorIndex;

        do
        {
            selectedColorIndex =
                Random.Range(
                    0,
                    flowerColors.Length
                );
        }
        while (
            selectedColorIndex ==
            previousColorIndex
        );

        previousColorIndex =
            selectedColorIndex;

        return flowerColors[
            selectedColorIndex
        ];
    }


    /// <summary>
    /// Materialの通常色と発光色を設定する。
    /// </summary>
    private void SetMaterialColor(Color color)
    {
        if (targetMaterial == null)
        {
            return;
        }

        if (targetMaterial.HasProperty("_Color"))
        {
            targetMaterial.SetColor(
                "_Color",
                color
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
                color * 0.35f
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