using System.Collections;
using UnityEngine;

public class LongGimmick : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float heightMultiplier = 3f;

    [SerializeField]
    private float growDuration = 1f;

    private bool isGrowing;
    private bool hasGrown;

    public void ActivateMagic()
    {
        if (isGrowing || hasGrown)
        {
            return;
        }

        StartCoroutine(GrowUpward());
    }

    private IEnumerator GrowUpward()
    {
        isGrowing = true;

        Vector3 startScale = transform.localScale;
        Vector3 startPosition = transform.position;

        Vector3 targetScale = new Vector3(
            startScale.x,
            startScale.y * heightMultiplier,
            startScale.z
        );

        float addedHeight =
            targetScale.y - startScale.y;

        Vector3 targetPosition =
            startPosition + new Vector3(
                0f,
                addedHeight / 2f,
                0f
            );

        float elapsedTime = 0f;

        while (elapsedTime < growDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate = Mathf.Clamp01(
                elapsedTime / growDuration
            );

            transform.localScale = Vector3.Lerp(
                startScale,
                targetScale,
                rate
            );

            transform.position = Vector3.Lerp(
                startPosition,
                targetPosition,
                rate
            );

            yield return null;
        }

        transform.localScale = targetScale;
        transform.position = targetPosition;

        isGrowing = false;
        hasGrown = true;

        Debug.Log("Cube‚ªã•ûŒü‚ÉL‚Ñ‚Ü‚µ‚½B");
    }
}