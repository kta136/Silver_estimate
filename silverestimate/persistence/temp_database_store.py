"""Lifecycle helpers for the plaintext temporary SQLite database."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

from silverestimate.infrastructure.settings import get_app_settings


class TempDatabaseStore:
    """Manage lifecycle and optional recovery metadata for a plaintext temp DB."""

    SETTINGS_KEY = "security/last_temp_db_path"
    _WIPE_CHUNK_SIZE = 1024 * 1024  # 1 MiB chunks when scrubbing the file

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        store_metadata: bool = True,
        settings_factory: Callable[[], object] = get_app_settings,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._path: Optional[Path] = None
        self._registered = False
        self._store_metadata = store_metadata
        self._settings_factory = settings_factory

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def create(self, suffix: str = ".sqlite") -> Path:
        if self._path is not None:
            raise RuntimeError("Temporary database already initialised.")
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle.close()
        self._path = Path(handle.name)
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
            self._path = None
            self._registered = False
            self._clear_settings_entry()
        elif self._store_metadata and self._path is not None and not self._registered:
            self.register_for_recovery()

    def _secure_unlink(self) -> None:
        if self._path is None or not self._path.exists():
            self._clear_settings_entry()
            return
        try:
            with open(self._path, "r+b", buffering=0) as handle:
                length = handle.seek(0, os.SEEK_END)
                handle.seek(0)
                chunk = b"\x00" * self._WIPE_CHUNK_SIZE
                remaining = length
                while remaining > 0:
                    to_write = chunk if remaining >= len(chunk) else b"\x00" * remaining
                    handle.write(to_write)
                    remaining -= len(to_write)
                try:
                    handle.flush()
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            os.remove(self._path)
            self._logger.debug(
                "Temporary database file securely deleted: %s", self._path
            )
        except Exception as exc:
            self._logger.warning(
                "Could not securely delete temporary DB '%s': %s", self._path, exc
            )
            try:
                os.remove(self._path)
            except Exception:
                pass
        finally:
            self._clear_settings_entry()

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
