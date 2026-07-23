from __future__ import annotations

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_windows_local.ps1"
DEPLOY_SPEC = Path(__file__).resolve().parents[2] / "pysidedeploy.spec"


def test_local_build_requires_locked_uv_environment():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "uv is required for a locked release build" in source
    assert "uv.Source sync --extra dev --python $pythonExe --locked" in source
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


def test_local_build_keeps_only_the_versioned_executable():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "$temporaryOnefileConfig" in source
    assert "-configFile $temporaryOnefileConfig" in source
    assert "Remove-Item -LiteralPath $baseExe -Force" in source
    assert "Compress-Archive" not in source


def test_deploy_spec_uses_msvc_for_a_self_contained_loader():
    source = DEPLOY_SPEC.read_text(encoding="utf-8")

    assert "--msvc=latest" in source
    assert "--zig" not in source
