using System.Collections;
using UnityEngine;

/// <summary>
/// 橋をタッチすると、左右に折れたように動き、破壊音が鳴る
/// </summary>
public class BridgeGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float breakAngle = 25f;

    [SerializeField]
    private float dropDistance = 0.4f;

    [SerializeField]
    private float breakDuration = 0.8f;

    private Renderer targetRenderer;

    private Transform leftPart;
    private Transform rightPart;

    private bool isBroken;

    // ★追加：橋の破壊音用
    private AudioSource audioSource;


    /// <summary>
    /// Reseiverから橋の切り抜きRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// Reseiverから橋の効果音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();

            if (audioSource == null)
            {
                audioSource =
                    gameObject.AddComponent<AudioSource>();
            }
        }

        audioSource.clip = clip;
        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
    }


    public void ActivateMagic()
    {
        if (isBroken)
        {
            return;
        }

        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "橋の切り抜き画像が設定されていません。"
            );

            return;
        }

        CreateBridgeParts();

        if (leftPart == null || rightPart == null)
        {
            return;
        }

        isBroken = true;


        // ★追加：橋の破壊音を再生
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.Play();
        }


        StartCoroutine(BreakBridge());
    }


    /// <summary>
    /// 元の橋画像を複製して左右パーツを作る
    /// </summary>
    private void CreateBridgeParts()
    {
        GameObject original =
            targetRenderer.gameObject;

        // 左側
        GameObject leftObject =
            Instantiate(
                original,
                original.transform.position,
                original.transform.rotation,
                transform
            );

        leftObject.name = "Bridge_Left";


        // 右側
        GameObject rightObject =
            Instantiate(
                original,
                original.transform.position,
                original.transform.rotation,
                transform
            );

        rightObject.name = "Bridge_Right";


        leftPart = leftObject.transform;
        rightPart = rightObject.transform;


        // 少し左右へずらす
        leftPart.localPosition +=
            new Vector3(
                -0.25f,
                0f,
                -0.001f
            );

        rightPart.localPosition +=
            new Vector3(
                0.25f,
                0f,
                -0.002f
            );


        // 元の橋画像を消す
        targetRenderer.enabled = false;
    }


    /// <summary>
    /// 左右へ折れて落ちる
    /// </summary>
    private IEnumerator BreakBridge()
    {
        Quaternion leftStartRotation =
            leftPart.localRotation;

        Quaternion rightStartRotation =
            rightPart.localRotation;


        Vector3 leftStartPosition =
            leftPart.localPosition;

        Vector3 rightStartPosition =
            rightPart.localPosition;


        Quaternion leftTargetRotation =
            leftStartRotation *
            Quaternion.Euler(
                0f,
                0f,
                breakAngle
            );

        Quaternion rightTargetRotation =
            rightStartRotation *
            Quaternion.Euler(
                0f,
                0f,
                -breakAngle
            );


        Vector3 leftTargetPosition =
            leftStartPosition +
            Vector3.down * dropDistance;

        Vector3 rightTargetPosition =
            rightStartPosition +
            Vector3.down * dropDistance;


        float elapsedTime = 0f;


        while (elapsedTime < breakDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / breakDuration
                );

            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            leftPart.localRotation =
                Quaternion.Lerp(
                    leftStartRotation,
                    leftTargetRotation,
                    smoothRate
                );

            rightPart.localRotation =
                Quaternion.Lerp(
                    rightStartRotation,
                    rightTargetRotation,
                    smoothRate
                );


            leftPart.localPosition =
                Vector3.Lerp(
                    leftStartPosition,
                    leftTargetPosition,
                    smoothRate
                );

            rightPart.localPosition =
                Vector3.Lerp(
                    rightStartPosition,
                    rightTargetPosition,
                    smoothRate
                );


            yield return null;
        }


        // 最終位置を確実に設定
        leftPart.localRotation =
            leftTargetRotation;

        rightPart.localRotation =
            rightTargetRotation;

        leftPart.localPosition =
            leftTargetPosition;

        rightPart.localPosition =
            rightTargetPosition;


        Debug.Log("橋が折れました。");
    }
}