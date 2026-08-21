using UnityEngine;

public class ClockGimmick : MonoBehaviour, GimmickBase
{
    private AudioSource audioSource;

    /// <summary>
    /// 時計の音を設定する
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource = gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1f;
        audioSource.mute = false;

        if (clip == null)
        {
            Debug.LogError(
                "Reseiverから渡された時計のAudioClipがnullです。"
            );
            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"時計の音声を設定しました：{clip.name}"
        );
    }

    /// <summary>
    /// 時計をタッチしたときに呼ばれる
    /// </summary>
    public void ActivateMagic()
    {
        if (audioSource == null)
        {
            Debug.LogWarning(
                "時計にAudioSourceがありません。"
            );
            return;
        }

        if (audioSource.clip == null)
        {
            Debug.LogWarning(
                "時計の音が設定されていません。"
            );
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log(
            $"時計の音を再生しました：{audioSource.clip.name}"
        );
    }
}