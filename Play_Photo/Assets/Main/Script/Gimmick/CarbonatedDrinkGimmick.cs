using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 炭酸飲料をタッチすると、
/// 丸い半透明の泡が下から上へ
/// シュワシュワと昇り続ける。
///
/// もう一度タッチすると泡と音が停止する。
/// </summary>
public class CarbonatedDrinkGimmick : MonoBehaviour, GimmickBase
{
    [Header("泡の数")]

    [SerializeField]
    private int bubbleCount = 20;


    [Header("泡が発生する範囲")]

    [SerializeField]
    private float bubbleAreaWidth = 0.9f;

    [SerializeField]
    private float bubbleStartY = -0.45f;

    [SerializeField]
    private float bubbleEndY = 0.65f;


    [Header("泡の大きさ")]

    [SerializeField]
    private float minimumBubbleSize = 0.025f;

    [SerializeField]
    private float maximumBubbleSize = 0.07f;


    [Header("泡の上昇速度")]

    [SerializeField]
    private float minimumBubbleSpeed = 0.35f;

    [SerializeField]
    private float maximumBubbleSpeed = 0.85f;


    [Header("左右のゆらぎ")]

    [SerializeField]
    private float minimumSwayAmount = 0.015f;

    [SerializeField]
    private float maximumSwayAmount = 0.05f;

    [SerializeField]
    private float minimumSwaySpeed = 1.5f;

    [SerializeField]
    private float maximumSwaySpeed = 4f;


    [Header("泡の見た目")]

    [SerializeField]
    private Color bubbleColor =
        new Color(
            0.92f,
            0.97f,
            1f,
            0.7f
        );

    // 円形Textureの解像度
    [SerializeField]
    private int bubbleTextureSize = 64;


    private Renderer targetRenderer;

    private bool isFizzing;


    private readonly List<GameObject> bubbles =
        new List<GameObject>();


    // 全ての泡で共有するTextureとMaterial
    private Texture2D bubbleTexture;
    private Material bubbleMaterial;


    // ★追加：炭酸のシュワシュワ音用
    private AudioSource audioSource;


    /// <summary>
    /// 泡ごとの個別情報。
    /// </summary>
    private class BubbleData : MonoBehaviour
    {
        public float speed;

        public float swayAmount;

        public float swaySpeed;

        public float timer;

        public float baseX;
    }


    /// <summary>
    /// Reseiverから飲み物のRendererを受け取る。
    /// </summary>
    public void SetTargetRenderer(
        Renderer renderer
    )
    {
        targetRenderer =
            renderer;

        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "CarbonatedDrinkGimmickのRendererが設定されていません。"
            );

