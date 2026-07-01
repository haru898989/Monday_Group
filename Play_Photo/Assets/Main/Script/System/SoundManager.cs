using UnityEngine;

public class SoundManager : MonoBehaviour
{
    public static SoundManager Instance { get; private set; }

    [Header("Audio Sources")]
    [SerializeField] private AudioSource bgmSource;
    [SerializeField] private AudioSource seSource;

    [Header("BGM Clips")]
    [SerializeField] private AudioClip[] bgmClips;

    [Header("SE Clips")]
    [SerializeField] private AudioClip[] seClips;

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;

        // シーンを移動しても消さない
        DontDestroyOnLoad(gameObject);
    }



    /// <summary>
    /// BGMを番号で再生
    /// </summary>
    /// <param name="index"></param>
    public void PlayBGM(int index)
    {
        if (bgmClips == null || index < 0 || index >= bgmClips.Length)
        {
            Debug.LogWarning("指定されたBGMが存在しません。 index: " + index);
            return;
        }

        if (bgmClips[index] == null)
        {
            Debug.LogWarning("BGMのAudioClipが設定されていません。 index: " + index);
            return;
        }

        bgmSource.clip = bgmClips[index];
        bgmSource.loop = true;
        bgmSource.Play();
    }



    /// <summary>
    /// SEを番号で再生
    /// </summary>
    /// <param name="index"></param>
    public void PlaySE(int index)
    {
        if (seClips == null || index < 0 || index >= seClips.Length)
        {
            Debug.LogWarning("指定されたSEが存在しません。 index: " + index);
            return;
        }

        if (seClips[index] == null)
        {
            Debug.LogWarning("SEのAudioClipが設定されていません。 index: " + index);
            return;
        }

        seSource.PlayOneShot(seClips[index]);
    }

    /// <summary>
    /// BGM停止
    /// </summary>
    public void StopBGM()
    {
        bgmSource.Stop();
    }

    /// <summary>
    /// BGM一時停止
    /// </summary>
    public void PauseBGM()
    {
        bgmSource.Pause();
    }

    /// <summary>
    /// BGM再開
    /// </summary>
    public void ResumeBGM()
    {
        bgmSource.UnPause();
    }

    /// <summary>
    /// BGM音量変更
    /// </summary>
    /// <param name="volume"></param>
    public void SetBGMVolume(float volume)
    {
        bgmSource.volume = Mathf.Clamp01(volume);
    }

    /// <summary>
    /// SE音量変更
    /// </summary>
    /// <param name="volume"></param>
    public void SetSEVolume(float volume)
    {
        seSource.volume = Mathf.Clamp01(volume);
    }
}