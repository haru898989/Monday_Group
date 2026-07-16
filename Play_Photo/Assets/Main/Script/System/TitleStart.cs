using UnityEngine;

public class TitleStart : MonoBehaviour
{
    public void StartLoadingLINE()
    {
        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            return;
        }

        SceneLoader.Instance.LoadScene("LoadingLINE");
    }
}