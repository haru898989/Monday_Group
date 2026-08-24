using System.Collections;
using UnityEngine;

public class DoorController : MonoBehaviour
{
    [Header("ドア")]
    [SerializeField] private Transform leftDoorPivot;
    [SerializeField] private Transform rightDoorPivot;

    [Header("カメラ")]
    [SerializeField] private Transform mainCamera;

    [Header("ドアの開閉設定")]
    [SerializeField] private float leftOpenAngle = 90f;
    [SerializeField] private float rightOpenAngle = -90f;
    [SerializeField] private float doorOpenTime = 1.5f;

    [Header("カメラ前進設定")]
    [SerializeField] private float cameraMoveDistance = 30f;
    [SerializeField] private float cameraMoveTime = 1.8f;

    [Header("カメラが動き始めるタイミング")]
    [SerializeField] private float cameraStartDelay = 0.35f;

    private bool isPlaying = false;

    public void StartEntranceAnimation()
    {
        if (isPlaying)
        {
            return;
        }

        StartCoroutine(EntranceSequence());
    }

    private IEnumerator EntranceSequence()
    {
        isPlaying = true;

        // ドア開始位置
        Quaternion leftStartRotation = leftDoorPivot.localRotation;
        Quaternion rightStartRotation = rightDoorPivot.localRotation;

        // ドア終了位置
        Quaternion leftTargetRotation =
            leftStartRotation * Quaternion.Euler(0f, leftOpenAngle, 0f);

        Quaternion rightTargetRotation =
            rightStartRotation * Quaternion.Euler(0f, rightOpenAngle, 0f);

        // カメラ開始位置
        Vector3 cameraStartPosition = mainCamera.position;

        // Z軸方向へ前進
        Vector3 cameraTargetPosition = new Vector3(
            cameraStartPosition.x,
            cameraStartPosition.y,
            cameraStartPosition.z + cameraMoveDistance
        );

        float elapsedTime = 0f;
        float totalTime = Mathf.Max(
            doorOpenTime,
            cameraStartDelay + cameraMoveTime
        );

        while (elapsedTime < totalTime)
        {
            elapsedTime += Time.deltaTime;

            // =========================
            // ドアを開く
            // =========================

            float doorT = Mathf.Clamp01(
                elapsedTime / doorOpenTime
            );

            doorT = Mathf.SmoothStep(
                0f,
                1f,
                doorT
            );

            leftDoorPivot.localRotation =
                Quaternion.Slerp(
                    leftStartRotation,
                    leftTargetRotation,
                    doorT
                );

            rightDoorPivot.localRotation =
                Quaternion.Slerp(
                    rightStartRotation,
                    rightTargetRotation,
                    doorT
                );

            // =========================
            // 少し遅れてカメラ前進
            // =========================

            if (elapsedTime >= cameraStartDelay)
            {
                float cameraElapsed =
                    elapsedTime - cameraStartDelay;

                float cameraT = Mathf.Clamp01(
                    cameraElapsed / cameraMoveTime
                );

                cameraT = Mathf.SmoothStep(
                    0f,
                    1f,
                    cameraT
                );

                mainCamera.position =
                    Vector3.Lerp(
                        cameraStartPosition,
                        cameraTargetPosition,
                        cameraT
                    );
            }

            yield return null;
        }

        // 最終位置を確実に設定
        leftDoorPivot.localRotation = leftTargetRotation;
        rightDoorPivot.localRotation = rightTargetRotation;
        mainCamera.position = cameraTargetPosition;

        // LoadingLINEへ
        if (SceneLoader.Instance == null)
        {
            Debug.LogError("SceneLoaderが見つかりません。");
            isPlaying = false;
            yield break;
        }

        SceneLoader.Instance.LoadScene("LoadingLINE");
    }
}