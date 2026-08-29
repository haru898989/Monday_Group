using UnityEngine;

/// <summary>
/// スマートフォンをタッチすると、着信音とバイブ音を鳴らしながら
/// スマートフォン本体を振動させる。もう一度タッチすると停止する。
/// </summary>
public class PhoneGimmick : MonoBehaviour, GimmickBase
{
    [Header("振動設定")]

    [SerializeField]
    private float vibrationAmount = 0.08f;

    [SerializeField]
    private float vibrationSpeed = 32f;

    [SerializeField]
    private float rotationAmount = 2.2f;

    private Vector3 originalLocalPosition;
    private Quaternion originalLocalRotation;
    private bool isVibrating;
    private float vibrationTimer;

    private AudioSource phoneAudioSource;
    private AudioSource vibrationAudioSource;


    private void Awake()
    {
        RememberOriginalTransform();
    }


    /// <summary>
    /// Reseiverから着信音とバイブ音を受け取る。
    /// </summary>
    public void SetAudioClip(
        AudioClip phoneClip,
        AudioClip vibrationClip
    )
    {
        if (phoneAudioSource == null)
        {
            phoneAudioSource =
                gameObject.AddComponent<AudioSource>();
        }

        phoneAudioSource.clip = phoneClip;
        phoneAudioSource.playOnAwake = false;
        phoneAudioSource.loop = true;
        phoneAudioSource.spatialBlend = 0f;

        if (vibrationAudioSource == null)
        {
            vibrationAudioSource =
                gameObject.AddComponent<AudioSource>();
        }

        vibrationAudioSource.clip = vibrationClip;
        vibrationAudioSource.playOnAwake = false;
        vibrationAudioSource.loop = true;
        vibrationAudioSource.spatialBlend = 0f;
    }


    private void Update()
    {
        if (!isVibrating)
        {
            return;
        }

        vibrationTimer += Time.deltaTime;

        float phase = vibrationTimer * vibrationSpeed;
        float offsetX = Mathf.Sin(phase) * vibrationAmount;
        float offsetY =
            Mathf.Sin(phase * 0.73f + 1.2f)
            * vibrationAmount
            * 0.2f;
        float angle =
            Mathf.Sin(phase * 0.91f)
            * rotationAmount;

        // 切り抜いたスマートフォンのルート自体を動かすため、
        // 画面だけではなく本体全体が振動する。
        transform.localPosition =
            originalLocalPosition
            + new Vector3(offsetX, offsetY, 0f);

        transform.localRotation =
            originalLocalRotation
            * Quaternion.Euler(0f, 0f, angle);
    }


    /// <summary>
    /// Reseiverとの呼び出し互換性を保つために残している。
    /// 白くなる原因だったマテリアル変更は行わない。
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        if (renderer == null)
        {
            Debug.LogWarning(
                "PhoneGimmickのRendererが設定されていません。"
            );
        }
    }


    public void ActivateMagic()
    {
        if (isVibrating)
        {
            StopVibration();
        }
        else
        {
            StartVibration();
        }
    }


    private void StartVibration()
    {
        RememberOriginalTransform();
        vibrationTimer = 0f;
        isVibrating = true;

        if (
            phoneAudioSource != null
            && phoneAudioSource.clip != null
        )
        {
            phoneAudioSource.Play();
        }

        if (
            vibrationAudioSource != null
            && vibrationAudioSource.clip != null
        )
        {
            vibrationAudioSource.Play();
        }
    }


    private void StopVibration()
    {
        isVibrating = false;
        vibrationTimer = 0f;
        RestoreOriginalTransform();

        if (phoneAudioSource != null)
        {
            phoneAudioSource.Stop();
        }

        if (vibrationAudioSource != null)
        {
            vibrationAudioSource.Stop();
        }
    }


    private void RememberOriginalTransform()
    {
        originalLocalPosition = transform.localPosition;
        originalLocalRotation = transform.localRotation;
    }


    private void RestoreOriginalTransform()
    {
        transform.localPosition = originalLocalPosition;
        transform.localRotation = originalLocalRotation;
    }


    private void OnDisable()
    {
        StopVibration();
    }
}
