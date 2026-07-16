using UnityEngine;

// タッチするたびにランダムな色に変わるギミック
public class ColorChangeGimmick : MonoBehaviour, GimmickBase
{
    private Renderer objectRenderer;

    void Start()
    {
        objectRenderer = GetComponent<Renderer>();
    }

    public void ActivateMagic()
    {
        if (objectRenderer == null)
        {
            Debug.LogError("Rendererが見つかりません");
            return;
        }

        Color randomColor = new Color(
            Random.value,
            Random.value,
            Random.value
        );

        objectRenderer.material.color = randomColor;

        Debug.Log("色が変わりました");
    }
}