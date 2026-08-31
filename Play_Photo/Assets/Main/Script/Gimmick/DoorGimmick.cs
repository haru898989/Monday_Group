using System.Collections;
using UnityEngine;

public class DoorGimmick : MonoBehaviour, GimmickBase
{
    // =========================================
    // ドア本体
    // =========================================
    private Renderer targetRenderer;

    // =========================================
    // ドアを開くための回転軸
    // =========================================
    private Transform doorPivot;

    // =========================================
    // 背景に残っているドアを隠す黒い板
    // =========================================
    private GameObject darkPanel;
    private Renderer darkPanelRenderer;

    // =========================================
    // 音
    // =========================================
    private AudioSource audioSource;

    // 開く音
    private AudioClip doorOpenAudioClip;

    // 閉まる音
    private AudioClip doorCloseAudioClip;

    // =========================================
    // 状態
    // =========================================
    private bool isRunning = false;
    private bool setupCompleted = false;

    // =========================================
    // ドアの設定
    // =========================================

    // 開く時間
    [SerializeField]
    private float openDuration = 0.8f;

    // 開いたまま待つ時間
    [SerializeField]
    private float waitDuration = 2.0f;

    // 閉じる時間
    [SerializeField]
    private float closeDuration = 0.8f;

    // 開く角度
    [SerializeField]
    private float openAngle = 75f;

    // 開く前にガタガタする時間
    [SerializeField]
    private float shakeDuration = 0.25f;

    // ガタガタの強さ
    [SerializeField]
    private float shakeAmount = 0.025f;


    // =========================================
    // ReseiverからRendererを受け取る
    // =========================================
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        if (targetRenderer == null)
        {
            Debug.LogError(
                "★ DoorGimmick：RendererがNULLです"
            );

            return;
        }

        Debug.Log(
            "★ DoorGimmick Renderer設定成功：" +
            targetRenderer.gameObject.name
        );

