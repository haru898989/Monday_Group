using System.Collections;
using UnityEngine;

/// <summary>
/// 飛行機をタッチすると真上へ飛ぶ
/// </summary>
public class AirplaneGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float flyHeight = 5f;

    [SerializeField]
    private float flyDuration = 2f;

    private bool isFlying;

    public void ActivateMagic()
    {
        if (isFlying)
        {
            return;
        }

        StartCoroutine(FlyUp());
    }

    private IEnumerator FlyUp()
    {
        isFlying = true;

        Vector3 startPosition = transform.position;
        Vector3 targetPosition = startPosition + Vector3.up * flyHeight;

        float elapsedTime = 0f;

        while (elapsedTime < flyDuration)
        {
            elapsedTime += Time.deltaTime;

            float t = Mathf.SmoothStep(
                0f,
                1f,
                elapsedTime / flyDuration
            );

            transform.position =
                Vector3.Lerp(
                    startPosition,
                    targetPosition,
                    t
                );

            yield return null;
        }

        transform.position = targetPosition;

        isFlying = false;
    }
}