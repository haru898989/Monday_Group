using System.Collections;
using UnityEngine;

/// <summary>
/// ボールをタッチするたびに、
/// 現在位置からランダムな方向へ回転しながら飛んでいく。
/// 元の位置には戻らず、次のタッチでさらに別方向へ飛ぶ。
///
/// 写真の後ろへ行かないように、
/// 移動中もZ座標は最初の値に固定する。
/// </summary>
public class BallGimmick : MonoBehaviour, GimmickBase
{
    [Header("移動設定")]

    [SerializeField]
    private float moveDuration = 0.8f;

    [SerializeField]
    private float minimumMoveDistance = 1.2f;

    [SerializeField]
    private float maximumMoveDistance = 2.3f;


    [Header("回転設定")]

    [SerializeField]
    private float minimumRotationAmount = 360f;

    [SerializeField]
    private float maximumRotationAmount = 900f;


    [Header("弧を描く高さ")]

    [SerializeField]
    private float arcHeight = 0.35f;


    private bool isMoving;

    // 写真より手前に表示されている最初のZ座標
    private float fixedLocalZ;


    private void Awake()
    {
        fixedLocalZ =
            transform.localPosition.z;
    }


    /// <summary>
    /// ボールをタッチしたときに呼ばれる。
    /// </summary>
    public void ActivateMagic()
    {
        if (isMoving)
        {
            return;
        }

        StartCoroutine(
            FlyInRandomDirection()
        );
    }


    /// <summary>
    /// 現在位置からランダム方向へ、
    /// 回転しながら飛ばす。
    /// </summary>
    private IEnumerator FlyInRandomDirection()
    {
        isMoving = true;

        Vector3 startPosition =
            transform.localPosition;

        // 移動開始時にもZを固定値へ合わせる
        startPosition.z =
            fixedLocalZ;

        transform.localPosition =
            startPosition;

        Quaternion startRotation =
            transform.localRotation;


        // 360度の中からランダムな方向を決める
        float randomAngle =
            Random.Range(
                0f,
                360f
            );

        float angleInRadians =
            randomAngle
            * Mathf.Deg2Rad;

        Vector3 moveDirection =
            new Vector3(
                Mathf.Cos(angleInRadians),
                Mathf.Sin(angleInRadians),
                0f
            ).normalized;


        // 飛ぶ距離をランダムに決める
        float moveDistance =
            Random.Range(
                minimumMoveDistance,
                maximumMoveDistance
            );

        Vector3 endPosition =
            startPosition
            + moveDirection
            * moveDistance;

        // Z方向には移動させない
        endPosition.z =
            fixedLocalZ;


        // 回転量をランダムに決める
        float rotationAmount =
            Random.Range(
                minimumRotationAmount,
                maximumRotationAmount
            );

        // 時計回り・反時計回りをランダムにする
        if (Random.value < 0.5f)
        {
            rotationAmount *= -1f;
        }

        Quaternion endRotation =
            startRotation
            * Quaternion.Euler(
                0f,
                0f,
                rotationAmount
            );


        float elapsedTime = 0f;

        float safeDuration =
            Mathf.Max(
                moveDuration,
                0.01f
            );

        while (elapsedTime < safeDuration)
        {
            elapsedTime +=
                Time.deltaTime;

            float rate =
                Mathf.Clamp01(
                    elapsedTime
                    / safeDuration
                );

            float smoothRate =
                Mathf.SmoothStep(
                    0f,
                    1f,
                    rate
                );


            // X・Y方向の基本移動
            Vector3 currentPosition =
                Vector3.Lerp(
                    startPosition,
                    endPosition,
                    smoothRate
                );


            // Y方向に少し弧を描く
            float arc =
                Mathf.Sin(
                    rate
                    * Mathf.PI
                )
                * arcHeight;

            currentPosition.y +=
                arc;

            // 写真の後ろへ行かないようにZ座標を固定
            currentPosition.z =
                fixedLocalZ;


            transform.localPosition =
                currentPosition;

            transform.localRotation =
                Quaternion.Slerp(
                    startRotation,
                    endRotation,
                    smoothRate
                );

            yield return null;
        }


        endPosition.z =
            fixedLocalZ;

        transform.localPosition =
            endPosition;

        transform.localRotation =
            endRotation;

        isMoving = false;
    }


    private void OnDisable()
    {
        isMoving = false;

        Vector3 currentPosition =
            transform.localPosition;

        currentPosition.z =
            fixedLocalZ;

        transform.localPosition =
            currentPosition;
    }
}