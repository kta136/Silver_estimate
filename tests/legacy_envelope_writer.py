"""Test-only SILVDB01 fixture writer; production retains no envelope writer."""

from __future__ import annotations

import base64
import math
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from silverestimate.security import encrypted_envelope as envelope


def write_envelope(
    plaintext_path: str | Path,
    output_path: str | Path,
    key: bytes,
    *,
    argon2: envelope.Argon2Metadata,
    chunk_size: int = envelope.DEFAULT_CHUNK_SIZE,
) -> envelope.EnvelopeMetadata:
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key.")
    if not 64 * 1024 <= chunk_size <= 16 * 1024 * 1024:
        raise ValueError("Envelope chunk size must be between 64 KiB and 16 MiB.")
    plaintext_size = os.path.getsize(plaintext_path)
    chunk_count = max(1, math.ceil(plaintext_size / chunk_size))
    header: dict[str, Any] = {
        "chunk_count": chunk_count,
        "chunk_size": chunk_size,
        "cipher": "AES-256-GCM",
        "format_version": envelope.FORMAT_VERSION,
        "kdf": {
            "algorithm": "argon2id",
            "memory_cost_kib": argon2.memory_cost_kib,
            "parallelism": argon2.parallelism,
            "salt": base64.b64encode(argon2.salt).decode("ascii"),
            "time_cost": argon2.time_cost,
        },
        "key_check": envelope._key_check(key),
        "plaintext_size": plaintext_size,
    }
    header["header_checksum"] = envelope._header_checksum(header)
    header_bytes = envelope._canonical_json(header)
    prefix = (
        envelope.MAGIC + envelope._HEADER_LENGTH.pack(len(header_bytes)) + header_bytes
    )
    cipher = AESGCM(key)
    with open(plaintext_path, "rb") as source, open(output_path, "wb") as output:
        output.write(prefix)
        for index in range(chunk_count):
            chunk = source.read(chunk_size)
            chunk_prefix = envelope._CHUNK_PREFIX.pack(index, len(chunk))
            nonce = os.urandom(envelope.NONCE_SIZE)
            ciphertext = cipher.encrypt(nonce, chunk, prefix + chunk_prefix)
            output.write(chunk_prefix)
            output.write(nonce)
            output.write(ciphertext)
        output.flush()
        os.fsync(output.fileno())
    return envelope._parse_header(header_bytes)
