using System.Collections;
using UnityEngine;

/// <summary>
/// 人をタッチすると左右にステップしながら踊り、
/// ダンス音を鳴らす。
/// </summary>
public class HumanGimmick1 : MonoBehaviour, GimmickBase
{
    [SerializeField]
    private float moveAmount = 0.4f;

    [SerializeField]
    private float bounceAmount = 0.12f;

    [SerializeField]
    private float rotationAmount = 12f;

    [SerializeField]
    private float danceSpeed = 6f;

    [SerializeField]
    private float danceDuration = 2.5f;

    private Renderer targetRenderer;

    private AudioClip danceAudioClip;
    private AudioSource audioSource;

    private bool isActivated = false;


    private void Awake()
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;
    }


    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// Receiverからダンス音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        danceAudioClip = clip;
    }


    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;

        StartCoroutine(Dance());
    }


    private IEnumerator Dance()
    {
        Vector3 startPosition =
            transform.position;

        Quaternion startRotation =
            transform.rotation;

        Vector3 startScale =
            transform.localScale;


        // =========================
        // ダンス音を再生
        // =========================

        if (audioSource != null &&
            danceAudioClip != null)
        {
            audioSource.PlayOneShot(
                danceAudioClip
            );
        }
        else
        {
            Debug.LogWarning(
                "HumanGimmick：ダンス音が設定されていません。"
            );
        }


        float elapsedTime = 0f;


        while (elapsedTime < danceDuration)
        {
            elapsedTime += Time.deltaTime;


            // 左右に動く
            float moveX =
                Mathf.Sin(
                    elapsedTime * danceSpeed
                ) * moveAmount;


            // 上下に跳ねる
            float bounceY =
                Mathf.Abs(
                    Mathf.Sin(
                        elapsedTime
                        * danceSpeed
                        * 2f
                    )
                ) * bounceAmount;


            transform.position =
                startPosition +
                new Vector3(
                    moveX,
                    bounceY,
                    0f
                );


            // 左右に傾ける
            float rotationZ =
                Mathf.Sin(
                    elapsedTime * danceSpeed
                ) * rotationAmount;


            transform.rotation =
                startRotation *
                Quaternion.Euler(
                    0f,
                    0f,
                    rotationZ
                );


            // 少し伸び縮み
            float scaleY =
                1f +
                Mathf.Abs(
                    Mathf.Sin(
                        elapsedTime
                        * danceSpeed
                        * 2f
                    )
                ) * 0.04f;


            transform.localScale =
                new Vector3(
                    startScale.x,
                    startScale.y * scaleY,
                    startScale.z
                );


            yield return null;
        }


        // ダンスが終わったら音も止める
        if (audioSource != null)
        {
            audioSource.Stop();
        }


        transform.position =
            startPosition;

        transform.rotation =
            startRotation;

        transform.localScale =
            startScale;


        isActivated = false;

        Debug.Log(
            "HumanGimmick：ダンス終了"
        );
    }
}