import os

from silverestimate.persistence.encrypted_database_store import EncryptedDatabaseStore
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


def test_decrypt_missing_file_returns_first_run(tmp_path):
    store = EncryptedDatabaseStore(str(tmp_path / "missing.db"), key=b"1" * 32)

    assert store.decrypt_to_path(str(tmp_path / "unused.sqlite")) == "first_run"


def test_check_recovery_candidate_prefers_newer_temp_file(tmp_path):
    settings = _StubSettings()
    temp_db_path = tmp_path / "temp.sqlite"
    encrypted_db_path = tmp_path / "encrypted.db"
    temp_db_path.write_text("temp")
    encrypted_db_path.write_text("enc")
    settings.setValue("security/last_temp_db_path", str(temp_db_path))

    os.utime(encrypted_db_path, (1, 1))
    os.utime(temp_db_path, (2, 2))

    assert (
        EncryptedDatabaseStore.check_recovery_candidate(
            str(encrypted_db_path),
            settings_factory=lambda: settings,
        )
        == str(temp_db_path)
    )

    os.utime(temp_db_path, (1, 1))
    os.utime(encrypted_db_path, (2, 2))

    assert (
        EncryptedDatabaseStore.check_recovery_candidate(
            str(encrypted_db_path),
            settings_factory=lambda: settings,
        )
        is None
    )


def test_recover_encrypt_plain_to_encrypted_clears_plaintext_and_metadata(tmp_path):
    settings = _StubSettings()
    plain_temp_path = tmp_path / "recovery.sqlite"
    plain_temp_path.write_bytes(b"recovery payload")
    encrypted_db_path = tmp_path / "encrypted.db"
    settings.setValue("security/last_temp_db_path", str(plain_temp_path))

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
    assert decrypted_db_path.read_bytes() == b"recovery payload"
