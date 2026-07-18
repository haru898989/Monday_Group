using System.Collections;
using UnityEngine;

// ライトをタッチしたときのギミック
public class LightGimmick2 : MonoBehaviour, GimmickBase
{
    // 写真を表示しているQuadやPlaneのRenderer
    [SerializeField]
    private Renderer photoRenderer;

    // ライトの見た目を表示しているRenderer
    [SerializeField]
    private Renderer lightRenderer;

    // 暗くしたときの明るさ
    // 0に近いほど暗く、1に近いほど明るい
    [SerializeField]
    [Range(0.0f, 1.0f)]
    private float darkLevel = 0.3f;

    // 現在ライトが点灯しているか
    private bool isLightOn = true;

    // ギミックが実行中か
    private bool isRunning = false;

    // 写真のマテリアル
    private Material photoMaterial;

    // 写真の最初の色
    private Color originalPhotoColor;

    // ライトの最初の色
    private Color originalLightColor;

    private void Start()
    {
        // ライトのRendererが設定されていない場合は、
        // 同じオブジェクトからRendererを取得する
        if (lightRenderer == null)
        {
            lightRenderer = GetComponent<Renderer>();
        }

        // 写真のRendererが設定されている場合
        if (photoRenderer != null)
        {
            // 写真のマテリアルを取得する
            photoMaterial = photoRenderer.material;

            // 最初の明るさを保存する
            originalPhotoColor = photoMaterial.color;
        }
        else
        {
            Debug.LogError(
                "LightGimmickのPhoto Rendererが設定されていません。"
            );
        }

        // ライトの最初の色を保存する
        if (lightRenderer != null)
        {
            originalLightColor = lightRenderer.material.color;
        }
    }

    // ライトがタッチされたときに呼び出される
    public void ActivateMagic()
    {
        // 実行中でなければギミックを開始する
        if (!isRunning)
        {
            StartCoroutine(BlinkAndToggle());
        }
    }

    // 点滅させた後、写真の明るさを切り替える
    private IEnumerator BlinkAndToggle()
    {
        isRunning = true;

        // 約0.5秒間ライトを点滅させる
        if (lightRenderer != null)
        {
            for (int i = 0; i < 5; i++)
            {
                // 黄色と元の色を交互に表示する
                if (i % 2 == 0)
                {
                    lightRenderer.material.color = Color.yellow;
                }
                else
                {
                    lightRenderer.material.color = originalLightColor;
                }

                yield return new WaitForSeconds(0.1f);
            }

            // 点滅後に元の色へ戻す
            lightRenderer.material.color = originalLightColor;
        }

        // 点灯状態を反転する
        isLightOn = !isLightOn;

        if (photoMaterial != null)
        {
            if (isLightOn)
            {
                // 写真を元の明るさに戻す
                photoMaterial.color = originalPhotoColor;

                Debug.Log("ライト点灯：写真を明るくしました");
            }
            else
            {
                // 写真全体を暗くする
                photoMaterial.color = new Color(
                    originalPhotoColor.r * darkLevel,
                    originalPhotoColor.g * darkLevel,
                    originalPhotoColor.b * darkLevel,
                    originalPhotoColor.a
                );

                Debug.Log("ライト消灯：写真を暗くしました");
            }
        }

        isRunning = false;
    }
}