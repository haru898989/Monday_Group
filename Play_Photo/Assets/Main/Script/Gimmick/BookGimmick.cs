using UnityEngine;

// このスクリプトを追加するとParticle Systemも自動追加される
[RequireComponent(typeof(ParticleSystem))]
public class BookGimmick : MonoBehaviour, GimmickBase
{
    // パーティクルを保存する変数
    private ParticleSystem butterflyEffect;

    void Awake()
    {
        // 同じオブジェクトのParticle Systemを自動取得
        butterflyEffect = GetComponent<ParticleSystem>();

        // ゲーム開始時に勝手に再生されないようにする
        butterflyEffect.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);
    }

    public void ActivateMagic()
    {
        // タッチされたらパーティクルを再生
        butterflyEffect.Play();

        Debug.Log("本からエフェクトが飛び出しました");
    }
}