using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>
/// PhotoLibrary内の写真を読み込み、額縁付きの展示物として横一列に並べる。
/// </summary>
public class PhotoSelectGalleryController : MonoBehaviour
{
    [Header("参照")]
    [SerializeField]
    private Camera galleryCamera;

    [SerializeField]
    private Sprite goldFrameSprite;

    [SerializeField]
    private Sprite hallWallSprite;

    [SerializeField]
    private Sprite usePhotoButtonSprite;

    [SerializeField]
    private Sprite arrowSprite;

    [Header("展示レイアウト")]
    [SerializeField]
    private float photoHeight = 3.8f;

    [SerializeField]
    private float maximumPhotoWidth = 6.4f;

    [SerializeField]
    private float visibleWallHeight = 10f;

    [SerializeField]
    private float photoVerticalPosition = 1.55f;

    [SerializeField]
    private float slideSmoothTime = 0.35f;

    private readonly List<UnityEngine.Object> generatedResources =
        new List<UnityEngine.Object>();

    private GameObject galleryRoot;
    private string statusMessage = string.Empty;
    private readonly List<float> photoCameraPositions =
        new List<float>();

    private readonly List<Texture2D> photoTextures =
        new List<Texture2D>();

    private readonly List<string> photoFilePaths =
        new List<string>();

    private int currentPhotoIndex;
    private float targetCameraX;
    private float cameraVelocityX;
    private bool isLoadingMainScene;

    private const int SlotsPerWall = 5;
    private const int BasePhotoCount = 12;

    // HallWall.pngの不透明部分は、画像全高724px中431px。
    private const float VisibleWallHeightRatio = 431f / 724f;

    // 不透明部分の中心をCamera中央へ合わせるための補正値。
    private const float VisibleWallCenterOffsetRatio = 21f / 724f;

    // HallWall.pngの左右端にある半分ずつの柱を1本に重ねる。
    private const float WallSeamOverlapRatio = 84f / 2172f;

    // Arrow.pngの矢印本体と、光の余白を含む表示範囲。
    private const float ArrowVisibleAspect = 535f / 418f;

    private static readonly Rect ArrowTextureCoordinates = new Rect(
        485f / 1536f,
        318f / 1024f,
        535f / 1536f,
        418f / 1024f
    );

    // HallWall.png内にある5つの大きな展示区画の中心位置。
    private static readonly float[] SlotCenterOffsets =
    {
        -0.388f,
        -0.194f,
        0f,
        0.194f,
        0.388f
    };

