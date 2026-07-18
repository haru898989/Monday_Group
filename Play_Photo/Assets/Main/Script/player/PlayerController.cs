using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.InputSystem;

public class PlayerController : MonoBehaviour
{
    // 入力情報を管理するPlayerInputクラス
    private PlayerInput playerInput_;

    // ゲーム開始時に1回だけ実行される
    void Start()
    {
        // PlayerInputを生成する
        playerInput_ = new PlayerInput();

        // 入力を有効化する
        playerInput_.Enable();
    }

    // 毎フレーム実行される
    void Update()
    {
        // タッチ（クリック）が行われた瞬間を判定する
        if (playerInput_.Player.touch.triggered)
        {
            // タッチした画面上の座標を取得する
            Vector2 screenPosition = Pointer.current.position.ReadValue();

            // 画面座標からカメラを通してレイを飛ばす
            Ray ray = Camera.main.ScreenPointToRay(screenPosition);

            // レイが当たったオブジェクトの情報を格納する変数
            RaycastHit hit;

            // レイがオブジェクトに当たったか判定する
            if (Physics.Raycast(ray, out hit))
            {
                // 当たったオブジェクトにGimmickBaseが付いているか取得する
                GimmickBase touchGimmick = hit.collider.GetComponent<GimmickBase>();

                // GimmickBaseが取得できた場合
                if (touchGimmick != null)
                {
                    // ギミックを発動する
                    touchGimmick.ActivateMagic();
                }
            }
        }
    }
}