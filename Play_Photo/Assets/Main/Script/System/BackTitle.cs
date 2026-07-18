using UnityEngine;

public class BackToTitleButton : MonoBehaviour
{
    public void BackToTitle()
    {
        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            return;
        }

        SceneLoader.Instance.LoadScene("Title");
    }
}