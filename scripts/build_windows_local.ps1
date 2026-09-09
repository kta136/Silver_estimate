param(
    [ValidatePattern('^[A-Za-z0-9-]*$')]
    [string]$ArtifactSuffix = "",
    [switch]$Fast
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$appConstants = Join-Path $repoRoot "silverestimate\infrastructure\app_constants.py"
$deployConfig = Join-Path $repoRoot "pysidedeploy.spec"
$artifactValidator = Join-Path $repoRoot "scripts\validate_frozen_artifact.py"
$distDir = Join-Path $repoRoot "dist"
$pythonPinPath = Join-Path $repoRoot ".python-version"
$pythonPin = (Get-Content -LiteralPath $pythonPinPath -Raw).Trim()
if ($pythonPin -notmatch '^\d+\.\d+\.\d+$') {
    throw ".python-version must contain an exact major.minor.patch version."
}
$requiredPython = [version]$pythonPin
$nuitkaVersion = "4.2.1"

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
    return $version -and $version -eq $requiredPython
}

function Sync-ProjectDependencies {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        throw "uv is required for a locked release build but was not found on PATH."
    }

    & $uv.Source sync --extra dev --python $pythonPin --locked
    if ($LASTEXITCODE -ne 0) {
        throw "uv dependency sync failed with exit code $LASTEXITCODE."
    }

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (-not (Test-PythonForBuild -pythonExe $venvPython)) {
        throw "Locked dependency sync did not produce the pinned Python $pythonPin virtual environment."
    }
    return $venvPython
}

function Get-PySideDeploy([string]$pythonExe) {
    $scriptsDir = Split-Path -Parent $pythonExe
    $deployExe = Join-Path $scriptsDir "pyside6-deploy.exe"
    if (-not (Test-Path $deployExe)) {
        throw "pyside6-deploy is unavailable at $deployExe"
    }
    return $deployExe
}

function Find-Dumpbin {
    $onPath = Get-Command dumpbin.exe -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }

    $searchRoots = @(
        "C:\BuildTools\VC\Tools\MSVC",
        (Join-Path ${env:ProgramFiles} "Microsoft Visual Studio"),
        (Join-Path ${env:ProgramFiles(x86)} "Microsoft Visual Studio")
    )
    foreach ($root in $searchRoots) {
        if (-not (Test-Path -LiteralPath $root)) {
            continue
        }
        $candidate = Get-ChildItem -LiteralPath $root -Recurse -Filter "dumpbin.exe" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*\bin\Hostx64\x64\dumpbin.exe" } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) {
            return $candidate.FullName
        }
    }
    throw "64-bit dumpbin.exe is required for native dependency discovery."
}

