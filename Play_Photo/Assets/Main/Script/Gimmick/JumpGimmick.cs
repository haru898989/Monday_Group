using System.Collections;
using UnityEngine;

// タッチすると上に跳ねるギミック
public class JumpGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float jumpHeight = 1.5f;

    [SerializeField]
    private float jumpTime = 0.6f;

    private bool isJumping = false;

    public void ActivateMagic()
    {
        if (!isJumping)
        {
            StartCoroutine(Jump());
        }
    }

    private IEnumerator Jump()
    {
        isJumping = true;

        Vector3 startPosition = transform.position;
        float elapsedTime = 0f;

        while (elapsedTime < jumpTime)
        {
            float progress = elapsedTime / jumpTime;

            float height =
                Mathf.Sin(progress * Mathf.PI) * jumpHeight;

            transform.position =
                startPosition + Vector3.up * height;

            elapsedTime += Time.deltaTime;
            yield return null;
        }

        transform.position = startPosition;

        Debug.Log("オブジェクトがジャンプしました");
        isJumping = false;
    }
}