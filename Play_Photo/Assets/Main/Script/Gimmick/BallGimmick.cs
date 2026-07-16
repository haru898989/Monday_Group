using System.Collections;
using UnityEngine;

public class BallGimmick : MonoBehaviour, GimmickBase
{
    private bool isMoving;

    public void ActivateMagic()
    {
        if (!isMoving)
        {
            StartCoroutine(Jump());
        }
    }

    private IEnumerator Jump()
    {
        isMoving = true;

        Vector3 startPosition = transform.position;
        Vector3 topPosition = startPosition + Vector3.up * 1.5f;

        float time = 0f;

        while (time < 0.3f)
        {
            transform.position =
                Vector3.Lerp(startPosition, topPosition, time / 0.3f);

            time += Time.deltaTime;
            yield return null;
        }

        time = 0f;

        while (time < 0.3f)
        {
            transform.position =
                Vector3.Lerp(topPosition, startPosition, time / 0.3f);

            time += Time.deltaTime;
            yield return null;
        }

        transform.position = startPosition;
        isMoving = false;
    }
}