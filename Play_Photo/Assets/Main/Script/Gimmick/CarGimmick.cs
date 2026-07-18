using UnityEngine;

public class CarGimmick : MonoBehaviour, GimmickBase
{
    private AudioSource audioSource;

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
                "Reseiverから渡された車のAudioClipがnullです。"
            );
            return;
        }

        audioSource.clip = clip;

        Debug.Log($"車の音声を設定しました：{clip.name}");
    }

    public void ActivateMagic()
    {
        if (audioSource == null || audioSource.clip == null)
        {
            Debug.LogWarning(
                "車の音声が設定されていません。"
            );
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log($"車の音を再生しました：{audioSource.clip.name}");
    }
}