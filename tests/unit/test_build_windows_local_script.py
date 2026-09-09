from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_windows_local.ps1"
LAUNCHER = Path(__file__).resolve().parents[2] / "scripts" / "build_windows_local.cmd"
DEPLOY_SPEC = Path(__file__).resolve().parents[2] / "pysidedeploy.spec"


def test_local_build_requires_locked_uv_environment():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "uv is required for a locked release build" in source
    assert "uv.Source sync --extra dev --python $pythonPin --locked" in source
    assert "pip install" not in source


def test_local_build_validates_onefile_before_versioning():
    source = SCRIPT.read_text(encoding="utf-8")

    onefile_build = source.index('-mode "onefile"')
    runtime_validate = source.index(
        "Invoke-ArtifactValidation -pythonExe $buildPython -artifact $baseExe"
    )
    native_validate = source.index(
        "Invoke-NativeOnefileValidation -dumpbinExe $dumpbinExe -artifact $baseExe"
    )
    versioned_copy = source.index(
        "Copy-Item -LiteralPath $baseExe -Destination $versionedExe"
    )

    assert onefile_build < runtime_validate < native_validate < versioned_copy


def test_local_build_validation_uses_system_only_path_and_prints_hashes():
    source = SCRIPT.read_text(encoding="utf-8")

    assert '$env:PATH = "$env:SystemRoot\\System32;$env:SystemRoot"' in source
    assert "function Get-Sha256" in source
    assert "Get-FileHash" not in source
    assert "Executable SHA-256:" in source


def test_local_build_rejects_external_onefile_runtime_dependencies():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-NativeOnefileValidation" in source
    assert '@("kernel32.dll", "shell32.dll")' in source
    assert "One-file loader has non-system startup dependencies" in source


@pytest.mark.skipif(os.name != "nt", reason="Windows command launcher")
def test_local_build_launcher_supports_workspace_paths_with_spaces(tmp_path):
    scripts_dir = tmp_path / "workspace with spaces" / "scripts"
    scripts_dir.mkdir(parents=True)
    launcher = scripts_dir / LAUNCHER.name
    script = scripts_dir / SCRIPT.name
    marker = scripts_dir.parent / "launcher result.txt"
    shutil.copy2(LAUNCHER, launcher)
    script.write_text(
        "param([string]$OutputPath)\n"
        'Set-Content -LiteralPath $OutputPath -Value "ok" -Encoding ascii\n',
        encoding="utf-8",
    )

    subprocess.run(
        [str(launcher), str(marker)],
        check=True,
        cwd=scripts_dir.parent,
    )

    assert marker.read_text(encoding="ascii").strip() == "ok"


def test_deploy_spec_uses_msvc_for_a_self_contained_loader():
    source = DEPLOY_SPEC.read_text(encoding="utf-8")

    assert "--msvc=latest" in source
    assert "--zig" not in source


def test_compiler_pin_matches_manifest_deploy_and_build_entrypoints():
    root = SCRIPT.parents[1]
    manifest = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    pin = next(
        dependency.split("==", 1)[1]
        for dependency in manifest["project"]["optional-dependencies"]["dev"]
        if dependency.startswith("Nuitka==")
    )
    deploy = configparser.ConfigParser()
    deploy.read(DEPLOY_SPEC, encoding="utf-8")
    assert f"Nuitka=={pin}" in deploy["python"]["packages"].split(",")
    assert f'$nuitkaVersion = "{pin}"' in SCRIPT.read_text(encoding="utf-8")
    assert f'NUITKA_VERSION = "{pin}"' in (root / "noxfile.py").read_text(
        encoding="utf-8"
    )


@pytest.mark.skipif(os.name != "nt", reason="Windows build interpreter guard")
def test_local_build_rejects_a_different_python_patch(tmp_path):
    # Run the real interpreter guard without invoking the build or syncing packages.
    source = SCRIPT.read_text(encoding="utf-8")
    functions = source[
        source.index("function Get-PythonVersion") : source.index(
            "function Sync-ProjectDependencies"
        )
    ]
    script = tmp_path / "check exact interpreter.ps1"
    actual_version = ".".join(map(str, sys.version_info[:3]))
    different_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro + 1}"
    quoted_python = sys.executable.replace("'", "''")
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        + functions
        + f"\n$requiredPython = [version]'{actual_version}'\n"
        + f"if (-not (Test-PythonForBuild '{quoted_python}')) {{ throw 'Matching interpreter rejected' }}\n"
        + f"$requiredPython = [version]'{different_version}'\n"
        + f"if (Test-PythonForBuild '{quoted_python}') {{ throw 'Wrong patch accepted' }}\n",
        encoding="utf-8",
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(script)],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_local_build_uses_project_pin_instead_of_launcher_or_registry():
    source = SCRIPT.read_text(encoding="utf-8")
    pin = (SCRIPT.parents[1] / ".python-version").read_text().strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", pin)
    assert "Get-Content -LiteralPath $pythonPinPath -Raw" in source
    assert "Find-WindowsPython" not in source
    assert "Get-Python314FromRegistry" not in source


