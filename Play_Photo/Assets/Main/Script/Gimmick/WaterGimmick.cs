using System.Collections;
using UnityEngine;

public class WaterGimmick : MonoBehaviour, GimmickBase
{
    private AudioSource audioSource;

    private Renderer targetRenderer;

    [Header("波紋設定")]

    [SerializeField]
    private int rippleCount = 3;

    [SerializeField]
    private float rippleDuration = 1.0f;

    [SerializeField]
    private float rippleInterval = 0.15f;

    [SerializeField]
    private float rippleStartSize = 0.1f;

    [SerializeField]
    private float rippleEndSize = 1.2f;

    [SerializeField]
    private Color rippleColor =
        new Color(
            0.7f,
            0.9f,
            1f,
            0.8f
        );


    /// <summary>
    /// Reseiverから水の切り抜きRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// Reseiverから水の音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        audioSource = GetComponent<AudioSource>();

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

        if (clip == null)
        {
            Debug.LogError(
                "Reseiverから渡された水のAudioClipがnullです。"
            );

            return;
        }

        audioSource.clip = clip;

        Debug.Log(
            $"水の音声を設定しました：{clip.name}"
        );
    }


    /// <summary>
    /// 水をタッチしたとき
    /// 音を鳴らして波紋を出す
    /// </summary>
    public void ActivateMagic()
    {
        // 水音
        if (audioSource != null &&
            audioSource.clip != null)
        {
            audioSource.Stop();
            audioSource.Play();

            Debug.Log(
                $"水の音を再生しました：" +
                $"{audioSource.clip.name}"
            );
        }
        else
        {
            Debug.LogWarning(
                "水の音声が設定されていません。"
            );
        }


        // Rendererがまだなければ探す
        if (targetRenderer == null)
        {
            targetRenderer =
                GetComponentInChildren<Renderer>(true);
        }


        // 波紋開始
        StartCoroutine(
            CreateRippleSequence()
        );
    }


    /// <summary>
    /// 複数の波紋を時間差で出す
    /// </summary>
    private IEnumerator CreateRippleSequence()
    {
        for (
            int i = 0;
            i < rippleCount;
            i++
        )
        {
            StartCoroutine(
                CreateRipple()
            );

            yield return new WaitForSeconds(
                rippleInterval
            );
        }
    }


    /// <summary>
    /// 波紋を1つ生成する
    /// </summary>
    private IEnumerator CreateRipple()
    {
        GameObject ripple =
            GameObject.CreatePrimitive(
                PrimitiveType.Quad
            );

        ripple.name =
            "WaterRipple";


        // 水のオブジェクトの子にする
        ripple.transform.SetParent(
            transform,
            false
        );


        // 写真より少し手前
        ripple.transform.localPosition =
            new Vector3(
                0f,
                0f,
                -0.02f
            );

        ripple.transform.localRotation =
            Quaternion.identity;


        // 当たり判定はいらない
        Collider rippleCollider =
            ripple.GetComponent<Collider>();

        if (rippleCollider != null)
        {
            rippleCollider.enabled = false;

            Destroy(
                rippleCollider
            );
        }


        Renderer rippleRenderer =
            ripple.GetComponent<Renderer>();


        Material rippleMaterial =
            CreateRippleMaterial();


        if (rippleRenderer != null)
        {
            rippleRenderer.sharedMaterial =
                rippleMaterial;
        }


        float elapsedTime = 0f;


        while (
            elapsedTime < rippleDuration
        )
        {
            elapsedTime +=
                Time.deltaTime;


            float rate =
                Mathf.Clamp01(
                    elapsedTime /
                    rippleDuration
                );


            // 徐々に大きくする
            float size =
                Mathf.Lerp(
                    rippleStartSize,
                    rippleEndSize,
                    rate
                );


            ripple.transform.localScale =
                new Vector3(
                    size,
                    size,
                    1f
                );


            // 徐々に透明にする
            if (
                rippleMaterial != null &&
                rippleMaterial.HasProperty("_Color")
            )
            {
                Color currentColor =
                    rippleColor;

                currentColor.a =
                    Mathf.Lerp(
                        rippleColor.a,
                        0f,
                        rate
                    );


                rippleMaterial.SetColor(
                    "_Color",
                    currentColor
                );
            }


            yield return null;
        }


        // 後片付け
        if (rippleRenderer != null)
        {
            rippleRenderer.sharedMaterial = null;
        }


        Texture texture =
            rippleMaterial != null
                ? rippleMaterial.mainTexture
                : null;


        if (rippleMaterial != null)
        {
            Destroy(
                rippleMaterial
            );
        }


        if (texture != null)
        {
            Destroy(
                texture
            );
        }


        Destroy(
            ripple
        );
    }


    /// <summary>
    /// 波紋用Materialを生成
    /// </summary>
    private Material CreateRippleMaterial()
    {
        Shader shader =
            Shader.Find(
                "Sprites/Default"
            );


        if (shader == null)
        {
            Debug.LogError(
                "波紋用Shaderが見つかりません。"
            );

            return null;
        }


        Material material =
            new Material(
                shader
            );


        material.name =
            "RuntimeWaterRippleMaterial";


        Texture2D ringTexture =
            CreateRingTexture(
                128
            );


        material.mainTexture =
            ringTexture;


        if (
            material.HasProperty("_Color")
        )
        {
            material.SetColor(
                "_Color",
                rippleColor
            );
        }


        return material;
    }


    /// <summary>
    /// 輪っか状のTextureを生成
    /// </summary>
    private Texture2D CreateRingTexture(
        int size
    )
    {
        Texture2D texture =
            new Texture2D(
                size,
                size,
                TextureFormat.RGBA32,
                false
            );


        texture.name =
            "RuntimeWaterRippleTexture";

        texture.wrapMode =
            TextureWrapMode.Clamp;


        float center =
            (size - 1) / 2f;

        float radius =
            size * 0.4f;

        float ringWidth =
            size * 0.035f;


        for (
            int y = 0;
            y < size;
            y++
        )
        {
            for (
                int x = 0;
                x < size;
                x++
            )
            {
                float dx =
                    x - center;

                float dy =
                    y - center;


                float distance =
                    Mathf.Sqrt(
                        dx * dx +
                        dy * dy
                    );


                float difference =
                    Mathf.Abs(
                        distance - radius
                    );


                float alpha =
                    Mathf.Clamp01(
                        1f -
                        difference /
                        ringWidth
                    );


                Color color =
                    new Color(
                        1f,
                        1f,
                        1f,
                        alpha
                    );


                texture.SetPixel(
                    x,
                    y,
                    color
                );
            }
        }


        texture.Apply();


        return texture;
    }
}