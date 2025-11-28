#!/usr/bin/env pwsh
param(
  [string]$PythonPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Build a Windows single-file executable for the Go/No-Go task (GoStop) only.
# Requires: python + PyInstaller (in the chosen environment) and Pillow.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$BuildDir = Join-Path $RootDir "build/gostop"

$AppName = "GoStop"
$EntryPoint = Join-Path $RootDir "gostop/gui/gui.py"
$PngIcon = Join-Path $RootDir "gostop/icon/icon.png"
$IcoIcon = Join-Path $BuildDir "icon.ico"

$DistDir = Join-Path $BuildDir "dist"
$WorkDir = Join-Path $BuildDir "pyi_build"
$SpecDir = $BuildDir
$PythonExe = $null

function Convert-PngToIco {
  param(
    [string]$PythonExe,
    [string]$PngPath,
    [string]$IcoPath
  )

  if (-not (Test-Path $PngPath)) { return $false }

  $needsRebuild = -not (Test-Path $IcoPath)
  if (-not $needsRebuild) {
    $needsRebuild = (Get-Item $PngPath).LastWriteTimeUtc -gt (Get-Item $IcoPath).LastWriteTimeUtc
  }
  if (-not $needsRebuild) { return $true }

  Write-Host "Converting PNG icon to ICO: $IcoPath"
  $icoScript = @'
from PIL import Image
import sys

png, ico = sys.argv[1:3]
image = Image.open(png)
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
image.save(ico, format="ICO", sizes=sizes)
'@
  try {
    $null = $icoScript | & $PythonExe - $PngPath $IcoPath 2>$null
    if ($LASTEXITCODE -eq 0 -and (Test-Path $IcoPath)) { return $true }
    Write-Warning "Failed to generate $IcoPath from $PngPath; falling back to default PyInstaller icon."
  } catch {
    Write-Warning "Exception while generating ICO: $($_.Exception.Message)"
  }
  return $false
}

# Prefer an explicit python path, otherwise fall back to the active conda env if present, else PATH.
if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
  $PythonExe = $PythonPath
} elseif ($env:CONDA_PREFIX) {
  $Candidate = Join-Path $env:CONDA_PREFIX "python.exe"
  if (Test-Path $Candidate) { $PythonExe = $Candidate }
} elseif ($env:CONDA_DEFAULT_ENV -and $env:CONDA_EXE) {
  $CondaRoot = Split-Path (Split-Path $env:CONDA_EXE)
  $Candidate = Join-Path $CondaRoot "envs/$($env:CONDA_DEFAULT_ENV)/python.exe"
  if (Test-Path $Candidate) { $PythonExe = $Candidate }
}
if (-not $PythonExe) { $PythonExe = "python" }

$OldPythonPath = $env:PYTHONPATH
try {
  # Clear PYTHONPATH during the build to avoid leaking foreign packages that can break PyInstaller isolation.
  $env:PYTHONPATH = ""

  $pythonDisplayScript = @'
import sys
sys.stdout.write(sys.executable)
'@
  $pythonDisplay = $pythonDisplayScript | & $PythonExe - 2>$null
  if (-not $pythonDisplay -or $LASTEXITCODE -ne 0) {
    throw "Python interpreter not runnable: $PythonExe"
  }

  $pyiCheck = @'
import PyInstaller, sys
sys.stdout.write(PyInstaller.__version__)
'@
  $pyiVersion = $pyiCheck | & $PythonExe - 2>$null
  if ($LASTEXITCODE -ne 0 -or -not $pyiVersion) {
    throw "PyInstaller not found in: $pythonDisplay. Activate the env with PyInstaller or pass -PythonPath to that env's python.exe."
  }
  Write-Host "Using Python: $pythonDisplay (PyInstaller $pyiVersion)"

  New-Item -ItemType Directory -Force -Path $DistDir, $WorkDir, $SpecDir | Out-Null

  $dataArgs = @()
  if (Test-Path $PngIcon) {
    $dataArgs = @("--add-data", "$PngIcon;gostop/icon")
  }

  # Use the provided .ico or auto-generate from the PNG (requires Pillow) when missing/outdated.
  $iconArgs = @()
  if (Convert-PngToIco -PythonExe $PythonExe -PngPath $PngIcon -IcoPath $IcoIcon) {
    $iconArgs = @("--icon", $IcoIcon)
  } elseif (Test-Path $IcoIcon) {
    $iconArgs = @("--icon", $IcoIcon)
  }

  & $PythonExe -m PyInstaller --clean --noconfirm `
    --name $AppName `
    --onefile `
    --windowed `
    --workpath $WorkDir `
    --distpath $DistDir `
    --specpath $SpecDir `
    @dataArgs `
    @iconArgs `
    $EntryPoint

  Write-Host "Built executable at: $DistDir\$AppName.exe"
}
finally {
  $env:PYTHONPATH = $OldPythonPath
}
