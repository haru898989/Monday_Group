using System.Collections;
using UnityEngine;

public class ClockGimmick : MonoBehaviour, GimmickBase
{
    [Header("j‚Ì‰æ‘œ")]
    [SerializeField]
    private Sprite minuteHandSprite;

    [SerializeField]
    private Sprite hourHandSprite;

    [Header("j‚ÌˆÊ’u")]
    [SerializeField]
    private Vector3 handCenterOffset =
        new Vector3(0f, 0f, -0.01f);

    [Header("j‚Ì‘å‚«‚³")]
    [SerializeField]
    private Vector3 minuteHandScale =
        new Vector3(0.15f, 0.6f, 1f);

    [SerializeField]
    private Vector3 hourHandScale =
        new Vector3(0.18f, 0.4f, 1f);

    [Header("‰ñ“]İ’è")]
    [SerializeField]
    private float rotateDuration = 2f;

    [SerializeField]
    private float minuteHandRotations = 3f;

    [SerializeField]
    private float hourHandRotations = 0.25f;

    private Transform minuteHandPivot;
    private Transform hourHandPivot;
    private bool isRotating;

    private void Start()
    {
        CreateClockHands();
    }

    /// <summary>
    /// Œv‰æ‘œ‚Ìã‚É’·j‚Æ’Zj‚ğì¬‚·‚é
    /// </summary>
    private void CreateClockHands()
    {
        if (minuteHandSprite == null)
        {
            Debug.LogWarning(
                "’·j‚ÌSprite‚ªİ’è‚³‚ê‚Ä‚¢‚Ü‚¹‚ñB"
            );
        }

        if (hourHandSprite == null)
        {
            Debug.LogWarning(
                "’Zj‚ÌSprite‚ªİ’è‚³‚ê‚Ä‚¢‚Ü‚¹‚ñB"
            );
        }

        minuteHandPivot =
            CreateHand(
                "MinuteHandPivot",
                "MinuteHand",
                minuteHandSprite,
                minuteHandScale,
                -0.01f
            );

        hourHandPivot =
            CreateHand(
                "HourHandPivot",
                "HourHand",
                hourHandSprite,
                hourHandScale,
                -0.02f
            );
    }

    /// <summary>
    /// j‚Ì‰ñ“]’†S‚Æ‰æ‘œ‚ğì¬‚·‚é
    /// </summary>
    private Transform CreateHand(
        string pivotName,
        string handName,
        Sprite handSprite,
        Vector3 handScale,
        float zOffset
    )
    {
        GameObject pivotObject =
            new GameObject(pivotName);

        pivotObject.transform.SetParent(
            transform,
            false
        );

        pivotObject.transform.localPosition =
            handCenterOffset +
            new Vector3(0f, 0f, zOffset);

        GameObject handObject =
            new GameObject(handName);

        handObject.transform.SetParent(
            pivotObject.transform,
            false
        );

        SpriteRenderer spriteRenderer =
            handObject.AddComponent<SpriteRenderer>();

        spriteRenderer.sprite = handSprite;
        spriteRenderer.sortingOrder = 200;

        // j‚ÌªŒ³‚ª‰ñ“]’†S‚É‚È‚é‚æ‚¤‚Éã‚Ö‚¸‚ç‚·
        handObject.transform.localPosition =
            new Vector3(
                0f,
                handScale.y / 2f,
                0f
            );

        handObject.transform.localScale =
            handScale;

        return pivotObject.transform;
    }

    /// <summary>
    /// Œv‚ğƒ^ƒbƒv‚µ‚½‚Æ‚«‚ÉŒÄ‚Î‚ê‚é
    /// </summary>
    public void ActivateMagic()
    {
        if (isRotating)
        {
            return;
        }

        if (minuteHandPivot == null ||
            hourHandPivot == null)
        {
            Debug.LogWarning(
                "Œv‚Ìj‚ªì¬‚³‚ê‚Ä‚¢‚Ü‚¹‚ñB"
            );
            return;
        }

        StartCoroutine(RotateHands());
    }

    /// <summary>
    /// ’·j‚Æ’Zj‚ğ‰ñ“]‚³‚¹‚é
    /// </summary>
    private IEnumerator RotateHands()
    {
        isRotating = true;

        Quaternion minuteStart =
            minuteHandPivot.localRotation;

        Quaternion hourStart =
            hourHandPivot.localRotation;

        float elapsedTime = 0f;

        while (elapsedTime < rotateDuration)
        {
            elapsedTime += Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime / rotateDuration
                );

            float minuteAngle =
                -360f *
                minuteHandRotations *
                rate;

            float hourAngle =
                -360f *
                hourHandRotations *
                rate;

            minuteHandPivot.localRotation =
                minuteStart *
                Quaternion.Euler(
                    0f,
                    0f,
                    minuteAngle
                );

            hourHandPivot.localRotation =
                hourStart *
                Quaternion.Euler(
                    0f,
                    0f,
                    hourAngle
                );

            yield return null;
        }

        isRotating = false;

        Debug.Log("Œv‚Ìj‚ª‰ñ‚è‚Ü‚µ‚½B");
    }
}