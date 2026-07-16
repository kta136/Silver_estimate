"""One-time migration of writable data from legacy runtime locations."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from collections.abc import Iterable
from pathlib import Path

from silverestimate.infrastructure.paths import get_runtime_root

_DATABASE_FILE_NAME = "estimation.db"
_DATABASE_RELATIVE_PATH = Path("database") / _DATABASE_FILE_NAME


class LegacyDatabaseMigrationError(RuntimeError):
    """Raised when a discovered legacy database cannot be moved safely."""


def legacy_database_candidates() -> tuple[Path, ...]:
    """Return known locations used before the database path was consolidated."""
    candidates = (
        Path.cwd() / _DATABASE_RELATIVE_PATH,
        Path.cwd() / _DATABASE_FILE_NAME,
        get_runtime_root() / _DATABASE_FILE_NAME,
    )
    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return tuple(unique)


def migrate_legacy_database(
    database_path: str | os.PathLike[str],
    *,
    candidates: Iterable[str | os.PathLike[str]] | None = None,
    logger: logging.Logger | None = None,
) -> Path:
    """Move the first discovered legacy database to the canonical path.

    An existing canonical database always wins. The legacy source is removed only
    after a byte-for-byte verified copy has been atomically installed.
    """
    target = Path(database_path).expanduser().resolve()
    if target.exists():
        if not target.is_file():
            raise LegacyDatabaseMigrationError(
                f"Canonical database path is not a file: {target}"
            )
        return target

    source_paths = (
        candidates if candidates is not None else legacy_database_candidates()
    )
    for candidate in source_paths:
        source = Path(candidate).expanduser().resolve()
        if source == target or not source.is_file():
            continue
        installed = _copy_verified_database(source, target)
        if not installed:
            return target
        try:
            source.unlink()
        except OSError as exc:
            if logger:
                logger.warning(
                    "Database migrated to %s, but legacy source %s could not be "
                    "removed: %s",
                    target,
                    source,
                    exc,
                )
        else:
            if logger:
                logger.info("Migrated legacy database from %s to %s", source, target)
        return target
    return target


def _copy_verified_database(source: Path, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.migrating")
    temporary.unlink(missing_ok=True)
    try:
        source_digest = _sha256(source)
        shutil.copy2(source, temporary)
        if _sha256(source) != source_digest or _sha256(temporary) != source_digest:
            raise LegacyDatabaseMigrationError(
                f"Legacy database changed or failed verification while copying: {source}"
            )
        if target.exists():
            temporary.unlink(missing_ok=True)
            return False
        os.replace(temporary, target)
    except LegacyDatabaseMigrationError:
        temporary.unlink(missing_ok=True)
        raise
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LegacyDatabaseMigrationError(
            f"Could not migrate legacy database from {source} to {target}: {exc}"
        ) from exc
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "LegacyDatabaseMigrationError",
    "legacy_database_candidates",
    "migrate_legacy_database",
]
