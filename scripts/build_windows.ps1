param(
  [string]$Python = "python",
  [switch]$OneFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Step {
  param(
    [Parameter(Mandatory = $true)][string]$Label,
    [Parameter(Mandatory = $true)][scriptblock]$Action
  )
  & $Action
  $exitCode = 0
  if (Test-Path variable:global:LASTEXITCODE) {
    $exitCode = [int]$global:LASTEXITCODE
  }
  if ($exitCode -ne 0) {
    throw "$Label failed with exit code $exitCode"
  }
}

Write-Host "[Build] Creating venv and installing requirements..."
$envDir = Join-Path $PSScriptRoot ".venv"
if (!(Test-Path $envDir)) {
  & $Python -m venv $envDir
}

# Prefer explicit venv executables by probing filesystem paths so this works
# in both Windows PowerShell 5.1 and PowerShell 7+.
$winPy = Join-Path $envDir "Scripts\python.exe"
$nixPy = Join-Path $envDir "bin/python"
$winPip = Join-Path $envDir "Scripts\pip.exe"
$nixPip = Join-Path $envDir "bin/pip"

if (Test-Path $winPy) {
  $pip = $winPip
  $py = $winPy
} elseif (Test-Path $nixPy) {
  $pip = $nixPip
  $py = $nixPy
} else {
  throw "Unable to locate virtualenv python executable in '$envDir'."
}

# Use python -m pip to avoid self-upgrade restrictions
Invoke-Step "pip upgrade" { & $py -m pip install --upgrade pip }
Invoke-Step "requirements install" {
  & $py -m pip install -r (Join-Path $PSScriptRoot "..\requirements.txt")
}
Invoke-Step "keyring import check" {
  & $py -c "import keyring; import keyring.errors; from importlib.metadata import version; print(version('keyring'))"
}

$iconPath = Join-Path $PSScriptRoot "..\assets\icons\silverestimate.ico"

Write-Host "[Build] Running PyInstaller..."
$spec = Join-Path $PSScriptRoot "..\SilverEstimate.spec"
if ($OneFile) {
  Invoke-Step "PyInstaller onefile build" {
    & $py -m PyInstaller `
      --clean `
      --noconfirm `
      --onefile `
      --windowed `
      --icon $iconPath `
      --name SilverEstimate `
      --hidden-import passlib.handlers.argon2 `
      --hidden-import passlib.handlers.bcrypt `
      --hidden-import keyring `
      --hidden-import keyring.errors `
      --hidden-import keyring.backends `
      --hidden-import keyring.backends.Windows `
      --hidden-import keyring.backends.fail `
      --hidden-import keyring.backends.null `
      main.py
  }
} elseif (Test-Path $spec) {
  Invoke-Step "PyInstaller spec build" { & $py -m PyInstaller --clean --noconfirm $spec }
} else {
  Invoke-Step "PyInstaller default build" {
    & $py -m PyInstaller `
      --clean `
      --noconfirm `
      --windowed `
      --icon $iconPath `
      --name SilverEstimate `
      --hidden-import passlib.handlers.argon2 `
      --hidden-import passlib.handlers.bcrypt `
      --hidden-import keyring `
      --hidden-import keyring.errors `
      --hidden-import keyring.backends `
      --hidden-import keyring.backends.Windows `
      --hidden-import keyring.backends.fail `
      --hidden-import keyring.backends.null `
      main.py
  }
}

Write-Host "[Build] Packaging zip..."
$outDir = Join-Path $PSScriptRoot "..\dist\SilverEstimate"
$outExe = Join-Path $PSScriptRoot "..\dist\SilverEstimate.exe"

$versionFile = Join-Path $PSScriptRoot '..\silverestimate\infrastructure\app_constants.py'
$version = (Get-Content $versionFile | Select-String -Pattern 'APP_VERSION\s*=\s*"([^"]+)' -AllMatches).Matches.Groups[1].Value
if (-not $version) { $version = "dev" }

$versionedExeName = "SilverEstimate-v$version.exe"
$versionedExePath = Join-Path $PSScriptRoot "..\dist\$versionedExeName"
$onedirExePath = Join-Path $outDir "SilverEstimate.exe"

# Keep the canonical output name, but also publish a versioned exe artifact.
if (Test-Path $outExe -PathType Leaf) {
  Copy-Item -Path $outExe -Destination $versionedExePath -Force
} elseif (Test-Path $onedirExePath -PathType Leaf) {
  Copy-Item -Path $onedirExePath -Destination $versionedExePath -Force
}

$zipName = "SilverEstimate-v$version-win64.zip"
$zipPath = Join-Path $PSScriptRoot "..\dist\$zipName"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
if (Test-Path $outDir -PathType Container) {
  Compress-Archive -Path (Join-Path $PSScriptRoot "..\dist\SilverEstimate\*") -DestinationPath $zipPath
} elseif (Test-Path $outExe -PathType Leaf) {
  Compress-Archive -Path $outExe -DestinationPath $zipPath
} else {
  throw "Expected build output not found: '$outDir' or '$outExe'."
}

Write-Host "[Build] Done: $zipPath"
if (Test-Path $versionedExePath -PathType Leaf) {
  Write-Host "[Build] Versioned EXE: $versionedExePath"
}




