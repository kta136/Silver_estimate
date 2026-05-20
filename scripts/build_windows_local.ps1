Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$appConstants = Join-Path $repoRoot "silverestimate\infrastructure\app_constants.py"
$specPath = Join-Path $repoRoot "SilverEstimate.spec"
$distDir = Join-Path $repoRoot "dist"

function Get-AppVersion {
    $match = Select-String -Path $appConstants -Pattern 'APP_VERSION = "([^"]+)"'
    if (-not $match) {
        throw "Could not read APP_VERSION from $appConstants"
    }
    return $match.Matches[0].Groups[1].Value
}

function Find-WindowsPython {
    $registryExe = $null
    try {
        $registryExe = (Get-ItemProperty `
            'HKCU:\SOFTWARE\Python\PythonCore\3.13\InstallPath' `
            -ErrorAction SilentlyContinue).ExecutablePath
    }
    catch {
        $registryExe = $null
    }
    if ($registryExe -and (Test-Path $registryExe)) {
        return $registryExe
    }

    $candidates = @(
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python",
        "C:\Python*",
        "C:\Program Files\Python*",
        "C:\Program Files (x86)\Python*"
    )

    foreach ($pattern in $candidates) {
        Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            ForEach-Object {
                $pythonExe = Join-Path $_.FullName "python.exe"
                if (Test-Path $pythonExe) {
                    return $pythonExe
                }
            }
    }

    throw "Windows python.exe was not found in common install locations."
}

function Ensure-PyInstaller([string]$pythonExe) {
    try {
        & $pythonExe -m PyInstaller --version | Out-Null
        return
    }
    catch {
        & $pythonExe -m pip install pyinstaller
    }
}

$pythonExe = Find-WindowsPython
Ensure-PyInstaller -pythonExe $pythonExe

$version = Get-AppVersion
$versionedExe = Join-Path $distDir "SilverEstimate-v$version.exe"
$versionedZip = Join-Path $distDir "SilverEstimate-v$version-win64.zip"
$baseExe = Join-Path $distDir "SilverEstimate.exe"

Push-Location $repoRoot
try {
    & $pythonExe -m PyInstaller --clean --noconfirm $specPath

    if (-not (Test-Path $baseExe)) {
        throw "Build did not produce $baseExe"
    }

    if (Test-Path $versionedExe) {
        Remove-Item -Force $versionedExe
    }
    if (Test-Path $versionedZip) {
        Remove-Item -Force $versionedZip
    }

    Copy-Item -Force $baseExe $versionedExe
    Compress-Archive -Path $versionedExe -DestinationPath $versionedZip

    Write-Host "Windows executable: $versionedExe"
    Write-Host "Windows archive: $versionedZip"
}
finally {
    Pop-Location
}
