"""Encrypted file I/O helpers for the SQLite payload."""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import time
from typing import Any, Callable, Optional, cast

from cryptography.exceptions import InvalidTag

from silverestimate.infrastructure.settings import (
    SettingsStore,
    get_app_settings,
)
from silverestimate.persistence.temp_database_store import TempDatabaseStore
from silverestimate.security import encryption as crypto_utils

RateValue = int | float
RateMetadata = dict[str, Any]


class EncryptedDatabaseStore:
    """Persist and recover the encrypted SQLite payload on disk."""

    def __init__(
        self,
        encrypted_db_path: str,
        *,
        key: bytes | None = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.encrypted_db_path = encrypted_db_path
        self.key = key
        self._logger = logger or logging.getLogger(__name__)

    def set_key(self, key: bytes | None) -> None:
        self.key = key

    def encrypt_from_path(self, temp_db_path: str | None) -> bool:
        """Encrypt the temp DB file and atomically save it to the encrypted path."""
        if not temp_db_path or not os.path.exists(temp_db_path):
            self._logger.warning(
                "Encryption skipped: No active connection or temporary DB file."
            )
            return False
        if not self.key:
            self._logger.warning("Encryption skipped: No encryption key available.")
            return False

        self._logger.info("Encrypting database to %s", self.encrypted_db_path)
        start_time = time.time()
        tmp_out_path = f"{self.encrypted_db_path}.new"
        snapshot_path = None
        try:
            snapshot_path = self.snapshot_copy(temp_db_path)
            source_path = snapshot_path if snapshot_path else temp_db_path

            with open(source_path, "rb") as handle:
                plaintext = handle.read()

            payload = crypto_utils.encrypt_payload(
                plaintext, self.key, logger=self._logger
            )

            with open(tmp_out_path, "wb") as handle:
                handle.write(payload)
                try:
                    handle.flush()
                    os.fsync(handle.fileno())
                except Exception:
                    pass

            os.replace(tmp_out_path, self.encrypted_db_path)
            duration = time.time() - start_time
            self._logger.info(
                "Database encrypted successfully in %.2f seconds", duration
            )
            return True
        except Exception as exc:
            self._logger.error("Database encryption failed: %s", exc, exc_info=True)
            try:
                if os.path.exists(tmp_out_path):
                    os.remove(tmp_out_path)
            except OSError as remove_error:
                self._logger.warning(
                    "Could not remove temporary encrypted file '%s': %s",
                    tmp_out_path,
                    remove_error,
                )
            return False
        finally:
            try:
                if snapshot_path and os.path.exists(snapshot_path):
                    TempDatabaseStore.secure_delete_path(
                        snapshot_path,
                        logger=self._logger,
                    )
            except Exception:
                pass

    def decrypt_to_path(self, temp_db_path: str | None) -> str:
        """Decrypt the encrypted DB into ``temp_db_path`` and report the outcome."""
        if not os.path.exists(self.encrypted_db_path):
            self._logger.info("Encrypted database file not found")
            return "first_run"
        if os.path.getsize(self.encrypted_db_path) <= crypto_utils.NONCE_BYTES:
            self._logger.warning("Encrypted database file is empty or too small")
            return "first_run"
        if not self.key:
            self._logger.error("Decryption skipped: No encryption key available")
            return "error"
        if not temp_db_path:
            raise RuntimeError("Temporary database path not set.")

        self._logger.info("Decrypting database to temporary location")
        start_time = time.time()
        try:
            with open(self.encrypted_db_path, "rb") as handle:
                payload = handle.read()

            plaintext = crypto_utils.decrypt_payload(
                payload,
                self.key,
                logger=self._logger,
            )

            with open(temp_db_path, "wb") as handle:
                handle.write(plaintext)

            duration = time.time() - start_time
            self._logger.info(
                "Database decrypted successfully in %.2f seconds", duration
            )
            return "success"
        except InvalidTag:
            self._logger.error(
                "Decryption failed: Invalid password or corrupted data (InvalidTag)"
            )
            return "error"
        except Exception as exc:
            self._logger.error("Database decryption failed: %s", exc, exc_info=True)
            return "error"

    def snapshot_copy(self, temp_db_path: str | None) -> str | None:
        """Create a consistent snapshot copy using SQLite backup API."""
        if not temp_db_path:
            return None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
            snapshot_path = tmp.name
            tmp.close()
            try:
                src = sqlite3.connect(
                    f"file:{temp_db_path}?mode=ro", uri=True, timeout=5
                )
            except Exception:
                src = sqlite3.connect(temp_db_path, timeout=5)
            dest = sqlite3.connect(snapshot_path, timeout=5)
            try:
                src.backup(dest)
            finally:
                try:
                    dest.close()
                except Exception:
                    pass
                try:
                    src.close()
                except Exception:
                    pass
            return snapshot_path
        except Exception as exc:
            self._logger.debug("Snapshot backup failed or skipped: %s", exc)
            return None

    def checkpoint_wal(self, temp_db_path: str | None) -> bool:
        """Force a WAL checkpoint using a short-lived side connection."""
        if not temp_db_path:
            return False
        try:
            conn = sqlite3.connect(temp_db_path, timeout=5)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                conn.close()
            return True
        except Exception as exc:
            self._logger.debug("WAL checkpoint skipped/failed: %s", exc)
            return False

    @staticmethod
    def get_or_create_salt(
        *,
        logger: Optional[logging.Logger] = None,
        settings_factory: Callable[[], SettingsStore] = get_app_settings,
    ) -> bytes:
        settings = settings_factory()
        return crypto_utils.get_or_create_salt(settings, logger=logger)

    @staticmethod
    def check_recovery_candidate(
        encrypted_db_path: str,
        *,
        settings_factory: Callable[[], SettingsStore] = get_app_settings,
    ) -> str | None:
        settings = settings_factory()
        temp_path = cast(str | None, settings.value("security/last_temp_db_path"))
        if not temp_path or not isinstance(temp_path, str):
            return None
        if not os.path.exists(temp_path):
            return None
        try:
            enc_exists = os.path.exists(encrypted_db_path)
            temp_mtime = os.path.getmtime(temp_path)
            enc_mtime = os.path.getmtime(encrypted_db_path) if enc_exists else 0
            if not enc_exists or temp_mtime > enc_mtime:
                return temp_path
        except Exception:
            return None
        return None

    @staticmethod
    def recover_encrypt_plain_to_encrypted(
        plain_temp_path: str,
        encrypted_db_path: str,
        password: str,
        *,
        logger: Optional[logging.Logger] = None,
        settings_factory: Callable[[], SettingsStore] = get_app_settings,
        iterations: int = crypto_utils.DEFAULT_KDF_ITERATIONS,
    ) -> bool:
        try:
            if not os.path.exists(plain_temp_path):
                if logger:
                    logger.error(
                        "Recovery failed: temp file not found: %s", plain_temp_path
                    )
                return False

            salt = EncryptedDatabaseStore.get_or_create_salt(
                logger=logger,
                settings_factory=settings_factory,
            )
            key = crypto_utils.derive_key(
                password,
                salt,
                iterations=iterations,
                logger=logger,
            )

            with open(plain_temp_path, "rb") as handle:
                plaintext = handle.read()

            payload = crypto_utils.encrypt_payload(plaintext, key, logger=logger)
            tmp_out_path = f"{encrypted_db_path}.new"
            with open(tmp_out_path, "wb") as handle:
                handle.write(payload)
                try:
                    handle.flush()
                    os.fsync(handle.fileno())
                except Exception:
                    pass
            os.replace(tmp_out_path, encrypted_db_path)
            if logger:
                logger.info("Recovered and encrypted temp DB into encrypted store.")
            try:
                TempDatabaseStore.secure_delete_path(
                    plain_temp_path,
                    logger=logger,
                )
            except Exception:
                pass
            try:
                settings = settings_factory()
                settings.remove("security/last_temp_db_path")
                settings.sync()
            except Exception:
                pass
            return True
        except Exception as exc:
            if logger:
                logger.error("Recovery encryption failed: %s", exc, exc_info=True)
            return False


__all__ = ["EncryptedDatabaseStore"]
