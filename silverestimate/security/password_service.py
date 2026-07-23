"""Password hashing policy and verification independent of the Qt UI."""

from __future__ import annotations

from dataclasses import dataclass

from argon2 import PasswordHasher, extract_parameters
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from argon2.low_level import Type

PASSWORD_TIME_COST = 3
PASSWORD_MEMORY_COST_KIB = 65_536
PASSWORD_PARALLELISM = 4
PASSWORD_HASH_LENGTH = 32
PASSWORD_SALT_LENGTH = 16


class PasswordHashError(RuntimeError):
    """Base error for password hashing and verification failures."""


class MalformedPasswordHashError(PasswordHashError):
    """Raised when a stored password hash is not a valid Argon2 PHC string."""


class PasswordHashingError(PasswordHashError):
    """Raised when the configured Argon2 implementation cannot hash a password."""


@dataclass(frozen=True)
class PasswordVerification:
    """Result of verifying a password against a stored Argon2 hash."""

    verified: bool
    replacement_hash: str | None = None


class PasswordHashService:
    """Own the application's Argon2id password-hashing policy."""

    def __init__(self, hasher: PasswordHasher | None = None) -> None:
        self._hasher = hasher or PasswordHasher(
            time_cost=PASSWORD_TIME_COST,
            memory_cost=PASSWORD_MEMORY_COST_KIB,
            parallelism=PASSWORD_PARALLELISM,
            hash_len=PASSWORD_HASH_LENGTH,
            salt_len=PASSWORD_SALT_LENGTH,
            type=Type.ID,
        )

    def hash_password(self, password: str) -> str:
        """Return a new Argon2id PHC hash for a non-empty password."""
        if not password:
            raise ValueError("Password must not be empty")
        try:
            return self._hasher.hash(password)
        except HashingError as exc:
            raise PasswordHashingError("Argon2 password hashing failed") from exc

    def verify_password(
        self,
        stored_hash: str,
        provided_password: str,
    ) -> PasswordVerification:
        """Verify a password and return a stronger replacement hash when needed."""
        if not stored_hash:
            raise MalformedPasswordHashError("Stored password hash is empty")
        try:
            parameters = extract_parameters(stored_hash)
        except InvalidHashError as exc:
            raise MalformedPasswordHashError(
                "Stored password hash is not a valid Argon2 PHC string"
            ) from exc
        if parameters.type is not Type.ID:
            raise MalformedPasswordHashError(
                "Stored password hash does not use Argon2id"
            )
        if not provided_password:
            return PasswordVerification(verified=False)

        try:
            self._hasher.verify(stored_hash, provided_password)
        except VerifyMismatchError:
            return PasswordVerification(verified=False)
        except InvalidHashError as exc:
            raise MalformedPasswordHashError(
                "Stored password hash is not a valid Argon2 PHC string"
            ) from exc
        except VerificationError as exc:
            raise MalformedPasswordHashError(
                "Stored password hash cannot be verified"
            ) from exc

        try:
            needs_rehash = self._hasher.check_needs_rehash(stored_hash)
        except InvalidHashError as exc:
            raise MalformedPasswordHashError(
                "Stored password hash is not a valid Argon2 PHC string"
            ) from exc

        replacement_hash = (
            self.hash_password(provided_password) if needs_rehash else None
        )
        return PasswordVerification(
            verified=True,
            replacement_hash=replacement_hash,
        )
