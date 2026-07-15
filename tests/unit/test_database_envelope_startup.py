import sqlite3
from contextlib import closing

import pytest

import silverestimate.persistence.database_manager as database_manager_module
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.encrypted_database_store import EncryptedDatabaseStore
from silverestimate.security import encryption as crypto_utils
from silverestimate.security.encrypted_envelope import Argon2Metadata


class _StubSettings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None, type=None):  # noqa: A002
        del type
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        return True


def _create_current_database(tmp_path, password: str):
    plaintext = tmp_path / "plain.sqlite"
    encrypted = tmp_path / "encrypted.db"
    with closing(sqlite3.connect(plaintext)) as connection:
        connection.execute("CREATE TABLE retained(value TEXT NOT NULL)")
        connection.execute("INSERT INTO retained(value) VALUES ('yes')")
        connection.commit()
    argon2 = Argon2Metadata(
        salt=b"header-owned-salt",
        time_cost=1,
        memory_cost_kib=1024,
        parallelism=1,
    )
    key = crypto_utils.derive_key(
        password,
        argon2.salt,
        time_cost=argon2.time_cost,
        memory_cost_kib=argon2.memory_cost_kib,
        parallelism=argon2.parallelism,
    )
    store = EncryptedDatabaseStore(
        str(encrypted),
        key=key,
        argon2_metadata=argon2,
    )
    assert store.encrypt_from_path(str(plaintext))
    return encrypted, argon2


def test_current_envelope_uses_header_salt_and_derives_only_argon2(
    tmp_path, monkeypatch
):
    password = "correct password"
    encrypted, argon2 = _create_current_database(tmp_path, password)
    settings = _StubSettings()
    algorithms = []
    original_derive = crypto_utils.derive_key

    def recording_derive(*args, **kwargs):
        algorithms.append(kwargs.get("algorithm", crypto_utils.PREFERRED_KDF_ALGORITHM))
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(database_manager_module, "get_app_settings", lambda: settings)
    monkeypatch.setattr(crypto_utils, "derive_key", recording_derive)

    manager = DatabaseManager(str(encrypted), password)
    try:
        assert manager.salt == argon2.salt
        assert algorithms == [crypto_utils.PREFERRED_KDF_ALGORITHM]
        assert settings.value(crypto_utils.SALT_SETTINGS_KEY) is None
        row = manager.conn.execute("SELECT value FROM retained").fetchone()
        assert tuple(row) == ("yes",)
    finally:
        manager.close()


def test_current_envelope_wrong_password_does_not_derive_legacy_key(
    tmp_path, monkeypatch
):
    encrypted, _argon2 = _create_current_database(tmp_path, "correct password")
    settings = _StubSettings()
    algorithms = []
    original_derive = crypto_utils.derive_key

    def recording_derive(*args, **kwargs):
        algorithms.append(kwargs.get("algorithm", crypto_utils.PREFERRED_KDF_ALGORITHM))
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(database_manager_module, "get_app_settings", lambda: settings)
    monkeypatch.setattr(crypto_utils, "derive_key", recording_derive)

    with pytest.raises(Exception, match="Database decryption failed"):
        DatabaseManager(str(encrypted), "wrong password")

    assert algorithms == [crypto_utils.PREFERRED_KDF_ALGORITHM]


def test_unsupported_current_envelope_does_not_derive_legacy_key(tmp_path, monkeypatch):
    encrypted, _argon2 = _create_current_database(tmp_path, "correct password")
    payload = encrypted.read_bytes()
    encrypted.write_bytes(b"SILVDB02" + payload[8:])
    settings = _StubSettings()
    algorithms = []
    original_derive = crypto_utils.derive_key

    def recording_derive(*args, **kwargs):
        algorithms.append(kwargs.get("algorithm", crypto_utils.PREFERRED_KDF_ALGORITHM))
        return original_derive(*args, **kwargs)

    monkeypatch.setattr(database_manager_module, "get_app_settings", lambda: settings)
    monkeypatch.setattr(crypto_utils, "derive_key", recording_derive)

    with pytest.raises(Exception, match="Database decryption failed"):
        DatabaseManager(str(encrypted), "correct password")

    assert algorithms == [crypto_utils.PREFERRED_KDF_ALGORITHM]
