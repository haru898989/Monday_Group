using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// 建物を細かな破片へ砕き、周囲へ散らして画面下へ落下させる。
/// </summary>
public class BuildingGimmick : MonoBehaviour, GimmickBase
{
    private sealed class BuildingFragment
    {
        public GameObject gameObject;
        public Transform transform;
        public Mesh mesh;
        public Vector3 velocity;
        public Vector3 angularVelocity;
        public Vector3 initialScale;
        public float startDelay;
    }

    [Header("Fragments")]
    [SerializeField, Range(2, 10)]
    private int fragmentColumns = 6;

    [SerializeField, Range(2, 8)]
    private int fragmentRows = 4;

    [SerializeField]
    private float maximumStartDelay = 0.12f;

    [Header("Scatter And Fall")]
    [SerializeField]
    private float minimumHorizontalSpeed = 0.18f;

    [SerializeField]
    private float maximumHorizontalSpeed = 0.62f;

    [SerializeField]
    private float minimumUpwardSpeed = 0.28f;

    [SerializeField]
    private float maximumUpwardSpeed = 0.82f;

    [SerializeField]
    private float gravity = 1.65f;

    [SerializeField]
    private float minimumAngularSpeed = 180f;

    [SerializeField]
    private float maximumAngularSpeed = 520f;

    [SerializeField]
    private float fallDuration = 2.25f;

    [SerializeField, Range(0.4f, 1f)]
    private float finalFragmentScale = 0.72f;

    private readonly List<BuildingFragment> fragments =
        new List<BuildingFragment>();

    private Renderer targetRenderer;
    private Material fragmentMaterial;
    private AudioSource audioSource;
    private bool isDestroyed;

    public void SetTargetRenderer(Renderer renderer)
    {
        targetRenderer = renderer;
    }

    public void SetAudioClip(AudioClip clip)
    {
        if (audioSource == null)
        {
            audioSource = GetComponent<AudioSource>();

            if (audioSource == null)
            {
                audioSource = gameObject.AddComponent<AudioSource>();
            }
        }

        audioSource.clip = clip;
        audioSource.playOnAwake = false;
        audioSource.loop = false;
        audioSource.spatialBlend = 0f;
    }

    public void ActivateMagic()
    {
        if (isDestroyed)
        {
            return;
        }

        if (targetRenderer == null)
        {
            Debug.LogWarning(
                "建物の切り抜き画像が設定されていません。"
            );
            return;
        }

        CreateFragments();

        if (fragments.Count == 0)
        {
            Debug.LogWarning(
                "建物の破片を生成できませんでした。"
            );
            return;
        }

        isDestroyed = true;
        targetRenderer.enabled = false;

        if (audioSource != null && audioSource.clip != null)
        {
            audioSource.Stop();
            audioSource.Play();
        }

        StartCoroutine(ScatterAndDropFragments());
    }

    private void CreateFragments()
    {
        CleanupFragments();

        Material sourceMaterial = targetRenderer.sharedMaterial;

        if (sourceMaterial == null)
        {
            return;
        }

        fragmentMaterial = new Material(sourceMaterial);
        fragmentMaterial.name = "RuntimeBuildingFragmentMaterial";

        if (fragmentMaterial.HasProperty("_Cull"))
        {
            fragmentMaterial.SetInt("_Cull", (int)CullMode.Off);
        }

        int columns = Mathf.Max(fragmentColumns, 2);
        int rows = Mathf.Max(fragmentRows, 2);
        int fragmentIndex = 0;

        for (int row = 0; row < rows; row++)
        {
            float y0 = -0.5f + row / (float)rows;
            float y1 = -0.5f + (row + 1f) / rows;

            for (int column = 0; column < columns; column++)
            {
                float x0 = -0.5f + column / (float)columns;
                float x1 = -0.5f + (column + 1f) / columns;

                Vector2 bottomLeft = new Vector2(x0, y0);
                Vector2 topLeft = new Vector2(x0, y1);
                Vector2 topRight = new Vector2(x1, y1);
                Vector2 bottomRight = new Vector2(x1, y0);

                if (Random.value < 0.5f)
                {
                    CreateTriangleFragment(
                        bottomLeft,
                        topLeft,
                        topRight,
                        fragmentIndex++
                    );

                    CreateTriangleFragment(
                        bottomLeft,
                        topRight,
                        bottomRight,
                        fragmentIndex++
                    );
                }
                else
                {
                    CreateTriangleFragment(
                        bottomLeft,
                        topLeft,
                        bottomRight,
                        fragmentIndex++
                    );

                    CreateTriangleFragment(
                        topLeft,
                        topRight,
                        bottomRight,
                        fragmentIndex++
                    );
                }
            }
        }
    }

