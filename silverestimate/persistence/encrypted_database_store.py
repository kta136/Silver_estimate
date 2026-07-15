"""Encrypted file I/O helpers for the SQLite payload."""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
import time
from contextlib import closing
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, cast

from cryptography.exceptions import InvalidTag

from silverestimate.infrastructure.settings import (
    SettingsStore,
    get_app_settings,
)
from silverestimate.persistence.temp_database_store import TempDatabaseStore
from silverestimate.security import encryption as crypto_utils
from silverestimate.security.encrypted_envelope import (
    Argon2Metadata,
    EnvelopeCorruptError,
    EnvelopeDuplicateChunkError,
    EnvelopeMetadata,
    EnvelopeReorderedError,
    EnvelopeTrailingDataError,
    EnvelopeTruncatedError,
    EnvelopeUnsupportedError,
    EnvelopeWrongPasswordError,
    decrypt_envelope_to_path,
    read_envelope_metadata,
    write_envelope,
)

RateValue = int | float
RateMetadata = dict[str, Any]


class DecryptionOutcome(str, Enum):
    FIRST_RUN = "first_run"
    CURRENT = "current"
    LEGACY = "legacy"
    WRONG_PASSWORD = "wrong_password"
    CORRUPT = "corrupt"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class DecryptionResult:
    outcome: DecryptionOutcome
    metadata: EnvelopeMetadata | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome in {
            DecryptionOutcome.CURRENT,
            DecryptionOutcome.LEGACY,
        }


