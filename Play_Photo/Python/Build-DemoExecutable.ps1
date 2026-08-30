param(
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"
$pythonDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$specPath = Join-Path $pythonDirectory "demo_click_udp.spec"

Push-Location $pythonDirectory
try {
    $arguments = @("-m", "PyInstaller", "--noconfirm")
    if (-not $SkipClean) {
        $arguments += "--clean"
    }
    $arguments += $specPath

    if ($env:MAGIC_PHOTO_PYTHON) {
        & $env:MAGIC_PHOTO_PYTHON @arguments
    }
    else {
        & py @arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }

    $executablePath = Join-Path (
        Join-Path $pythonDirectory "dist\demo_click_udp"
    ) "demo_click_udp.exe"

    if (-not (Test-Path -LiteralPath $executablePath)) {
        throw "Executable was not generated: $executablePath"
    }

    Write-Host "Generated: $executablePath"
}
finally {
    Pop-Location
}