    private void CreateTriangleFragment(
        Vector2 first,
        Vector2 second,
        Vector2 third,
        int fragmentIndex
    )
    {
        Transform sourceTransform = targetRenderer.transform;
        Transform fragmentParent = sourceTransform.parent;

        Vector2 center = (first + second + third) / 3f;

        GameObject fragmentObject = new GameObject(
            "BuildingFragment_" + fragmentIndex
        );

        fragmentObject.transform.SetParent(fragmentParent, false);

        Vector3 scaledCenter = Vector3.Scale(
            new Vector3(center.x, center.y, 0f),
            sourceTransform.localScale
        );

        fragmentObject.transform.localPosition =
            sourceTransform.localPosition +
            sourceTransform.localRotation * scaledCenter +
            new Vector3(0f, 0f, -0.00001f * fragmentIndex);

        fragmentObject.transform.localRotation =
            sourceTransform.localRotation;

        fragmentObject.transform.localScale =
            sourceTransform.localScale;

        Mesh mesh = new Mesh();
        mesh.name = "RuntimeBuildingFragmentMesh";

        mesh.vertices = new[]
        {
            ToVertex(first - center),
            ToVertex(second - center),
            ToVertex(third - center)
        };

        mesh.uv = new[]
        {
            ToUv(first),
            ToUv(second),
            ToUv(third)
        };

        mesh.triangles = new[] { 0, 1, 2 };
        mesh.normals = new[]
        {
            Vector3.back,
            Vector3.back,
            Vector3.back
        };

        mesh.RecalculateBounds();

        MeshFilter meshFilter =
            fragmentObject.AddComponent<MeshFilter>();

        meshFilter.sharedMesh = mesh;

        MeshRenderer meshRenderer =
            fragmentObject.AddComponent<MeshRenderer>();

        meshRenderer.sharedMaterial = fragmentMaterial;
        meshRenderer.shadowCastingMode = ShadowCastingMode.Off;
        meshRenderer.receiveShadows = false;
        meshRenderer.sortingLayerID = targetRenderer.sortingLayerID;
        meshRenderer.sortingOrder = targetRenderer.sortingOrder;

        float outwardDirection = Mathf.Sign(center.x);
        if (Mathf.Approximately(outwardDirection, 0f))
        {
            outwardDirection = Random.value < 0.5f ? -1f : 1f;
        }

        float horizontalSpeed = Random.Range(
            minimumHorizontalSpeed,
            Mathf.Max(maximumHorizontalSpeed, minimumHorizontalSpeed)
        );

        float upwardSpeed = Random.Range(
            minimumUpwardSpeed,
            Mathf.Max(maximumUpwardSpeed, minimumUpwardSpeed)
        );

        float angularSpeed = Random.Range(
            minimumAngularSpeed,
            Mathf.Max(maximumAngularSpeed, minimumAngularSpeed)
        );

        BuildingFragment fragment = new BuildingFragment
        {
            gameObject = fragmentObject,
            transform = fragmentObject.transform,
            mesh = mesh,
            velocity = new Vector3(
                outwardDirection * horizontalSpeed +
                Random.Range(-0.12f, 0.12f),
                upwardSpeed,
                0f
            ),
            angularVelocity = new Vector3(
                Random.Range(-angularSpeed, angularSpeed),
                Random.Range(-angularSpeed, angularSpeed),
                Random.Range(-angularSpeed, angularSpeed)
            ),
            initialScale = fragmentObject.transform.localScale,
            startDelay = Random.Range(
                0f,
                Mathf.Max(maximumStartDelay, 0f)
            )
        };

        fragments.Add(fragment);
    }

    private IEnumerator ScatterAndDropFragments()
    {
        float duration = Mathf.Max(fallDuration, 0.2f);
        float elapsedTime = 0f;

        while (elapsedTime < duration)
        {
            float deltaTime = Time.deltaTime;
            elapsedTime += deltaTime;

            for (int index = 0; index < fragments.Count; index++)
            {
                BuildingFragment fragment = fragments[index];
                float activeTime =
                    elapsedTime - fragment.startDelay;

                if (fragment.transform == null || activeTime < 0f)
                {
                    continue;
                }

                fragment.velocity +=
                    Vector3.down * gravity * deltaTime;

                fragment.transform.localPosition +=
                    fragment.velocity * deltaTime;

                fragment.transform.localRotation *=
                    Quaternion.Euler(
                        fragment.angularVelocity * deltaTime
                    );

                float rate = Mathf.Clamp01(activeTime / duration);
                float scale = Mathf.Lerp(
                    1f,
                    finalFragmentScale,
                    rate
                );

                fragment.transform.localScale =
                    fragment.initialScale * scale;
            }

            yield return null;
        }

        Debug.Log("建物が粉々に崩れて落下しました。");
        CleanupFragments();
    }

    private static Vector3 ToVertex(Vector2 point)
    {
        return new Vector3(point.x, point.y, 0f);
    }

    private static Vector2 ToUv(Vector2 point)
    {
        return point + Vector2.one * 0.5f;
    }

    private void CleanupFragments()
    {
        for (int index = 0; index < fragments.Count; index++)
        {
            BuildingFragment fragment = fragments[index];

            if (fragment.mesh != null)
            {
                Destroy(fragment.mesh);
            }

            if (fragment.gameObject != null)
            {
                Destroy(fragment.gameObject);
            }
        }

        fragments.Clear();

        if (fragmentMaterial != null)
        {
            Destroy(fragmentMaterial);
            fragmentMaterial = null;
        }
    }

    private void OnDestroy()
    {
        CleanupFragments();
    }
}
