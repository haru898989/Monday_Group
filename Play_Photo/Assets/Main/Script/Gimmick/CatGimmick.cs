using UnityEngine;

public class CatGimmick : MonoBehaviour, GimmickBase
{
    private AudioSource audioSource;

    /// <summary>
    /// ”L‚Ì–Â‚«º‚ğİ’è‚·‚é
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
                "Reseiver‚©‚ç“n‚³‚ê‚½”L‚ÌAudioClip‚ªnull‚Å‚·B"
            );
            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"”L‚Ì‰¹º‚ğİ’è‚µ‚Ü‚µ‚½F{clip.name}"
        );
    }

    /// <summary>
    /// ”L‚ğƒ^ƒbƒ`‚µ‚½‚Æ‚«‚ÉŒÄ‚Î‚ê‚é
    /// </summary>
    public void ActivateMagic()
    {
        if (audioSource == null)
        {
            Debug.LogWarning(
                "”L‚ÉAudioSource‚ª‚ ‚è‚Ü‚¹‚ñB"
            );
            return;
        }

        if (audioSource.clip == null)
        {
            Debug.LogWarning(
                "”L‚Ì–Â‚«º‚ªİ’è‚³‚ê‚Ä‚¢‚Ü‚¹‚ñB"
            );
            return;
        }

        audioSource.Stop();
        audioSource.Play();

        Debug.Log(
            $"”L‚ª–Â‚«‚Ü‚µ‚½F{audioSource.clip.name}"
        );
    }
}