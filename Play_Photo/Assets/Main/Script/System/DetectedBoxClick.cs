using System.Collections;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class DetectedBoxClick :
    MonoBehaviour,
    IPointerClickHandler
{
    // ========================================
    // 検出された物体の情報
    // ========================================

    private string detectedObjectName;
    private string detectedObjectId;
    private float confidence;


    // ========================================
    // 写真上の演出に使用
    // ========================================

    private Image boxImage;
    private Color originalColor;
    private Coroutine activeEffect;


    // ========================================
    // Prefabギミックの実行に使用
    // ========================================

    private Reseiver receiver;


    // ========================================
    // AnalysisPhotoViewerから情報を受け取る
    // ========================================

    public void Initialize(
        string objectName,
        string objectId,
        float objectConfidence
    )
    {
        detectedObjectName =
            objectName;

        detectedObjectId =
            objectId;

        confidence =
            objectConfidence;

        boxImage =
            GetComponent<Image>();

        if (boxImage != null)
        {
            // 枠非表示時は透明色が保存される
            originalColor =
                boxImage.color;

            // 透明でもクリックできるようにする
            boxImage.raycastTarget =
                true;
        }

        // Scene内のReseiverを探す
        receiver =
            FindObjectOfType<Reseiver>();
    }


    // ========================================
    // 写真上の物体が押されたとき
    // ========================================

    public void OnPointerClick(
        PointerEventData eventData
    )
    {
        Debug.Log(
            detectedObjectName +
            "をタッチしました！" +
            " ID=" +
            detectedObjectId +
            " 信頼度=" +
            confidence.ToString("F2")
        );

/*
        // ========================================
        // 登録済みPrefabのギミックを実行
        // ========================================

        if (receiver == null)
        {
            receiver =
                FindObjectOfType<Reseiver>();
        }

        if (receiver != null)
        {
            receiver.ActivateGimmickFromUI(
                detectedObjectId,
                detectedObjectName
            );
        }
        else
        {
            Debug.LogError(
                "Scene内にReseiverが見つかりません。"
            );
        }
*/

        // ========================================
        // 前の写真上の演出を停止
        // ========================================

        if (activeEffect != null)
        {
            StopCoroutine(
                activeEffect
            );

            activeEffect =
                null;

            if (boxImage != null)
            {
                boxImage.color =
                    originalColor;
            }
        }

        if (boxImage == null)
        {
            Debug.LogWarning(
                detectedObjectName +
                "のクリック範囲にImageがありません。"
            );

            return;
        }


        // ========================================
        // 物体名ごとに写真上の演出を変更
        // ========================================

        string objectName =
            string.IsNullOrWhiteSpace(
                detectedObjectName
            )
                ? ""
                : detectedObjectName
                    .Trim()
                    .ToLowerInvariant();

        switch (objectName)
        {
            case "human":
            case "person":
            case "hand":

                activeEffect =
                    StartCoroutine(
                        RainbowEffect()
                    );

                break;


            case "lamp":
            case "light":

                activeEffect =
                    StartCoroutine(
                        LampEffect()
                    );

                break;


            case "television":
            case "tv":
            case "monitor":

                activeEffect =
                    StartCoroutine(
                        TelevisionEffect()
                    );

                break;


            default:

                activeEffect =
                    StartCoroutine(
                        DefaultEffect()
                    );

                break;
        }
    }


    // ========================================
    // 人を虹色に光らせる
    // ========================================

    private IEnumerator RainbowEffect()
    {
        float duration =
            2f;

        float elapsedTime =
            0f;

        while (elapsedTime < duration)
        {
            elapsedTime +=
                Time.deltaTime;

            float hue =
                Mathf.Repeat(
                    elapsedTime * 0.8f,
                    1f
                );

            Color rainbowColor =
                Color.HSVToRGB(
                    hue,
                    1f,
                    1f
                );

            // 写真が見える程度に半透明
            rainbowColor.a =
                0.45f;

            boxImage.color =
                rainbowColor;

            yield return null;
        }

        RestoreOriginalColor();
    }


    // ========================================
    // ライトを白・黄色に点滅させる
    // ========================================

    private IEnumerator LampEffect()
    {
        for (int i = 0; i < 4; i++)
        {
            // 白く光る
            boxImage.color =
                new Color(
                    1f,
                    1f,
                    1f,
                    0.75f
                );

            yield return
                new WaitForSeconds(
                    0.15f
                );

            // 黄色く光る
            boxImage.color =
                new Color(
                    1f,
                    0.9f,
                    0.1f,
                    0.45f
                );

            yield return
                new WaitForSeconds(
                    0.15f
                );
        }

        RestoreOriginalColor();
    }


    // ========================================
    // テレビを青く点滅させる
    // ========================================

    private IEnumerator TelevisionEffect()
    {
        for (int i = 0; i < 3; i++)
        {
            boxImage.color =
                new Color(
                    0f,
                    0.8f,
                    1f,
                    0.65f
                );

            yield return
                new WaitForSeconds(
                    0.2f
                );

            boxImage.color =
                new Color(
                    0f,
                    0.2f,
                    1f,
                    0.25f
                );

            yield return
                new WaitForSeconds(
                    0.2f
                );
        }

        RestoreOriginalColor();
    }


    // ========================================
    // その他の物体を黄色く光らせる
    // ========================================

    private IEnumerator DefaultEffect()
    {
        boxImage.color =
            new Color(
                1f,
                1f,
                0f,
                0.55f
            );

        yield return
            new WaitForSeconds(
                0.5f
            );

        RestoreOriginalColor();
    }


    // ========================================
    // 元の透明色へ戻す
    // ========================================

    private void RestoreOriginalColor()
    {
        if (boxImage != null)
        {
            boxImage.color =
                originalColor;
        }

        activeEffect =
            null;
    }


    // ========================================
    // 無効化されたときの後処理
    // ========================================

    private void OnDisable()
    {
        if (activeEffect != null)
        {
            StopCoroutine(
                activeEffect
            );

            activeEffect =
                null;
        }

        if (boxImage != null)
        {
            boxImage.color =
                originalColor;
        }
    }
}