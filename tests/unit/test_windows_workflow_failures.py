"""Exercise Windows workflow failure handling without building or publishing."""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell is required")

STUBS = r"""
$ErrorActionPreference = 'Stop'
function uv {
    $command = $args -join ' '
    [IO.File]::AppendAllText($env:TEST_COMMAND_LOG, "$command`n")
    $global:LASTEXITCODE = 0
    if ($command.Contains($env:TEST_FAIL_TOKEN)) { $global:LASTEXITCODE = 17 }
    if ($command.Contains('APP_VERSION')) { Write-Output '3.12' }
}
function signtool { $global:LASTEXITCODE = [int]$env:TEST_SIGN_EXIT }
function Copy-Item { }
function Compress-Archive { }
function Get-FileHash { [pscustomobject]@{ Hash = 'ABCD' } }
function Set-Content { }
"""


def _steps(workflow: str) -> list[dict]:
    document = yaml.safe_load(
        (ROOT / ".github" / "workflows" / workflow).read_text(encoding="utf-8")
    )
    return [
        step
        for job in document["jobs"].values()
        for step in job["steps"]
        if "run" in step
    ]


def _run_step(tmp_path: Path, step: dict, **environment: str):
    body = step["run"].replace("${{ github.ref_name }}", "v3.12")
    script = tmp_path / "workflow-step.ps1"
    # Match the GitHub PowerShell wrapper's terminating cmdlet errors and final
    # native exit-code propagation. External commands above are harmless stubs.
    script.write_text(STUBS + "\n" + body + "\nexit $LASTEXITCODE\n", encoding="utf-8")
    return subprocess.run(
        [str(PWSH), "-NoProfile", "-NonInteractive", "-File", str(script)],
        cwd=tmp_path,
        env={
            **os.environ,
            "RUNNER_TEMP": str(tmp_path),
            "TEST_COMMAND_LOG": str(tmp_path / "commands.log"),
            "TEST_FAIL_TOKEN": "never-matches",
            "TEST_SIGN_EXIT": "0",
            **environment,
        },
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


@pytest.mark.parametrize(
    ("workflow", "command"),
    [
        ("release-windows.yml", "nox -s ruff"),
        ("release-windows.yml", "nox -s mypy"),
        ("release-windows.yml", "nox -s bandit"),
        ("release-windows.yml", "nox -s dependency_policy"),
        ("release-windows.yml", "--wheel vendor/sqlcipher/"),
        ("pr-validation.yml", "--wheel vendor/sqlcipher/"),
        ("main-validation.yml", "--wheel vendor/sqlcipher/"),
        ("release-windows.yml", "from silverestimate.infrastructure.app_constants"),
        ("release-windows.yml", "cyclonedx-py environment"),
        ("release-windows.yml", "scripts/augment_release_sbom.py"),
        ("release-windows.yml", "scripts/check_dependency_policy.py"),
    ],
)
def test_failed_native_gate_blocks_workflow(tmp_path, workflow, command):
    step = next(step for step in _steps(workflow) if command in step["run"])
    assert not step.get("continue-on-error", False)
    result = _run_step(tmp_path, step, TEST_FAIL_TOKEN=command)
    assert result.returncode != 0, result.stdout + result.stderr
    commands = (tmp_path / "commands.log").read_text().splitlines()
    assert command in commands[-1], "A later native command ran after failure"


@pytest.mark.parametrize("sign_exit", [0, 17])
def test_signing_cleans_certificate_and_propagates_failure(tmp_path, sign_exit):
    step = next(
        step for step in _steps("release-windows.yml") if "signtool sign" in step["run"]
    )
    assert not step.get("continue-on-error", False)
    result = _run_step(
        tmp_path,
        step,
        TEST_SIGN_EXIT=str(sign_exit),
        SIGNING_CERTIFICATE_BASE64=base64.b64encode(b"synthetic certificate").decode(),
        SIGNING_CERTIFICATE_PASSWORD="synthetic password",
    )
    assert (result.returncode == 0) == (sign_exit == 0), result.stderr
    assert not (tmp_path / "silverestimate-signing.pfx").exists()
