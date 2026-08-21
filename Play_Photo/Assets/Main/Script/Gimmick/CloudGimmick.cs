using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 雲をタッチすると雨が降り続ける。
/// もう一度タッチすると雨が止まる。
///
/// 雨粒は小さめ・細め・半透明で、
/// 長さや速度をランダムにし、
/// 少し斜めに落ちる。
/// </summary>
public class CloudGimmick : MonoBehaviour, GimmickBase
{
    [Header("雨の設定")]

    [SerializeField]
    private int rainDropCount = 22;

    [SerializeField]
    private float rainAreaWidth = 1.0f;

    [SerializeField]
    private float rainStartY = -0.35f;

    [SerializeField]
    private float rainEndY = -1.8f;


    [Header("雨粒の速度")]

    [SerializeField]
    private float minimumRainSpeed = 2.0f;

    [SerializeField]
    private float maximumRainSpeed = 3.8f;


    [Header("雨粒の大きさ")]

    // 雨粒の最小の太さ
    [SerializeField]
    private float minimumRainWidth = 0.007f;

    // 雨粒の最大の太さ
    [SerializeField]
    private float maximumRainWidth = 0.014f;

    // 雨粒の最小の長さ
    [SerializeField]
    private float minimumRainLength = 0.12f;

    // 雨粒の最大の長さ
    [SerializeField]
    private float maximumRainLength = 0.22f;


    [Header("風による横移動")]

    [SerializeField]
    private float minimumWindSpeed = -0.12f;

    [SerializeField]
    private float maximumWindSpeed = -0.05f;


    [Header("雨の色")]

    // 薄い青白色＋半透明
    [SerializeField]
    private Color rainColor =
        new Color(
            0.72f,
            0.86f,
            1f,
            0.38f
        );


    private Renderer targetRenderer;

    private bool isRaining;


    private readonly List<GameObject> rainDrops =
        new List<GameObject>();


    /// <summary>
    /// 雨粒ごとの情報。
    /// </summary>
    private class RainDropData : MonoBehaviour
    {
        public float speed;

        public float windSpeed;
    }


