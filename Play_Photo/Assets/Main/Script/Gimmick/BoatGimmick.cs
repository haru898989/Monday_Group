using System.Collections;
using UnityEngine;

public class BoatGimmick : MonoBehaviour, GimmickBase
{
    // =========================================
    // 船の見た目
    // =========================================
    private Renderer targetRenderer;


    // =========================================
    // 水しぶき
    // =========================================
    private ParticleSystem splashParticle;


    // =========================================
    // 音
    // =========================================
    private AudioSource audioSource;
    private AudioClip boatAudioClip;


    // =========================================
    // 状態
    // =========================================
    private bool isMoving = false;


    // =========================================
    // 船の移動設定
    // =========================================

    [SerializeField]
    private float moveSpeed = 1.5f;

    [SerializeField]
    private float acceleration = 0.8f;

    [SerializeField]
    private float moveDuration = 4f;


    // =========================================
    // 波の設定
    // =========================================

    [SerializeField]
    private float waveHeight = 0.08f;

    [SerializeField]
    private float waveSpeed = 5f;

    [SerializeField]
    private float tiltAngle = 5f;


    // =========================================
    // ReseiverからRendererを受け取る
    // =========================================

    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;

        Debug.Log(
            "★ BoatGimmick SetTargetRenderer"
        );

