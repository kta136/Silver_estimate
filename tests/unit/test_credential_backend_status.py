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
