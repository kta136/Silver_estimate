import pytest
from argon2 import PasswordHasher
from argon2.low_level import Type

from silverestimate.security.password_service import (
    MalformedPasswordHashError,
    PasswordHashService,
)

SYNTHETIC_PASSWORD = "synthetic-main-password"

# Fixed Argon2id fixture using the application's current policy.
CURRENT_POLICY_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$c3ludGhldGljLXNhbHQhIQ$"
    "FX332B9UqVYkQQBqgo/RIhU0EiPnwKVjvSXVXSgSYc8"
)

def test_hash_password_uses_explicit_argon2id_policy() -> None:
    password_service = PasswordHashService()

    password_hash = password_service.hash_password(SYNTHETIC_PASSWORD)

    assert password_hash.startswith("$argon2id$v=19$m=65536,t=3,p=4$")
    assert PasswordHasher().verify(password_hash, SYNTHETIC_PASSWORD)


def test_current_policy_hash_verifies() -> None:
    password_service = PasswordHashService()

    verification = password_service.verify_password(
        CURRENT_POLICY_HASH,
        SYNTHETIC_PASSWORD,
    )

    assert verification.verified


def test_noncurrent_policy_hash_is_rejected() -> None:
    noncurrent_hash = PasswordHasher(
        time_cost=2,
        memory_cost=8192,
        parallelism=1,
        hash_len=32,
        salt_len=16,
        type=Type.ID,
    ).hash(SYNTHETIC_PASSWORD)

    with pytest.raises(MalformedPasswordHashError, match="current Argon2id policy"):
        PasswordHashService().verify_password(
            noncurrent_hash,
            SYNTHETIC_PASSWORD,
        )


def test_wrong_password_is_an_expected_mismatch() -> None:
    verification = PasswordHashService().verify_password(
        CURRENT_POLICY_HASH,
        "wrong-password",
    )

    assert not verification.verified


@pytest.mark.parametrize("stored_hash", ["", "not-a-password-hash", "$argon2id$bad"])
def test_malformed_hash_is_distinct_from_password_mismatch(stored_hash: str) -> None:
    with pytest.raises(MalformedPasswordHashError):
        PasswordHashService().verify_password(stored_hash, SYNTHETIC_PASSWORD)


def test_empty_password_is_rejected_for_new_hashes() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        PasswordHashService().hash_password("")
