"""Versioned metadata and operation journals for encrypted database storage."""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, ClassVar, Self


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


@dataclass(frozen=True)
class KdfMetadata:
    """Exact version-1 password-to-database-key policy."""

    version: int
    algorithm: str
    salt_b64: str
    time_cost: int
    memory_cost_kib: int
    parallelism: int
    output_bytes: int

    VERSION: ClassVar[int] = 1
    ALGORITHM: ClassVar[str] = "argon2id"
    TIME_COST: ClassVar[int] = 3
    MEMORY_COST_KIB: ClassVar[int] = 65_536
    PARALLELISM: ClassVar[int] = 4
    OUTPUT_BYTES: ClassVar[int] = 32
    SALT_BYTES: ClassVar[int] = 16

    @classmethod
    def create(cls) -> Self:
        return cls(
            version=cls.VERSION,
            algorithm=cls.ALGORITHM,
            salt_b64=base64.b64encode(os.urandom(cls.SALT_BYTES)).decode("ascii"),
            time_cost=cls.TIME_COST,
            memory_cost_kib=cls.MEMORY_COST_KIB,
            parallelism=cls.PARALLELISM,
            output_bytes=cls.OUTPUT_BYTES,
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        expected = {
            "version",
            "algorithm",
            "salt_b64",
            "time_cost",
            "memory_cost_kib",
            "parallelism",
            "output_bytes",
        }
        if set(value) != expected:
            raise StorageMetadataError("KDF metadata has missing or unknown fields")
        try:
            result = cls(**value)
            salt = base64.b64decode(result.salt_b64, validate=True)
        except (TypeError, ValueError) as exc:
            raise StorageMetadataError("Malformed KDF metadata") from exc
        if (
            result.version != cls.VERSION
            or result.algorithm != cls.ALGORITHM
            or result.time_cost != cls.TIME_COST
            or result.memory_cost_kib != cls.MEMORY_COST_KIB
            or result.parallelism != cls.PARALLELISM
            or result.output_bytes != cls.OUTPUT_BYTES
            or len(salt) != cls.SALT_BYTES
        ):
            raise StorageMetadataError("Unsupported or weakened KDF policy")
        return result

    @classmethod
    def read(cls, path: str | Path) -> Self:
        return cls.from_dict(read_json(path))

    @property
    def salt(self) -> bytes:
        return base64.b64decode(self.salt_b64, validate=True)

    def write(self, path: str | Path) -> None:
        atomic_write_json(path, asdict(self))


@dataclass(frozen=True)
class BackupManifest:
    version: int
    created_utc: str
    database_sha256: str
    kdf_sha256: str
    schema_version: int
    sqlcipher_version: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MigrationJournal:
    version: int
    phase: str
    source_sha256: str
    backup_path: str
    target_path: str


@dataclass(frozen=True)
class RekeyJournal:
    version: int
    phase: str
    old_database_sha256: str
    old_metadata_sha256: str
    target_path: str
    retained_path: str
    retained_metadata_path: str


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
    journal: MigrationJournal | RekeyJournal | RestoreJournal,
) -> None:
    atomic_write_json(path, asdict(journal))


__all__ = [
    "BackupManifest",
    "KdfMetadata",
    "MigrationJournal",
    "RekeyJournal",
    "RestoreJournal",
    "StorageMetadataError",
    "atomic_write_json",
    "read_json",
    "sha256_file",
    "write_journal",
]
