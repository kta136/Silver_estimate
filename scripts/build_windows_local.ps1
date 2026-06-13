Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$appConstants = Join-Path $repoRoot "silverestimate\infrastructure\app_constants.py"
$specPath = Join-Path $repoRoot "SilverEstimate.spec"
$distDir = Join-Path $repoRoot "dist"
$requiredPython = [version]"3.14"

function Get-AppVersion {
    $match = Select-String -Path $appConstants -Pattern 'APP_VERSION = "([^"]+)"'
    if (-not $match) {
        throw "Could not read APP_VERSION from $appConstants"
    }
    return $match.Matches[0].Groups[1].Value
}

function Get-PythonVersion([string]$pythonExe) {
    try {
        $versionText = & $pythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null |
            Select-Object -First 1
        if (-not $versionText) {
            return $null
        }
        return [version]$versionText
    }
    catch {
        return $null
    }
}

function Test-PythonForBuild([string]$pythonExe) {
    if (-not $pythonExe -or -not (Test-Path $pythonExe)) {
        return $false
    }
    $version = Get-PythonVersion -pythonExe $pythonExe
    return $version -and $version -ge $requiredPython
}

function Get-Python314FromLauncher {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        return $null
    }

    $pythonExe = & $launcher.Source -3.14 -c "import sys; print(sys.executable)" 2>$null |
        Select-Object -First 1
    if (Test-PythonForBuild -pythonExe $pythonExe) {
        return $pythonExe
    }
    return $null
}

function Get-Python314FromRegistry {
    $registryPaths = @(
        'HKCU:\SOFTWARE\Python\PythonCore\3.14\InstallPath',
        'HKLM:\SOFTWARE\Python\PythonCore\3.14\InstallPath',
        'HKCU:\SOFTWARE\WOW6432Node\Python\PythonCore\3.14\InstallPath',
        'HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\3.14\InstallPath'
    )

    foreach ($path in $registryPaths) {
        $properties = Get-ItemProperty $path -ErrorAction SilentlyContinue
        if (-not $properties) {
            continue
        }

        $executableProperty = $properties.PSObject.Properties["ExecutablePath"]
        $pythonExe = if ($executableProperty) { $executableProperty.Value } else { $null }

        $defaultProperty = $properties.PSObject.Properties["(default)"]
        if (-not $pythonExe -and $defaultProperty -and $defaultProperty.Value) {
            $pythonExe = Join-Path $defaultProperty.Value "python.exe"
        }

        if (Test-PythonForBuild -pythonExe $pythonExe) {
            return $pythonExe
        }
    }
    return $null
}

function Find-WindowsPython {
    $preferred = @(
        (Get-Python314FromLauncher),
        (Get-Python314FromRegistry),
        (Join-Path $repoRoot ".venv\Scripts\python.exe")
    )

    foreach ($pythonExe in $preferred) {
        if (Test-PythonForBuild -pythonExe $pythonExe) {
            return $pythonExe
        }
    }

    $candidates = @(
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Python",
        "C:\Python*",
        "C:\Program Files\Python*",
        "C:\Program Files (x86)\Python*"
    )

    foreach ($pattern in $candidates) {
        $directories = Get-ChildItem -Path $pattern -Directory -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending
        foreach ($directory in $directories) {
            $pythonExe = Join-Path $directory.FullName "python.exe"
            if (Test-PythonForBuild -pythonExe $pythonExe) {
                return $pythonExe
            }
        }
    }

    throw "Python 3.14 or newer was not found in common Windows install locations."
}

function Sync-ProjectDependencies([string]$pythonExe) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & $uv.Source sync --extra dev --python $pythonExe --locked
        if (-not $?) {
            throw "uv dependency sync failed."
        }

        $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
        if (Test-PythonForBuild -pythonExe $venvPython) {
            return $venvPython
        }
    }

    & $pythonExe -m pip install --upgrade pip
    if (-not $?) {
        throw "pip upgrade failed."
    }
    & $pythonExe -m pip install -e ".[dev]"
    if (-not $?) {
        throw "project dependency install failed."
    }
    return $pythonExe
}

function Ensure-PyInstaller([string]$pythonExe) {
    & $pythonExe -m PyInstaller --version | Out-Null
    if ($?) {
        return
    }
    & $pythonExe -m pip install pyinstaller
    if (-not $?) {
        throw "PyInstaller installation failed."
    }
}

$pythonExe = Find-WindowsPython

$version = Get-AppVersion
$versionedExe = Join-Path $distDir "SilverEstimate-v$version.exe"
$versionedZip = Join-Path $distDir "SilverEstimate-v$version-win64.zip"
$baseExe = Join-Path $distDir "SilverEstimate.exe"

Push-Location $repoRoot
try {
    $buildPython = Sync-ProjectDependencies -pythonExe $pythonExe
    Ensure-PyInstaller -pythonExe $buildPython

    & $buildPython -m PyInstaller --clean --noconfirm $specPath
    if (-not $?) {
        throw "PyInstaller build failed."
    }

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
