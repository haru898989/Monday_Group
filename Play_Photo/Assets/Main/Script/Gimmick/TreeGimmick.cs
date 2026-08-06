using System.Collections;
using UnityEngine;

/// <summary>
/// 木をタッチすると、木の切り抜き画像だけが上方向へ伸びる。
/// 背景写真と親の当たり判定は動かさない。
/// </summary>
public class TreeGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float growMultiplier = 1.5f;

    [SerializeField]
    private float growDuration = 1.5f;

    private Renderer targetRenderer;
    private Transform targetVisual;

    private bool isGrowing;
    private bool hasGrown;

    /// <summary>
    /// Reseiverから木の切り抜きRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        if (targetRenderer != null)
        {
            targetVisual = targetRenderer.transform;
        }
    }

    /// <summary>
    /// 木をタップしたときに呼ばれる
    /// </summary>
    public void ActivateMagic()
    {
        if (isGrowing || hasGrown)
        {
            return;
        }

        if (targetVisual == null)
        {
            FindTargetVisual();
        }

        if (targetVisual == null)
        {
            Debug.LogWarning(
                "伸ばす木の切り抜き画像が見つかりません。"
            );
            return;
        }

        StartCoroutine(GrowTree());
    }

    /// <summary>
    /// Cutout_treeなどの子画像を探す
    /// </summary>
    private void FindTargetVisual()
    {
        Renderer[] renderers =
            GetComponentsInChildren<Renderer>(true);

        foreach (Renderer renderer in renderers)
        {
            // 親の当たり判定用Rendererは除外
            if (renderer.gameObject == gameObject)
            {
                continue;
            }

            if (renderer.gameObject.name.StartsWith("Cutout_"))
            {
                targetRenderer = renderer;
                targetVisual = renderer.transform;
                return;
            }
        }
    }

    /// <summary>
    /// 木の切り抜き画像だけを縦方向へ伸ばす
    /// </summary>
    private IEnumerator GrowTree()
    {
        isGrowing = true;

        Vector3 startScale =
            targetVisual.localScale;

        Vector3 targetScale =
            new Vector3(
                startScale.x,
                startScale.y * growMultiplier,
                startScale.z
            );

        Vector3 startPosition =
            targetVisual.localPosition;

        /*
         * 縦に伸びた分だけ上へ移動させ、
         * 木の根元がなるべく同じ位置に残るようにする。
         */
        float addedScale =
            targetScale.y - startScale.y;

        Vector3 targetPosition =
            startPosition +
            new Vector3(
                0f,
                addedScale / 2f,
                0f
            );

        float elapsedTime = 0f;

        while (elapsedTime < growDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / growDuration
                );

            float smoothRate =
                Mathf.SmoothStep(0f, 1f, rate);

            targetVisual.localScale =
                Vector3.Lerp(
                    startScale,
                    targetScale,
                    smoothRate
                );

            targetVisual.localPosition =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    smoothRate
                );

            yield return null;
        }

        targetVisual.localScale = targetScale;
        targetVisual.localPosition = targetPosition;

        isGrowing = false;
        hasGrown = true;

        Debug.Log("木の切り抜き画像だけが伸びました。");
    }
}