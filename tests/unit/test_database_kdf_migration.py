import sqlite3

import silverestimate.persistence.database_manager as database_manager_module
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.encrypted_database_store import EncryptedDatabaseStore
from silverestimate.security import encryption as crypto_utils


class _StubSettings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None, type=None):  # noqa: A002 - QSettings parity
        del type
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        return True


def _create_legacy_encrypted_database(
    tmp_path,
    *,
    password: str,
    settings: _StubSettings,
):
    plain_db_path = tmp_path / "legacy.sqlite"
    encrypted_db_path = tmp_path / "encrypted.db"

    conn = sqlite3.connect(plain_db_path)
    try:
        conn.execute("CREATE TABLE legacy_test (value TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_test(value) VALUES (?)", ("kept",))
        conn.commit()
    finally:
        conn.close()

    salt = EncryptedDatabaseStore.get_or_create_salt(settings_factory=lambda: settings)
    legacy_key = crypto_utils.derive_key(
        password,
        salt,
        algorithm=crypto_utils.LEGACY_KDF_ALGORITHM,
        iterations=crypto_utils.DEFAULT_KDF_ITERATIONS,
    )
    store = EncryptedDatabaseStore(str(encrypted_db_path), key=legacy_key)
    assert store.encrypt_from_path(str(plain_db_path)) is True
    plain_db_path.unlink()
    return encrypted_db_path, salt, legacy_key


def test_database_manager_migrates_legacy_pbkdf2_database_to_argon2(
    tmp_path,
    monkeypatch,
):
    settings = _StubSettings()
    password = "migration-password"
    encrypted_db_path, salt, legacy_key = _create_legacy_encrypted_database(
        tmp_path,
        password=password,
        settings=settings,
    )

    monkeypatch.setattr(
        database_manager_module,
        "get_app_settings",
        lambda: settings,
    )

    manager = DatabaseManager(str(encrypted_db_path), password)
    try:
        assert manager._pending_kdf_migration is False
        assert manager._active_kdf_algorithm == crypto_utils.PREFERRED_KDF_ALGORITHM
        assert manager.key == manager._preferred_key

        preferred_key = crypto_utils.derive_key(
            password,
            salt,
            algorithm=crypto_utils.PREFERRED_KDF_ALGORITHM,
        )
        assert preferred_key == manager.key
    finally:
        manager.close()

    preferred_store = EncryptedDatabaseStore(
        str(encrypted_db_path),
        key=preferred_key,
    )
    decrypted_db_path = tmp_path / "decrypted.sqlite"
    assert preferred_store.decrypt_to_path(str(decrypted_db_path)) == "success"

    conn = sqlite3.connect(decrypted_db_path)
    try:
        row = conn.execute("SELECT value FROM legacy_test").fetchone()
    finally:
        conn.close()
    assert row == ("kept",)

    legacy_store = EncryptedDatabaseStore(str(encrypted_db_path), key=legacy_key)
    assert legacy_store.decrypt_to_path(str(tmp_path / "legacy-decrypt.sqlite")) == "error"