function Remove-DistBuildDirectory([string]$target) {
    if (-not (Test-Path -LiteralPath $target)) {
        return
    }
    $resolvedDist = [IO.Path]::GetFullPath($distDir).TrimEnd("\")
    $resolvedTarget = [IO.Path]::GetFullPath($target).TrimEnd("\")
    if (
        $resolvedTarget -eq $resolvedDist -or
        -not $resolvedTarget.StartsWith("$resolvedDist\", [StringComparison]::OrdinalIgnoreCase)
    ) {
        throw "Refusing to remove build directory outside dist: $resolvedTarget"
    }
    Remove-Item -LiteralPath $resolvedTarget -Recurse -Force
}

function Get-Sha256([string]$path) {
    $stream = [IO.File]::OpenRead($path)
    try {
        $sha256 = [Security.Cryptography.SHA256]::Create()
        try {
            return [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace("-", "")
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Invoke-BuildStage([string]$name, [scriptblock]$action) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    Write-Host "Starting: $name"
    try {
        & $action
    }
    finally {
        $timer.Stop()
        $stageTimings[$name] = [Math]::Round($timer.Elapsed.TotalSeconds, 2)
        Write-Host ("{0}: {1:N2}s" -f $name, $timer.Elapsed.TotalSeconds)
    }
}

function Invoke-PySideDeployBuild(
    [string]$deployExe,
    [string]$configFile,
    [string]$mode,
    [string]$dumpbinExe
) {
    $previousPath = $env:PATH
    try {
        $env:PATH = "$(Split-Path -Parent $dumpbinExe);$previousPath"
        & $deployExe --config-file $configFile --force --mode $mode --nuitka-version $nuitkaVersion
        if ($LASTEXITCODE -ne 0) {
            throw "pyside6-deploy $mode build failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        $env:PATH = $previousPath
    }
}

function Invoke-ArtifactValidation([string]$pythonExe, [string]$artifact) {
    if (-not (Test-Path -LiteralPath $artifactValidator)) {
        throw "Frozen artifact validator is unavailable at $artifactValidator"
    }

    $previousPath = $env:PATH
    $hadConsoleOverride = Test-Path "Env:\SILVER_SHOW_CONSOLE"
    $previousConsoleOverride = $env:SILVER_SHOW_CONSOLE
    try {
        # Do not let Python, Qt, OpenSSL, or VC runtime files installed on the
        # build machine satisfy a missing dependency in the frozen artifact.
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        $env:SILVER_SHOW_CONSOLE = "1"
        & $pythonExe $artifactValidator --artifact $artifact
        if ($LASTEXITCODE -ne 0) {
            throw "Frozen artifact validation failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        $env:PATH = $previousPath
        if ($hadConsoleOverride) {
            $env:SILVER_SHOW_CONSOLE = $previousConsoleOverride
        }
        else {
            Remove-Item "Env:\SILVER_SHOW_CONSOLE" -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-NativeOnefileValidation(
    [string]$dumpbinExe,
    [string]$artifact
) {
    $dumpbinOutput = @(& $dumpbinExe /nologo /dependents $artifact)
    if ($LASTEXITCODE -ne 0) {
        throw "Native dependency inspection failed with exit code $LASTEXITCODE."
    }

    $dependencies = @(
        $dumpbinOutput |
            ForEach-Object {
                if ($_ -match '^\s+([A-Za-z0-9._-]+\.dll)\s*$') {
                    $Matches[1].ToLowerInvariant()
                }
            } |
            Sort-Object -Unique
    )
    $allowedSystemDependencies = @("kernel32.dll", "shell32.dll")
    $unexpectedDependencies = @(
        $dependencies | Where-Object { $allowedSystemDependencies -notcontains $_ }
    )
    if ($unexpectedDependencies.Count -gt 0) {
        throw (
            "One-file loader has non-system startup dependencies: " +
            ($unexpectedDependencies -join ", ")
        )
    }
    foreach ($requiredDependency in $allowedSystemDependencies) {
        if ($dependencies -notcontains $requiredDependency) {
            throw "One-file loader is missing expected dependency $requiredDependency"
        }
    }
    Write-Host "One-file native dependencies: $($dependencies -join ', ')"
}

if ($env:OS -ne "Windows_NT" -or -not [Environment]::Is64BitOperatingSystem) {
    throw "The local release build requires 64-bit Windows."
}

$version = Get-AppVersion
# Keep development artifacts separate from the release executable by default.
if ($Fast -and -not $ArtifactSuffix) {
    $ArtifactSuffix = "fast"
}
$buildProfile = if ($Fast) { "fast" } else { "release" }
$artifactTag = if ($ArtifactSuffix) { "-$ArtifactSuffix" } else { "" }
$versionedExe = Join-Path $distDir "SilverEstimate-v$version$artifactTag.exe"
$baseExe = Join-Path $distDir "SilverEstimate.exe"
$standaloneDir = Join-Path $distDir "SilverEstimate.dist"
$portableDir = Join-Path $distDir "SilverEstimate-v$version-portable"
$portableZip = Join-Path $distDir "SilverEstimate-v$version-portable-win64.zip"
$versionedZip = Join-Path $distDir "SilverEstimate-v$version-win64.zip"
$temporaryOnefileConfig = Join-Path $repoRoot ".pysidedeploy-local-onefile.spec"
$timingsDir = Join-Path $repoRoot "artifacts\local-build"
$timingsFile = Join-Path $timingsDir "build-timings$artifactTag.json"
$stageTimings = [ordered]@{}
$buildStatus = "failed"
$buildTimer = [Diagnostics.Stopwatch]::StartNew()

Push-Location $repoRoot
try {
    New-Item -ItemType Directory -Path $timingsDir -Force | Out-Null
    Write-Host "Build profile: $buildProfile"
    $buildPython = Invoke-BuildStage "dependencies" { Sync-ProjectDependencies }
    $deployExe = Get-PySideDeploy -pythonExe $buildPython
    $dumpbinExe = Find-Dumpbin

    New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    if (Test-Path -LiteralPath $baseExe) {
        Remove-Item -LiteralPath $baseExe -Force
    }
    Remove-DistBuildDirectory -target $standaloneDir
    Remove-DistBuildDirectory -target $portableDir
    foreach ($obsoleteArtifact in @($portableZip, $versionedZip)) {
        if (Test-Path -LiteralPath $obsoleteArtifact) {
            Remove-Item -LiteralPath $obsoleteArtifact -Force
        }
    }

    Copy-Item -LiteralPath $deployConfig -Destination $temporaryOnefileConfig -Force
    $configContent = Get-Content -LiteralPath $temporaryOnefileConfig -Raw
    $configContent = $configContent -replace '(?m)^extra_args = ', "extra_args = --file-version=$version --product-version=$version "
    if ($Fast) {
        # Retain normal C optimization and all packaging checks; avoid the
        # expensive whole-program optimization pass for local iteration.
        $configContent = $configContent -replace '(?m)^extra_args = ', 'extra_args = --lto=no '
    }
    [IO.File]::WriteAllText($temporaryOnefileConfig, $configContent, [Text.UTF8Encoding]::new($false))
    Invoke-BuildStage "compile_and_package" {
        Invoke-PySideDeployBuild `
            -deployExe $deployExe `
            -configFile $temporaryOnefileConfig `
            -mode "onefile" `
            -dumpbinExe $dumpbinExe
    }

    if (-not (Test-Path -LiteralPath $baseExe -PathType Leaf)) {
        throw "Build did not produce $baseExe"
    }
    Invoke-BuildStage "validation" {
        Invoke-ArtifactValidation -pythonExe $buildPython -artifact $baseExe
        Invoke-NativeOnefileValidation -dumpbinExe $dumpbinExe -artifact $baseExe
    }

    if (Test-Path -LiteralPath $versionedExe) {
        Remove-Item -LiteralPath $versionedExe -Force
    }

    Copy-Item -LiteralPath $baseExe -Destination $versionedExe -Force
    $baseHash = Get-Sha256 -path $baseExe
    $versionedHash = Get-Sha256 -path $versionedExe
    if ($baseHash -ne $versionedHash) {
        throw "Versioned executable does not match the validated build artifact."
    }

    Remove-Item -LiteralPath $baseExe -Force
    Write-Host "Windows executable: $versionedExe"
    Write-Host "Executable SHA-256: $versionedHash"
    $buildStatus = "success"
}
finally {
    if (Test-Path -LiteralPath $temporaryOnefileConfig) {
        Remove-Item -LiteralPath $temporaryOnefileConfig -Force
    }
    Pop-Location
    $buildTimer.Stop()
    $timings = [ordered]@{
        profile = $buildProfile
        status = $buildStatus
        total_seconds = [Math]::Round($buildTimer.Elapsed.TotalSeconds, 2)
        stages_seconds = $stageTimings
    }
    if (Test-Path -LiteralPath $timingsDir) {
        $timings | ConvertTo-Json | Set-Content -LiteralPath $timingsFile -Encoding UTF8
    }
    Write-Host ("Total build time: {0:N2}s ({1})" -f $buildTimer.Elapsed.TotalSeconds, $buildStatus)
    Write-Host "Build timings: $timingsFile"
}
