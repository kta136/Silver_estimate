param(
    [string]$OutputDirectory = "dist/sqlcipher",
    [switch]$KeepSources,
    [switch]$ReuseWorkspace
)

$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $true
$SqlCipherRevision = "f9788efa8ac4dfed75c03e4756b1666a1d0845da"
$SqlCipherCommit = "810db22f575ee7cf94ea96a3e91622b5fcece3dc"
$BindingRevision = "14fc2632676b20011e0bba64fdda49763a2dd2ec"
$OpenSslRevision = "f52b9f81a985dc1e45b28cd7b5671feb32815b83"
$OpenSslCommit = "7b371d80d959ec9ab4139d09d78e83c090de9779"
$ControlledVersion = "0.6.2+silverestimate.4.17.0.1"
$env:SOURCE_DATE_EPOCH = "1783018435"
$env:PYTHONHASHSEED = "0"
$Workspace = Join-Path ([IO.Path]::GetTempPath()) "silverestimate-sqlcipher-build"
$Workspace = [IO.Path]::GetFullPath($Workspace)
$ExpectedParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
if (-not $Workspace.StartsWith($ExpectedParent, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use build workspace outside the system temporary directory"
}
if ($ReuseWorkspace) {
    if (-not (Test-Path -LiteralPath $Workspace)) {
        throw "Cannot reuse missing build workspace: $Workspace"
    }
} else {
    if (Test-Path -LiteralPath $Workspace) {
        Remove-Item -LiteralPath $Workspace -Recurse -Force
    }
    New-Item -ItemType Directory -Path $Workspace | Out-Null

    git clone --quiet https://github.com/sqlcipher/sqlcipher.git "$Workspace/sqlcipher"
    git -C "$Workspace/sqlcipher" checkout --quiet $SqlCipherRevision
    git clone --quiet https://github.com/coleifer/sqlcipher3.git "$Workspace/sqlcipher3"
    git -C "$Workspace/sqlcipher3" checkout --quiet $BindingRevision
    git clone --quiet https://github.com/openssl/openssl.git "$Workspace/openssl"
    git -C "$Workspace/openssl" checkout --quiet $OpenSslRevision
}

foreach ($entry in @(
    [pscustomobject]@{ Path = "$Workspace/sqlcipher"; Revision = $SqlCipherRevision; Commit = $SqlCipherCommit },
    [pscustomobject]@{ Path = "$Workspace/sqlcipher3"; Revision = $BindingRevision; Commit = $BindingRevision },
    [pscustomobject]@{ Path = "$Workspace/openssl"; Revision = $OpenSslRevision; Commit = $OpenSslCommit }
)) {
    $object = git -C $entry.Path rev-parse $entry.Revision
    if ($object -ne $entry.Revision) {
        throw "Source tag/revision object check failed: $object"
    }
    $actual = git -C $entry.Path rev-parse HEAD
    if ($actual -ne $entry.Commit) {
        throw "Source commit check failed: expected $($entry.Commit), got $actual"
    }
}

if (-not (Test-Path -LiteralPath "$Workspace/sqlcipher/sqlite3.c")) {
    Push-Location "$Workspace/sqlcipher"
    try {
        nmake /f Makefile.msc sqlite3.c
    } finally {
        Pop-Location
    }
}
Copy-Item "$Workspace/sqlcipher/sqlite3.c" "$Workspace/sqlcipher3/vendor/sqlite3.c" -Force
Copy-Item "$Workspace/sqlcipher/sqlite3.h" "$Workspace/sqlcipher3/vendor/sqlite3.h" -Force

$OpenSslPrefix = "$Workspace/openssl-install"
if (-not (Test-Path -LiteralPath "$OpenSslPrefix/lib/libcrypto.lib")) {
    Push-Location "$Workspace/openssl"
    try {
        perl Configure VC-WIN64A no-shared no-tests no-zlib --prefix="$OpenSslPrefix" --openssldir="$OpenSslPrefix/ssl"
        nmake
        nmake install_sw
    } finally {
        Pop-Location
    }
}
$env:INCLUDE = "$OpenSslPrefix/include;$env:INCLUDE"
$env:LIB = "$OpenSslPrefix/lib;$env:LIB"

$SetupPath = "$Workspace/sqlcipher3/setup.py"
$Setup = Get-Content -LiteralPath $SetupPath -Raw
$Setup = $Setup.Replace("VERSION = '0.6.2'", "VERSION = '$ControlledVersion'")
$Setup = $Setup.Replace(
    "extra_compile_args = ['-Qunused-arguments'] if sys.platform == 'darwin' else []",
    "extra_compile_args = ['-Qunused-arguments'] if sys.platform == 'darwin' else ['/Brepro']"
)
$Setup = $Setup.Replace(
    "extra_link_args = []",
    "extra_link_args = ['/Brepro'] if sys.platform == 'win32' else []"
)
Set-Content -LiteralPath $SetupPath -Value $Setup -Encoding utf8
$PyProjectPath = "$Workspace/sqlcipher3/pyproject.toml"
$PyProject = Get-Content -LiteralPath $PyProjectPath -Raw
$PyProject = $PyProject -replace '(?m)^\s*"conan>=2\.0",\r?\n', ''
$PyProject = $PyProject.Replace('version = "0.6.2"', "version = `"$ControlledVersion`"")
Set-Content -LiteralPath $PyProjectPath -Value $PyProject -Encoding utf8
try {
    python -m pip --version | Out-Null
} catch {
    python -m ensurepip --upgrade
}
python -m pip install --disable-pip-version-check --upgrade `
    "build==1.5.0" `
    "packaging==26.2" `
    "pyproject-hooks==1.2.0" `
    "setuptools==83.0.0" `
    "wheel==0.46.3"
foreach ($BuildOutput in @(
    "$Workspace/sqlcipher3/build",
    "$Workspace/sqlcipher3/dist",
    "$Workspace/sqlcipher3/sqlcipher3.egg-info"
)) {
    if (Test-Path -LiteralPath $BuildOutput) {
        Remove-Item -LiteralPath $BuildOutput -Recurse -Force
    }
}
Push-Location "$Workspace/sqlcipher3"
try {
    python -m build --wheel --no-isolation
} finally {
    Pop-Location
}
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$Wheels = @(Get-ChildItem "$Workspace/sqlcipher3/dist/*.whl")
if ($Wheels.Count -ne 1) {
    throw "Expected exactly one controlled wheel, found $($Wheels.Count)"
}
$Wheel = $Wheels[0]
Copy-Item -LiteralPath $Wheel.FullName -Destination $OutputDirectory -Force
$Published = Join-Path $OutputDirectory $Wheel.Name
python scripts/verify_sqlcipher_runtime.py --candidate --wheel $Published --provenance vendor/sqlcipher/PROVENANCE.json
Get-FileHash -Algorithm SHA256 -LiteralPath $Published

if (-not $KeepSources) {
    $Resolved = [IO.Path]::GetFullPath($Workspace)
    if ($Resolved.StartsWith($ExpectedParent, [StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $Resolved -Recurse -Force
    }
}
