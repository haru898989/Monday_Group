using System.Collections;
using UnityEngine;

// 植物をタッチすると大きくなるギミック
public class PlantGimmick : MonoBehaviour, GimmickBase
{
    // 成長後の大きさ
    [SerializeField]
    private float growthScale = 1.5f;

    // 成長にかける時間
    [SerializeField]
    private float growthTime = 1.0f;

    // 成長中かどうか
    private bool isGrowing = false;

    // 最初の大きさ
    private Vector3 startScale;

    void Start()
    {
        startScale = transform.localScale;
    }

    // タッチされたときに呼ばれる
    public void ActivateMagic()
    {
        if (!isGrowing)
        {
            StartCoroutine(GrowPlant());
        }
    }

    // 少しずつ大きくする処理
    private IEnumerator GrowPlant()
    {
        isGrowing = true;

        Vector3 targetScale = startScale * growthScale;
        float elapsedTime = 0f;

        while (elapsedTime < growthTime)
        {
            transform.localScale = Vector3.Lerp(
                startScale,
                targetScale,
                elapsedTime / growthTime
            );

            elapsedTime += Time.deltaTime;
            yield return null;
        }

        transform.localScale = targetScale;

        Debug.Log("植物が成長しました");
        isGrowing = false;
    }
}