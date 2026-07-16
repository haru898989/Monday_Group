using UnityEngine;

// 犬をタップしたときのギミック
public class DogGimmick : MonoBehaviour, GimmickBase
{
    // 犬の鳴き声
    [SerializeField]
    private AudioSource audioSource;

    // タップされたときの処理
    public void ActivateMagic()
    {
        Debug.Log("ワン！");

        // 鳴き声を再生
        audioSource.Play();
    }
}