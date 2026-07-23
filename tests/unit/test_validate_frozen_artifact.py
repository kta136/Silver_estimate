from pathlib import Path

import pytest

from scripts.validate_frozen_artifact import _validate_payload


def _valid_payload(artifact: Path) -> dict[str, object]:
    return {
        "artifact_startup": "ok",
        "cipher_version": "4.17.0 community",
        "crypto_provider": "openssl",
        "icon_available": True,
        "keyring_available": True,
        "keyring_backend": "keyring.backends.Windows.WinVaultKeyring",
        "password_hashing": True,
        "pdf_bytes": 2_000,
        "qt_platform": "windows",
        "runtime_root": str(artifact.parent),
        "svg_image_format": True,
    }


def test_validate_payload_accepts_password_service_smoke(tmp_path: Path) -> None:
    artifact = tmp_path / "SilverEstimate.exe"

    _validate_payload(_valid_payload(artifact), artifact)


def test_validate_payload_requires_password_service_smoke(tmp_path: Path) -> None:
    artifact = tmp_path / "SilverEstimate.exe"
    payload = _valid_payload(artifact)
    payload["password_hashing"] = False

    with pytest.raises(ValueError, match="Argon2id"):
        _validate_payload(payload, artifact)
