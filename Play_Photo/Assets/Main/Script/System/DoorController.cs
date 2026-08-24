using System.Collections;
using System.Collections.Generic;
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
    [SerializeField] private float cameraMoveDistance = 900f;
    [SerializeField] private float cameraMoveTime = 2f;

    [Header("カメラが動き始めるタイミング")]
    [SerializeField] private float cameraStartDelay = 0.2f;

    [Header("暗くするオブジェクト")]
    [Tooltip("TitleBack、LeftDoorPivot、RightDoorPivot、HallwayBackなどを入れてください")]
    [SerializeField] private GameObject[] darkenObjects;

    [Header("暗転設定")]
    [Range(0f, 1f)]
    [SerializeField] private float darkenStartPoint = 0.55f;

    [Range(0f, 1f)]
    [SerializeField] private float finalBrightness = 0f;

    private bool isPlaying = false;

    // 暗くする対象のMaterial
    private readonly List<Material> targetMaterials = new List<Material>();

    // 各Materialの元の色
    private readonly List<Color> originalColors = new List<Color>();


    private void Awake()
    {
        PrepareDarkenMaterials();
    }


    private void PrepareDarkenMaterials()
    {
        targetMaterials.Clear();
        originalColors.Clear();

        if (darkenObjects == null)
        {
            return;
        }

        foreach (GameObject targetObject in darkenObjects)
        {
            if (targetObject == null)
            {
                continue;
            }

            // 自分自身＋子オブジェクトにあるRendererを全部取得
            Renderer[] renderers =
                targetObject.GetComponentsInChildren<Renderer>(true);

            foreach (Renderer targetRenderer in renderers)
            {
                // .materials にすることで
                // このScene内専用のMaterialとして扱う
                Material[] materials = targetRenderer.materials;

                foreach (Material material in materials)
                {
                    if (material == null)
                    {
                        continue;
                    }

                    // Standard ShaderなどのColorを持つMaterialだけ登録
                    if (material.HasProperty("_Color"))
                    {
                        targetMaterials.Add(material);
                        originalColors.Add(material.color);
                    }
                }
            }
        }
    }


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

        // =========================
        // ドア
        // =========================

        Quaternion leftStartRotation =
            leftDoorPivot.localRotation;

        Quaternion rightStartRotation =
            rightDoorPivot.localRotation;

        Quaternion leftTargetRotation =
            leftStartRotation *
            Quaternion.Euler(
                0f,
                leftOpenAngle,
                0f
            );

        Quaternion rightTargetRotation =
            rightStartRotation *
            Quaternion.Euler(
                0f,
                rightOpenAngle,
                0f
            );


        // =========================
        // カメラ
        // =========================

        Vector3 cameraStartPosition =
            mainCamera.position;

        Vector3 cameraTargetPosition =
            new Vector3(
                cameraStartPosition.x,
                cameraStartPosition.y,
                cameraStartPosition.z + cameraMoveDistance
            );


        float elapsedTime = 0f;

        float totalTime = Mathf.Max(
            doorOpenTime,
            cameraStartDelay + cameraMoveTime
        );


        // =========================
        // メイン演出
        // =========================

        while (elapsedTime < totalTime)
        {
            elapsedTime += Time.deltaTime;


            // -------------------------
            // ドアを開く
            // -------------------------

            float doorT =
                Mathf.Clamp01(
                    elapsedTime / doorOpenTime
                );

            doorT =
                Mathf.SmoothStep(
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


            // -------------------------
            // カメラ前進
            // -------------------------

            if (elapsedTime >= cameraStartDelay)
            {
                float cameraElapsed =
                    elapsedTime - cameraStartDelay;

                float cameraT =
                    Mathf.Clamp01(
                        cameraElapsed / cameraMoveTime
                    );

                float smoothCameraT =
                    Mathf.SmoothStep(
                        0f,
                        1f,
                        cameraT
                    );

                mainCamera.position =
                    Vector3.Lerp(
                        cameraStartPosition,
                        cameraTargetPosition,
                        smoothCameraT
                    );


                // =========================
                // 前進後半から暗くする
                // =========================

                if (cameraT >= darkenStartPoint)
                {
                    float darkenT =
                        Mathf.InverseLerp(
                            darkenStartPoint,
                            1f,
                            cameraT
                        );

                    darkenT =
                        Mathf.SmoothStep(
                            0f,
                            1f,
                            darkenT
                        );

                    float brightness =
                        Mathf.Lerp(
                            1f,
                            finalBrightness,
                            darkenT
                        );

                    SetBrightness(brightness);
                }
            }

            yield return null;
        }


        // =========================
        // 最終状態
        // =========================

        leftDoorPivot.localRotation =
            leftTargetRotation;

        rightDoorPivot.localRotation =
            rightTargetRotation;

        mainCamera.position =
            cameraTargetPosition;

        // 最後は指定した暗さにする
        SetBrightness(finalBrightness);


        // =========================
        // LoadingLINEへ
        // =========================

        if (SceneLoader.Instance == null)
        {
            Debug.LogError(
                "SceneLoaderが見つかりません。"
            );

            isPlaying = false;
            yield break;
        }

        SceneLoader.Instance.LoadScene(
            "LoadingLINE"
        );
    }


    // =========================
    // Materialを暗くする処理
    // =========================

    private void SetBrightness(float brightness)
    {
        for (int i = 0; i < targetMaterials.Count; i++)
        {
            Material material =
                targetMaterials[i];

            Color originalColor =
                originalColors[i];

            Color darkenedColor =
                new Color(
                    originalColor.r * brightness,
                    originalColor.g * brightness,
                    originalColor.b * brightness,
                    originalColor.a
                );

            material.color = darkenedColor;

            // Emissionが設定されているMaterialなら
            // 発光も一緒に弱くする
            if (material.HasProperty("_EmissionColor"))
            {
                material.SetColor(
                    "_EmissionColor",
                    Color.black
                );
            }
        }
    }
}