@pytest.mark.skipif(os.name != "nt", reason="Windows build orchestration")
@pytest.mark.parametrize(
    ("arguments", "profile", "suffix", "fail_validation"),
    [
        ([], "release", "", False),
        (["-Fast"], "fast", "-fast", False),
        (["-Fast", "-ArtifactSuffix", "test"], "fast", "-test", False),
        (["-Fast"], "fast", "-fast", True),
    ],
)
def test_build_profiles_and_failure_reporting(
    tmp_path, arguments, profile, suffix, fail_validation
):
    # Execute the real orchestration with only the expensive external tools
    # substituted. Configuration, publishing, hashing, cleanup and timers run.
    root = tmp_path / "workspace with spaces"
    scripts = root / "scripts"
    constants = root / "silverestimate" / "infrastructure"
    scripts.mkdir(parents=True)
    constants.mkdir(parents=True)
    (constants / "app_constants.py").write_text('APP_VERSION = "4.0"\n')
    (root / ".python-version").write_text("3.14.7\n")
    shutil.copy2(DEPLOY_SPEC, root / DEPLOY_SPEC.name)
    dist = root / "dist"
    dist.mkdir()
    release = dist / "SilverEstimate-v4.0.exe"
    release.write_bytes(b"existing release")
    target = dist / f"SilverEstimate-v4.0{suffix}.exe"
    target.write_bytes(b"existing release")
    mocks = """
function Sync-ProjectDependencies { return 'python.exe' }
function Get-PySideDeploy { return 'pyside6-deploy.exe' }
function Find-Dumpbin { return 'dumpbin.exe' }
function Invoke-PySideDeployBuild {
    param($deployExe, $configFile, $mode, $dumpbinExe)
    Copy-Item -LiteralPath $configFile -Destination (Join-Path $repoRoot 'used.spec')
    [IO.File]::WriteAllText($baseExe, 'new executable')
}
function Invoke-ArtifactValidation {
    param($pythonExe, $artifact)
    Add-Content -LiteralPath (Join-Path $repoRoot 'checks.txt') -Value 'runtime'
    VALIDATION_RESULT
}
function Invoke-NativeOnefileValidation {
    param($dumpbinExe, $artifact)
    Add-Content -LiteralPath (Join-Path $repoRoot 'checks.txt') -Value 'native'
}
""".replace("VALIDATION_RESULT", "throw 'validation failed'" if fail_validation else "")
    source = SCRIPT.read_text(encoding="utf-8")
    marker = 'if ($env:OS -ne "Windows_NT"'
    source = source.replace(marker, mocks + "\n" + marker, 1)
    script = scripts / SCRIPT.name
    script.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(script),
            *arguments,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert (result.returncode != 0) == fail_validation, result.stdout + result.stderr
    config = configparser.ConfigParser(interpolation=None)
    config.read(root / "used.spec", encoding="utf-8")
    flags = config["nuitka"]["extra_args"].split()
    assert ("--lto=no" in flags) == (profile == "fast")
    assert "--file-version=4.0" in flags
    assert (root / DEPLOY_SPEC.name).read_bytes() == DEPLOY_SPEC.read_bytes()
    assert not (root / ".pysidedeploy-local-onefile.spec").exists()
    checks = (root / "checks.txt").read_text().splitlines()
    assert checks == (["runtime"] if fail_validation else ["runtime", "native"])
    assert target.read_bytes() == (
        b"existing release" if fail_validation else b"new executable"
    )
    if profile == "fast":
        assert release.read_bytes() == b"existing release"
    report = json.loads(
        (root / "artifacts" / "local-build" / f"build-timings{suffix}.json").read_text(
            encoding="utf-8-sig"
        )
    )
    assert report["profile"] == profile
    assert report["status"] == ("failed" if fail_validation else "success")
    assert report["total_seconds"] >= 0
    assert set(report["stages_seconds"]) == {
        "dependencies",
        "compile_and_package",
        "validation",
    }
    assert all(value >= 0 for value in report["stages_seconds"].values())
