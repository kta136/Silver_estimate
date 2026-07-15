import json
import os
import sqlite3
import time
from contextlib import closing

import pytest

from silverestimate.persistence.encrypted_database_store import (
    DecryptionOutcome,
    EncryptedDatabaseStore,
)
from silverestimate.persistence.temp_database_store import TempDatabaseStore
from silverestimate.security import encryption as crypto_utils


class _StubSettings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        return True


def test_encrypt_and_decrypt_roundtrip(tmp_path):
    temp_db_path = tmp_path / "plain.sqlite"
    temp_db_path.write_bytes(b"sqlite payload")
    encrypted_db_path = tmp_path / "encrypted.db"
    decrypted_db_path = tmp_path / "decrypted.sqlite"

    store = EncryptedDatabaseStore(str(encrypted_db_path), key=b"1" * 32)

    assert store.encrypt_from_path(str(temp_db_path)) is True
    assert encrypted_db_path.exists()
    assert store.decrypt_to_path(str(decrypted_db_path)) == "success"
    assert decrypted_db_path.read_bytes() == b"sqlite payload"


def test_store_reports_current_wrong_password_corrupt_and_unsupported(tmp_path):
    plain = tmp_path / "plain.sqlite"
    plain.write_bytes(b"sqlite payload")
    encrypted = tmp_path / "encrypted.db"
    restored = tmp_path / "restored.sqlite"
    store = EncryptedDatabaseStore(str(encrypted), key=b"1" * 32)
    assert store.encrypt_from_path(str(plain))

    wrong = EncryptedDatabaseStore(str(encrypted), key=b"2" * 32)
    assert wrong.decrypt_to_path_result(str(restored)).outcome == (
        DecryptionOutcome.WRONG_PASSWORD
    )

    payload = bytearray(encrypted.read_bytes())
    payload[-1] ^= 1
    encrypted.write_bytes(payload)
    assert store.decrypt_to_path_result(str(restored)).outcome == (
        DecryptionOutcome.CORRUPT
    )

    encrypted.write_bytes(b"SILVDB02" + payload[8:])
    assert store.decrypt_to_path_result(str(restored)).outcome == (
        DecryptionOutcome.UNSUPPORTED
    )


def test_store_reports_authenticated_legacy_payload(tmp_path):
    encrypted = tmp_path / "legacy.db"
    restored = tmp_path / "restored.sqlite"
    key = b"1" * 32
    encrypted.write_bytes(crypto_utils.encrypt_payload(b"legacy sqlite", key))
    store = EncryptedDatabaseStore(str(encrypted), key=key)

    result = store.decrypt_to_path_result(str(restored))

    assert result.outcome == DecryptionOutcome.LEGACY
    assert restored.read_bytes() == b"legacy sqlite"


def test_decrypt_missing_file_returns_first_run(tmp_path):
    store = EncryptedDatabaseStore(str(tmp_path / "missing.db"), key=b"1" * 32)

    assert store.decrypt_to_path(str(tmp_path / "unused.sqlite")) == "first_run"


def test_check_recovery_candidate_prefers_newer_temp_file(tmp_path):
    settings = _StubSettings()
    encrypted_db_path = tmp_path / "encrypted.db"
    encrypted_db_path.write_text("enc")
    temp_store = TempDatabaseStore(
        encrypted_db_path=str(encrypted_db_path),
        settings_factory=lambda: settings,
    )
    temp_db_path = temp_store.create()
    temp_store.register_for_recovery()
    with closing(sqlite3.connect(temp_db_path)) as connection:
        connection.execute("CREATE TABLE recovery(value TEXT)")
        connection.commit()

    os.utime(encrypted_db_path, (1, 1))
    os.utime(temp_db_path, (2, 2))

    try:
        assert EncryptedDatabaseStore.check_recovery_candidate(
            str(encrypted_db_path),
            settings_factory=lambda: settings,
        ) == str(temp_db_path)

        os.utime(temp_db_path, (1, 1))
        os.utime(encrypted_db_path, (2, 2))

        assert (
            EncryptedDatabaseStore.check_recovery_candidate(
                str(encrypted_db_path),
                settings_factory=lambda: settings,
            )
            is None
        )
    finally:
        temp_store.cleanup()


def test_recover_encrypt_plain_to_encrypted_clears_plaintext_and_metadata(tmp_path):
    settings = _StubSettings()
    encrypted_db_path = tmp_path / "encrypted.db"
    temp_store = TempDatabaseStore(
        encrypted_db_path=str(encrypted_db_path),
        settings_factory=lambda: settings,
    )
    plain_temp_path = temp_store.create()
    temp_store.register_for_recovery()
    with closing(sqlite3.connect(plain_temp_path)) as connection:
        connection.execute("CREATE TABLE recovery(value TEXT NOT NULL)")
        connection.execute("INSERT INTO recovery(value) VALUES ('payload')")
        connection.commit()
    assert (
        EncryptedDatabaseStore.recover_encrypt_plain_to_encrypted(
            str(plain_temp_path),
            str(encrypted_db_path),
            "recovery-password",
            settings_factory=lambda: settings,
        )
        is True
    )
    assert encrypted_db_path.exists()
    assert not plain_temp_path.exists()
    assert settings.value("security/last_temp_db_path") is None

    key = crypto_utils.derive_key(
        "recovery-password",
        EncryptedDatabaseStore.get_or_create_salt(settings_factory=lambda: settings),
    )
    store = EncryptedDatabaseStore(str(encrypted_db_path), key=key)
    decrypted_db_path = tmp_path / "recovered.sqlite"

    assert store.decrypt_to_path(str(decrypted_db_path)) == "success"
    with closing(sqlite3.connect(decrypted_db_path)) as connection:
        row = connection.execute("SELECT value FROM recovery").fetchone()
    assert row == ("payload",)


@pytest.mark.parametrize("mode", ["invalid", "expired"])
def test_candidate_scan_removes_invalid_or_expired_marked_databases(tmp_path, mode):
    settings = _StubSettings()
    encrypted_db_path = tmp_path / "encrypted.db"
    encrypted_db_path.write_bytes(b"encrypted")
    store = TempDatabaseStore(
        encrypted_db_path=str(encrypted_db_path),
        settings_factory=lambda: settings,
    )
    candidate = store.create()
    store.register_for_recovery()
    if mode == "invalid":
        candidate.write_bytes(b"not sqlite")
    else:
        with closing(sqlite3.connect(candidate)) as connection:
            connection.execute("CREATE TABLE recovery(value TEXT)")
            connection.commit()
        marker_path = candidate.parent / TempDatabaseStore.MARKER_FILENAME
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        marker["created_at"] = time.time() - (25 * 60 * 60)
        marker_path.write_text(json.dumps(marker), encoding="utf-8")

    assert (
        EncryptedDatabaseStore.check_recovery_candidate(
            str(encrypted_db_path),
            settings_factory=lambda: settings,
        )
        is None
    )
    assert not candidate.exists()
