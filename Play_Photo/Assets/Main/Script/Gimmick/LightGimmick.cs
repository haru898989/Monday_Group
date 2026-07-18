using System.Collections;
using UnityEngine;

// ライトをタップしたときのギミック
public class LightGimmick : MonoBehaviour, GimmickBase
{
    // ライトのRenderer
    private Renderer objectRenderer;

    // ライトが点灯しているかどうか
    private bool isOn = true;

    // ゲーム開始時に呼ばれる
    void Start()
    {
        // Rendererを取得
        objectRenderer = GetComponent<Renderer>();
    }

    // タップされたときに呼ばれる
    public void ActivateMagic()
    {
        StartCoroutine(BlinkLight());
    }

    // ライトを0.5秒点滅させる
    IEnumerator BlinkLight()
    {
        // 約0.5秒点滅（0.1秒×5回）
        for (int i = 0; i < 5; i++)
        {
            objectRenderer.enabled = !objectRenderer.enabled;
            yield return new WaitForSeconds(0.1f);
        }

        // 最終的な点灯・消灯状態を切り替える
        isOn = !isOn;
        objectRenderer.enabled = isOn;

        if (isOn)
        {
            Debug.Log("ライト点灯");
        }
        else
        {
            Debug.Log("ライト消灯");
        }
    }
}