        CreateSplashParticle();
    }


    // =========================================
    // Reseiverから船の音を受け取る
    // =========================================

    public void SetAudioClip(AudioClip clip)
    {
        boatAudioClip = clip;


        // AudioSourceを探す
        audioSource =
            GetComponent<AudioSource>();


        // 無ければ自動で追加
        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }


        // ゲーム開始時に勝手に鳴らさない
        audioSource.playOnAwake =
            false;


        // 2D音声
        // カメラとの距離に関係なく聞こえる
        audioSource.spatialBlend =
            0f;


        // 音量
        audioSource.volume =
            1f;


        if (boatAudioClip != null)
        {
            Debug.Log(
                "★ 船の音声設定成功"
            );
        }
        else
        {
            Debug.LogWarning(
                "★ boatAudioClipがNULLです"
            );
        }
    }


    // =========================================
    // 水しぶきParticleを作る
    // =========================================

    private void CreateSplashParticle()
    {
        // すでに作成済みなら作らない
        if (splashParticle != null)
        {
            return;
        }


        // =====================================
        // 水しぶき用GameObject
        // =====================================

        GameObject splashObject =
            new GameObject(
                "BoatSplash"
            );


        splashObject.transform.SetParent(
            transform
        );


        // =====================================
        // 船の左下に配置
        // 船が右へ進むので左側が後ろ
        // =====================================

        splashObject.transform.localPosition =
            new Vector3(
                -0.45f,
                -0.18f,
                -0.2f
            );


        // 左斜め上方向
        splashObject.transform.localRotation =
            Quaternion.Euler(
                0f,
                -90f,
                -15f
            );


        splashObject.transform.localScale =
            Vector3.one;


        // =====================================
        // ParticleSystem追加
        // =====================================

        splashParticle =
            splashObject.AddComponent<
                ParticleSystem
            >();


        // =====================================
        // Main
        // =====================================

        var main =
            splashParticle.main;


        main.loop =
            true;


        main.playOnAwake =
            false;


        // -----------------------------
        // 水滴の寿命
        // -----------------------------

        main.startLifetime =
            new ParticleSystem.MinMaxCurve(
                0.35f,
                0.9f
            );


        // -----------------------------
        // 水滴のサイズ
        // -----------------------------

        main.startSize =
            new ParticleSystem.MinMaxCurve(
                0.025f,
                0.11f
            );


        // -----------------------------
        // 水滴の初速
        // -----------------------------

        main.startSpeed =
            new ParticleSystem.MinMaxCurve(
                0.8f,
                2.2f
            );


        // -----------------------------
        // 水滴の色
        // 白〜薄い水色
        // -----------------------------

        main.startColor =
            new ParticleSystem.MinMaxGradient(
                new Color(
                    0.78f,
                    0.92f,
                    1f,
                    0.9f
                ),

                new Color(
                    1f,
                    1f,
                    1f,
                    1f
                )
            );


        // -----------------------------
        // 重力
        // -----------------------------

        main.gravityModifier =
            0.65f;


        // -----------------------------
        // World空間
        // 船が進んでも水滴は
        // 出た場所に少し残る
        // -----------------------------

        main.simulationSpace =
            ParticleSystemSimulationSpace.World;


        main.maxParticles =
            500;


        // =====================================
        // Emission
        // =====================================

        var emission =
            splashParticle.emission;


        emission.enabled =
            true;


        // 水滴の量
        emission.rateOverTime =
            55f;


        // =====================================
        // Shape
        // =====================================

        var shape =
            splashParticle.shape;


        shape.enabled =
            true;


        // 円錐状に飛ばす
        shape.shapeType =
            ParticleSystemShapeType.Cone;


        // 広がり
        shape.angle =
            18f;


        // 発射口
        shape.radius =
            0.04f;


        // Coneの長さ
        shape.length =
            0.15f;


        // =====================================
        // Velocity Over Lifetime
        //
        // 水滴を
        // 後ろ＋上へ飛ばす
        // =====================================

        var velocity =
            splashParticle
                .velocityOverLifetime;


        velocity.enabled =
            true;


        velocity.space =
            ParticleSystemSimulationSpace.World;


        // 船が右へ進むので
        // 水滴は左へ
        velocity.x =
            new ParticleSystem.MinMaxCurve(
                -0.8f,
                -0.2f
            );


        // 上方向にも散らす
        velocity.y =
            new ParticleSystem.MinMaxCurve(
                0.15f,
                0.65f
            );


        // 奥行き方向にも少し
        velocity.z =
            new ParticleSystem.MinMaxCurve(
                -0.05f,
                0.05f
            );


        // =====================================
        // Size Over Lifetime
        //
        // 小さい
        // ↓
        // 一瞬大きくなる
        // ↓
        // 小さくなって消える
        // =====================================

        var sizeOverLifetime =
            splashParticle
                .sizeOverLifetime;


        sizeOverLifetime.enabled =
            true;


        AnimationCurve sizeCurve =
            new AnimationCurve();


        // 発生直後
        sizeCurve.AddKey(
            0f,
            0.4f
        );


        // 一瞬大きく
        sizeCurve.AddKey(
            0.15f,
            1f
        );


        // 最後は小さく
        sizeCurve.AddKey(
            1f,
            0f
        );


        sizeOverLifetime.size =
            new ParticleSystem.MinMaxCurve(
                1f,
                sizeCurve
            );


        // =====================================
        // Color Over Lifetime
        //
        // 徐々に透明にする
        // =====================================

        var colorOverLifetime =
            splashParticle
                .colorOverLifetime;


        colorOverLifetime.enabled =
            true;


        Gradient gradient =
            new Gradient();


        gradient.SetKeys(

            new GradientColorKey[]
            {
                new GradientColorKey(
                    Color.white,
                    0f
                ),

                new GradientColorKey(
                    new Color(
                        0.7f,
                        0.9f,
                        1f
                    ),
                    1f
                )
            },

            new GradientAlphaKey[]
            {
                new GradientAlphaKey(
                    0.95f,
                    0f
                ),

                new GradientAlphaKey(
                    0.65f,
                    0.5f
                ),

                new GradientAlphaKey(
                    0f,
                    1f
                )
            }
        );


        colorOverLifetime.color =
            gradient;


        // =====================================
        // Noise
        //
        // 水滴を少し不規則に動かす
        // =====================================

        var noise =
            splashParticle.noise;


        noise.enabled =
            true;


        noise.strength =
            0.12f;


        noise.frequency =
            1.5f;


        noise.scrollSpeed =
            0.5f;


        // =====================================
        // Particle Renderer
        // =====================================

        ParticleSystemRenderer psRenderer =
            splashObject.GetComponent<
                ParticleSystemRenderer
            >();


        psRenderer.renderMode =
            ParticleSystemRenderMode.Billboard;


        // =====================================
        // Particle用Material
        // =====================================

        Shader shader =
            Shader.Find(
                "Sprites/Default"
            );


        if (shader == null)
        {
            Debug.LogError(
                "★ Sprites/Default Shaderが見つかりません"
            );
        }
        else
        {
            Material material =
                new Material(
                    shader
                );


            material.color =
                Color.white;


            psRenderer.material =
                material;


            Debug.Log(
                "★ 水しぶきMaterial作成成功"
            );
        }


        // =====================================
        // 船より手前に表示
        // =====================================

        if (targetRenderer != null)
        {
            psRenderer.sortingLayerID =
                targetRenderer.sortingLayerID;


            psRenderer.sortingOrder =
                targetRenderer.sortingOrder
                + 10;
        }


        // =====================================
        // 最初は停止
        // =====================================

        splashParticle.Stop(
            true,
            ParticleSystemStopBehavior
                .StopEmittingAndClear
        );


        Debug.Log(
            "★ リアル水しぶきParticle作成完了"
        );
    }


    // =========================================
    // 船をタップした時
    // =========================================

    public void ActivateMagic()
    {
        Debug.Log(
            "★ 船がタップされました"
        );


        // すでに動いていたら無視
        if (isMoving)
        {
            return;
        }


        StartCoroutine(
            SailAway()
        );
    }


    // =========================================
    // 船が航海する
    // =========================================

    private IEnumerator SailAway()
    {
        isMoving =
            true;


        // =====================================
        // ★ 船の音を再生
        // =====================================

        if (
            audioSource != null &&
            boatAudioClip != null
        )
        {
            audioSource.PlayOneShot(
                boatAudioClip
            );


            Debug.Log(
                "★ 船の音を再生しました"
            );
        }
        else
        {
            Debug.LogWarning(
                "★ 船の音を再生できません"
            );
        }


        Vector3 basePosition =
            transform.position;


        Quaternion startRotation =
            transform.rotation;


        float timer =
            0f;


        float currentSpeed =
            moveSpeed;


        // =====================================
        // 水しぶき開始
        // =====================================

        if (splashParticle != null)
        {
            splashParticle.Play();


            Debug.Log(
                "★ 水しぶきSTART"
            );
        }
        else
        {
            Debug.LogError(
                "★ splashParticleがNULL"
            );
        }


        // =====================================
        // 船を動かす
        // =====================================

        while (timer < moveDuration)
        {
            timer +=
                Time.deltaTime;


            // =================================
            // 徐々に加速
            // =================================

            currentSpeed +=
                acceleration *
                Time.deltaTime;


            // =================================
            // 右へ進む
            // =================================

            basePosition +=
                Vector3.right *
                currentSpeed *
                Time.deltaTime;


            // =================================
            // 波
            // =================================

            float wave =
                Mathf.Sin(
                    timer *
                    waveSpeed
                );


            // =================================
            // 上下に揺れる
            // =================================

            float yOffset =
                wave *
                waveHeight;


            transform.position =
                basePosition +
                Vector3.up *
                yOffset;


            // =================================
            // 左右に傾く
            // =================================

            float angle =
                wave *
                tiltAngle;


            transform.rotation =
                startRotation *
                Quaternion.Euler(
                    0f,
                    0f,
                    angle
                );


            yield return null;
        }


        // =====================================
        // 水しぶき停止
        //
        // すでに出ている水滴は
        // 自然に消えるまで残す
        // =====================================

        if (splashParticle != null)
        {
            splashParticle.Stop(
                true,
                ParticleSystemStopBehavior
                    .StopEmitting
            );


            Debug.Log(
                "★ 水しぶきSTOP"
            );
        }


        // =====================================
        // 船を消す
        // =====================================

        if (targetRenderer != null)
        {
            targetRenderer.enabled =
                false;
        }


        // =====================================
        // Colliderを無効化
        // =====================================

        Collider[] colliders =
            GetComponentsInChildren<
                Collider
            >();


        foreach (
            Collider col
            in colliders
        )
        {
            col.enabled =
                false;
        }


        Debug.Log(
            "★ 船が水しぶきを上げながら航海しました！"
        );


        isMoving =
            false;
    }


    // =========================================
    // オブジェクト削除時
    // =========================================

    private void OnDestroy()
    {
        if (splashParticle != null)
        {
            splashParticle.Stop();
        }
    }
}