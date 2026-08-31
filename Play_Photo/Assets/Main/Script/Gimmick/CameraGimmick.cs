using System.Collections;
using UnityEngine;

/// <summary>
/// カメラをタッチすると、
/// シャッター音と同時に画面全体が白くフラッシュする。
/// </summary>
public class CameraGimmick : MonoBehaviour, GimmickBase
{
    [Header("フラッシュ設定")]

    [SerializeField]
    private float flashInDuration = 0.03f;

    [SerializeField]
    private float flashHoldDuration = 0.05f;

    [SerializeField]
    private float flashOutDuration = 0.25f;

    [SerializeField]
    private float maximumAlpha = 0.9f;


    private AudioSource audioSource;

    private GameObject flashObject;

    private SpriteRenderer flashRenderer;

    private Coroutine flashCoroutine;


    private void Awake()
    {
        // AudioSourceを取得
        audioSource =
            GetComponent<AudioSource>();

        // 無ければ自動追加
        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
        audioSource.volume = 1f;
        audioSource.mute = false;
    }


    /// <summary>
    /// Reseiverからシャッター音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource == null)
        {
            audioSource =
                GetComponent<AudioSource>();

            if (audioSource == null)
            {
                audioSource =
                    gameObject.AddComponent<AudioSource>();
            }
        }

        if (clip == null)
        {
            Debug.LogError(
                "カメラのAudioClipがnullです。"
            );

            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"カメラ音を設定しました：{clip.name}"
        );
    }


    /// <summary>
    /// カメラをタッチしたとき
    /// </summary>
    public void ActivateMagic()
    {
        // シャッター音
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.PlayOneShot(
                audioSource.clip
            );
        }
        else
        {
            Debug.LogWarning(
                "カメラの音声が設定されていません。"
            );
        }


        // 連続タップされた場合
        // 前のフラッシュを終了
        if (flashCoroutine != null)
        {
            StopCoroutine(
                flashCoroutine
            );
        }


        flashCoroutine =
            StartCoroutine(
                Flash()
            );
    }


    /// <summary>
    /// 白いフラッシュを表示
    /// </summary>
    private IEnumerator Flash()
    {
        CreateFlashObject();


        // 最初は透明
        SetFlashAlpha(
            0f
        );


        /*
         * 一気に白くする
         */
        float elapsedTime = 0f;

        float safeFlashInDuration =
            Mathf.Max(
                flashInDuration,
                0.001f
            );


        while (
            elapsedTime <
            safeFlashInDuration
        )
        {
            elapsedTime +=
                Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    safeFlashInDuration
                );


            float alpha =
                Mathf.Lerp(
                    0f,
                    maximumAlpha,
                    rate
                );


            SetFlashAlpha(
                alpha
            );


            yield return null;
        }


        SetFlashAlpha(
            maximumAlpha
        );


        /*
         * 一瞬だけ白い状態を維持
         */
        yield return new WaitForSeconds(
            flashHoldDuration
        );


        /*
         * 徐々に元へ戻す
         */
        elapsedTime = 0f;

        float safeFlashOutDuration =
            Mathf.Max(
                flashOutDuration,
                0.001f
            );


        while (
            elapsedTime <
            safeFlashOutDuration
        )
        {
            elapsedTime +=
                Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    safeFlashOutDuration
                );


            float alpha =
                Mathf.Lerp(
                    maximumAlpha,
                    0f,
                    rate
                );


            SetFlashAlpha(
                alpha
            );


            yield return null;
        }


        SetFlashAlpha(
            0f
        );


        if (flashObject != null)
        {
            Destroy(
                flashObject
            );
        }


        flashObject = null;
        flashRenderer = null;
        flashCoroutine = null;
    }


    /// <summary>
    /// フラッシュ用の白い画像を生成
    /// </summary>
    private void CreateFlashObject()
    {
        // 前のものが残っていたら削除
        if (flashObject != null)
        {
            Destroy(
                flashObject
            );
        }


        flashObject =
            new GameObject(
                "CameraFlash"
            );


        flashRenderer =
            flashObject.AddComponent<SpriteRenderer>();


        // 1x1の白いTextureを作る
        Texture2D texture =
            new Texture2D(
                1,
                1
            );


        texture.SetPixel(
            0,
            0,
            Color.white
        );

        texture.Apply();


        Sprite sprite =
            Sprite.Create(
                texture,
                new Rect(
                    0,
                    0,
                    1,
                    1
                ),
                new Vector2(
                    0.5f,
                    0.5f
                ),
                1f
            );


        flashRenderer.sprite =
            sprite;


        /*
         * カメラの正面に配置
         */
        Camera mainCamera =
            Camera.main;


        if (mainCamera != null)
        {
            flashObject.transform.position =
                mainCamera.transform.position
                + mainCamera.transform.forward
                * 1f;

            flashObject.transform.rotation =
                mainCamera.transform.rotation;


            /*
             * 画面全体を覆えるように
             * 大きめにする
             */
            flashObject.transform.localScale =
                new Vector3(
                    100f,
                    100f,
                    1f
                );
        }


        // 最前面
        flashRenderer.sortingOrder =
            32767;
    }


    /// <summary>
    /// フラッシュの透明度を変更
    /// </summary>
    private void SetFlashAlpha(
        float alpha
    )
    {
        if (flashRenderer == null)
        {
            return;
        }


        Color color =
            Color.white;

        color.a =
            Mathf.Clamp01(
                alpha
            );


        flashRenderer.color =
            color;
    }


    private void OnDisable()
    {
        if (flashCoroutine != null)
        {
            StopCoroutine(
                flashCoroutine
            );

            flashCoroutine = null;
        }


        if (flashObject != null)
        {
            Destroy(
                flashObject
            );

            flashObject = null;
        }


        flashRenderer = null;
    }
}