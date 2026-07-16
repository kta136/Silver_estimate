"""Argon2id key derivation for encrypted SQLite envelopes."""

from __future__ import annotations

import logging
import time
from typing import Optional

from argon2.low_level import Type, hash_secret_raw

DEFAULT_SALT_BYTES = 16
DEFAULT_ARGON2_TIME_COST = 3
DEFAULT_ARGON2_MEMORY_COST_KIB = 64 * 1024
DEFAULT_ARGON2_PARALLELISM = 4


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