    /// <summary>
    /// Reseiverから雲の切り抜きRendererを受け取る。
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
                "CloudGimmickのRendererが設定されていません。"
            );

            return;
        }
    }


    private void Update()
    {
        if (isRaining)
        {
            UpdateRain();
        }
    }


    /// <summary>
    /// 雲をタッチしたときに呼ばれる。
    ///
    /// 1回目：雨開始
    /// 2回目：雨停止
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
            return;
        }


        if (isRaining)
        {
            StopRain();
        }
        else
        {
            StartRain();
        }
    }


    /// <summary>
    /// 雨を開始する。
    /// </summary>
    private void StartRain()
    {
        isRaining =
            true;


        // 初回だけ雨粒を作成
        if (rainDrops.Count == 0)
        {
            CreateRainDrops();
        }


        // 雨粒を表示
        foreach (
            GameObject rainDrop
            in rainDrops
        )
        {
            if (rainDrop != null)
            {
                rainDrop.SetActive(
                    true
                );
            }
        }
    }


    /// <summary>
    /// 雨を停止する。
    /// </summary>
    private void StopRain()
    {
        isRaining =
            false;


        foreach (
            GameObject rainDrop
            in rainDrops
        )
        {
            if (rainDrop != null)
            {
                rainDrop.SetActive(
                    false
                );
            }
        }
    }


    /// <summary>
    /// 雨粒を生成する。
    /// </summary>
    private void CreateRainDrops()
    {
        for (
            int i = 0;
            i < rainDropCount;
            i++
        )
        {
            GameObject rainDrop =
                GameObject.CreatePrimitive(
                    PrimitiveType.Quad
                );


            rainDrop.name =
                "RainDrop_" + i;


            rainDrop.transform.SetParent(
                transform,
                false
            );


            /*
             * 雨粒には当たり判定が必要ないので
             * Colliderを削除する。
             */
            Collider rainCollider =
                rainDrop.GetComponent<Collider>();


            if (rainCollider != null)
            {
                rainCollider.enabled =
                    false;


                Destroy(
                    rainCollider
                );
            }


            /*
             * 雨粒ごとに太さをランダムにする。
             */
            float randomWidth =
                Random.Range(
                    minimumRainWidth,
                    maximumRainWidth
                );


            /*
             * 雨粒ごとに長さもランダムにする。
             */
            float randomLength =
                Random.Range(
                    minimumRainLength,
                    maximumRainLength
                );


            rainDrop.transform.localScale =
                new Vector3(
                    randomWidth,
                    randomLength,
                    1f
                );


            /*
             * 少しだけ斜めにする。
             * 真下に落ちるより自然な雨に見える。
             */
            rainDrop.transform.localRotation =
                Quaternion.Euler(
                    0f,
                    0f,
                    -4f
                );


            /*
             * 最初の位置を設定。
             */
            ResetRainDrop(
                rainDrop,
                true
            );


            /*
             * 雨粒のMaterialを設定。
             */
            Renderer rainRenderer =
                rainDrop.GetComponent<Renderer>();


            if (rainRenderer != null)
            {
                Material rainMaterial =
                    CreateRainMaterial();


                rainRenderer.sharedMaterial =
                    rainMaterial;
            }


            /*
             * 雨粒ごとの落下情報を設定。
             */
            RainDropData rainData =
                rainDrop.AddComponent<RainDropData>();


            rainData.speed =
                Random.Range(
                    minimumRainSpeed,
                    maximumRainSpeed
                );


            rainData.windSpeed =
                Random.Range(
                    minimumWindSpeed,
                    maximumWindSpeed
                );


            /*
             * 最初は非表示。
             */
            rainDrop.SetActive(
                false
            );


            rainDrops.Add(
                rainDrop
            );
        }
    }


    /// <summary>
    /// 雨粒用のMaterialを作る。
    /// </summary>
    private Material CreateRainMaterial()
    {
        Shader shader =
            Shader.Find(
                "Unlit/Color"
            );


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
                "雨粒用Shaderが見つかりません。"
            );

            return null;
        }


        Material material =
            new Material(
                shader
            );


        material.name =
            "RuntimeRainMaterial";


        /*
         * 雨粒の色を設定。
         */
        if (material.HasProperty("_Color"))
        {
            material.SetColor(
                "_Color",
                rainColor
            );
        }


        /*
         * Standard Shaderを使った場合は
         * 半透明になるように設定する。
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
    /// 雨粒を移動させる。
    /// </summary>
    private void UpdateRain()
    {
        foreach (
            GameObject rainDrop
            in rainDrops
        )
        {
            if (
                rainDrop == null
                || !rainDrop.activeSelf
            )
            {
                continue;
            }


            RainDropData rainData =
                rainDrop.GetComponent<RainDropData>();


            if (rainData == null)
            {
                continue;
            }


            Vector3 position =
                rainDrop.transform.localPosition;


            /*
             * 下方向へ落下。
             */
            position.y -=
                rainData.speed
                * Time.deltaTime;


            /*
             * 少しだけ横方向へ流す。
             */
            position.x +=
                rainData.windSpeed
                * Time.deltaTime;


            rainDrop.transform.localPosition =
                position;


            /*
             * 一番下まで落ちたら、
             * 雲の下へ戻して再利用する。
             */
            if (
                position.y <= rainEndY
            )
            {
                ResetRainDrop(
                    rainDrop,
                    false
                );


                /*
                 * 戻るたびに落下速度を
                 * 少しランダムに変更。
                 */
                rainData.speed =
                    Random.Range(
                        minimumRainSpeed,
                        maximumRainSpeed
                    );


                /*
                 * 風の強さも少し変える。
                 */
                rainData.windSpeed =
                    Random.Range(
                        minimumWindSpeed,
                        maximumWindSpeed
                    );
            }
        }
    }


    /// <summary>
    /// 雨粒を雲の下へ戻す。
    /// </summary>
    private void ResetRainDrop(
        GameObject rainDrop,
        bool randomizeY
    )
    {
        /*
         * 雨が横一列にならないよう、
         * X座標をランダムにする。
         */
        float randomX =
            Random.Range(
                -rainAreaWidth / 2f,
                rainAreaWidth / 2f
            );


        float startY =
            rainStartY;


        /*
         * 最初だけY座標をランダムにして、
         * 全ての雨粒が同時に出てくるのを防ぐ。
         */
        if (randomizeY)
        {
            startY =
                Random.Range(
                    rainEndY,
                    rainStartY
                );
        }


        rainDrop.transform.localPosition =
            new Vector3(
                randomX,
                startY,
                -0.01f
            );
    }


    /// <summary>
    /// オブジェクトが無効になった場合は
    /// 雨を停止する。
    /// </summary>
    private void OnDisable()
    {
        isRaining =
            false;


        foreach (
            GameObject rainDrop
            in rainDrops
        )
        {
            if (rainDrop != null)
            {
                rainDrop.SetActive(
                    false
                );
            }
        }
    }


    /// <summary>
    /// 生成した雨粒とMaterialを削除する。
    /// </summary>
    private void OnDestroy()
    {
        foreach (
            GameObject rainDrop
            in rainDrops
        )
        {
            if (rainDrop != null)
            {
                Renderer rainRenderer =
                    rainDrop.GetComponent<Renderer>();


                if (
                    rainRenderer != null
                    && rainRenderer.sharedMaterial != null
                )
                {
                    Destroy(
                        rainRenderer.sharedMaterial
                    );
                }


                Destroy(
                    rainDrop
                );
            }
        }


        rainDrops.Clear();
    }
}