        SetupDoor();
    }


    // =========================================
    // 開く音・閉まる音を設定
    // =========================================
    public void SetAudioClips(
        AudioClip openClip,
        AudioClip closeClip
    )
    {
        doorOpenAudioClip = openClip;
        doorCloseAudioClip = closeClip;

        audioSource = GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;

        // 2D音声
        audioSource.spatialBlend = 0f;

        audioSource.volume = 1f;

        Debug.Log(
            "★ ドア開閉音設定完了"
        );
    }


    // =========================================
    // ドアの初期設定
    // =========================================
    private void SetupDoor()
    {
        if (setupCompleted)
        {
            return;
        }

        if (targetRenderer == null)
        {
            return;
        }

        // 先に黒い板を作る
        CreateDarkPanel();

        // ドアの左端にPivotを作る
        CreateDoorPivot();

        setupCompleted = true;

        Debug.Log(
            "★ DoorGimmick初期設定完了"
        );
    }


    // =========================================
    // 背景のドアを隠す黒い板を作る
    // =========================================
    private void CreateDarkPanel()
    {
        if (darkPanel != null)
        {
            return;
        }

        if (targetRenderer == null)
        {
            return;
        }

        // =====================================
        // ドアの大きさを取得
        // =====================================
        Bounds bounds =
            targetRenderer.bounds;


        // =====================================
        // Quadを作る
        // =====================================
        darkPanel =
            GameObject.CreatePrimitive(
                PrimitiveType.Quad
            );

        darkPanel.name =
            "DoorDarkPanel";


        // =====================================
        // Colliderはいらないので削除
        // =====================================
        Collider collider =
            darkPanel.GetComponent<Collider>();

        if (collider != null)
        {
            Destroy(collider);
        }


        // =====================================
        // Renderer取得
        // =====================================
        darkPanelRenderer =
            darkPanel.GetComponent<Renderer>();


        // =====================================
        // Shader
        // =====================================
        Shader shader =
            Shader.Find(
                "Unlit/Color"
            );

        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Sprites/Default"
                );
        }

        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Universal Render Pipeline/Unlit"
                );
        }


        // =====================================
        // 黒Material
        // =====================================
        if (
            shader != null &&
            darkPanelRenderer != null
        )
        {
            Material material =
                new Material(shader);

            material.color =
                Color.black;

            darkPanelRenderer.material =
                material;
        }
        else
        {
            Debug.LogWarning(
                "★ DoorDarkPanel用Shaderが見つかりません"
            );
        }


        // =====================================
        // ドアと同じ向き
        // =====================================
        darkPanel.transform.rotation =
            targetRenderer.transform.rotation;


        // =====================================
        // ドアより少しだけ大きくする
        // =====================================
        darkPanel.transform.localScale =
            new Vector3(
                bounds.size.x * 1.02f,
                bounds.size.y * 1.02f,
                1f
            );


        // =====================================
        // 黒板の位置
        // =====================================
        Vector3 panelPosition =
            bounds.center;


        // =====================================
        // カメラ方向を取得
        // =====================================
        Camera mainCamera =
            Camera.main;


        if (mainCamera != null)
        {
            Vector3 towardCamera =
                (
                    mainCamera.transform.position -
                    bounds.center
                ).normalized;


            // 背景写真より少し手前
            panelPosition +=
                towardCamera * 0.03f;
        }


        darkPanel.transform.position =
            panelPosition;


        // =====================================
        // 描画順
        // =====================================
        if (
            darkPanelRenderer != null &&
            targetRenderer != null
        )
        {
            darkPanelRenderer.sortingLayerID =
                targetRenderer.sortingLayerID;

            darkPanelRenderer.sortingOrder =
                targetRenderer.sortingOrder - 1;
        }


        // =====================================
        // 最初は非表示
        // =====================================
        darkPanel.SetActive(
            false
        );


        Debug.Log(
            "★ DoorDarkPanel作成完了"
        );
    }


    // =========================================
    // ドア左側に回転軸を作る
    // =========================================
    private void CreateDoorPivot()
    {
        if (targetRenderer == null)
        {
            return;
        }


        Transform doorTransform =
            targetRenderer.transform;


        Bounds bounds =
            targetRenderer.bounds;


        // =====================================
        // ドアの左端中央
        // =====================================
        Vector3 leftCenter =
            new Vector3(
                bounds.min.x,
                bounds.center.y,
                bounds.center.z
            );


        // =====================================
        // Pivot作成
        // =====================================
        GameObject pivotObject =
            new GameObject(
                "DoorPivot"
            );


        doorPivot =
            pivotObject.transform;


        // =====================================
        // ギミック本体の子にする
        // =====================================
        doorPivot.SetParent(
            transform,
            true
        );


        // =====================================
        // 左端に配置
        // =====================================
        doorPivot.position =
            leftCenter;


        doorPivot.rotation =
            Quaternion.identity;


        // =====================================
        // ドアを黒い板より手前にする
        // =====================================
        Camera mainCamera =
            Camera.main;


        if (mainCamera != null)
        {
            Vector3 towardCamera =
                (
                    mainCamera.transform.position -
                    doorTransform.position
                ).normalized;


            doorTransform.position +=
                towardCamera * 0.06f;
        }


        // =====================================
        // ドアをPivotの子にする
        // =====================================
        doorTransform.SetParent(
            doorPivot,
            true
        );


        Debug.Log(
            "★ DoorPivot作成完了"
        );
    }


    // =========================================
    // ドアをタップ
    // =========================================
    public void ActivateMagic()
    {
        Debug.Log(
            "★★★ ドアがタップされました ★★★"
        );


        // 実行中なら無視
        if (isRunning)
        {
            Debug.Log(
                "★ ドアギミック実行中"
            );

            return;
        }


        if (targetRenderer == null)
        {
            Debug.LogError(
                "★ Door Rendererがありません"
            );

            return;
        }


        if (!setupCompleted)
        {
            SetupDoor();
        }


        if (doorPivot == null)
        {
            Debug.LogError(
                "★ DoorPivotがありません"
            );

            return;
        }


        StartCoroutine(
            DoorSequence()
        );
    }


    // =========================================
    // ドアギミック本体
    // =========================================
    private IEnumerator DoorSequence()
    {
        isRunning = true;


        Debug.Log(
            "★ ドアギミックSTART"
        );


        // =====================================
        // 元の状態を保存
        // =====================================
        Quaternion originalRotation =
            doorPivot.localRotation;


        Vector3 originalDoorPosition =
            targetRenderer.transform.localPosition;


        // =====================================
        // ① 最初にドアをガタガタさせる
        // =====================================
        float timer = 0f;


        while (
            timer <
            shakeDuration
        )
        {
            timer +=
                Time.deltaTime;


            float shake =
                Mathf.Sin(
                    timer * 60f
                )
                *
                shakeAmount;


            Vector3 position =
                originalDoorPosition;


            position.x +=
                shake;


            targetRenderer.transform.localPosition =
                position;


            yield return null;
        }


        // 元位置に戻す
        targetRenderer.transform.localPosition =
            originalDoorPosition;


        // =====================================
        // ② 開く音
        // =====================================
        if (
            audioSource != null &&
            doorOpenAudioClip != null
        )
        {
            audioSource.PlayOneShot(
                doorOpenAudioClip
            );


            Debug.Log(
                "★ ドア開く音再生"
            );
        }
        else
        {
            Debug.Log(
                "★ ドア開く音なし"
            );
        }


        // =====================================
        // ③ 背景の元ドアを黒板で隠す
        // =====================================
        if (darkPanel != null)
        {
            darkPanel.SetActive(
                true
            );


            Debug.Log(
                "★ DoorDarkPanel表示"
            );
        }


        // 1フレーム待つ
        yield return null;


        // =====================================
        // ④ ドアOPEN
        // =====================================
        Quaternion openedRotation =
            originalRotation *
            Quaternion.Euler(
                0f,
                openAngle,
                0f
            );


        timer = 0f;


        while (
            timer <
            openDuration
        )
        {
            timer +=
                Time.deltaTime;


            float progress =
                Mathf.Clamp01(
                    timer /
                    openDuration
                );


            float smooth =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    progress
                );


            doorPivot.localRotation =
                Quaternion.Slerp(
                    originalRotation,
                    openedRotation,
                    smooth
                );


            yield return null;
        }


        // 完全に開いた状態
        doorPivot.localRotation =
            openedRotation;


        Debug.Log(
            "★ ドアOPEN"
        );


        // =====================================
        // ⑤ 開いたまま待つ
        // =====================================
        yield return new WaitForSeconds(
            waitDuration
        );


        // =====================================
        // ⑥ 閉まる音
        // =====================================
        if (
            audioSource != null &&
            doorCloseAudioClip != null
        )
        {
            audioSource.PlayOneShot(
                doorCloseAudioClip
            );


            Debug.Log(
                "★ ドア閉まる音再生"
            );
        }
        else
        {
            Debug.Log(
                "★ ドア閉まる音なし"
            );
        }


        // =====================================
        // ⑦ ドアCLOSE
        // =====================================
        timer = 0f;


        while (
            timer <
            closeDuration
        )
        {
            timer +=
                Time.deltaTime;


            float progress =
                Mathf.Clamp01(
                    timer /
                    closeDuration
                );


            float smooth =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    progress
                );


            doorPivot.localRotation =
                Quaternion.Slerp(
                    openedRotation,
                    originalRotation,
                    smooth
                );


            yield return null;
        }


        // =====================================
        // ⑧ 完全に元へ戻す
        // =====================================
        doorPivot.localRotation =
            originalRotation;


        targetRenderer.transform.localPosition =
            originalDoorPosition;


        // =====================================
        // ⑨ 黒板を消す
        // =====================================
        if (darkPanel != null)
        {
            darkPanel.SetActive(
                false
            );


            Debug.Log(
                "★ DoorDarkPanel非表示"
            );
        }


        Debug.Log(
            "★ ドアCLOSE"
        );


        // =====================================
        // 終了
        // =====================================
        isRunning = false;


        Debug.Log(
            "★ ドアギミック終了"
        );
    }


    // =========================================
    // 削除時
    // =========================================
    private void OnDestroy()
    {
        if (darkPanel != null)
        {
            Destroy(
                darkPanel
            );
        }
    }
}