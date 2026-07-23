"""Run and validate the self-report emitted by a frozen release artifact."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import Any


def _validate_payload(payload: dict[str, Any], artifact: Path) -> None:
    artifact_parent = artifact.resolve().parent
    expected_runtime_root = (
        artifact_parent.parent
        if artifact_parent.name.endswith(".dist")
        else artifact_parent
    )
    actual_runtime_root = Path(payload.get("runtime_root", "")).resolve()
    if actual_runtime_root != expected_runtime_root:
        raise ValueError(
            "Artifact writable root is not beside the executable: "
            f"{actual_runtime_root} != {expected_runtime_root}"
        )
    if payload.get("icon_available") is not True:
        raise ValueError("Bundled application icon is unavailable")
    if payload.get("keyring_available") is not True:
        raise ValueError("Windows keyring backend is unavailable")
    if not str(payload.get("keyring_backend", "")).startswith(
        "keyring.backends.Windows."
    ):
        raise ValueError("Artifact did not load the Windows keyring backend")
    if payload.get("qt_platform") != "windows":
        raise ValueError("Artifact did not initialize the Windows Qt platform plugin")
    if payload.get("svg_image_format") is not True:
        raise ValueError("Artifact did not initialize SVG image support")
    if int(payload.get("pdf_bytes", 0)) < 1_000:
        raise ValueError("Artifact did not render a PDF")
    if payload.get("artifact_startup") != "ok":
        raise ValueError("Artifact did not report successful startup")
    if not str(payload.get("cipher_version", "")).startswith("4."):
        raise ValueError("Artifact did not load the required SQLCipher runtime")
    if payload.get("crypto_provider") != "openssl":
        raise ValueError("Artifact did not load the OpenSSL crypto provider")


def validate_artifact(artifact: Path) -> dict[str, Any]:
    """Run ``artifact`` and validate its encrypted-runtime self-report."""
    if not artifact.is_file():
        raise ValueError(f"Frozen artifact is missing: {artifact}")

    env = os.environ.copy()
    env["SILVER_SHOW_CONSOLE"] = "1"
    result = subprocess.run(
        [str(artifact), "--artifact-smoke"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no output"
        raise ValueError(
            f"Artifact smoke failed with exit code {result.returncode}: {detail}"
        )

    output_lines = [line for line in result.stdout.splitlines() if line.strip()]
    if not output_lines:
        raise ValueError("Artifact smoke produced no JSON output")
    try:
        payload = json.loads(output_lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError("Artifact smoke output is not valid JSON") from exc

    _validate_payload(payload, artifact)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()

    print(json.dumps(validate_artifact(args.artifact.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
