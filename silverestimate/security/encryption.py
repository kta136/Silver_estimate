"""Encryption utilities for the Silver Estimate application."""
from __future__ import annotations

import base64
import logging
import os
import time
from typing import Optional

from PyQt5.QtCore import QSettings
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

SALT_SETTINGS_KEY = "security/db_salt"
DEFAULT_SALT_BYTES = 16
DEFAULT_KDF_ITERATIONS = 100_000
NONCE_BYTES = 12


def get_or_create_salt(
    settings: QSettings,
    logger: Optional[logging.Logger] = None,
    *,
    settings_key: str = SALT_SETTINGS_KEY,
    length: int = DEFAULT_SALT_BYTES,
) -> bytes:
    """Return an existing salt from settings or create and persist a new one."""
    salt_b64 = settings.value(settings_key)
    if salt_b64:
        try:
            salt = base64.b64decode(salt_b64)
            if logger:
                logger.debug("Retrieved existing salt from settings")
            return salt
        except Exception as exc:  # noqa: BLE001 - log and regenerate
            if logger:
                logger.warning("Failed to decode stored salt: %s. Regenerating.", exc)

    if logger:
        logger.info("Generating new database salt")
    salt = os.urandom(length)
    settings.setValue(settings_key, base64.b64encode(salt).decode("utf-8"))
    settings.sync()
    return salt


def derive_key(
    password: str,
    salt: bytes,
    *,
    iterations: int = DEFAULT_KDF_ITERATIONS,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Derive a 32-byte AES key using PBKDF2."""
    if not password:
        raise ValueError("Password cannot be empty for key derivation.")
    if not salt:
        raise ValueError("Salt cannot be empty for key derivation.")

    if logger:
        logger.debug("Deriving encryption key")
    start = time.time()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
        backend=default_backend(),
    )
    key = kdf.derive(password.encode("utf-8"))
    if logger:
        logger.debug("Encryption key derived in %.2f seconds", time.time() - start)
    return key


def encrypt_payload(
    plaintext: bytes,
    key: bytes,
    *,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Encrypt plaintext and return nonce+ciphertext payload."""
    if not key:
        raise ValueError("Encryption key is required.")

    aesgcm = AESGCM(key)
    nonce = os.urandom(NONCE_BYTES)
    if not plaintext:
        if logger:
            logger.warning("Encrypting empty payload; writing nonce only.")
        return nonce

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext


def decrypt_payload(
    payload: bytes,
    key: bytes,
    *,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Decrypt a nonce+ciphertext payload and return plaintext."""
    if not key:
        raise ValueError("Encryption key is required.")
    if not payload or len(payload) <= NONCE_BYTES:
        raise ValueError("Encrypted payload is incomplete or missing nonce.")

    nonce, ciphertext = payload[:NONCE_BYTES], payload[NONCE_BYTES:]
    if not ciphertext:
        raise ValueError("Encrypted payload is missing ciphertext.")

    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        if logger:
            logger.error("Decryption failed: InvalidTag")
        raise
    except Exception as exc:  # noqa: BLE001 - bubble up for caller to handle
        if logger:
            logger.error("Decryption failed: %s", exc)
        raise
