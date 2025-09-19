import base64
import os

import pytest
from cryptography.exceptions import InvalidTag

from silverestimate.security import encryption


class FakeSettings:
    def __init__(self, initial=None):
        self._storage = dict(initial or {})
        self.synced = False

    def value(self, key):
        return self._storage.get(key)

    def setValue(self, key, value):
        self._storage[key] = value

    def sync(self):
        self.synced = True

    def remove(self, key):
        self._storage.pop(key, None)


def test_get_or_create_salt_creates_and_persists():
    settings = FakeSettings()
    salt = encryption.get_or_create_salt(settings, length=8)
    assert isinstance(salt, bytes)
    assert len(salt) == 8

    stored = settings.value(encryption.SALT_SETTINGS_KEY)
    assert stored is not None
    assert base64.b64decode(stored) == salt
    assert settings.synced

    # Subsequent call should reuse the stored salt
    reused = encryption.get_or_create_salt(settings, length=8)
    assert reused == salt


def test_get_or_create_salt_recovers_from_bad_value():
    settings = FakeSettings({encryption.SALT_SETTINGS_KEY: "not-base64"})
    salt = encryption.get_or_create_salt(settings, length=8)
    assert isinstance(salt, bytes)
    assert len(salt) == 8


def test_derive_key_roundtrip():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    key = encryption.derive_key("password", salt, iterations=1_000)
    assert len(key) == 32


def test_derive_key_requires_password_and_salt():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    with pytest.raises(ValueError):
        encryption.derive_key("", salt)
    with pytest.raises(ValueError):
        encryption.derive_key("password", b"")


def test_encrypt_decrypt_roundtrip():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    key = encryption.derive_key("secret", salt, iterations=1_000)
    payload = encryption.encrypt_payload(b"super-secret", key)
    assert len(payload) > encryption.NONCE_BYTES
    plaintext = encryption.decrypt_payload(payload, key)
    assert plaintext == b"super-secret"


def test_encrypt_payload_empty_returns_nonce_only():
    key = os.urandom(32)
    payload = encryption.encrypt_payload(b"", key)
    assert len(payload) == encryption.NONCE_BYTES


def test_decrypt_payload_invalid_tag_raises():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    key = encryption.derive_key("secret", salt, iterations=1_000)
    payload = encryption.encrypt_payload(b"data", key)
    tampered = payload[:-1] + bytes([payload[-1] ^ 1])
    with pytest.raises(InvalidTag):
        encryption.decrypt_payload(tampered, key)
