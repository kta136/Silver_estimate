"""Coordination helpers for encrypted database flush and shutdown."""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from typing import Callable, Optional

from silverestimate.persistence.encrypted_database_store import EncryptedDatabaseStore
from silverestimate.persistence.flush_scheduler import (
    Callback,
    FlushScheduler,
    _ThreadHandle,
    _TimerHandle,
)

BytesGetter = Callable[[], bytes | None]
ConnectionGetter = Callable[[], object | None]
StringGetter = Callable[[], str | None]
KeySetter = Callable[[bytes | None], None]
BoolCallback = Callable[[], bool]
CleanupCallback = Callable[[bool], None]
CloseConnectionCallback = Callable[[], None]


class DatabaseLifecycleCoordinator:
    """Coordinate encryption flushes, key rotation, and shutdown cleanup."""

    def __init__(
        self,
        *,
        encrypted_store: EncryptedDatabaseStore,
        connection_getter: ConnectionGetter,
        temp_db_path_getter: StringGetter,
        key_getter: BytesGetter,
        key_setter: KeySetter,
        commit: BoolCallback,
        checkpoint: BoolCallback,
        logger: Optional[logging.Logger] = None,
        on_queued_getter: Optional[Callable[[], Callback]] = None,
        on_done_getter: Optional[Callable[[], Callback]] = None,
        timer_factory: Optional[
            Callable[[float, Callable[[], None]], _TimerHandle]
        ] = None,
        thread_factory: Optional[Callable[..., _ThreadHandle]] = None,
        time_func: Optional[Callable[[], float]] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self._encrypted_store = encrypted_store
        self._connection_getter = connection_getter
        self._temp_db_path_getter = temp_db_path_getter
        self._key_getter = key_getter
        self._key_setter = key_setter
        self._commit = commit
        self._checkpoint = checkpoint
        self._logger = logger or logging.getLogger(__name__)
        self._encrypt_lock = threading.Lock()
        self._flush_scheduler = FlushScheduler(
            has_connection=lambda: self._connection_getter() is not None,
            commit=self._commit,
            checkpoint=self._checkpoint,
            encrypt=self.encrypt_current_state,
            logger=self._logger,
            on_queued_getter=on_queued_getter,
            on_done_getter=on_done_getter,
            timer_factory=timer_factory,
            thread_factory=thread_factory,
            time_func=time_func,
            sleep_func=sleep_func,
        )

    def encrypt_current_state(self) -> bool:
        """Encrypt the active temp DB using the current key."""
        with self._encrypt_lock:
            conn = self._connection_getter()
            temp_db_path = self._temp_db_path_getter()
            key = self._key_getter()

            if not conn or not temp_db_path or not os.path.exists(temp_db_path):
                self._logger.warning(
                    "Encryption skipped: No active connection or temporary DB file."
                )
                return False
            if not key:
                self._logger.warning("Encryption skipped: No encryption key available.")
                return False
            if not self._commit():
                return False

            try:
                self._checkpoint()
            except Exception as exc:
                self._logger.debug("Checkpoint before encryption failed: %s", exc)

            self._encrypted_store.set_key(key)
            return self._encrypted_store.encrypt_from_path(temp_db_path)

    def decrypt_current_temp(
        self, *, on_error: Optional[Callable[[], None]] = None
    ) -> str:
        """Decrypt the encrypted DB into the current temp path and report status."""
        self._encrypted_store.set_key(self._key_getter())
        status = self._encrypted_store.decrypt_to_path(self._temp_db_path_getter())
        if status == "error" and on_error is not None:
            on_error()
        return status

    def reencrypt_with_new_password(
        self,
        new_password: str,
        *,
        salt: bytes,
        derive_key: Callable[[str, bytes], bytes],
    ) -> bool:
        """Rotate the current password-derived key and rewrite the encrypted DB."""
        try:
            if not new_password:
                raise ValueError("New password cannot be empty.")
            old_key = self._key_getter()
            new_key = derive_key(new_password, salt)
            self._key_setter(new_key)
            success = False
            try:
                success = self.encrypt_current_state()
            finally:
                if not success:
                    self._key_setter(old_key)
            if success:
                self._logger.info("Database re-encrypted with new password.")
            return success
        except Exception as exc:
            self._logger.error("Re-encryption failed: %s", exc, exc_info=True)
            return False

    def flush_to_encrypted(self) -> bool:
        """Persist the current temp DB state into the encrypted store."""
        if not self._connection_getter():
            self._logger.warning("flush_to_encrypted skipped: No active connection.")
            return False
        return self.encrypt_current_state()

    def request_flush(self, delay_seconds: float = 2.0) -> None:
        """Debounce a background flush of the encrypted database."""
        self._flush_scheduler.schedule(delay_seconds=delay_seconds)

    def close(
        self,
        *,
        close_connection: CloseConnectionCallback,
        cleanup_temp_db: CleanupCallback,
        preserve_plaintext_on_failure: bool = False,
    ) -> None:
        """Flush on shutdown, close the connection, and clean temp artifacts."""
        self._shutdown_scheduler()

        encrypt_success = False
        encryption_attempted = False
        if self._connection_getter():
            self._logger.info("Closing database connection and encrypting data")
            encryption_attempted = True
            try:
                encrypt_success = self.encrypt_current_state()
            except Exception:
                encrypt_success = False

            if encrypt_success:
                self._logger.info("Temporary database encrypted successfully")
            else:
                self._logger.critical("Failed to encrypt database on close!")
                self._logger.critical(
                    "The unencrypted data might still be in: %s",
                    self._temp_db_path_getter(),
                )

            try:
                close_connection()
                self._logger.debug("Database connection closed")
            except sqlite3.Error as exc:
                self._logger.error(
                    "Error closing SQLite connection: %s",
                    exc,
                    exc_info=True,
                )
        else:
            self._logger.debug("No active database connection to close")

        if encrypt_success:
            cleanup_temp_db(False)
        elif encryption_attempted:
            if preserve_plaintext_on_failure:
                self._logger.critical(
                    "Preserving temporary database file due to encryption failure."
                )
                cleanup_temp_db(True)
            else:
                self._logger.critical(
                    "Plaintext temp-db recovery is disabled; deleting temporary database file."
                )
                cleanup_temp_db(False)
        else:
            cleanup_temp_db(False)

    def _shutdown_scheduler(self) -> None:
        try:
            self._flush_scheduler.shutdown()
        except Exception as exc:
            self._logger.debug("Failed to shut down flush scheduler: %s", exc)


__all__ = ["DatabaseLifecycleCoordinator"]
