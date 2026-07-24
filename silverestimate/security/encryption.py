"""Argon2id key derivation for encrypted SQLite envelopes."""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Optional

from argon2.low_level import Type, hash_secret_raw

DEFAULT_SALT_BYTES = 16
DEFAULT_ARGON2_TIME_COST = 3
DEFAULT_ARGON2_MEMORY_COST_KIB = 64 * 1024
DEFAULT_ARGON2_PARALLELISM = 4
DEVICE_BINDING_BYTES = 32
DEVICE_BOUND_KEY_CONTEXT = b"SilverEstimate/device-bound-sqlcipher/v1"


def derive_key(
    password: str,
    salt: bytes,
    *,
    time_cost: int = DEFAULT_ARGON2_TIME_COST,
    memory_cost_kib: int = DEFAULT_ARGON2_MEMORY_COST_KIB,
    parallelism: int = DEFAULT_ARGON2_PARALLELISM,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Derive a 32-byte AES key with Argon2id."""
    if not password:
        raise ValueError("Password cannot be empty for key derivation.")
    if not salt:
        raise ValueError("Salt cannot be empty for key derivation.")

    if logger:
        logger.debug("Deriving encryption key using Argon2id")
    start = time.time()
    key = hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost_kib,
        parallelism=parallelism,
        hash_len=32,
        type=Type.ID,
    )
    if logger:
        logger.debug(
            "Encryption key derived using Argon2id in %.2f seconds",
            time.time() - start,
        )
    return key


def derive_device_bound_key(
    password: str,
    salt: bytes,
    device_secret: bytes,
    *,
    time_cost: int = DEFAULT_ARGON2_TIME_COST,
    memory_cost_kib: int = DEFAULT_ARGON2_MEMORY_COST_KIB,
    parallelism: int = DEFAULT_ARGON2_PARALLELISM,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Derive a SQLCipher key that requires both a password and this device."""
    if len(salt) != DEFAULT_SALT_BYTES:
        raise ValueError("Database salts must contain exactly 16 bytes.")
    if len(device_secret) != DEVICE_BINDING_BYTES:
        raise ValueError("Device-binding secrets must contain exactly 32 bytes.")
    password_key = derive_key(
        password,
        salt,
        time_cost=time_cost,
        memory_cost_kib=memory_cost_kib,
        parallelism=parallelism,
        logger=logger,
    )
    return hmac.digest(
        device_secret,
        DEVICE_BOUND_KEY_CONTEXT + b"\x00" + salt + password_key,
        "sha256",
    )


def device_binding_fingerprint(device_secret: bytes) -> str:
    """Return a non-secret identifier used to reject foreign-device backups."""
    if len(device_secret) != DEVICE_BINDING_BYTES:
        raise ValueError("Device-binding secrets must contain exactly 32 bytes.")
    return hashlib.sha256(
        DEVICE_BOUND_KEY_CONTEXT + b"\x00fingerprint\x00" + device_secret
    ).hexdigest()
