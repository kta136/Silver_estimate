param(
  [string]$Python = "python",
  [switch]$OneFile
)

Write-Host "[Build] Creating venv and installing requirements..."
$envDir = Join-Path $PSScriptRoot ".venv"
if (!(Test-Path $envDir)) {
  & $Python -m venv $envDir
}

if ($IsWindows) {
  $pip = Join-Path $envDir "Scripts\pip.exe"
  $py  = Join-Path $envDir "Scripts\python.exe"
} else {
  $pip = Join-Path $envDir "bin/pip"
  $py  = Join-Path $envDir "bin/python"
}

& $pip install --upgrade pip
& $pip install -r (Join-Path $PSScriptRoot "..\requirements.txt")

Write-Host "[Build] Running PyInstaller..."
$spec = Join-Path $PSScriptRoot "..\silverestimate.spec"
if ($OneFile) {
  & $py -m PyInstaller --noconfirm --onefile --windowed --name SilverEstimate \
    --hidden-import passlib.handlers.argon2 \
    --hidden-import passlib.handlers.bcrypt \
    main.py
} elseif (Test-Path $spec) {
  & $py -m PyInstaller --noconfirm $spec
} else {
  & $py -m PyInstaller --noconfirm --windowed --name SilverEstimate \
    --hidden-import passlib.handlers.argon2 \
    --hidden-import passlib.handlers.bcrypt \
    main.py
}

Write-Host "[Build] Packaging zip..."
$outDir = Join-Path $PSScriptRoot "..\dist\SilverEstimate"
if (!(Test-Path $outDir)) { throw "Output directory not found: $outDir" }

$versionFile = Join-Path $PSScriptRoot "..\app_constants.py"
$version = (Get-Content $versionFile | Select-String -Pattern 'APP_VERSION\s*=\s*"([^"]+)' -AllMatches).Matches.Groups[1].Value
if (-not $version) { $version = "dev" }

$zipName = "SilverEstimate-v$version-win64.zip"
$zipPath = Join-Path $PSScriptRoot "..\dist\$zipName"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $PSScriptRoot "..\dist\SilverEstimate\*") -DestinationPath $zipPath

Write-Host "[Build] Done: $zipPath"