    private static readonly HashSet<string> SupportedExtensions =
        new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            ".jpg",
            ".jpeg",
            ".png"
        };

    private sealed class PhotoData
    {
        public string filePath;
        public Texture2D texture;
        public Sprite sprite;
        public float displayWidth;
        public float displayHeight;
        public float frameWidth;
        public float frameHeight;
    }


    private void Start()
    {
        if (galleryCamera == null)
        {
            galleryCamera = Camera.main;
        }

        ConfigureCamera();
        BuildGallery();
    }


    private void ConfigureCamera()
    {
        if (galleryCamera == null)
        {
            Debug.LogError("PhotoSelect用のCameraが見つかりません。");
            return;
        }

        galleryCamera.orthographic = true;
        galleryCamera.transform.position = new Vector3(0f, 0f, -10f);
        galleryCamera.transform.rotation = Quaternion.identity;
        galleryCamera.backgroundColor =
            new Color(0.045f, 0.018f, 0.012f, 1f);
    }


    private void Update()
    {
        if (galleryCamera == null || photoCameraPositions.Count == 0)
        {
            return;
        }

        Vector3 cameraPosition = galleryCamera.transform.position;

        cameraPosition.x = Mathf.SmoothDamp(
            cameraPosition.x,
            targetCameraX,
            ref cameraVelocityX,
            Mathf.Max(slideSmoothTime, 0.01f)
        );

        galleryCamera.transform.position = cameraPosition;
    }


    private void BuildGallery()
    {
        string photoLibraryPath = GetPhotoLibraryPath();

        if (!Directory.Exists(photoLibraryPath))
        {
            statusMessage =
                "PhotoLibraryフォルダが見つかりません。\n" +
                photoLibraryPath;

            Debug.LogWarning(statusMessage);
            return;
        }

        string[] photoFiles;

        try
        {
            photoFiles = Directory.GetFiles(photoLibraryPath);
        }
        catch (Exception exception)
        {
            statusMessage =
                "PhotoLibraryを読み込めませんでした。\n" +
                exception.Message;

            Debug.LogError(statusMessage);
            return;
        }

        Array.Sort(photoFiles, ComparePhotoFiles);

        List<PhotoData> photos = new List<PhotoData>();

        foreach (string photoFile in photoFiles)
        {
            string extension = Path.GetExtension(photoFile);

            if (!SupportedExtensions.Contains(extension))
            {
                continue;
            }

            PhotoData photo = LoadPhoto(photoFile);

            if (photo != null)
            {
                photos.Add(photo);
            }
        }

        if (photos.Count == 0)
        {
            statusMessage =
                "PhotoLibraryに表示できる写真がありません。\n" +
                "JPG・JPEG・PNGを入れてください。";

            Debug.LogWarning(statusMessage);
            return;
        }

        CreateGalleryObjects(photos);

        statusMessage = string.Empty;

        Debug.Log(
            $"PhotoLibraryから{photos.Count}枚の写真を展示しました。" +
            $" 読み込み先: {photoLibraryPath}"
        );
    }


    private string GetPhotoLibraryPath()
    {
        return Path.GetFullPath(
            Path.Combine(
                Application.dataPath,
                "..",
                "PhotoLibrary"
            )
        );
    }


    private static int ComparePhotoFiles(string left, string right)
    {
        int leftBaseOrder = GetBasePhotoOrder(left);
        int rightBaseOrder = GetBasePhotoOrder(right);

        int baseOrderComparison = leftBaseOrder.CompareTo(rightBaseOrder);

        if (baseOrderComparison != 0)
        {
            return baseOrderComparison;
        }

        return StringComparer.OrdinalIgnoreCase.Compare(
            Path.GetFileName(left),
            Path.GetFileName(right)
        );
    }


    private static int GetBasePhotoOrder(string photoFile)
    {
        string fileName = Path.GetFileNameWithoutExtension(photoFile);
        int photoNumber;

        bool isNumber = int.TryParse(fileName, out photoNumber);
        bool hasTwoDigitName =
            isNumber &&
            string.Equals(
                fileName,
                photoNumber.ToString("00"),
                StringComparison.Ordinal
            );

        if (!hasTwoDigitName ||
            photoNumber < 1 ||
            photoNumber > BasePhotoCount)
        {
            return int.MaxValue;
        }

        return photoNumber - 1;
    }


    private PhotoData LoadPhoto(string photoFile)
    {
        byte[] imageBytes;

        try
        {
            imageBytes = File.ReadAllBytes(photoFile);
        }
        catch (Exception exception)
        {
            Debug.LogWarning(
                $"写真を読み込めませんでした: {photoFile}\n" +
                exception.Message
            );
            return null;
        }

        Texture2D texture = new Texture2D(
            2,
            2,
            TextureFormat.RGBA32,
            false
        );

        if (!texture.LoadImage(imageBytes, false))
        {
            Destroy(texture);
            Debug.LogWarning("画像形式を読み込めませんでした: " + photoFile);
            return null;
        }

        texture.name = Path.GetFileName(photoFile);
        texture.wrapMode = TextureWrapMode.Clamp;
        texture.filterMode = FilterMode.Bilinear;

        Sprite photoSprite = Sprite.Create(
            texture,
            new Rect(0f, 0f, texture.width, texture.height),
            new Vector2(0.5f, 0.5f),
            100f,
            0,
            SpriteMeshType.FullRect
        );

        photoSprite.name = Path.GetFileNameWithoutExtension(photoFile);

        generatedResources.Add(texture);
        generatedResources.Add(photoSprite);

        float safeHeight = Mathf.Max(photoHeight, 0.1f);
        float aspectRatio =
            (float)texture.width / Mathf.Max(texture.height, 1);

        float frameHorizontalBorder = 0f;
        float frameVerticalBorder = 0f;

        if (goldFrameSprite != null)
        {
            float pixelsPerUnit = Mathf.Max(
                goldFrameSprite.pixelsPerUnit,
                0.0001f
            );

            Vector4 border = goldFrameSprite.border;

            frameHorizontalBorder =
                (border.x + border.z) / pixelsPerUnit;

            frameVerticalBorder =
                (border.y + border.w) / pixelsPerUnit;
        }

        float displayWidth = safeHeight * aspectRatio;
        float safeMaximumWidth = Mathf.Max(maximumPhotoWidth, 0.1f);

        if (displayWidth > safeMaximumWidth)
        {
            float shrinkRatio = safeMaximumWidth / displayWidth;

            displayWidth = safeMaximumWidth;
            safeHeight *= shrinkRatio;
        }

        return new PhotoData
        {
            filePath = photoFile,
            texture = texture,
            sprite = photoSprite,
            displayWidth = displayWidth,
            displayHeight = safeHeight,
            frameWidth = displayWidth + frameHorizontalBorder,
            frameHeight = safeHeight + frameVerticalBorder
        };
    }


    private void CreateGalleryObjects(List<PhotoData> photos)
    {
        if (hallWallSprite == null)
        {
            statusMessage = "HallWall.pngが設定されていません。";
            Debug.LogError(statusMessage);
            return;
        }

        galleryRoot = new GameObject("GeneratedGallery");
        galleryRoot.transform.SetParent(transform, false);

        float safeVisibleWallHeight = Mathf.Max(visibleWallHeight, 1f);
        float wallSpriteHeight = Mathf.Max(
            hallWallSprite.bounds.size.y,
            0.0001f
        );

        float wallScale =
            safeVisibleWallHeight /
            (wallSpriteHeight * VisibleWallHeightRatio);

        float wallSegmentWidth =
            hallWallSprite.bounds.size.x * wallScale;

        float wallStride =
            wallSegmentWidth * (1f - WallSeamOverlapRatio);

        float fullWallHeight = wallSpriteHeight * wallScale;
        float wallY =
            -fullWallHeight * VisibleWallCenterOffsetRatio;

        int wallCount = Mathf.CeilToInt(
            photos.Count / (float)SlotsPerWall
        );

        // 最初と最後の展示区画でCameraが壁の外側を映さないよう、
        // 写真を配置する壁の左右にも同じ壁を1枚ずつつなげる。
        for (int wallIndex = -1; wallIndex <= wallCount; wallIndex++)
        {
            CreateHallWall(
                wallIndex * wallStride,
                wallY,
                wallScale,
                wallIndex
            );
        }

        for (int photoIndex = 0; photoIndex < photos.Count; photoIndex++)
        {
            int wallIndex = photoIndex / SlotsPerWall;
            int slotIndex = photoIndex % SlotsPerWall;

            float centerX =
                wallIndex * wallStride +
                SlotCenterOffsets[slotIndex] * wallSegmentWidth;

            CreatePhotoEntry(photos[photoIndex], centerX);

            photoCameraPositions.Add(centerX);
            photoTextures.Add(photos[photoIndex].texture);
            photoFilePaths.Add(photos[photoIndex].filePath);
        }

        galleryCamera.orthographicSize = safeVisibleWallHeight * 0.5f;

        currentPhotoIndex = 0;
        targetCameraX = photoCameraPositions[0];

        Vector3 initialCameraPosition = galleryCamera.transform.position;
        initialCameraPosition.x = targetCameraX;
        galleryCamera.transform.position = initialCameraPosition;
    }


    private void CreatePhotoEntry(PhotoData photo, float centerX)
    {
        GameObject entry = new GameObject(
            "Photo_" + Path.GetFileNameWithoutExtension(photo.filePath)
        );

        entry.transform.SetParent(galleryRoot.transform, false);
        entry.transform.localPosition = new Vector3(
            centerX,
            photoVerticalPosition,
            0f
        );

        GameObject photoObject = new GameObject("PhotoImage");
        photoObject.transform.SetParent(entry.transform, false);

        SpriteRenderer photoRenderer =
            photoObject.AddComponent<SpriteRenderer>();

        photoRenderer.sprite = photo.sprite;
        photoRenderer.sortingOrder = 0;
        photoRenderer.shadowCastingMode = ShadowCastingMode.Off;
        photoRenderer.receiveShadows = false;

        Vector2 spriteSize = photo.sprite.bounds.size;

        photoObject.transform.localScale = new Vector3(
            photo.displayWidth / Mathf.Max(spriteSize.x, 0.0001f),
            photo.displayHeight / Mathf.Max(spriteSize.y, 0.0001f),
            1f
        );

        if (goldFrameSprite == null)
        {
            return;
        }

        GameObject frameObject = new GameObject("GoldFrame");
        frameObject.transform.SetParent(entry.transform, false);

        SpriteRenderer frameRenderer =
            frameObject.AddComponent<SpriteRenderer>();

        frameRenderer.sprite = goldFrameSprite;
        frameRenderer.drawMode = SpriteDrawMode.Sliced;
        frameRenderer.size = new Vector2(
            photo.frameWidth,
            photo.frameHeight
        );
        frameRenderer.sortingOrder = 10;
        frameRenderer.shadowCastingMode = ShadowCastingMode.Off;
        frameRenderer.receiveShadows = false;
    }


    private void CreateHallWall(
        float centerX,
        float centerY,
        float scale,
        int wallIndex
    )
    {
        GameObject wallObject = new GameObject(
            "HallWall_" + (wallIndex + 1)
        );

        wallObject.transform.SetParent(galleryRoot.transform, false);
        wallObject.transform.localPosition = new Vector3(
            centerX,
            centerY,
            1f
        );
        wallObject.transform.localScale = new Vector3(scale, scale, 1f);

        SpriteRenderer wallRenderer =
            wallObject.AddComponent<SpriteRenderer>();

        wallRenderer.sprite = hallWallSprite;
        wallRenderer.color = Color.white;
        wallRenderer.sortingOrder = -100;
        wallRenderer.shadowCastingMode = ShadowCastingMode.Off;
        wallRenderer.receiveShadows = false;
    }


    private void MoveToPhoto(int requestedIndex)
    {
        if (photoCameraPositions.Count == 0)
        {
            return;
        }

        currentPhotoIndex = Mathf.Clamp(
            requestedIndex,
            0,
            photoCameraPositions.Count - 1
        );

        targetCameraX = photoCameraPositions[currentPhotoIndex];
    }


    private void UseCurrentPhoto()
    {
        if (isLoadingMainScene ||
            currentPhotoIndex < 0 ||
            currentPhotoIndex >= photoTextures.Count ||
            currentPhotoIndex >= photoFilePaths.Count)
        {
            return;
        }

        isLoadingMainScene = true;

        string temporaryPhotoPath = string.Empty;

        try
        {
            byte[] jpegBytes =
                photoTextures[currentPhotoIndex].EncodeToJPG(95);

            if (jpegBytes == null || jpegBytes.Length == 0)
            {
                throw new InvalidOperationException(
                    "選択した写真をJPEGに変換できませんでした。"
                );
            }

            string downloadedImagesPath = Path.GetFullPath(
                Path.Combine(
                    Application.dataPath,
                    "..",
                    "downloaded_images"
                )
            );

            Directory.CreateDirectory(downloadedImagesPath);

            string selectedPhotoPath = Path.Combine(
                downloadedImagesPath,
                "sample.jpg"
            );

            temporaryPhotoPath = Path.Combine(
                downloadedImagesPath,
                "sample.jpg.tmp"
            );

            File.WriteAllBytes(temporaryPhotoPath, jpegBytes);
            File.Copy(
                temporaryPhotoPath,
                selectedPhotoPath,
                true
            );
            File.Delete(temporaryPhotoPath);

            string originalPhotoPath =
                photoFilePaths[currentPhotoIndex];

            if (GetBasePhotoOrder(originalPhotoPath) == int.MaxValue &&
                File.Exists(originalPhotoPath))
            {
                File.Delete(originalPhotoPath);

                Debug.Log(
                    "PhotoLibraryから追加写真を削除しました: " +
                    originalPhotoPath
                );
            }

            Debug.Log(
                "選択した写真をMain用に保存しました: " +
                selectedPhotoPath
            );

            if (SceneLoader.Instance == null)
            {
                throw new InvalidOperationException(
                    "SceneLoaderが見つかりません。"
                );
            }

            SceneLoader.Instance.LoadScene("Main");
        }
        catch (Exception exception)
        {
            if (!string.IsNullOrEmpty(temporaryPhotoPath) &&
                File.Exists(temporaryPhotoPath))
            {
                try
                {
                    File.Delete(temporaryPhotoPath);
                }
                catch (Exception)
                {
                    // 一時ファイルの後始末失敗は元の例外を優先する。
                }
            }

            isLoadingMainScene = false;
            statusMessage =
                "選択した写真を使用できませんでした。\n" +
                exception.Message;

            Debug.LogError(statusMessage);
        }
    }


    private void OnGUI()
    {
        if (!string.IsNullOrEmpty(statusMessage))
        {
            DrawStatusMessage();
            return;
        }

        if (photoCameraPositions.Count == 0)
        {
            return;
        }

        Rect usePhotoButtonRect = GetUsePhotoButtonRect();

        DrawArrowButtons(usePhotoButtonRect);
        DrawUsePhotoButton(usePhotoButtonRect);

        GUIStyle labelStyle = new GUIStyle(GUI.skin.box)
        {
            alignment = TextAnchor.MiddleCenter,
            fontSize = 32,
            normal =
            {
                textColor = Color.white
            }
        };

        string currentLabel =
            $"{currentPhotoIndex + 1} / {photoCameraPositions.Count}";

        GUI.Box(
            new Rect(
                Screen.width * 0.35f,
                Screen.height - 62f,
                Screen.width * 0.3f,
                46f
            ),
            currentLabel,
            labelStyle
        );
    }


    private void DrawArrowButtons(Rect usePhotoButtonRect)
    {
        bool canMoveLeft = currentPhotoIndex > 0;
        bool canMoveRight =
            currentPhotoIndex < photoCameraPositions.Count - 1;

        if (DrawArrowButton(
                arrowSprite,
                true,
                canMoveLeft,
                usePhotoButtonRect))
        {
            MoveToPhoto(currentPhotoIndex - 1);
        }

        if (DrawArrowButton(
                arrowSprite,
                false,
                canMoveRight,
                usePhotoButtonRect))
        {
            MoveToPhoto(currentPhotoIndex + 1);
        }
    }


    private bool DrawArrowButton(
        Sprite arrowSprite,
        bool isLeft,
        bool isEnabled,
        Rect usePhotoButtonRect
    )
    {
        float buttonHeight = Mathf.Clamp(
            usePhotoButtonRect.height * 0.72f,
            90f,
            170f
        );

        Texture2D arrowTexture = null;

        if (arrowSprite != null && arrowSprite.texture != null)
        {
            arrowTexture = arrowSprite.texture;
        }

        float buttonWidth = buttonHeight * ArrowVisibleAspect;
        float maximumButtonWidth = Screen.width * 0.17f;

        if (buttonWidth > maximumButtonWidth)
        {
            buttonWidth = maximumButtonWidth;
            buttonHeight = buttonWidth / ArrowVisibleAspect;
        }

        float buttonGap = Mathf.Clamp(
            Screen.width * 0.0125f,
            18f,
            30f
        );

        float horizontalMargin = 18f;
        float buttonX = isLeft
            ? usePhotoButtonRect.xMin - buttonGap - buttonWidth
            : usePhotoButtonRect.xMax + buttonGap;

        buttonX = Mathf.Clamp(
            buttonX,
            horizontalMargin,
            Screen.width - buttonWidth - horizontalMargin
        );

        Rect buttonRect = new Rect(
            buttonX,
            usePhotoButtonRect.center.y - buttonHeight * 0.5f,
            buttonWidth,
            buttonHeight
        );

        bool previousEnabled = GUI.enabled;
        Color previousColor = GUI.color;

        GUI.enabled = isEnabled && !isLoadingMainScene;
        GUI.color = GUI.enabled
            ? Color.white
            : new Color(1f, 1f, 1f, 0.35f);

        GUIStyle imageButtonStyle = new GUIStyle(GUIStyle.none);
        bool wasClicked;

        if (arrowTexture != null)
        {
            Rect textureCoordinates = ArrowTextureCoordinates;

            if (!isLeft)
            {
                textureCoordinates = new Rect(
                    textureCoordinates.xMax,
                    textureCoordinates.y,
                    -textureCoordinates.width,
                    textureCoordinates.height
                );
            }

            GUI.DrawTextureWithTexCoords(
                buttonRect,
                arrowTexture,
                textureCoordinates,
                true
            );

            wasClicked = GUI.Button(
                buttonRect,
                GUIContent.none,
                imageButtonStyle
            );
        }
        else
        {
            wasClicked = GUI.Button(
                buttonRect,
                isLeft ? "<" : ">"
            );
        }

        GUI.color = previousColor;
        GUI.enabled = previousEnabled;

        return wasClicked;
    }


    private Rect GetUsePhotoButtonRect()
    {
        float textureAspect = 3f;

        if (usePhotoButtonSprite != null &&
            usePhotoButtonSprite.texture != null)
        {
            textureAspect =
                (float)usePhotoButtonSprite.texture.width /
                Mathf.Max(usePhotoButtonSprite.texture.height, 1);
        }

        float buttonWidth = Mathf.Clamp(
            Screen.width * 0.34f,
            320f,
            780f
        );

        float buttonHeight = buttonWidth / textureAspect;
        float maximumButtonHeight = Screen.height * 0.23f;

        if (buttonHeight > maximumButtonHeight)
        {
            buttonHeight = maximumButtonHeight;
            buttonWidth = buttonHeight * textureAspect;
        }

        return new Rect(
            (Screen.width - buttonWidth) * 0.5f,
            Screen.height * 0.59f,
            buttonWidth,
            buttonHeight
        );
    }


    private void DrawUsePhotoButton(Rect buttonRect)
    {
        if (usePhotoButtonSprite == null ||
            usePhotoButtonSprite.texture == null)
        {
            return;
        }

        Texture2D buttonTexture = usePhotoButtonSprite.texture;

        GUIStyle imageButtonStyle = new GUIStyle(GUIStyle.none);

        GUI.enabled = !isLoadingMainScene;

        if (GUI.Button(
                buttonRect,
                new GUIContent(buttonTexture),
                imageButtonStyle))
        {
            UseCurrentPhoto();
        }

        GUI.enabled = true;
    }


    private void DrawStatusMessage()
    {

        GUIStyle style = new GUIStyle(GUI.skin.box)
        {
            alignment = TextAnchor.MiddleCenter,
            fontSize = 24,
            wordWrap = true,
            normal =
            {
                textColor = Color.white
            }
        };

        Rect messageRect = new Rect(
            Screen.width * 0.15f,
            Screen.height * 0.35f,
            Screen.width * 0.7f,
            Screen.height * 0.3f
        );

        GUI.Box(messageRect, statusMessage, style);
    }


    private void OnDestroy()
    {
        foreach (UnityEngine.Object resource in generatedResources)
        {
            if (resource != null)
            {
                Destroy(resource);
            }
        }

        generatedResources.Clear();
    }
}
