using System.Collections;
using UnityEngine;

/// <summary>
/// 壁をタッチすると、壁の切り抜き画像だけが左右にガタッと揺れる。
/// 背景や当たり判定は動かさない。
/// </summary>
public class WallGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float shakeDistance = 0.08f;

    [SerializeField]
    private float shakeDuration = 0.35f;

    [SerializeField]
    private float shakeSpeed = 30f;

    private Renderer targetRenderer;
    private Transform targetVisual;

    private bool isShaking;

    /// <summary>
    /// Reseiverから壁の切り抜きRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        if (targetRenderer != null)
        {
            targetVisual = targetRenderer.transform;
        }
    }

    public void ActivateMagic()
    {
        if (isShaking)
        {
            return;
        }

        if (targetVisual == null)
        {
            Debug.LogWarning(
                "壁の切り抜き画像が設定されていません。"
            );
            return;
        }

        StartCoroutine(ShakeWall());
    }

    private IEnumerator ShakeWall()
    {
        isShaking = true;

        Vector3 startPosition =
            targetVisual.localPosition;

        float elapsedTime = 0f;

        while (elapsedTime < shakeDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / shakeDuration
                );

            // 徐々に揺れを弱くする
            float strength = 1f - rate;

            float offsetX =
                Mathf.Sin(
                    elapsedTime * shakeSpeed
                )
                * shakeDistance
                * strength;

            targetVisual.localPosition =
                startPosition +
                new Vector3(
                    offsetX,
                    0f,
                    0f
                );

            yield return null;
        }

        // 最後は必ず元の位置へ戻す
        targetVisual.localPosition =
            startPosition;

        isShaking = false;

        Debug.Log("壁がガタッと揺れました。");
    }
}