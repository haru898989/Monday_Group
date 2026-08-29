using System.Collections;
using UnityEngine;

/// <summary>
/// ガラス・窓をタッチすると、
/// 検出された範囲いっぱいにヒビが広がり、
/// パリンという音と小さなガラス片を表示する。
///
/// 画像素材は使用しない。
/// </summary>
public class GlassGimmick : MonoBehaviour, GimmickBase
{
    // =========================
    // 揺れ
    // =========================

    [SerializeField]
    private float shakeDuration = 0.18f;

    [SerializeField]
    private float shakeAmount = 0.025f;


    // =========================
    // ヒビ
    // =========================

    // 中心から伸びるヒビの本数
    [SerializeField]
    private int crackLineCount = 10;

    // 線の太さ
    [SerializeField]
    private float crackWidth = 0.012f;

    // ヒビを表示しておく時間
    [SerializeField]
    private float crackDisplayTime = 0.4f;

    // ヒビの枝分かれ確率
    [SerializeField]
    [Range(0f, 1f)]
    private float branchChance = 0.55f;


    // =========================
    // ガラス片
    // =========================

    [SerializeField]
    private int shardCount = 10;

    [SerializeField]
    private float shardSpeed = 1.2f;

    [SerializeField]
    private float shardLifetime = 0.45f;


    // =========================
    // Receiverから受け取るもの
    // =========================

    private Renderer targetRenderer;

    private AudioClip glassBreakAudioClip;


    // =========================
    // 内部変数
    // =========================

    private AudioSource audioSource;

    private Material crackMaterial;
    private Material shardMaterial;

    private bool isActivated = false;


    // =========================
    // 初期化
    // =========================

    private void Awake()
    {
        audioSource =
            GetComponent<AudioSource>();

        if (audioSource == null)
        {
            audioSource =
                gameObject.AddComponent<AudioSource>();
        }

        audioSource.playOnAwake = false;
        audioSource.spatialBlend = 0f;


        // ヒビ用Material
        Shader spriteShader =
            Shader.Find("Sprites/Default");

        if (spriteShader != null)
        {
            crackMaterial =
                new Material(spriteShader);

            crackMaterial.name =
                "RuntimeGlassCrackMaterial";


            shardMaterial =
                new Material(spriteShader);

            shardMaterial.name =
                "RuntimeGlassShardMaterial";

            shardMaterial.color =
                new Color(
                    0.75f,
                    0.9f,
                    1f,
                    0.85f
                );
        }
    }


    // =========================
    // Receiverから設定
    // =========================

