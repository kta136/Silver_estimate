import pytest

from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError


def test_backend_status_reports_missing_keyring(monkeypatch):
    monkeypatch.setattr(credential_store, "keyring", None)
    status = credential_store.get_backend_status()
    assert status.available is False
    assert status.backend_name == "missing"


def test_backend_status_rejects_null_backend(monkeypatch):
    class NullBackend:
        __module__ = "keyring.backends.null"

    class FakeKeyring:
        @staticmethod
        def get_keyring():
            return NullBackend()

    monkeypatch.setattr(credential_store, "keyring", FakeKeyring)
    status = credential_store.get_backend_status()
    assert status.available is False
    assert "null" in status.backend_name.lower()


def test_get_password_hash_fails_fast_with_untrusted_backend(monkeypatch):
    class FailBackend:
        __module__ = "keyring.backends.fail"

    class FakeKeyring:
        @staticmethod
        def get_keyring():
            return FailBackend()

    monkeypatch.setattr(credential_store, "keyring", FakeKeyring)
    with pytest.raises(CredentialStoreError):
        credential_store.get_password_hash("main")


def test_backend_status_cache_invalidates_when_keyring_object_changes(monkeypatch):
    class GoodBackend:
        __module__ = "keyring.backends.Windows"

    class NullBackend:
        __module__ = "keyring.backends.null"

    class GoodKeyring:
        @staticmethod
        def get_keyring():
            return GoodBackend()

    class BadKeyring:
        @staticmethod
        def get_keyring():
            return NullBackend()

    monkeypatch.setattr(credential_store, "keyring", GoodKeyring)
    good_status = credential_store.get_backend_status()
    assert good_status.available is True

    monkeypatch.setattr(credential_store, "keyring", BadKeyring)
    bad_status = credential_store.get_backend_status()
    assert bad_status.available is False


@pytest.mark.parametrize(
    "kind",
    (
        "main",
        "backup",
        "pending_main",
        "pending_backup",
        "recovery_main",
        "recovery_backup",
        "device_binding",
    ),
)
def test_all_database_credential_kinds_use_the_os_keyring(monkeypatch, kind):
    stored = {}

    class WindowsBackend:
        __module__ = "keyring.backends.Windows"

    class FakeKeyring:
        @staticmethod
        def get_keyring():
            return WindowsBackend()

        @staticmethod
        def get_password(service, secure_id):
            return stored.get((service, secure_id))

        @staticmethod
        def set_password(service, secure_id, value):
            stored[(service, secure_id)] = value

        @staticmethod
        def delete_password(service, secure_id):
            stored.pop((service, secure_id), None)

    monkeypatch.setattr(credential_store, "keyring", FakeKeyring)

    credential_store.set_password_hash(kind, "hash")
    assert credential_store.get_password_hash(kind) == "hash"
    credential_store.delete_password_hash(kind)
    assert credential_store.get_password_hash(kind) is None


def test_unknown_credential_kind_is_rejected_before_keyring_access():
    with pytest.raises(ValueError, match="Unknown credential kind"):
        credential_store.get_password_hash("unknown")


def test_device_binding_secret_is_stable_and_deletable(monkeypatch):
    stored = {}
    writes = 0

    class WindowsBackend:
        __module__ = "keyring.backends.Windows"
        persist = "enterprise"

    backend = WindowsBackend()

    class FakeKeyring:
        @staticmethod
        def get_keyring():
            return backend

        @staticmethod
        def get_password(service, secure_id):
            return stored.get((service, secure_id))

        @staticmethod
        def set_password(service, secure_id, value):
            nonlocal writes
            assert backend.persist == "local machine"
            writes += 1
            stored[(service, secure_id)] = value

        @staticmethod
        def delete_password(service, secure_id):
            stored.pop((service, secure_id), None)

    monkeypatch.setattr(credential_store, "keyring", FakeKeyring)

    first = credential_store.create_device_binding_secret()
    second = credential_store.create_device_binding_secret()

    assert first == second
    assert len(first) == 32
    assert writes == 2
    assert backend.persist == "enterprise"
    credential_store.delete_device_binding_secret()
    assert credential_store.get_device_binding_secret() is None


def test_device_binding_rejects_non_windows_keyring(monkeypatch):
    class SecretServiceBackend:
        __module__ = "keyring.backends.SecretService"

    class FakeKeyring:
        @staticmethod
        def get_keyring():
            return SecretServiceBackend()

    monkeypatch.setattr(credential_store, "keyring", FakeKeyring)

    with pytest.raises(
        CredentialStoreError,
        match="requires the Windows Credential Manager backend",
    ):
        credential_store.create_device_binding_secret()
