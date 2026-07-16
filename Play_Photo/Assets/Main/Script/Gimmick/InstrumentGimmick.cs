using UnityEngine;

// このスクリプトを追加したとき、
// AudioSourceとParticleSystemも自動的に追加する
[RequireComponent(typeof(AudioSource))]
[RequireComponent(typeof(ParticleSystem))]
public class InstrumentGimmick : MonoBehaviour, GimmickBase
{
    // 楽器の音を再生するコンポーネント
    private AudioSource audioSource_;

    // 音符のような粒を出すパーティクル
    private ParticleSystem noteEffect_;

    // 音符画像を設定したマテリアル
    // 設定しなければ、普通の丸い粒が表示される
    [SerializeField]
    private Material noteMaterial;

    // オブジェクトが読み込まれたときに実行
    private void Awake()
    {
        // 同じオブジェクトのAudioSourceを取得
        audioSource_ = GetComponent<AudioSource>();

        // 同じオブジェクトのParticleSystemを取得
        noteEffect_ = GetComponent<ParticleSystem>();

        // ゲーム開始時に勝手に音を鳴らさない
        audioSource_.playOnAwake = false;

        // パーティクルの設定
        SetupParticle();

        // ゲーム開始時に勝手に粒を出さない
        noteEffect_.Stop(
            true,
            ParticleSystemStopBehavior.StopEmittingAndClear
        );
    }

    // パーティクルの見た目や動きを設定する
    private void SetupParticle()
    {
        // Particle Systemの基本設定
        ParticleSystem.MainModule main = noteEffect_.main;

        // 繰り返し再生しない
        main.loop = false;

        // 粒が表示される時間
        main.startLifetime = 1.5f;

        // 粒が飛ぶ速さ
        main.startSpeed = 2.0f;

        // 粒の大きさ
        main.startSize = 0.3f;

        // カラフルな色にする
        main.startColor = new ParticleSystem.MinMaxGradient(
            Color.cyan,
            Color.magenta
        );

        // 通常時は粒を出し続けない
        ParticleSystem.EmissionModule emission = noteEffect_.emission;
        emission.rateOverTime = 0f;

        // タッチされた瞬間に12個の粒を出す
        ParticleSystem.Burst[] bursts =
        {
            new ParticleSystem.Burst(0f, 12)
        };

        emission.SetBursts(bursts);

        // 上方向へ広がるようにする
        ParticleSystem.ShapeModule shape = noteEffect_.shape;
        shape.shapeType = ParticleSystemShapeType.Cone;
        shape.angle = 25f;
        shape.radius = 0.2f;

        // 音符用のマテリアルが設定されていれば使用する
        if (noteMaterial != null)
        {
            ParticleSystemRenderer particleRenderer =
                GetComponent<ParticleSystemRenderer>();

            particleRenderer.material = noteMaterial;
        }
    }

    // 楽器がタッチされたときに呼び出される
    public void ActivateMagic()
    {
        Debug.Log("楽器のギミック発動！");

        // AudioClipが設定されている場合
        if (audioSource_.clip != null)
        {
            // 楽器の音を再生
            audioSource_.Play();
        }
        else
        {
            Debug.LogWarning(
                "Audio SourceのAudio Clipに楽器の音を設定してください。"
            );
        }

        // 連続タッチでも最初からエフェクトを出し直す
        noteEffect_.Stop(
            true,
            ParticleSystemStopBehavior.StopEmittingAndClear
        );

        // 音符エフェクトを再生
        noteEffect_.Play();
    }
}