using UnityEngine;

// 人をタップしたときのギミック
public class HumanGimmick1 : MonoBehaviour, GimmickBase
{
    // 人物のRenderer
    private Renderer objectRenderer;

    // 光るかどうか
    private bool isLight = false;

    void Start()
    {
        // Rendererを取得
        objectRenderer = GetComponent<Renderer>();

        // Emissionを有効化
        objectRenderer.material.EnableKeyword("_EMISSION");
    }

    public void ActivateMagic()
    {
        Debug.Log("人が光った");

        isLight = true;
    }

    void Update()
    {
        if (isLight)
        {
            // 虹色に変化
            float hue = Mathf.Repeat(Time.time * 0.5f, 1f);
            Color rainbow = Color.HSVToRGB(hue, 1f, 1f);

            // 発光色
            objectRenderer.material.SetColor("_EmissionColor", rainbow * 3f);
        }
    }
}