using UnityEngine;

public class GlassGimmick : MonoBehaviour, GimmickBase
{
    private AudioSource audioSource;

    /// <summary>
    /// ガラスが割れる音を設定する
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
            Debug.LogError("窓ガラスのAudioClipがnullです。");
            return;
        }

        audioSource.clip = clip;

        Debug.Log($"窓ガラスの音を設定しました：{clip.name}");
    }

    /// <summary>
    /// 窓ガラスをタップしたときに呼ばれる
    /// </summary>
    public void ActivateMagic()
    {
        if (audioSource == null)
        {
            Debug.LogWarning("窓ガラスにAudioSourceがありません。");
            return;
        }

        if (audioSource.clip == null)
        {
            Debug.LogWarning("窓ガラスの音が設定されていません。");
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log($"窓ガラスが割れました：{audioSource.clip.name}");
    }
}