    /// <summary>
    /// 検出された窓のRendererを受け取る
    /// </summary>
    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }


    /// <summary>
    /// ガラスが割れる音を受け取る
    /// </summary>
    public void SetAudioClip(AudioClip clip)
    {
        glassBreakAudioClip = clip;
    }


    // =========================
    // ギミック発動
    // =========================

    public void ActivateMagic()
    {
        if (isActivated)
        {
            return;
        }

        isActivated = true;

        StartCoroutine(BreakGlass());
    }


    // =========================
    // ガラス割れ本体
    // =========================

    private IEnumerator BreakGlass()
    {
        Vector3 originalPosition =
            transform.position;


        // -------------------------
        // ① 一瞬揺れる
        // -------------------------

        float elapsedTime = 0f;


        while (elapsedTime < shakeDuration)
        {
            elapsedTime += Time.deltaTime;


            float shakeX =
                Random.Range(
                    -shakeAmount,
                    shakeAmount
                );


            float shakeY =
                Random.Range(
                    -shakeAmount,
                    shakeAmount
                );


            transform.position =
                originalPosition +
                new Vector3(
                    shakeX,
                    shakeY,
                    0f
                );


            yield return null;
        }


        transform.position =
            originalPosition;


        // -------------------------
        // ② パリン音
        // -------------------------

        if (audioSource != null &&
            glassBreakAudioClip != null)
        {
            audioSource.PlayOneShot(
                glassBreakAudioClip
            );
        }
        else
        {
            Debug.LogWarning(
                "GlassGimmick：割れる音が設定されていません。"
            );
        }


        // -------------------------
        // ③ ヒビを生成
        // -------------------------

        GameObject crackRoot =
            CreateCracks();


        // -------------------------
        // ④ 小さなガラス片
        // -------------------------

        CreateGlassShards();


        // -------------------------
        // ⑤ 少し表示
        // -------------------------

        yield return new WaitForSeconds(
            crackDisplayTime
        );


        // -------------------------
        // ⑥ ヒビを消す
        // -------------------------

        if (crackRoot != null)
        {
            Destroy(crackRoot);
        }


        isActivated = false;


        Debug.Log(
            "GlassGimmick：ガラス割れ演出終了"
        );
    }


    // =========================
    // 検出サイズに合わせてヒビを作る
    // =========================

    private GameObject CreateCracks()
    {
        GameObject crackRoot =
            new GameObject("GlassCracks");


        // ★重要
        // 検出オブジェクトの子にすることで、
        // Receiverが設定した検出サイズに自動追従する
        crackRoot.transform.SetParent(
            transform,
            false
        );


        // 写真より少し手前
        crackRoot.transform.localPosition =
            new Vector3(
                0f,
                0f,
                -0.05f
            );


        crackRoot.transform.localRotation =
            Quaternion.identity;


        crackRoot.transform.localScale =
            Vector3.one;


        // =========================
        // 中心から放射状にヒビ
        // =========================

        for (int i = 0;
             i < crackLineCount;
             i++)
        {
            CreateMainCrack(
                crackRoot.transform,
                i
            );
        }


        return crackRoot;
    }


    // =========================
    // メインのヒビ1本
    // =========================

    private void CreateMainCrack(
        Transform parent,
        int index
    )
    {
        GameObject crackObject =
            new GameObject(
                "Crack_" + index
            );


        crackObject.transform.SetParent(
            parent,
            false
        );


        LineRenderer line =
            crackObject.AddComponent<LineRenderer>();


        // ★ローカル座標で描画
        line.useWorldSpace = false;


        line.positionCount = 5;


        line.startWidth =
            crackWidth;


        line.endWidth =
            crackWidth * 0.2f;


        line.startColor =
            new Color(
                1f,
                1f,
                1f,
                1f
            );


        line.endColor =
            new Color(
                0.65f,
                0.85f,
                1f,
                0.3f
            );


        if (crackMaterial != null)
        {
            line.sharedMaterial =
                crackMaterial;
        }


        line.sortingOrder = 2000;


        // =========================
        // ヒビの方向
        // =========================

        float angle =
            (360f / crackLineCount) * index
            + Random.Range(
                -18f,
                18f
            );


        float rad =
            angle * Mathf.Deg2Rad;


        Vector2 direction =
            new Vector2(
                Mathf.Cos(rad),
                Mathf.Sin(rad)
            );


        // =========================
        // 検出範囲の端を計算
        // =========================

        Vector2 edgePoint =
            GetRectangleEdgePoint(
                direction
            );


        // 全部同じ長さだと人工的なので
        // 少しだけ短くする
        edgePoint *=
            Random.Range(
                0.78f,
                1f
            );


        Vector3 p0 =
            Vector3.zero;


        Vector3 p1 =
            new Vector3(
                edgePoint.x * 0.25f,
                edgePoint.y * 0.25f,
                0f
            );


        Vector3 p2 =
            new Vector3(
                edgePoint.x * 0.5f,
                edgePoint.y * 0.5f,
                0f
            );


        Vector3 p3 =
            new Vector3(
                edgePoint.x * 0.75f,
                edgePoint.y * 0.75f,
                0f
            );


        Vector3 p4 =
            new Vector3(
                edgePoint.x,
                edgePoint.y,
                0f
            );


        // =========================
        // ジグザグにする
        // =========================

        Vector3 perpendicular =
            new Vector3(
                -direction.y,
                direction.x,
                0f
            );


        p1 +=
            perpendicular *
            Random.Range(
                -0.035f,
                0.035f
            );


        p2 +=
            perpendicular *
            Random.Range(
                -0.05f,
                0.05f
            );


        p3 +=
            perpendicular *
            Random.Range(
                -0.035f,
                0.035f
            );


        p1 = ClampToDetectedArea(p1);
        p2 = ClampToDetectedArea(p2);
        p3 = ClampToDetectedArea(p3);
        p4 = ClampToDetectedArea(p4);


        line.SetPosition(0, p0);
        line.SetPosition(1, p1);
        line.SetPosition(2, p2);
        line.SetPosition(3, p3);
        line.SetPosition(4, p4);


        // =========================
        // 枝分かれ
        // =========================

        if (Random.value < branchChance)
        {
            CreateBranchCrack(
                parent,
                p2,
                direction
            );
        }


        if (Random.value < branchChance * 0.6f)
        {
            CreateBranchCrack(
                parent,
                p3,
                direction
            );
        }
    }


    // =========================
    // 枝分かれしたヒビ
    // =========================

    private void CreateBranchCrack(
        Transform parent,
        Vector3 startPoint,
        Vector2 originalDirection
    )
    {
        GameObject branchObject =
            new GameObject("BranchCrack");


        branchObject.transform.SetParent(
            parent,
            false
        );


        LineRenderer line =
            branchObject.AddComponent<LineRenderer>();


        line.useWorldSpace = false;


        line.positionCount = 3;


        line.startWidth =
            crackWidth * 0.6f;


        line.endWidth =
            crackWidth * 0.1f;


        line.startColor =
            new Color(
                1f,
                1f,
                1f,
                0.85f
            );


        line.endColor =
            new Color(
                0.65f,
                0.85f,
                1f,
                0.15f
            );


        if (crackMaterial != null)
        {
            line.sharedMaterial =
                crackMaterial;
        }


        line.sortingOrder = 2000;


        // 枝の角度
        float branchAngle =
            Random.Range(
                25f,
                65f
            );


        if (Random.value < 0.5f)
        {
            branchAngle *= -1f;
        }


        Vector2 branchDirection =
            Quaternion.Euler(
                0f,
                0f,
                branchAngle
            )
            * originalDirection;


        float length =
            Random.Range(
                0.08f,
                0.22f
            );


        Vector3 middle =
            startPoint +
            new Vector3(
                branchDirection.x,
                branchDirection.y,
                0f
            )
            * length
            * 0.5f;


        Vector3 end =
            startPoint +
            new Vector3(
                branchDirection.x,
                branchDirection.y,
                0f
            )
            * length;


        middle =
            ClampToDetectedArea(middle);


        end =
            ClampToDetectedArea(end);


        line.SetPosition(
            0,
            startPoint
        );


        line.SetPosition(
            1,
            middle
        );


        line.SetPosition(
            2,
            end
        );
    }


    // =========================
    // 四角形の端までの座標
    // =========================

    private Vector2 GetRectangleEdgePoint(
        Vector2 direction
    )
    {
        // Receiver側で検出サイズにScaleされているため、
        // ローカルではこの範囲が検出された窓全体になる
        const float halfWidth =
            0.5f;

        const float halfHeight =
            0.5f;


        float xDistance =
            Mathf.Abs(direction.x) > 0.0001f
                ? halfWidth /
                  Mathf.Abs(direction.x)
                : float.MaxValue;


        float yDistance =
            Mathf.Abs(direction.y) > 0.0001f
                ? halfHeight /
                  Mathf.Abs(direction.y)
                : float.MaxValue;


        float distance =
            Mathf.Min(
                xDistance,
                yDistance
            );


        return direction *
               distance;
    }


    // =========================
    // 検出範囲からヒビを出さない
    // =========================

    private Vector3 ClampToDetectedArea(
        Vector3 point
    )
    {
        point.x =
            Mathf.Clamp(
                point.x,
                -0.5f,
                0.5f
            );


        point.y =
            Mathf.Clamp(
                point.y,
                -0.5f,
                0.5f
            );


        return point;
    }


    // =========================
    // 小さなガラス片
    // =========================

    private void CreateGlassShards()
    {
        for (int i = 0;
             i < shardCount;
             i++)
        {
            GameObject shard =
                GameObject.CreatePrimitive(
                    PrimitiveType.Quad
                );


            shard.name =
                "GlassShard";


            // Colliderはいらない
            Collider shardCollider =
                shard.GetComponent<Collider>();


            if (shardCollider != null)
            {
                Destroy(shardCollider);
            }


            // 検出された窓の中心
            shard.transform.position =
                transform.position +
                new Vector3(
                    0f,
                    0f,
                    -0.1f
                );


            // ★検出サイズに合わせて
            // ガラス片の大きさを決める
            float detectedSize =
                Mathf.Min(
                    Mathf.Abs(
                        transform.lossyScale.x
                    ),
                    Mathf.Abs(
                        transform.lossyScale.y
                    )
                );


            float size =
                detectedSize *
                Random.Range(
                    0.015f,
                    0.035f
                );


            shard.transform.localScale =
                new Vector3(
                    size,
                    size *
                    Random.Range(
                        0.5f,
                        1.4f
                    ),
                    1f
                );


            shard.transform.rotation =
                Quaternion.Euler(
                    0f,
                    0f,
                    Random.Range(
                        0f,
                        360f
                    )
                );


            Renderer shardRenderer =
                shard.GetComponent<Renderer>();


            if (shardRenderer != null &&
                shardMaterial != null)
            {
                shardRenderer.sharedMaterial =
                    shardMaterial;

                shardRenderer.sortingOrder =
                    1900;
            }


            StartCoroutine(
                MoveShard(
                    shard,
                    detectedSize
                )
            );
        }
    }


    // =========================
    // ガラス片を飛ばす
    // =========================

    private IEnumerator MoveShard(
        GameObject shard,
        float detectedSize
    )
    {
        if (shard == null)
        {
            yield break;
        }


        Vector3 startPosition =
            shard.transform.position;


        Vector2 randomDirection =
            Random.insideUnitCircle;


        if (randomDirection.sqrMagnitude <
            0.001f)
        {
            randomDirection =
                Vector2.up;
        }


        randomDirection.Normalize();


        Vector3 direction =
            new Vector3(
                randomDirection.x,
                randomDirection.y,
                0f
            );


        float speed =
            shardSpeed *
            Mathf.Max(
                detectedSize,
                0.1f
            )
            * Random.Range(
                0.7f,
                1.3f
            );


        float elapsedTime = 0f;


        while (elapsedTime <
               shardLifetime)
        {
            elapsedTime +=
                Time.deltaTime;


            if (shard == null)
            {
                yield break;
            }


            Vector3 movement =
                direction *
                speed *
                elapsedTime;


            Vector3 gravity =
                Vector3.down *
                elapsedTime *
                elapsedTime *
                0.5f;


            shard.transform.position =
                startPosition +
                movement +
                gravity;


            shard.transform.Rotate(
                0f,
                0f,
                420f *
                Time.deltaTime
            );


            yield return null;
        }


        if (shard != null)
        {
            Destroy(shard);
        }
    }


    // =========================
    // 終了処理
    // =========================

    private void OnDestroy()
    {
        if (crackMaterial != null)
        {
            Destroy(crackMaterial);
            crackMaterial = null;
        }


        if (shardMaterial != null)
        {
            Destroy(shardMaterial);
            shardMaterial = null;
        }
    }
}