using System.Collections;
using UnityEngine;

// タッチすると震えるギミック
public class ShakeGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float shakeTime = 0.5f;

    [SerializeField]
    private float shakePower = 0.1f;

    private bool isShaking = false;

    public void ActivateMagic()
    {
        if (!isShaking)
        {
            StartCoroutine(Shake());
        }
    }

    private IEnumerator Shake()
    {
        isShaking = true;

        Vector3 startPosition = transform.localPosition;
        float elapsedTime = 0f;

        while (elapsedTime < shakeTime)
        {
            float x = Random.Range(-shakePower, shakePower);
            float y = Random.Range(-shakePower, shakePower);

            transform.localPosition =
                startPosition + new Vector3(x, y, 0f);

            elapsedTime += Time.deltaTime;
            yield return null;
        }

        transform.localPosition = startPosition;

        Debug.Log("オブジェクトが震えました");
        isShaking = false;
    }
}