class EncryptedDatabaseStore:
    """Persist and recover the encrypted SQLite payload on disk."""

    def __init__(
        self,
        encrypted_db_path: str,
        *,
        key: bytes | None = None,
        argon2_metadata: Argon2Metadata | None = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.encrypted_db_path = encrypted_db_path
        self.key = key
        self.argon2_metadata = argon2_metadata or Argon2Metadata(
            salt=b"\0" * crypto_utils.DEFAULT_SALT_BYTES,
            time_cost=crypto_utils.DEFAULT_ARGON2_TIME_COST,
            memory_cost_kib=crypto_utils.DEFAULT_ARGON2_MEMORY_COST_KIB,
            parallelism=crypto_utils.DEFAULT_ARGON2_PARALLELISM,
        )
        self.last_decryption_result = DecryptionResult(DecryptionOutcome.FIRST_RUN)
        self._logger = logger or logging.getLogger(__name__)

    def set_key(self, key: bytes | None) -> None:
        self.key = key

    def set_argon2_metadata(self, metadata: Argon2Metadata) -> None:
        self.argon2_metadata = metadata

    @staticmethod
    def read_metadata(encrypted_db_path: str) -> EnvelopeMetadata | None:
        if not os.path.exists(encrypted_db_path):
            return None
        return read_envelope_metadata(encrypted_db_path)

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
        start_time = time.perf_counter()
        tmp_out_path = f"{self.encrypted_db_path}.new"
        snapshot_path = None
        try:
            snapshot_path = self.snapshot_copy(temp_db_path)
            source_path = snapshot_path if snapshot_path else temp_db_path
            write_envelope(
                source_path,
                tmp_out_path,
                self.key,
                argon2=self.argon2_metadata,
            )

            os.replace(tmp_out_path, self.encrypted_db_path)
            duration = time.perf_counter() - start_time
            byte_size = os.path.getsize(self.encrypted_db_path)
            self._logger.info(
                "Database encrypted successfully in %.2f seconds", duration
            )
            self._logger.info(
                '[telemetry] {"metric":"encrypted_flush","duration_ms":%.3f,"bytes":%d}',
                duration * 1000.0,
                byte_size,
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
            except Exception as exc:
                self._logger.debug(
                    "Failed to clean up encrypted-database snapshot copy: %s", exc
                )

    def decrypt_to_path(self, temp_db_path: str | None) -> str:
        """Compatibility wrapper returning ``success``, ``first_run``, or ``error``."""
        result = self.decrypt_to_path_result(temp_db_path)
        if result.succeeded:
            return "success"
        if result.outcome == DecryptionOutcome.FIRST_RUN:
            return "first_run"
        return "error"

    def decrypt_to_path_result(
        self,
        temp_db_path: str | None,
    ) -> DecryptionResult:
        """Decrypt the store with distinct current/legacy/failure outcomes."""
        if not os.path.exists(self.encrypted_db_path):
            self._logger.info("Encrypted database file not found")
            return self._remember(DecryptionResult(DecryptionOutcome.FIRST_RUN))
        if os.path.getsize(self.encrypted_db_path) <= crypto_utils.NONCE_BYTES:
            self._logger.warning("Encrypted database file is empty or too small")
            return self._remember(DecryptionResult(DecryptionOutcome.FIRST_RUN))
        if not self.key:
            self._logger.error("Decryption skipped: No encryption key available")
            return self._remember(DecryptionResult(DecryptionOutcome.WRONG_PASSWORD))
        if not temp_db_path:
            raise RuntimeError("Temporary database path not set.")

        self._logger.info("Decrypting database to temporary location")
        start_time = time.perf_counter()
        try:
            metadata = read_envelope_metadata(self.encrypted_db_path)
            if metadata is not None:
                decrypt_envelope_to_path(
                    self.encrypted_db_path,
                    temp_db_path,
                    self.key,
                )
                outcome = DecryptionResult(DecryptionOutcome.CURRENT, metadata)
            else:
                self._decrypt_legacy_to_path(temp_db_path)
                outcome = DecryptionResult(DecryptionOutcome.LEGACY)
            duration = time.perf_counter() - start_time
            self._logger.info(
                "Database decrypted successfully in %.2f seconds", duration
            )
            return self._remember(outcome)
        except EnvelopeWrongPasswordError as exc:
            self._logger.warning("Encrypted database password rejected: %s", exc)
            return self._remember(DecryptionResult(DecryptionOutcome.WRONG_PASSWORD))
        except EnvelopeUnsupportedError as exc:
            self._logger.error("Encrypted database format is unsupported: %s", exc)
            return self._remember(DecryptionResult(DecryptionOutcome.UNSUPPORTED))
        except (
            EnvelopeCorruptError,
            EnvelopeDuplicateChunkError,
            EnvelopeReorderedError,
            EnvelopeTrailingDataError,
            EnvelopeTruncatedError,
        ) as exc:
            self._logger.error("Encrypted database is corrupt: %s", exc)
            return self._remember(DecryptionResult(DecryptionOutcome.CORRUPT))
        except InvalidTag:
            self._logger.error(
                "Legacy decryption failed: password is wrong or payload is corrupt"
            )
            return self._remember(DecryptionResult(DecryptionOutcome.WRONG_PASSWORD))
        except Exception as exc:
            self._logger.error("Database decryption failed: %s", exc, exc_info=True)
            return self._remember(DecryptionResult(DecryptionOutcome.CORRUPT))

    def _decrypt_legacy_to_path(self, temp_db_path: str) -> None:
        assert self.key is not None
        with open(self.encrypted_db_path, "rb") as handle:
            payload = handle.read()
        plaintext = crypto_utils.decrypt_payload(payload, self.key, logger=self._logger)
        partial_path = f"{temp_db_path}.decrypting"
        try:
            with open(partial_path, "wb") as handle:
                handle.write(plaintext)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(partial_path, temp_db_path)
        finally:
            Path(partial_path).unlink(missing_ok=True)

    def _remember(self, result: DecryptionResult) -> DecryptionResult:
        self.last_decryption_result = result
        return result

    def snapshot_copy(self, temp_db_path: str | None) -> str | None:
        """Create a consistent snapshot copy using SQLite backup API."""
        if not temp_db_path:
            return None
        try:
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".sqlite",
                prefix="snapshot-",
                dir=os.path.dirname(temp_db_path),
            ) as tmp:
                snapshot_path = tmp.name
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
                except Exception as exc:
                    self._logger.debug(
                        "Failed to close encrypted-database snapshot destination: %s",
                        exc,
                    )
                try:
                    src.close()
                except Exception as exc:
                    self._logger.debug(
                        "Failed to close encrypted-database snapshot source: %s", exc
                    )
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

    def verify_current_envelope(self) -> bool:
        """Authenticate the newly written envelope and run SQLite quick-check."""
        if not self.key:
            return False
        verification_store = TempDatabaseStore(
            logger=self._logger,
            store_metadata=False,
            encrypted_db_path=self.encrypted_db_path,
        )
        verification_path = verification_store.create(suffix=".verify.sqlite")
        try:
            decrypt_envelope_to_path(
                self.encrypted_db_path,
                str(verification_path),
                self.key,
            )
            with closing(sqlite3.connect(verification_path)) as connection:
                row = connection.execute("PRAGMA quick_check").fetchone()
            return bool(row and str(row[0]).lower() == "ok")
        except Exception as exc:
            self._logger.error(
                "Encrypted database verification failed: %s",
                exc,
                exc_info=True,
            )
            return False
        finally:
            verification_store.cleanup()

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
        candidates: set[Path] = set()
        if isinstance(temp_path, str) and temp_path:
            candidates.add(Path(temp_path))
        temp_root = Path(tempfile.gettempdir())
        for directory in temp_root.glob("silverestimate-db-*"):
            marker_path = directory / TempDatabaseStore.MARKER_FILENAME
            if not marker_path.is_file():
                continue
            candidates.update(directory.glob("session*.sqlite"))

        encrypted_mtime = (
            os.path.getmtime(encrypted_db_path)
            if os.path.exists(encrypted_db_path)
            else 0.0
        )
        now = time.time()
        valid: list[Path] = []
        for candidate in candidates:
            if not candidate.is_file():
                continue
            if not TempDatabaseStore.belongs_to_encrypted_database(
                candidate,
                encrypted_db_path,
            ):
                continue
            marker = TempDatabaseStore.read_ownership_marker(candidate) or {}
            try:
                created_at = float(marker.get("created_at", 0.0) or 0.0)
            except TypeError, ValueError:
                created_at = 0.0
            expired = created_at <= 0 or now - created_at > 24 * 60 * 60
            if expired or not EncryptedDatabaseStore._is_valid_sqlite(candidate):
                TempDatabaseStore.cleanup_marked_database(
                    candidate,
                    encrypted_db_path,
                )
                continue
            if candidate.stat().st_mtime > encrypted_mtime:
                valid.append(candidate)
        if not valid:
            return None
        return str(max(valid, key=lambda path: path.stat().st_mtime))

    @staticmethod
    def discard_recovery_candidate(
        plain_temp_path: str,
        encrypted_db_path: str,
        *,
        logger: Optional[logging.Logger] = None,
        settings_factory: Callable[[], SettingsStore] = get_app_settings,
    ) -> bool:
        removed = TempDatabaseStore.cleanup_marked_database(
            plain_temp_path,
            encrypted_db_path,
            logger=logger,
        )
        if removed:
            try:
                settings = settings_factory()
                settings.remove("security/last_temp_db_path")
                settings.sync()
            except Exception as exc:
                if logger:
                    logger.warning(
                        "Failed to clear declined recovery metadata: %s", exc
                    )
        return removed

    @staticmethod
    def _is_valid_sqlite(path: str | Path) -> bool:
        try:
            with closing(
                sqlite3.connect(f"file:{Path(path)}?mode=ro", uri=True, timeout=2)
            ) as connection:
                row = connection.execute("PRAGMA quick_check").fetchone()
            return bool(row and str(row[0]).lower() == "ok")
        except sqlite3.Error:
            return False

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
            store = EncryptedDatabaseStore(
                encrypted_db_path,
                key=key,
                argon2_metadata=Argon2Metadata(
                    salt=salt,
                    time_cost=crypto_utils.DEFAULT_ARGON2_TIME_COST,
                    memory_cost_kib=crypto_utils.DEFAULT_ARGON2_MEMORY_COST_KIB,
                    parallelism=crypto_utils.DEFAULT_ARGON2_PARALLELISM,
                ),
                logger=logger,
            )
            if not store.encrypt_from_path(plain_temp_path):
                return False
            if not store.verify_current_envelope():
                return False
            if logger:
                logger.info("Recovered and encrypted temp DB into encrypted store.")
            try:
                removed = TempDatabaseStore.cleanup_marked_database(
                    plain_temp_path,
                    encrypted_db_path,
                    logger=logger,
                )
                if not removed and logger:
                    logger.warning(
                        "Recovered plaintext was not removed because its directory is unmarked."
                    )
            except Exception as exc:
                if logger:
                    logger.warning(
                        "Failed to delete recovered plaintext temp database '%s': %s",
                        plain_temp_path,
                        exc,
                    )
            try:
                settings = settings_factory()
                settings.remove("security/last_temp_db_path")
                settings.sync()
            except Exception as exc:
                if logger:
                    logger.warning(
                        "Failed to clear recovery metadata after temp DB recovery: %s",
                        exc,
                    )
            return True
        except Exception as exc:
            if logger:
                logger.error("Recovery encryption failed: %s", exc, exc_info=True)
            return False


__all__ = [
    "DecryptionOutcome",
    "DecryptionResult",
    "EncryptedDatabaseStore",
]
