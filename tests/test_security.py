import os

import pytest

from silverestimate.security import encryption


def test_derive_key_uses_argon2id_deterministically():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    options = {
        "time_cost": 1,
        "memory_cost_kib": 1024,
        "parallelism": 1,
    }

    first = encryption.derive_key("password", salt, **options)
    second = encryption.derive_key("password", salt, **options)

    assert len(first) == 32
    assert first == second


def test_derive_key_requires_password_and_salt():
    salt = os.urandom(encryption.DEFAULT_SALT_BYTES)
    with pytest.raises(ValueError):
        encryption.derive_key("", salt)
    with pytest.raises(ValueError):
        encryption.derive_key("password", b"")
