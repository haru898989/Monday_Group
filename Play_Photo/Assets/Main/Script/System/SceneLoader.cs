using UnityEngine;
using UnityEngine.SceneManagement;

public class SceneLoader : MonoBehaviour
{
    public static SceneLoader Instance { get; private set; }

    private void Awake()
    {
        if (Instance != null && Instance != this)
        {
            Destroy(gameObject);
            return;
        }

        Instance = this;

        // シーンを移動しても、このオブジェクトを削除しない
        DontDestroyOnLoad(gameObject);
    }



    /// <summary>
    /// ボタンからシーン名を受け取って遷移する
    /// </summary>
    /// <param name="sceneName"></param>
    public void LoadScene(string sceneName)
    {
        if (string.IsNullOrEmpty(sceneName))
        {
            Debug.LogWarning("シーン名が存在しません");
            return;
        }

        SceneManager.LoadScene(sceneName);
    }
}