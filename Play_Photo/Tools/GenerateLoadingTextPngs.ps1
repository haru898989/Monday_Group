param(
    [string]$OutputDirectory = "Assets/Main/Resources/LoadingText"
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

$projectRoot = Split-Path -Parent $PSScriptRoot
$fontPath = Join-Path $projectRoot "Assets/NotoSansJP-Medium.ttf"
$outputPath = Join-Path $projectRoot $OutputDirectory

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null

$fontCollection = New-Object System.Drawing.Text.PrivateFontCollection
$fontCollection.AddFontFile($fontPath)
$fontFamily = $fontCollection.Families[0]

function Write-CenteredTextPng {
    param(
        [string]$FileName,
        [string]$Text,
        [int]$Width,
        [int]$Height,
        [float]$FontSize,
        [System.Drawing.Color]$TextColor,
        [System.Drawing.Color]$ShadowColor
    )

    $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.Clear([System.Drawing.Color]::Transparent)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    $font = New-Object System.Drawing.Font(
        $fontFamily,
        $FontSize,
        [System.Drawing.FontStyle]::Regular,
        [System.Drawing.GraphicsUnit]::Pixel
    )

    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center

    $shadowBrush = New-Object System.Drawing.SolidBrush($ShadowColor)
    $textBrush = New-Object System.Drawing.SolidBrush($TextColor)

    $shadowRect = New-Object System.Drawing.RectangleF(2, 3, $Width, $Height)
    $textRect = New-Object System.Drawing.RectangleF(0, 0, $Width, $Height)

    $graphics.DrawString($Text, $font, $shadowBrush, $shadowRect, $format)
    $graphics.DrawString($Text, $font, $textBrush, $textRect, $format)

    $destination = Join-Path $outputPath $FileName
    $bitmap.Save($destination, [System.Drawing.Imaging.ImageFormat]::Png)

    $textBrush.Dispose()
    $shadowBrush.Dispose()
    $format.Dispose()
    $font.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}

$gold = [System.Drawing.Color]::FromArgb(255, 255, 184, 46)
$white = [System.Drawing.Color]::FromArgb(255, 255, 255, 255)
$darkShadow = [System.Drawing.Color]::FromArgb(210, 45, 8, 4)

Write-CenteredTextPng "loading_title.png" "写真をかざる準備をしています" 1300 100 52 $gold $darkShadow
Write-CenteredTextPng "stage_preparing.png" "展示の準備を始めています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_receiving.png" "写真を受け取っています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_inspecting.png" "写真の中を見ています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_detecting.png" "写真の中のものを見つけています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_cleaning.png" "写真をきれいに整えています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_gimmicks.png" "楽しいしかけを準備しています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_displaying.png" "写真をかざっています" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "stage_complete.png" "写真をかざす準備ができました" 1300 72 34 $white $darkShadow
Write-CenteredTextPng "elapsed_label.png" "経過時間" 210 52 27 $gold $darkShadow

$fontCollection.Dispose()

function Write-FolderMeta {
    param([string]$DirectoryPath, [string]$Guid)

    $meta = @"
fileFormatVersion: 2
guid: $Guid
folderAsset: yes
DefaultImporter:
  externalObjects: {}
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"@

    [System.IO.File]::WriteAllText(
        "$DirectoryPath.meta",
        $meta.TrimStart() + "`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
}

function Write-TextureMeta {
    param([string]$ImagePath, [string]$Guid)

    $meta = @"
fileFormatVersion: 2
guid: $Guid
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {}
  serializedVersion: 13
  mipmaps:
    mipMapMode: 0
    enableMipMap: 0
    sRGBTexture: 1
    linearTexture: 0
    fadeOut: 0
    borderMipMap: 0
    mipMapsPreserveCoverage: 0
    alphaTestReferenceValue: 0.5
    mipMapFadeDistanceStart: 1
    mipMapFadeDistanceEnd: 3
  bumpmap:
    convertToNormalMap: 0
    externalNormalMap: 0
    heightScale: 0.25
    normalMapFilter: 0
    flipGreenChannel: 0
  isReadable: 0
  streamingMipmaps: 0
  streamingMipmapsPriority: 0
  vTOnly: 0
  ignoreMipmapLimit: 0
  grayScaleToAlpha: 0
  generateCubemap: 6
  cubemapConvolution: 0
  seamlessCubemap: 0
  textureFormat: 1
  maxTextureSize: 2048
  textureSettings:
    serializedVersion: 2
    filterMode: 1
    aniso: 1
    mipBias: 0
    wrapU: 1
    wrapV: 1
    wrapW: 1
  nPOTScale: 0
  lightmap: 0
  compressionQuality: 50
  spriteMode: 0
  spriteExtrude: 1
  spriteMeshType: 1
  alignment: 0
  spritePivot: {x: 0.5, y: 0.5}
  spritePixelsToUnits: 100
  spriteBorder: {x: 0, y: 0, z: 0, w: 0}
  spriteGenerateFallbackPhysicsShape: 1
  alphaUsage: 1
  alphaIsTransparency: 1
  spriteTessellationDetail: -1
  textureType: 0
  textureShape: 1
  singleChannelComponent: 0
  flipbookRows: 1
  flipbookColumns: 1
  maxTextureSizeSet: 0
  compressionQualitySet: 0
  textureFormatSet: 0
  ignorePngGamma: 0
  applyGammaDecoding: 0
  swizzle: 50462976
  cookieLightType: 0
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: 2048
    resizeAlgorithm: 0
    textureFormat: -1
    textureCompression: 1
    compressionQuality: 50
    crunchedCompression: 0
    allowsAlphaSplitting: 0
    overridden: 0
    ignorePlatformSupport: 0
    androidETC2FallbackOverride: 0
    forceMaximumCompressionQuality_BC6H_BC7: 0
  spriteSheet:
    serializedVersion: 2
    sprites: []
    outline: []
    physicsShape: []
    bones: []
    spriteID: 
    internalID: 0
    vertices: []
    indices: 
    edges: []
    weights: []
    secondaryTextures: []
    nameFileIdTable: {}
  mipmapLimitGroupName: 
  pSDRemoveMatte: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"@

    [System.IO.File]::WriteAllText(
        "$ImagePath.meta",
        $meta.TrimStart() + "`n",
        (New-Object System.Text.UTF8Encoding($false))
    )
}

Write-FolderMeta (Join-Path $projectRoot "Assets/Main/Resources") "cf3426aaf48c4ba2a18dfb7bfe71e4b0"
Write-FolderMeta $outputPath "286ce2f9d5224aeea826a8df8db17bd0"

$imageGuids = @{
    "loading_title.png" = "266a6cf405ca4a54b35167ab2d89d2d1"
    "stage_preparing.png" = "4a7fda26508649a199a725635e74b0bb"
    "stage_receiving.png" = "6c22417cdfd641a692a16e1637d4f0ce"
    "stage_inspecting.png" = "483e57dbcccf4d9d965944c321e70138"
    "stage_detecting.png" = "974826bf6bc646728ebdcb06554b0c4d"
    "stage_cleaning.png" = "dd065ff106a148d89d613d6ac145c0c1"
    "stage_gimmicks.png" = "234c1808b82a4b1a9e2c33fd783d18dd"
    "stage_displaying.png" = "1306d5b53f0e42a28020b73b3c0f04bf"
    "stage_complete.png" = "81d7736b174f4ca1a6a8599bc7170b58"
    "elapsed_label.png" = "b4d52f9efcef4eaab1b48271d393f514"
}

foreach ($entry in $imageGuids.GetEnumerator()) {
    Write-TextureMeta (Join-Path $outputPath $entry.Key) $entry.Value
}