            return;
        }
    }


    /// <summary>
    /// Reseiverから炭酸の効果音を受け取る。
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

        audioSource.clip = clip;

        audioSource.playOnAwake = false;

        // 泡が出ている間は音を繰り返す
        audioSource.loop = true;

        // 2D音声
        audioSource.spatialBlend = 0f;
    }


    private void Update()
    {
        if (isFizzing)
        {
            UpdateBubbles();
        }
    }


    /// <summary>
    /// 飲み物をタッチしたときに呼ばれる。
    ///
    /// 1回目：シュワシュワ開始
    /// 2回目：停止
    /// </summary>
    public void ActivateMagic()
    {
        if (targetRenderer == null)
        {
            SetTargetRenderer(
                GetComponentInChildren<Renderer>(true)
            );
        }


        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "CarbonatedDrinkGimmickのRendererがありません。"
            );

            return;
        }


        if (isFizzing)
        {
            StopFizz();
        }
        else
        {
            StartFizz();
        }
    }


    /// <summary>
    /// シュワシュワを開始する。
    /// </summary>
    private void StartFizz()
    {
        isFizzing =
            true;


        if (bubbles.Count == 0)
        {
            CreateBubbles();
        }


        foreach (
            GameObject bubble
            in bubbles
        )
        {
            if (bubble == null)
            {
                continue;
            }


            ResetBubble(
                bubble,
                true
            );


            bubble.SetActive(
                true
            );
        }


        // ★追加：シュワシュワ音を開始
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.Play();
        }
    }


    /// <summary>
    /// シュワシュワを停止する。
    /// </summary>
    private void StopFizz()
    {
        isFizzing =
            false;


        foreach (
            GameObject bubble
            in bubbles
        )
        {
            if (bubble != null)
            {
                bubble.SetActive(
                    false
                );
            }
        }


        // ★追加：シュワシュワ音を停止
        if (audioSource != null)
        {
            audioSource.Stop();
        }
    }


    /// <summary>
    /// 泡をまとめて生成する。
    /// </summary>
    private void CreateBubbles()
    {
        /*
         * 泡用のTextureとMaterialは
         * 全ての泡で共有する。
         */
        bubbleTexture =
            CreateCircularBubbleTexture(
                bubbleTextureSize
            );


        bubbleMaterial =
            CreateBubbleMaterial(
                bubbleTexture
            );


        for (
            int i = 0;
            i < bubbleCount;
            i++
        )
        {
            GameObject bubble =
                GameObject.CreatePrimitive(
                    PrimitiveType.Quad
                );


            bubble.name =
                "Bubble_" + i;


            bubble.transform.SetParent(
                transform,
                false
            );


            /*
             * 泡にはColliderは必要ない。
             */
            Collider bubbleCollider =
                bubble.GetComponent<Collider>();


            if (bubbleCollider != null)
            {
                bubbleCollider.enabled =
                    false;


                Destroy(
                    bubbleCollider
                );
            }


            /*
             * 泡ごとにサイズを変える。
             */
            float bubbleSize =
                Random.Range(
                    minimumBubbleSize,
                    maximumBubbleSize
                );


            bubble.transform.localScale =
                new Vector3(
                    bubbleSize,
                    bubbleSize,
                    1f
                );


            /*
             * 円形Textureを使ったMaterialを設定。
             */
            Renderer bubbleRenderer =
                bubble.GetComponent<Renderer>();


            if (bubbleRenderer != null)
            {
                bubbleRenderer.sharedMaterial =
                    bubbleMaterial;
            }


            /*
             * 泡ごとの動きを設定。
             */
            BubbleData bubbleData =
                bubble.AddComponent<BubbleData>();


            bubbleData.speed =
                Random.Range(
                    minimumBubbleSpeed,
                    maximumBubbleSpeed
                );


            bubbleData.swayAmount =
                Random.Range(
                    minimumSwayAmount,
                    maximumSwayAmount
                );


            bubbleData.swaySpeed =
                Random.Range(
                    minimumSwaySpeed,
                    maximumSwaySpeed
                );


            bubbleData.timer =
                Random.Range(
                    0f,
                    10f
                );


            ResetBubble(
                bubble,
                true
            );


            bubble.SetActive(
                false
            );


            bubbles.Add(
                bubble
            );
        }
    }


    /// <summary>
    /// 丸い泡のTextureをコードで生成する。
    ///
    /// 中心は透明気味、
    /// 外周だけ少し白くして
    /// 気泡らしい見た目にする。
    /// </summary>
    private Texture2D CreateCircularBubbleTexture(
        int textureSize
    )
    {
        int safeSize =
            Mathf.Max(
                textureSize,
                16
            );


        Texture2D texture =
            new Texture2D(
                safeSize,
                safeSize,
                TextureFormat.RGBA32,
                false
            );


        texture.name =
            "RuntimeCircularBubbleTexture";


        texture.wrapMode =
            TextureWrapMode.Clamp;


        texture.filterMode =
            FilterMode.Bilinear;


        float center =
            (safeSize - 1)
            / 2f;


        float radius =
            safeSize
            * 0.45f;


        for (
            int y = 0;
            y < safeSize;
            y++
        )
        {
            for (
                int x = 0;
                x < safeSize;
                x++
            )
            {
                float dx =
                    x - center;


                float dy =
                    y - center;


                float distance =
                    Mathf.Sqrt(
                        dx * dx
                        + dy * dy
                    );


                float normalizedDistance =
                    distance
                    / radius;


                Color pixelColor =
                    Color.clear;


                /*
                 * 円の内側だけ描画する。
                 */
                if (normalizedDistance <= 1f)
                {
                    /*
                     * 中心部分はかなり透明。
                     */
                    float centerAlpha =
                        Mathf.Lerp(
                            0.08f,
                            0.02f,
                            normalizedDistance
                        );


                    /*
                     * 円の外周に近づくほど
                     * 白い輪っかを強くする。
                     */
                    float edge =
                        Mathf.InverseLerp(
                            0.68f,
                            1f,
                            normalizedDistance
                        );


                    float edgeAlpha =
                        Mathf.SmoothStep(
                            0f,
                            1f,
                            edge
                        )
                        * 0.9f;


                    /*
                     * 円の一番端は
                     * 少し滑らかに透明化。
                     */
                    float outerFade =
                        1f;


                    if (normalizedDistance > 0.93f)
                    {
                        outerFade =
                            Mathf.InverseLerp(
                                1f,
                                0.93f,
                                normalizedDistance
                            );
                    }


                    float alpha =
                        Mathf.Max(
                            centerAlpha,
                            edgeAlpha
                        )
                        * outerFade;


                    /*
                     * 左上に小さなハイライトを入れる。
                     */
                    float highlightX =
                        -0.25f;


                    float highlightY =
                        0.25f;


                    float normalizedX =
                        dx / radius;


                    float normalizedY =
                        dy / radius;


                    float highlightDistance =
                        Vector2.Distance(
                            new Vector2(
                                normalizedX,
                                normalizedY
                            ),
                            new Vector2(
                                highlightX,
                                highlightY
                            )
                        );


                    float highlight =
                        Mathf.Clamp01(
                            1f
                            - highlightDistance
                            / 0.22f
                        );


                    alpha +=
                        highlight
                        * 0.45f;


                    alpha =
                        Mathf.Clamp01(
                            alpha
                        );


                    pixelColor =
                        new Color(
                            1f,
                            1f,
                            1f,
                            alpha
                        );
                }


                texture.SetPixel(
                    x,
                    y,
                    pixelColor
                );
            }
        }


        texture.Apply();


        return texture;
    }


    /// <summary>
    /// 泡用Materialを生成する。
    /// </summary>
    private Material CreateBubbleMaterial(
        Texture2D texture
    )
    {
        Shader shader =
            Shader.Find(
                "Sprites/Default"
            );


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Unlit/Transparent"
                );
        }


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Standard"
                );
        }


        if (shader == null)
        {
            Debug.LogError(
                "泡用Shaderが見つかりません。"
            );

            return null;
        }


        Material material =
            new Material(
                shader
            );


        material.name =
            "RuntimeCircularBubbleMaterial";


        material.mainTexture =
            texture;


        if (material.HasProperty(
                "_Color"
            ))
        {
            material.SetColor(
                "_Color",
                bubbleColor
            );
        }


        /*
         * Standard Shaderを使用した場合は
         * 半透明に設定する。
         */
        if (shader.name == "Standard")
        {
            material.SetFloat(
                "_Mode",
                3f
            );


            material.SetInt(
                "_SrcBlend",
                (int)
                UnityEngine.Rendering
                    .BlendMode
                    .SrcAlpha
            );


            material.SetInt(
                "_DstBlend",
                (int)
                UnityEngine.Rendering
                    .BlendMode
                    .OneMinusSrcAlpha
            );


            material.SetInt(
                "_ZWrite",
                0
            );


            material.DisableKeyword(
                "_ALPHATEST_ON"
            );


            material.EnableKeyword(
                "_ALPHABLEND_ON"
            );


            material.DisableKeyword(
                "_ALPHAPREMULTIPLY_ON"
            );


            material.renderQueue =
                3000;
        }


        return material;
    }


    /// <summary>
    /// 泡を上方向へ移動させる。
    /// 同時に少し左右へフワフワさせる。
    /// </summary>
    private void UpdateBubbles()
    {
        foreach (
            GameObject bubble
            in bubbles
        )
        {
            if (
                bubble == null
                || !bubble.activeSelf
            )
            {
                continue;
            }


            BubbleData bubbleData =
                bubble.GetComponent<BubbleData>();


            if (bubbleData == null)
            {
                continue;
            }


            bubbleData.timer +=
                Time.deltaTime;


            Vector3 position =
                bubble.transform.localPosition;


            /*
             * 上方向へ移動。
             */
            position.y +=
                bubbleData.speed
                * Time.deltaTime;


            /*
             * 左右へゆっくり揺れる。
             */
            float sway =
                Mathf.Sin(
                    bubbleData.timer
                    * bubbleData.swaySpeed
                )
                * bubbleData.swayAmount;


            position.x =
                bubbleData.baseX
                + sway;


            bubble.transform.localPosition =
                position;


            /*
             * 上まで行ったら
             * また下から出す。
             */
            if (
                position.y >= bubbleEndY
            )
            {
                ResetBubble(
                    bubble,
                    false
                );


                bubbleData.speed =
                    Random.Range(
                        minimumBubbleSpeed,
                        maximumBubbleSpeed
                    );


                bubbleData.swayAmount =
                    Random.Range(
                        minimumSwayAmount,
                        maximumSwayAmount
                    );


                bubbleData.swaySpeed =
                    Random.Range(
                        minimumSwaySpeed,
                        maximumSwaySpeed
                    );
            }
        }
    }


    /// <summary>
    /// 泡を飲み物の下側へ戻す。
    /// </summary>
    private void ResetBubble(
        GameObject bubble,
        bool randomizeY
    )
    {
        BubbleData bubbleData =
            bubble.GetComponent<BubbleData>();


        float randomX =
            Random.Range(
                -bubbleAreaWidth / 2f,
                bubbleAreaWidth / 2f
            );


        float startY =
            bubbleStartY;


        /*
         * 最初は泡を上下にばらけさせる。
         */
        if (randomizeY)
        {
            startY =
                Random.Range(
                    bubbleStartY,
                    bubbleEndY
                );
        }


        bubble.transform.localPosition =
            new Vector3(
                randomX,
                startY,
                -0.015f
            );


        if (bubbleData != null)
        {
            bubbleData.baseX =
                randomX;


            bubbleData.timer =
                Random.Range(
                    0f,
                    10f
                );
        }


        /*
         * 新しく下から出るたびに
         * 大きさも少しランダムに変更。
         */
        float newSize =
            Random.Range(
                minimumBubbleSize,
                maximumBubbleSize
            );


        bubble.transform.localScale =
            new Vector3(
                newSize,
                newSize,
                1f
            );
    }


    /// <summary>
    /// オブジェクトが無効になったら停止する。
    /// </summary>
    private void OnDisable()
    {
        isFizzing =
            false;


        foreach (
            GameObject bubble
            in bubbles
        )
        {
            if (bubble != null)
            {
                bubble.SetActive(
                    false
                );
            }
        }


        // ★追加：音も停止する
        if (audioSource != null)
        {
            audioSource.Stop();
        }
    }


    /// <summary>
    /// 実行時に生成したものを削除する。
    /// </summary>
    private void OnDestroy()
    {
        foreach (
            GameObject bubble
            in bubbles
        )
        {
            if (bubble != null)
            {
                Destroy(
                    bubble
                );
            }
        }


        bubbles.Clear();


        if (bubbleMaterial != null)
        {
            Destroy(
                bubbleMaterial
            );


            bubbleMaterial =
                null;
        }


        if (bubbleTexture != null)
        {
            Destroy(
                bubbleTexture
            );


            bubbleTexture =
                null;
        }
    }
}