using System.Collections;
using UnityEngine;

/// <summary>
/// 魚をタップすると左右にピチピチ揺れるギミック
/// </summary>
public class FishGlowGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float shakeTime = 1f;

    [SerializeField]
    private float shakeAngle = 15f;

    [SerializeField]
    private float shakeSpeed = 20f;

    private bool isActivated;
    private Quaternion originalRotation;

    // Reseiver.csから呼ばれるため残している
    public void SetTargetRenderer(Renderer renderer)
    {
    }

    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;
        originalRotation = transform.localRotation;

        StartCoroutine(ShakeFish());
    }

    private IEnumerator ShakeFish()
    {
        float elapsedTime = 0f;

        while (elapsedTime < shakeTime)
        {
            elapsedTime += Time.deltaTime;

            float angle = Mathf.Sin(elapsedTime * shakeSpeed) * shakeAngle;

            transform.localRotation =
                originalRotation * Quaternion.Euler(0f, 0f, angle);

            yield return null;
        }

        transform.localRotation = originalRotation;
        isActivated = false;
    }
}