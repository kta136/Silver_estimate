"""Lifecycle helpers for the plaintext temporary SQLite database."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Callable, Optional

from silverestimate.infrastructure.settings import SettingsStore, get_app_settings


class TempDatabaseStore:
    """Manage lifecycle and optional recovery metadata for a plaintext temp DB."""

    SETTINGS_KEY = "security/last_temp_db_path"
    MARKER_FILENAME = ".silverestimate-temp.json"
    MARKER_OWNER = "Silver Estimate"
    _WIPE_CHUNK_SIZE = 1024 * 1024  # 1 MiB chunks when scrubbing the file

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        store_metadata: bool = True,
        encrypted_db_path: str | None = None,
        settings_factory: Callable[[], SettingsStore] = get_app_settings,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._path: Optional[Path] = None
        self._directory: Optional[Path] = None
        self._registered = False
        self._store_metadata = store_metadata
        self._encrypted_db_path = encrypted_db_path
        self._settings_factory = settings_factory

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def create(self, suffix: str = ".sqlite") -> Path:
        if self._path is not None:
            raise RuntimeError("Temporary database already initialised.")
        self._directory = Path(tempfile.mkdtemp(prefix="silverestimate-db-"))
        self._restrict_path_permissions(self._directory, is_dir=True)
        self._path = self._directory / f"session{suffix}"
        fd = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        self._restrict_path_permissions(self._path, is_dir=False)
        self._write_ownership_marker()
        return self._path

    def register_for_recovery(self) -> None:
        if not self._store_metadata or self._path is None or self._registered:
            return
        try:
            settings = self._settings_factory()
            settings.setValue(self.SETTINGS_KEY, str(self._path))
            settings.sync()
            self._registered = True
        except Exception as exc:
            self._logger.warning("Could not store temp DB path for recovery: %s", exc)

    def cleanup(self, *, preserve: bool = False) -> None:
        """Securely delete the temp file and clear recovery breadcrumbs."""
        if not preserve:
            self._secure_unlink()
            self._remove_temp_dir()
            self._path = None
            self._directory = None
            self._registered = False
            self._clear_settings_entry()
        elif self._store_metadata and self._path is not None and not self._registered:
            self.register_for_recovery()

    @classmethod
    def secure_delete_path(
        cls,
        path: str | Path | None,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        target = Path(path) if path is not None else None
        if target is None or not target.exists():
            return

        active_logger = logger or logging.getLogger(__name__)
        try:
            with open(target, "r+b", buffering=0) as handle:
                length = handle.seek(0, os.SEEK_END)
                handle.seek(0)
                chunk = b"\x00" * cls._WIPE_CHUNK_SIZE
                remaining = length
                while remaining > 0:
                    to_write = chunk if remaining >= len(chunk) else b"\x00" * remaining
                    handle.write(to_write)
                    remaining -= len(to_write)
                try:
                    handle.flush()
                    os.fsync(handle.fileno())
                except Exception as exc:
                    active_logger.debug(
                        "Failed to fsync temporary file during secure delete: %s", exc
                    )
            os.remove(target)
            active_logger.debug("Securely deleted temporary file: %s", target)
        except Exception as exc:
            active_logger.warning(
                "Could not securely delete temporary file '%s': %s", target, exc
            )
            try:
                os.remove(target)
            except Exception as remove_error:
                active_logger.warning(
                    "Could not remove temporary file '%s' after wipe failure: %s",
                    target,
                    remove_error,
                )

    def _secure_unlink(self) -> None:
        if self._path is None:
            self._clear_settings_entry()
            return
        try:
            if self._path.exists():
                self.secure_delete_path(self._path, logger=self._logger)
            for suffix in ("-wal", "-shm"):
                self.secure_delete_path(
                    f"{self._path}{suffix}",
                    logger=self._logger,
                )
        finally:
            self._clear_settings_entry()

    @classmethod
    def encrypted_database_identity(cls, encrypted_db_path: str) -> str:
        normalized = os.path.normcase(os.path.abspath(encrypted_db_path))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _write_ownership_marker(self) -> None:
        if self._directory is None:
            return
        marker_path = self._directory / self.MARKER_FILENAME
        metadata = {
            "created_at": time.time(),
            "encrypted_database_identity": (
                self.encrypted_database_identity(self._encrypted_db_path)
                if self._encrypted_db_path
                else "unbound"
            ),
            "owner": self.MARKER_OWNER,
            "pid": os.getpid(),
            "plaintext_database": self._path.name if self._path else "session.sqlite",
        }
        try:
            marker_path.write_text(
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
                encoding="utf-8",
            )
            self._restrict_path_permissions(marker_path, is_dir=False)
        except Exception as exc:
            self._logger.warning("Could not mark temporary database directory: %s", exc)

    @classmethod
    def read_ownership_marker(cls, database_path: str | Path) -> dict | None:
        path = Path(database_path)
        marker_path = path.parent / cls.MARKER_FILENAME
        if not marker_path.is_file():
            return None
        try:
            metadata = json.loads(marker_path.read_text(encoding="utf-8"))
        except OSError, UnicodeError, json.JSONDecodeError:
            return None
        if not isinstance(metadata, dict) or metadata.get("owner") != cls.MARKER_OWNER:
            return None
        return metadata

    @classmethod
    def belongs_to_encrypted_database(
        cls,
        database_path: str | Path,
        encrypted_db_path: str,
    ) -> bool:
        metadata = cls.read_ownership_marker(database_path)
        return bool(
            metadata
            and metadata.get("encrypted_database_identity")
            == cls.encrypted_database_identity(encrypted_db_path)
        )

    @classmethod
    def cleanup_marked_database(
        cls,
        database_path: str | Path,
        encrypted_db_path: str,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> bool:
        """Delete only a marked database belonging to ``encrypted_db_path``."""
        path = Path(database_path)
        if not cls.belongs_to_encrypted_database(path, encrypted_db_path):
            return False
        active_logger = logger or logging.getLogger(__name__)
        for target in (path, Path(f"{path}-wal"), Path(f"{path}-shm")):
            cls.secure_delete_path(target, logger=active_logger)
        for snapshot in path.parent.glob("snapshot-*.sqlite"):
            cls.secure_delete_path(snapshot, logger=active_logger)
        marker = path.parent / cls.MARKER_FILENAME
        try:
            marker.unlink(missing_ok=True)
            path.parent.rmdir()
        except OSError as exc:
            active_logger.debug("Could not remove marked temp directory: %s", exc)
        return True

    @staticmethod
    def _restrict_path_permissions(path: Path, *, is_dir: bool) -> None:
        mode = 0o700 if is_dir else 0o600
        try:
            os.chmod(path, mode)
        except Exception as exc:
            logging.getLogger(__name__).debug(
                "Failed to restrict temp database path permissions for '%s': %s",
                path,
                exc,
            )

    def _remove_temp_dir(self) -> None:
        if self._directory is None:
            return
        try:
            for snapshot in self._directory.glob("snapshot-*.sqlite"):
                self.secure_delete_path(snapshot, logger=self._logger)
            (self._directory / self.MARKER_FILENAME).unlink(missing_ok=True)
            self._directory.rmdir()
        except Exception as exc:
            self._logger.debug(
                "Failed to remove temp database directory '%s': %s",
                self._directory,
                exc,
            )

    def _clear_settings_entry(self) -> None:
        if not self._store_metadata or not self._registered:
            return
        try:
            settings = self._settings_factory()
            settings.remove(self.SETTINGS_KEY)
            settings.sync()
        except Exception as exc:
            self._logger.warning("Could not clear temp DB recovery metadata: %s", exc)
        self._registered = False


__all__ = ["TempDatabaseStore"]
