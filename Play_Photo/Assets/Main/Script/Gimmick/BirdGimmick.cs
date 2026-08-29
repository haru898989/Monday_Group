using System.Collections;
using UnityEngine;

/// <summary>
/// ’¹‚ğƒ^ƒbƒ`‚·‚é‚Æ‰H‚Î‚½‚«‚È‚ª‚çÎ‚ßã‚Ö”ò‚ñ‚Å‚¢‚­B
/// </summary>
public class BirdGimmick : MonoBehaviour, GimmickBase
{
    // ”ò‚Ô‹——£
    [SerializeField]
    private float flyDistanceX = 4f;

    [SerializeField]
    private float flyDistanceY = 3f;

    // ”òsŠÔ
    [SerializeField]
    private float flyDuration = 2.5f;

    // ‰H‚Î‚½‚«‚Ì‘å‚«‚³
    [SerializeField]
    private float flapAmount = 0.08f;

    // ‰H‚Î‚½‚«‘¬“x
    [SerializeField]
    private float flapSpeed = 12f;

    // ¶‰E‚Ì—h‚ê
    [SerializeField]
    private float swayAmount = 0.15f;

    private Renderer targetRenderer;

    private AudioClip birdAudioClip;
    private AudioSource audioSource;

    private bool isActivated = false;


    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }


    /// <summary>
    /// Receiver‚©‚ç’¹‚ÌRenderer‚ğó‚¯æ‚é
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// Receiver‚©‚ç’¹‚Ì–Â‚«º‚ğó‚¯æ‚é
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        birdAudioClip = clip;
    }


    /// <summary>
    /// ƒ^ƒbƒ`
    /// </summary>
    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;

        StartCoroutine(FlyAway());
    }


    private IEnumerator FlyAway()
    {
        Vector3 startPosition =
            transform.position;

        Vector3 startScale =
            transform.localScale;


        // –Â‚«º
        if (audioSource != null &&
            birdAudioClip != null)
        {
            audioSource.PlayOneShot(
                birdAudioClip
            );
        }


        float elapsedTime = 0f;


        while (elapsedTime < flyDuration)
        {
            elapsedTime += Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime / flyDuration
                );


            // ™X‚É‰Á‘¬‚·‚é
            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            // ¶‰E‚É­‚µ—h‚ç‚·
            float sway =
                Mathf.Sin(
                    elapsedTime * 6f
                ) * swayAmount;


            // Î‚ßã‚Ö”ò‚Ô
            transform.position =
                startPosition +
                new Vector3(
                    flyDistanceX * smoothRate + sway,
                    flyDistanceY * smoothRate,
                    0f
                );


            // ‰H‚Î‚½‚¢‚Ä‚¢‚é‚æ‚¤‚Éc•ûŒü‚ğLk
            float flap =
                1f +
                Mathf.Sin(
                    elapsedTime * flapSpeed
                ) * flapAmount;


            transform.localScale =
                new Vector3(
                    startScale.x,
                    startScale.y * flap,
                    startScale.z
                );


            // ­‚µŒX‚¯‚é
            float rotationZ =
                Mathf.Sin(
                    elapsedTime * 5f
                ) * 5f;


            transform.rotation =
                Quaternion.Euler(
                    0f,
                    0f,
                    rotationZ
                );


            yield return null;
        }


        HideBird();


        float destroyDelay =
            birdAudioClip != null
                ? birdAudioClip.length
                : 0f;


        Destroy(
            gameObject,
            destroyDelay
        );
    }


    /// <summary>
    /// ’¹‚ğŒ©‚¦‚È‚­‚µ‚Ä“–‚½‚è”»’è‚à’â~
    /// </summary>
    private void HideBird()
    {
        if (targetRenderer == null)
        {
            targetRenderer =
                GetComponentInChildren<Renderer>(true);
        }


        if (targetRenderer != null)
        {
            targetRenderer.enabled = false;
        }


        Collider[] colliders =
            GetComponentsInChildren<Collider>(true);


        foreach (Collider targetCollider in colliders)
        {
            targetCollider.enabled = false;
        }
    }
}