using System.Collections;
using System.Collections.Generic;
using UnityEngine;

// 人をタップしたときのギミックを管理するクラス
public class HumanGimmick : MonoBehaviour, GimmickBase
{
    // AudioSource（今回は使用していないが、必要に応じて音源を設定できる）
    [SerializeField]
    private AudioSource audioSource;

    // タップされたときに呼び出される処理
    public void ActivateMagic()
    {
        // コンソールにギミックが発動したことを表示
        Debug.Log("ギミック発動");

        // SoundManagerのSEリストの0番目の効果音を再生
        SoundManager.Instance.PlaySE(0);
    }

}
