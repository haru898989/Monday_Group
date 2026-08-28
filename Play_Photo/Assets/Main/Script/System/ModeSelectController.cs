using UnityEngine;

public class ModeSelectController : MonoBehaviour
{
    // 自分の写真を使う
    public void UseMyPhoto()
    {
        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            return;
        }

        SceneLoader.Instance.LoadScene("LoadingLINE");
    }

    // 写真を選んで遊ぶ
    public void SelectPreparedPhoto()
    {
        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            return;
        }

        SceneLoader.Instance.LoadScene("PhotoSelect");
    }
}