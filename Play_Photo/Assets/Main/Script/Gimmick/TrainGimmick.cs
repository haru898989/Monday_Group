using System.Collections;
using UnityEngine;

public class TrainGimmick : MonoBehaviour, GimmickBase
{
    // =========================================
    // 電車本体
    // =========================================
    private Renderer targetRenderer;


    // =========================================
    // 音
    // =========================================
    private AudioSource audioSource;
    private AudioClip trainAudioClip;


    // =========================================
    // Particle
    // =========================================
    private ParticleSystem smokeParticle;
    private ParticleSystem sparkParticle;


    // =========================================
    // 状態
    // =========================================
    private bool isRunning = false;


    // =========================================
    // 暴走時間
    // =========================================
    [SerializeField]
    private float runawayDuration = 7f;


    // =========================================
    // 揺れ設定
    // =========================================
    [SerializeField]
    private float startShake = 0.01f;

    [SerializeField]
    private float maxShake = 0.10f;

    [SerializeField]
    private float startShakeSpeed = 8f;

    [SerializeField]
    private float maxShakeSpeed = 40f;

    [SerializeField]
    private float maxTiltAngle = 8f;


    // =========================================
    // Rendererを受け取る
    // =========================================
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        Debug.Log("★ TrainGimmick設定成功");

