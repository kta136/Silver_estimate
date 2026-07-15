"""Versioned, chunked AES-GCM envelope for encrypted SQLite snapshots."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"SILVDB01"
MAGIC_PREFIX = b"SILVDB"
FORMAT_VERSION = 1
DEFAULT_CHUNK_SIZE = 1024 * 1024
NONCE_SIZE = 12
TAG_SIZE = 16
MAX_HEADER_SIZE = 64 * 1024
_HEADER_LENGTH = struct.Struct(">I")
_CHUNK_PREFIX = struct.Struct(">QI")
_KEY_CHECK_CONTEXT = b"SILVDB01 key verification"


class EnvelopeError(RuntimeError):
    """Base class for current-envelope failures."""


class EnvelopeTruncatedError(EnvelopeError):
    """The envelope ended before all declared bytes were present."""


class EnvelopeReorderedError(EnvelopeError):
    """A chunk appeared out of sequence."""


class EnvelopeDuplicateChunkError(EnvelopeError):
    """A chunk index appeared more than once."""


class EnvelopeTrailingDataError(EnvelopeError):
    """Bytes followed the final declared chunk."""


class EnvelopeUnsupportedError(EnvelopeError):
    """The envelope version, KDF, or cipher is unsupported."""


class EnvelopeCorruptError(EnvelopeError):
    """Authenticated metadata or ciphertext was corrupted."""


class EnvelopeWrongPasswordError(EnvelopeError):
    """The supplied password-derived key does not match the envelope."""


@dataclass(frozen=True)
class Argon2Metadata:
    salt: bytes
    time_cost: int
    memory_cost_kib: int
    parallelism: int


@dataclass(frozen=True)
class EnvelopeMetadata:
    plaintext_size: int
    chunk_size: int
    chunk_count: int
    argon2: Argon2Metadata
    header_bytes: bytes


def is_current_envelope(path: str | os.PathLike[str]) -> bool:
    try:
        with open(path, "rb") as source:
            return source.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")


def _header_checksum(header_without_checksum: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(header_without_checksum)).hexdigest()


def _key_check(key: bytes) -> str:
    return hmac.new(key, _KEY_CHECK_CONTEXT, hashlib.sha256).hexdigest()


def _read_exact(source: BinaryIO, length: int, label: str) -> bytes:
    data = source.read(length)
    if len(data) != length:
        raise EnvelopeTruncatedError(f"Envelope truncated while reading {label}.")
    return data


def _parse_header(header_bytes: bytes) -> EnvelopeMetadata:
    try:
        header = json.loads(header_bytes.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EnvelopeCorruptError("Envelope header is not canonical JSON.") from exc
    if not isinstance(header, dict):
        raise EnvelopeCorruptError("Envelope header must be a JSON object.")
    checksum = header.get("header_checksum")
    if not isinstance(checksum, str):
        raise EnvelopeCorruptError("Envelope header checksum is missing.")
    without_checksum = dict(header)
    without_checksum.pop("header_checksum", None)
    if not hmac.compare_digest(checksum, _header_checksum(without_checksum)):
        raise EnvelopeCorruptError("Envelope header checksum does not match.")

    if header.get("format_version") != FORMAT_VERSION:
        raise EnvelopeUnsupportedError(
            f"Unsupported encrypted envelope version: {header.get('format_version')!r}."
        )
    if header.get("cipher") != "AES-256-GCM":
        raise EnvelopeUnsupportedError(
            f"Unsupported encrypted envelope cipher: {header.get('cipher')!r}."
        )
    kdf = header.get("kdf")
    if not isinstance(kdf, dict) or kdf.get("algorithm") != "argon2id":
        raise EnvelopeUnsupportedError("Only Argon2id envelopes are supported.")
    try:
        salt = base64.b64decode(str(kdf["salt"]), validate=True)
        time_cost = int(kdf["time_cost"])
        memory_cost_kib = int(kdf["memory_cost_kib"])
        parallelism = int(kdf["parallelism"])
        plaintext_size = int(header["plaintext_size"])
        chunk_size = int(header["chunk_size"])
        chunk_count = int(header["chunk_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise EnvelopeCorruptError(
            "Envelope metadata has invalid field types."
        ) from exc
    if len(salt) < 16:
        raise EnvelopeCorruptError("Envelope Argon2id salt is too short.")
    if min(time_cost, memory_cost_kib, parallelism) <= 0:
        raise EnvelopeCorruptError("Envelope Argon2id parameters must be positive.")
    if plaintext_size < 0 or not 64 * 1024 <= chunk_size <= 16 * 1024 * 1024:
        raise EnvelopeCorruptError("Envelope size metadata is invalid.")
    expected_chunks = max(1, math.ceil(plaintext_size / chunk_size))
    if chunk_count != expected_chunks:
        raise EnvelopeCorruptError(
            "Envelope chunk count does not match plaintext size."
        )

    canonical = _canonical_json(header)
    if canonical != header_bytes:
        raise EnvelopeCorruptError("Envelope header is not canonically encoded.")
    return EnvelopeMetadata(
        plaintext_size=plaintext_size,
        chunk_size=chunk_size,
        chunk_count=chunk_count,
        argon2=Argon2Metadata(
            salt=salt,
            time_cost=time_cost,
            memory_cost_kib=memory_cost_kib,
            parallelism=parallelism,
        ),
        header_bytes=header_bytes,
    )


def read_envelope_metadata(
    path: str | os.PathLike[str],
) -> EnvelopeMetadata | None:
    """Read public KDF/size metadata, or return ``None`` for a legacy payload."""
    with open(path, "rb") as source:
        magic = source.read(len(MAGIC))
        if magic != MAGIC:
            if magic.startswith(MAGIC_PREFIX):
                raise EnvelopeUnsupportedError(
                    f"Unsupported encrypted envelope magic: {magic!r}."
                )
            return None
        header_length = _HEADER_LENGTH.unpack(
            _read_exact(source, _HEADER_LENGTH.size, "header length")
        )[0]
        if not 0 < header_length <= MAX_HEADER_SIZE:
            raise EnvelopeCorruptError("Envelope header length is invalid.")
        return _parse_header(_read_exact(source, header_length, "header"))


def write_envelope(
    plaintext_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    key: bytes,
    *,
    argon2: Argon2Metadata,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> EnvelopeMetadata:
    """Stream ``plaintext_path`` into an authenticated current envelope."""
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
        "format_version": FORMAT_VERSION,
        "kdf": {
            "algorithm": "argon2id",
            "memory_cost_kib": argon2.memory_cost_kib,
            "parallelism": argon2.parallelism,
            "salt": base64.b64encode(argon2.salt).decode("ascii"),
            "time_cost": argon2.time_cost,
        },
        "key_check": _key_check(key),
        "plaintext_size": plaintext_size,
    }
    header["header_checksum"] = _header_checksum(header)
    header_bytes = _canonical_json(header)
    if len(header_bytes) > MAX_HEADER_SIZE:
        raise ValueError("Envelope header exceeds the maximum supported size.")
    prefix = MAGIC + _HEADER_LENGTH.pack(len(header_bytes)) + header_bytes
    aesgcm = AESGCM(key)

    with open(plaintext_path, "rb") as source, open(output_path, "wb") as output:
        output.write(prefix)
        for index in range(chunk_count):
            chunk = source.read(chunk_size)
            if index < chunk_count - 1 and len(chunk) != chunk_size:
                raise OSError("Plaintext snapshot changed while it was encrypted.")
            chunk_prefix = _CHUNK_PREFIX.pack(index, len(chunk))
            nonce = os.urandom(NONCE_SIZE)
            ciphertext = aesgcm.encrypt(nonce, chunk, prefix + chunk_prefix)
            output.write(chunk_prefix)
            output.write(nonce)
            output.write(ciphertext)
        if source.read(1):
            raise OSError("Plaintext snapshot grew while it was encrypted.")
        output.flush()
        os.fsync(output.fileno())
    return _parse_header(header_bytes)


def decrypt_envelope_to_path(
    encrypted_path: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    key: bytes,
) -> EnvelopeMetadata:
    """Authenticate and stream a current envelope into ``output_path``."""
    if len(key) != 32:
        raise EnvelopeWrongPasswordError("Password-derived key has invalid length.")
    encrypted_path = str(encrypted_path)
    output_path = str(output_path)
    partial_path = f"{output_path}.decrypting"
    try:
        with open(encrypted_path, "rb") as source:
            magic = _read_exact(source, len(MAGIC), "magic")
            if magic != MAGIC:
                if magic.startswith(MAGIC_PREFIX):
                    raise EnvelopeUnsupportedError(
                        f"Unsupported encrypted envelope magic: {magic!r}."
                    )
                raise EnvelopeUnsupportedError("Payload is not a current envelope.")
            header_length_bytes = _read_exact(
                source, _HEADER_LENGTH.size, "header length"
            )
            header_length = _HEADER_LENGTH.unpack(header_length_bytes)[0]
            if not 0 < header_length <= MAX_HEADER_SIZE:
                raise EnvelopeCorruptError("Envelope header length is invalid.")
            header_bytes = _read_exact(source, header_length, "header")
            metadata = _parse_header(header_bytes)
            header = json.loads(header_bytes.decode("ascii"))
            if not hmac.compare_digest(
                str(header.get("key_check", "")), _key_check(key)
            ):
                raise EnvelopeWrongPasswordError(
                    "Password does not match the encrypted database."
                )

            prefix = magic + header_length_bytes + header_bytes
            aesgcm = AESGCM(key)
            written = 0
            seen: set[int] = set()
            with open(partial_path, "wb") as output:
                for expected_index in range(metadata.chunk_count):
                    chunk_prefix = _read_exact(
                        source, _CHUNK_PREFIX.size, "chunk prefix"
                    )
                    index, chunk_length = _CHUNK_PREFIX.unpack(chunk_prefix)
                    if index in seen:
                        raise EnvelopeDuplicateChunkError(
                            f"Duplicate encrypted chunk index {index}."
                        )
                    if index != expected_index:
                        raise EnvelopeReorderedError(
                            f"Expected encrypted chunk {expected_index}, found {index}."
                        )
                    seen.add(index)
                    remaining = metadata.plaintext_size - written
                    expected_length = min(metadata.chunk_size, max(0, remaining))
                    if chunk_length != expected_length:
                        raise EnvelopeCorruptError(
                            f"Encrypted chunk {index} length does not match metadata."
                        )
                    nonce = _read_exact(source, NONCE_SIZE, "chunk nonce")
                    ciphertext = _read_exact(
                        source,
                        chunk_length + TAG_SIZE,
                        "chunk ciphertext",
                    )
                    try:
                        plaintext = aesgcm.decrypt(
                            nonce,
                            ciphertext,
                            prefix + chunk_prefix,
                        )
                    except InvalidTag as exc:
                        raise EnvelopeCorruptError(
                            f"Encrypted chunk {index} authentication failed."
                        ) from exc
                    output.write(plaintext)
                    written += len(plaintext)
                if source.read(1):
                    raise EnvelopeTrailingDataError(
                        "Encrypted envelope contains trailing data."
                    )
                if written != metadata.plaintext_size:
                    raise EnvelopeTruncatedError(
                        "Decrypted size does not match envelope metadata."
                    )
                output.flush()
                os.fsync(output.fileno())
        os.replace(partial_path, output_path)
        return metadata
    except Exception:
        try:
            Path(partial_path).unlink(missing_ok=True)
        except OSError:
            pass
        raise


__all__ = [
    "Argon2Metadata",
    "DEFAULT_CHUNK_SIZE",
    "EnvelopeCorruptError",
    "EnvelopeDuplicateChunkError",
    "EnvelopeError",
    "EnvelopeMetadata",
    "EnvelopeReorderedError",
    "EnvelopeTrailingDataError",
    "EnvelopeTruncatedError",
    "EnvelopeUnsupportedError",
    "EnvelopeWrongPasswordError",
    "MAGIC",
    "decrypt_envelope_to_path",
    "is_current_envelope",
    "read_envelope_metadata",
    "write_envelope",
]
