"""Versioned metadata and operation journals for encrypted database storage."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class StorageMetadataError(ValueError):
    """Raised when security metadata is absent, malformed, or unsupported."""


def _canonical_json(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def atomic_write_json(path: str | Path, value: dict[str, Any]) -> None:
    """Durably publish canonical JSON in the destination directory."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_canonical_json(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)
        raise


def read_json(path: str | Path) -> dict[str, Any]:
    try:
        raw = Path(path).read_bytes()
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StorageMetadataError(f"Invalid metadata file: {path}") from exc
    if not isinstance(value, dict):
        raise StorageMetadataError(f"Metadata must be an object: {path}")
    return value


# Argon2id policy for the device-bound database key.
KDF_TIME_COST = 3
KDF_MEMORY_COST_KIB = 65_536
KDF_PARALLELISM = 4


@dataclass(frozen=True)
class BackupManifest:
    version: int
    created_utc: str
    database_sha256: str
    schema_version: int
    sqlcipher_version: str
    device_binding_fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RekeyJournal:
    version: int
    phase: str
    old_database_sha256: str
    target_path: str
    retained_path: str


@dataclass(frozen=True)
class RestoreJournal:
    version: int
    phase: str
    staged_path: str
    staged_sha256: str
    retained_path: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_journal(
    path: str | Path,
    journal: RekeyJournal | RestoreJournal,
) -> None:
    atomic_write_json(path, asdict(journal))


__all__ = [
    "BackupManifest",
    "KDF_MEMORY_COST_KIB",
    "KDF_PARALLELISM",
    "KDF_TIME_COST",
    "RekeyJournal",
    "RestoreJournal",
    "StorageMetadataError",
    "atomic_write_json",
    "read_json",
    "sha256_file",
    "write_journal",
]
