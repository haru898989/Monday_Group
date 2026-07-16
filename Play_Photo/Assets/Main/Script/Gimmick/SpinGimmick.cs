using System.Collections;
using UnityEngine;

// タッチすると1回転するギミック
public class SpinGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float spinTime = 1.0f;

    private bool isSpinning = false;

    public void ActivateMagic()
    {
        if (!isSpinning)
        {
            StartCoroutine(Spin());
        }
    }

    private IEnumerator Spin()
    {
        isSpinning = true;

        Quaternion startRotation = transform.rotation;
        float elapsedTime = 0f;

        while (elapsedTime < spinTime)
        {
            float angle = 360f * elapsedTime / spinTime;

            transform.rotation =
                startRotation * Quaternion.Euler(0f, angle, 0f);

            elapsedTime += Time.deltaTime;
            yield return null;
        }

        transform.rotation = startRotation;

        Debug.Log("オブジェクトが回転しました");
        isSpinning = false;
    }
}