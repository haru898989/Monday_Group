using UnityEngine;

// 人をタップしたときのギミック
public class HumanGimmick1 : MonoBehaviour, GimmickBase
{
    // 人物のRenderer
    private Renderer objectRenderer;

    // Reseiverが生成した人物専用マテリアル
    private Material objectMaterial;

    // 光るかどうか
    private bool isLight = false;

    void Start()
    {
        if (objectRenderer == null)
        {
            Renderer[] childRenderers =
                GetComponentsInChildren<Renderer>(true);

            foreach (Renderer renderer in childRenderers)
            {
                if (renderer.gameObject != gameObject)
                {
                    objectRenderer = renderer;
                    break;
                }
            }

            if (objectRenderer == null)
            {
                objectRenderer = GetComponent<Renderer>();
            }
        }

        ConfigureTargetRenderer();
    }

    /// <summary>
    /// 当たり判定の子として生成した人物Rendererを登録する
    /// </summary>
    public void SetTargetRenderer(Renderer targetRenderer)
    {
        objectRenderer = targetRenderer;
        ConfigureTargetRenderer();
    }

    private void ConfigureTargetRenderer()
    {
        if (objectRenderer == null)
        {
            Debug.LogWarning(
                "人物切り抜きのRendererが設定されていません。"
            );
            return;
        }

        objectMaterial = objectRenderer.sharedMaterial;
        if (objectMaterial == null)
        {
            Debug.LogWarning(
                "人物切り抜きのMaterialが設定されていません。"
            );
            return;
        }

        // Emissionを有効化
        objectMaterial.EnableKeyword("_EMISSION");
        objectMaterial.SetColor("_EmissionColor", Color.black);
    }

    public void ActivateMagic()
    {
        Debug.Log("人が光った");

        isLight = true;
    }

    void Update()
    {
        if (isLight && objectMaterial != null)
        {
            // 虹色に変化
            float hue = Mathf.Repeat(Time.time * 0.5f, 1f);
            Color rainbow = Color.HSVToRGB(hue, 1f, 1f);

            // 発光色
            objectMaterial.SetColor(
                "_EmissionColor",
                rainbow * 3f
            );
        }
    }
}