        CreateSmoke();
        CreateSparks();
    }


    // =========================================
    // 音声を受け取る
    // =========================================
    public void SetAudioClip(AudioClip clip)
    {
        trainAudioClip = clip;

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

        if (trainAudioClip != null)
        {
            Debug.Log("★ 電車の音声設定成功");
        }
        else
        {
            Debug.LogWarning(
                "★ trainAudioClipがNULLです"
            );
        }
    }


    // =========================================
    // 煙Particle作成
    // =========================================
    private void CreateSmoke()
    {
        if (smokeParticle != null)
        {
            return;
        }


        // =====================================
        // GameObject作成
        // =====================================
        GameObject smokeObject =
            new GameObject(
                "TrainSmoke"
            );

        smokeObject.transform.SetParent(
            transform
        );


        // 電車の下あたり
        smokeObject.transform.localPosition =
            new Vector3(
                0f,
                -0.35f,
                -0.5f
            );

        smokeObject.transform.localRotation =
            Quaternion.identity;

        smokeObject.transform.localScale =
            Vector3.one;


        // =====================================
        // ParticleSystem追加
        // =====================================
        smokeParticle =
            smokeObject.AddComponent<
                ParticleSystem
            >();


        // =====================================
        // Main
        // =====================================
        var main =
            smokeParticle.main;

        main.loop = true;

        main.playOnAwake = false;


        // 煙の寿命
        main.startLifetime =
            new ParticleSystem.MinMaxCurve(
                1f,
                2f
            );


        // 煙のサイズ
        main.startSize =
            new ParticleSystem.MinMaxCurve(
                0.15f,
                0.35f
            );


        // 煙の初速
        main.startSpeed =
            new ParticleSystem.MinMaxCurve(
                0.2f,
                0.7f
            );


        // 煙の色
        main.startColor =
            new ParticleSystem.MinMaxGradient(
                new Color(
                    0.15f,
                    0.15f,
                    0.15f,
                    0.9f
                ),

                new Color(
                    0.55f,
                    0.55f,
                    0.55f,
                    0.7f
                )
            );


        // 少し上へ
        main.gravityModifier =
            -0.15f;


        // 世界座標
        main.simulationSpace =
            ParticleSystemSimulationSpace.World;


        main.maxParticles =
            500;


        // =====================================
        // Emission
        // =====================================
        var emission =
            smokeParticle.emission;

        emission.enabled =
            true;

        emission.rateOverTime =
            80f;


        // =====================================
        // Shape
        // =====================================
        var shape =
            smokeParticle.shape;

        shape.enabled =
            true;

        shape.shapeType =
            ParticleSystemShapeType.Box;


        // 電車の下全体から出す
        shape.scale =
            new Vector3(
                1.5f,
                0.05f,
                0.05f
            );


        // =====================================
        // Velocity Over Lifetime
        // =====================================
        var velocity =
            smokeParticle
                .velocityOverLifetime;

        velocity.enabled =
            true;

        velocity.space =
            ParticleSystemSimulationSpace.World;


        // ★X・Y・Z全部MinMaxCurveに統一
        velocity.x =
            new ParticleSystem.MinMaxCurve(
                -0.15f,
                0.15f
            );

        velocity.y =
            new ParticleSystem.MinMaxCurve(
                0.3f,
                0.8f
            );

        velocity.z =
            new ParticleSystem.MinMaxCurve(
                0f,
                0f
            );


        // =====================================
        // Color Over Lifetime
        // =====================================
        var colorOverLifetime =
            smokeParticle
                .colorOverLifetime;

        colorOverLifetime.enabled =
            true;


        Gradient smokeGradient =
            new Gradient();


        smokeGradient.SetKeys(

            new GradientColorKey[]
            {
                new GradientColorKey(
                    new Color(
                        0.25f,
                        0.25f,
                        0.25f
                    ),
                    0f
                ),

                new GradientColorKey(
                    new Color(
                        0.6f,
                        0.6f,
                        0.6f
                    ),
                    1f
                )
            },

            new GradientAlphaKey[]
            {
                new GradientAlphaKey(
                    0.9f,
                    0f
                ),

                new GradientAlphaKey(
                    0.5f,
                    0.5f
                ),

                new GradientAlphaKey(
                    0f,
                    1f
                )
            }
        );


        colorOverLifetime.color =
            smokeGradient;


        // =====================================
        // Size Over Lifetime
        // =====================================
        var sizeOverLifetime =
            smokeParticle
                .sizeOverLifetime;

        sizeOverLifetime.enabled =
            true;


        AnimationCurve smokeSizeCurve =
            new AnimationCurve();

        smokeSizeCurve.AddKey(
            0f,
            0.4f
        );

        smokeSizeCurve.AddKey(
            0.4f,
            1f
        );

        smokeSizeCurve.AddKey(
            1f,
            1.5f
        );


        sizeOverLifetime.size =
            new ParticleSystem.MinMaxCurve(
                1f,
                smokeSizeCurve
            );


        // =====================================
        // Noise
        // =====================================
        var noise =
            smokeParticle.noise;

        noise.enabled =
            true;

        noise.strength =
            0.15f;

        noise.frequency =
            1.2f;

        noise.scrollSpeed =
            0.4f;


        // =====================================
        // Renderer
        // =====================================
        ParticleSystemRenderer psRenderer =
            smokeObject.GetComponent<
                ParticleSystemRenderer
            >();


        psRenderer.renderMode =
            ParticleSystemRenderMode.Billboard;


        Shader shader =
            Shader.Find(
                "Particles/Standard Unlit"
            );


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Universal Render Pipeline/Particles/Unlit"
                );
        }


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Sprites/Default"
                );
        }


        if (shader != null)
        {
            Material material =
                new Material(shader);

            material.color =
                Color.white;

            psRenderer.material =
                material;

            Debug.Log(
                "★ 煙Material成功：" +
                shader.name
            );
        }
        else
        {
            Debug.LogError(
                "★ 煙用Shaderが見つかりません"
            );
        }


        // 電車より手前
        if (targetRenderer != null)
        {
            psRenderer.sortingLayerID =
                targetRenderer.sortingLayerID;

            psRenderer.sortingOrder =
                targetRenderer.sortingOrder
                + 20;
        }
        else
        {
            psRenderer.sortingOrder =
                100;
        }


        // =====================================
        // 最初は停止
        // =====================================
        smokeParticle.Stop(
            true,
            ParticleSystemStopBehavior
                .StopEmittingAndClear
        );


        Debug.Log(
            "★ 煙Particle作成完了"
        );
    }


    // =========================================
    // 火花Particle作成
    // =========================================
    private void CreateSparks()
    {
        if (sparkParticle != null)
        {
            return;
        }


        // =====================================
        // GameObject作成
        // =====================================
        GameObject sparkObject =
            new GameObject(
                "TrainSparks"
            );


        sparkObject.transform.SetParent(
            transform
        );


        // 電車の車輪付近
        sparkObject.transform.localPosition =
            new Vector3(
                0f,
                -0.38f,
                -0.6f
            );


        sparkObject.transform.localRotation =
            Quaternion.identity;

        sparkObject.transform.localScale =
            Vector3.one;


        // =====================================
        // ParticleSystem
        // =====================================
        sparkParticle =
            sparkObject.AddComponent<
                ParticleSystem
            >();


        // =====================================
        // Main
        // =====================================
        var main =
            sparkParticle.main;

        main.loop =
            true;

        main.playOnAwake =
            false;


        // 火花寿命
        main.startLifetime =
            new ParticleSystem.MinMaxCurve(
                0.2f,
                0.6f
            );


        // 火花サイズ
        main.startSize =
            new ParticleSystem.MinMaxCurve(
                0.03f,
                0.09f
            );


        // 初速
        main.startSpeed =
            new ParticleSystem.MinMaxCurve(
                1f,
                3f
            );


        // 色
        main.startColor =
            new ParticleSystem.MinMaxGradient(
                new Color(
                    1f,
                    1f,
                    0.2f,
                    1f
                ),

                new Color(
                    1f,
                    0.25f,
                    0f,
                    1f
                )
            );


        // 下に落とす
        main.gravityModifier =
            0.8f;


        main.simulationSpace =
            ParticleSystemSimulationSpace.World;


        main.maxParticles =
            1000;


        // =====================================
        // Emission
        // =====================================
        var emission =
            sparkParticle.emission;

        emission.enabled =
            true;

        emission.rateOverTime =
            150f;


        // =====================================
        // Shape
        // =====================================
        var shape =
            sparkParticle.shape;

        shape.enabled =
            true;

        shape.shapeType =
            ParticleSystemShapeType.Box;


        // 電車下部全体
        shape.scale =
            new Vector3(
                1.4f,
                0.03f,
                0.03f
            );


        // =====================================
        // Velocity Over Lifetime
        // =====================================
        var velocity =
            sparkParticle
                .velocityOverLifetime;

        velocity.enabled =
            true;

        velocity.space =
            ParticleSystemSimulationSpace.World;


        // ★3軸ともMinMaxCurveに統一
        velocity.x =
            new ParticleSystem.MinMaxCurve(
                -0.8f,
                0.8f
            );

        velocity.y =
            new ParticleSystem.MinMaxCurve(
                -0.2f,
                0.5f
            );

        velocity.z =
            new ParticleSystem.MinMaxCurve(
                0f,
                0f
            );


        // =====================================
        // Color Over Lifetime
        // =====================================
        var colorOverLifetime =
            sparkParticle
                .colorOverLifetime;

        colorOverLifetime.enabled =
            true;


        Gradient sparkGradient =
            new Gradient();


        sparkGradient.SetKeys(

            new GradientColorKey[]
            {
                new GradientColorKey(
                    new Color(
                        1f,
                        1f,
                        0.3f
                    ),
                    0f
                ),

                new GradientColorKey(
                    new Color(
                        1f,
                        0.1f,
                        0f
                    ),
                    1f
                )
            },

            new GradientAlphaKey[]
            {
                new GradientAlphaKey(
                    1f,
                    0f
                ),

                new GradientAlphaKey(
                    0.8f,
                    0.3f
                ),

                new GradientAlphaKey(
                    0f,
                    1f
                )
            }
        );


        colorOverLifetime.color =
            sparkGradient;


        // =====================================
        // Renderer
        // =====================================
        ParticleSystemRenderer psRenderer =
            sparkObject.GetComponent<
                ParticleSystemRenderer
            >();


        psRenderer.renderMode =
            ParticleSystemRenderMode.Stretch;


        psRenderer.velocityScale =
            0.2f;

        psRenderer.lengthScale =
            2f;


        Shader shader =
            Shader.Find(
                "Particles/Standard Unlit"
            );


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Universal Render Pipeline/Particles/Unlit"
                );
        }


        if (shader == null)
        {
            shader =
                Shader.Find(
                    "Sprites/Default"
                );
        }


        if (shader != null)
        {
            Material material =
                new Material(shader);

            material.color =
                Color.white;

            psRenderer.material =
                material;

            Debug.Log(
                "★ 火花Material成功：" +
                shader.name
            );
        }
        else
        {
            Debug.LogError(
                "★ 火花用Shaderが見つかりません"
            );
        }


        // 電車より手前
        if (targetRenderer != null)
        {
            psRenderer.sortingLayerID =
                targetRenderer.sortingLayerID;

            psRenderer.sortingOrder =
                targetRenderer.sortingOrder
                + 30;
        }
        else
        {
            psRenderer.sortingOrder =
                110;
        }


        // 最初は停止
        sparkParticle.Stop(
            true,
            ParticleSystemStopBehavior
                .StopEmittingAndClear
        );


        Debug.Log(
            "★ 火花Particle作成完了"
        );
    }


    // =========================================
    // 電車タップ
    // =========================================
    public void ActivateMagic()
    {
        if (isRunning)
        {
            return;
        }


        Debug.Log(
            "★ 暴走電車スタート！"
        );


        StartCoroutine(
            RunawayTrain()
        );
    }


    // =========================================
    // 暴走本体
    // =========================================
    private IEnumerator RunawayTrain()
    {
        isRunning =
            true;


        Vector3 originalPosition =
            transform.position;


        Quaternion originalRotation =
            transform.rotation;


        float timer =
            0f;


        // =====================================
        // 踏切音
        // =====================================
        if (
            audioSource != null &&
            trainAudioClip != null
        )
        {
            audioSource.PlayOneShot(
                trainAudioClip
            );

            Debug.Log(
                "★ 踏切音START"
            );
        }
        else
        {
            Debug.LogWarning(
                "★ 踏切音を再生できません"
            );
        }


        // =====================================
        // 煙START
        // =====================================
        if (smokeParticle != null)
        {
            smokeParticle.Play();

            Debug.Log(
                "★ 煙START"
            );
        }
        else
        {
            Debug.LogError(
                "★ smokeParticleがNULLです"
            );
        }


        // =====================================
        // 暴走中
        // =====================================
        while (
            timer <
            runawayDuration
        )
        {
            timer +=
                Time.deltaTime;


            // 0～1
            float progress =
                Mathf.Clamp01(
                    timer /
                    runawayDuration
                );


            // =================================
            // 徐々に揺れを強く
            // =================================
            float currentShake =
                Mathf.Lerp(
                    startShake,
                    maxShake,
                    progress
                );


            float currentShakeSpeed =
                Mathf.Lerp(
                    startShakeSpeed,
                    maxShakeSpeed,
                    progress
                );


            // =================================
            // 上下の揺れ
            // =================================
            float yShake =
                Mathf.Sin(
                    timer *
                    currentShakeSpeed
                )
                *
                currentShake;


            // =================================
            // 左右の揺れ
            // =================================
            float xShake =
                Mathf.Cos(
                    timer *
                    currentShakeSpeed *
                    1.3f
                )
                *
                currentShake
                *
                0.5f;


            transform.position =
                originalPosition +
                new Vector3(
                    xShake,
                    yShake,
                    0f
                );


            // =================================
            // 電車をガタガタ傾ける
            // =================================
            float tilt =
                Mathf.Sin(
                    timer *
                    currentShakeSpeed *
                    0.9f
                )
                *
                maxTiltAngle
                *
                progress;


            transform.rotation =
                originalRotation *
                Quaternion.Euler(
                    0f,
                    0f,
                    tilt
                );


            // =================================
            // 約40％で火花開始
            // =================================
            if (
                progress >= 0.4f &&
                sparkParticle != null &&
                !sparkParticle.isPlaying
            )
            {
                sparkParticle.Play();

                Debug.Log(
                    "★ 火花START"
                );
            }


            // =================================
            // 後半は煙をさらに増やす
            // =================================
            if (smokeParticle != null)
            {
                var smokeEmission =
                    smokeParticle.emission;


                smokeEmission.rateOverTime =
                    Mathf.Lerp(
                        40f,
                        140f,
                        progress
                    );
            }


            // =================================
            // 後半は火花も増やす
            // =================================
            if (
                sparkParticle != null &&
                sparkParticle.isPlaying
            )
            {
                var sparkEmission =
                    sparkParticle.emission;


                sparkEmission.rateOverTime =
                    Mathf.Lerp(
                        70f,
                        250f,
                        progress
                    );
            }


            yield return null;
        }


        // =====================================
        // 最後の暴走MAX
        // =====================================
        Debug.Log(
            "★ 暴走MAX！！！"
        );


        float maxTimer =
            0f;


        while (maxTimer < 1f)
        {
            maxTimer +=
                Time.deltaTime;


            // ランダムに激しく揺らす
            float crazyX =
                Random.Range(
                    -0.08f,
                    0.08f
                );


            float crazyY =
                Random.Range(
                    -0.12f,
                    0.12f
                );


            transform.position =
                originalPosition +
                new Vector3(
                    crazyX,
                    crazyY,
                    0f
                );


            float crazyTilt =
                Random.Range(
                    -10f,
                    10f
                );


            transform.rotation =
                originalRotation *
                Quaternion.Euler(
                    0f,
                    0f,
                    crazyTilt
                );


            yield return null;
        }


        // =====================================
        // Particle停止
        // =====================================
        if (smokeParticle != null)
        {
            smokeParticle.Stop(
                true,
                ParticleSystemStopBehavior
                    .StopEmitting
            );
        }


        if (sparkParticle != null)
        {
            sparkParticle.Stop(
                true,
                ParticleSystemStopBehavior
                    .StopEmitting
            );
        }


        // =====================================
        // 元の位置に戻す
        // =====================================
        transform.position =
            originalPosition;


        transform.rotation =
            originalRotation;


        Debug.Log(
            "★ 暴走電車終了！元に戻りました"
        );


        isRunning =
            false;
    }


    // =========================================
    // 削除時
    // =========================================
    private void OnDestroy()
    {
        if (smokeParticle != null)
        {
            smokeParticle.Stop();
        }


        if (sparkParticle != null)
        {
            sparkParticle.Stop();
        }
    }
}