param(
    [switch]$Gpu,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating .venv..."
    python -m venv .venv
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip
if ($Gpu) {
    Write-Host "Installing CPU + CUDA runtime dependencies (large download)..."
    & $Python -m pip install -e ".[dev,gpu]"
} else {
    & $Python -m pip install -e ".[dev]"
}

if ($Clean) {
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "build", "dist"
}

if ($Gpu) {
    $env:SUBLOOM_BUNDLE_CUDA = "1"
} else {
    Remove-Item Env:SUBLOOM_BUNDLE_CUDA -ErrorAction SilentlyContinue
}

& $Python -m PyInstaller "packaging\subloom.spec" --noconfirm
Write-Host ""
Write-Host "Build output: dist\SubLoom"
Write-Host "Models are not included; they download on first use."
