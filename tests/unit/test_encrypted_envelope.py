import os
import struct

import pytest

from silverestimate.security import encrypted_envelope as envelope
from silverestimate.security.encrypted_envelope import (
    MAGIC,
    Argon2Metadata,
    EnvelopeCorruptError,
    EnvelopeDuplicateChunkError,
    EnvelopeReorderedError,
    EnvelopeTrailingDataError,
    EnvelopeTruncatedError,
    EnvelopeUnsupportedError,
    EnvelopeWrongPasswordError,
    decrypt_envelope_to_path,
    read_envelope_metadata,
    write_envelope,
)

KEY = b"k" * 32
OTHER_KEY = b"x" * 32
ARGON2 = Argon2Metadata(
    salt=b"s" * 16,
    time_cost=3,
    memory_cost_kib=64 * 1024,
    parallelism=4,
)
CHUNK_SIZE = 64 * 1024


def _write_fixture(tmp_path, payload: bytes):
    plain = tmp_path / "plain.sqlite"
    encrypted = tmp_path / "database.enc"
    restored = tmp_path / "restored.sqlite"
    plain.write_bytes(payload)
    metadata = write_envelope(
        plain,
        encrypted,
        KEY,
        argon2=ARGON2,
        chunk_size=CHUNK_SIZE,
    )
    return encrypted, restored, metadata


def _split_envelope(payload: bytes):
    header_length = struct.unpack(">I", payload[len(MAGIC) : len(MAGIC) + 4])[0]
    offset = len(MAGIC) + 4 + header_length
    prefix = payload[:offset]
    records = []
    while offset < len(payload):
        chunk_length = struct.unpack(">I", payload[offset + 8 : offset + 12])[0]
        record_length = 12 + 12 + chunk_length + 16
        records.append(payload[offset : offset + record_length])
        offset += record_length
    return prefix, records


def test_round_trip_streams_multiple_chunks_and_exposes_kdf_metadata(tmp_path):
    payload = os.urandom(CHUNK_SIZE * 2 + 123)
    encrypted, restored, written = _write_fixture(tmp_path, payload)

    public = read_envelope_metadata(encrypted)
    decrypted = decrypt_envelope_to_path(encrypted, restored, KEY)

    assert encrypted.read_bytes().startswith(MAGIC)
    assert restored.read_bytes() == payload
    assert written.plaintext_size == len(payload)
    assert written.chunk_count == 3
    assert public == decrypted == written
    assert public.argon2 == ARGON2


def test_empty_plaintext_still_authenticates_header(tmp_path):
    encrypted, restored, metadata = _write_fixture(tmp_path, b"")

    decrypt_envelope_to_path(encrypted, restored, KEY)

    assert restored.read_bytes() == b""
    assert metadata.chunk_count == 1


def test_wrong_password_is_distinct_from_corruption(tmp_path):
    encrypted, restored, _metadata = _write_fixture(tmp_path, b"sqlite payload")

    with pytest.raises(EnvelopeWrongPasswordError):
        decrypt_envelope_to_path(encrypted, restored, OTHER_KEY)

    payload = bytearray(encrypted.read_bytes())
    payload[-1] ^= 0x01
    encrypted.write_bytes(payload)
    with pytest.raises(EnvelopeCorruptError, match="authentication failed"):
        decrypt_envelope_to_path(encrypted, restored, KEY)


def test_truncated_and_trailing_data_are_rejected(tmp_path):
    encrypted, restored, _metadata = _write_fixture(tmp_path, os.urandom(100_000))
    payload = encrypted.read_bytes()

    encrypted.write_bytes(payload[:-10])
    with pytest.raises(EnvelopeTruncatedError):
        decrypt_envelope_to_path(encrypted, restored, KEY)

    encrypted.write_bytes(payload + b"unexpected")
    with pytest.raises(EnvelopeTrailingDataError):
        decrypt_envelope_to_path(encrypted, restored, KEY)


def test_reordered_and_duplicate_chunks_are_rejected(tmp_path):
    encrypted, restored, _metadata = _write_fixture(
        tmp_path, os.urandom(CHUNK_SIZE * 2)
    )
    prefix, records = _split_envelope(encrypted.read_bytes())
    assert len(records) == 2

    encrypted.write_bytes(prefix + records[1] + records[0])
    with pytest.raises(EnvelopeReorderedError):
        decrypt_envelope_to_path(encrypted, restored, KEY)

    encrypted.write_bytes(prefix + records[0] + records[0])
    with pytest.raises(EnvelopeDuplicateChunkError):
        decrypt_envelope_to_path(encrypted, restored, KEY)


def test_unknown_silvdb_magic_is_unsupported(tmp_path):
    encrypted, restored, _metadata = _write_fixture(tmp_path, b"sqlite payload")
    payload = encrypted.read_bytes()
    encrypted.write_bytes(b"SILVDB02" + payload[len(MAGIC) :])

    with pytest.raises(EnvelopeUnsupportedError):
        read_envelope_metadata(encrypted)
    with pytest.raises(EnvelopeUnsupportedError):
        decrypt_envelope_to_path(encrypted, restored, KEY)


def _header_bytes(**updates):
    header = {
        "chunk_count": 1,
        "chunk_size": CHUNK_SIZE,
        "cipher": "AES-256-GCM",
        "format_version": 1,
        "kdf": {
            "algorithm": "argon2id",
            "memory_cost_kib": ARGON2.memory_cost_kib,
            "parallelism": ARGON2.parallelism,
            "salt": "c3Nzc3Nzc3Nzc3Nzc3Nzcw==",
            "time_cost": ARGON2.time_cost,
        },
        "key_check": "unused",
        "plaintext_size": 1,
    }
    header.update(updates)
    header["header_checksum"] = envelope._header_checksum(header)
    return envelope._canonical_json(header)


@pytest.mark.parametrize(
    ("header_bytes", "error", "message"),
    [
        (b"\xff", EnvelopeCorruptError, "canonical JSON"),
        (b"[]", EnvelopeCorruptError, "JSON object"),
        (b"{}", EnvelopeCorruptError, "checksum is missing"),
        (
            envelope._canonical_json({"header_checksum": "bad"}),
            EnvelopeCorruptError,
            "checksum does not match",
        ),
        (_header_bytes(format_version=99), EnvelopeUnsupportedError, "version"),
        (_header_bytes(cipher="other"), EnvelopeUnsupportedError, "cipher"),
        (
            _header_bytes(kdf={"algorithm": "pbkdf2"}),
            EnvelopeUnsupportedError,
            "Argon2id",
        ),
        (_header_bytes(plaintext_size="bad"), EnvelopeCorruptError, "field types"),
        (
            _header_bytes(
                kdf={
                    "algorithm": "argon2id",
                    "memory_cost_kib": 1,
                    "parallelism": 1,
                    "salt": "c2hvcnQ=",
                    "time_cost": 1,
                }
            ),
            EnvelopeCorruptError,
            "salt is too short",
        ),
        (
            _header_bytes(
                kdf={
                    "algorithm": "argon2id",
                    "memory_cost_kib": 1,
                    "parallelism": 0,
                    "salt": "c3Nzc3Nzc3Nzc3Nzc3Nzcw==",
                    "time_cost": 1,
                }
            ),
            EnvelopeCorruptError,
            "parameters must be positive",
        ),
        (_header_bytes(chunk_size=1), EnvelopeCorruptError, "size metadata"),
        (_header_bytes(chunk_count=2), EnvelopeCorruptError, "chunk count"),
        (_header_bytes() + b" ", EnvelopeCorruptError, "canonically encoded"),
    ],
)
def test_header_metadata_validation_is_specific(header_bytes, error, message):
    with pytest.raises(error, match=message):
        envelope._parse_header(header_bytes)


def test_envelope_file_detection_and_argument_validation(tmp_path):
    unsupported = tmp_path / "unsupported.enc"
    unsupported.write_bytes(b"unsupported")
    encrypted, restored, _metadata = _write_fixture(tmp_path, b"payload")

    with pytest.raises(EnvelopeUnsupportedError, match="magic"):
        read_envelope_metadata(unsupported)

    with pytest.raises(ValueError, match="32-byte"):
        write_envelope(unsupported, encrypted, b"short", argon2=ARGON2)
    with pytest.raises(ValueError, match="chunk size"):
        write_envelope(unsupported, encrypted, KEY, argon2=ARGON2, chunk_size=1)
    with pytest.raises(EnvelopeWrongPasswordError, match="invalid length"):
        decrypt_envelope_to_path(encrypted, restored, b"short")

    unsupported.write_bytes(b"not-current-envelope")
    with pytest.raises(EnvelopeUnsupportedError, match="not a current"):
        decrypt_envelope_to_path(unsupported, restored, KEY)


def test_zero_header_length_is_rejected_by_metadata_and_decrypt(tmp_path):
    encrypted = tmp_path / "bad-header.enc"
    restored = tmp_path / "restored.sqlite"
    encrypted.write_bytes(MAGIC + struct.pack(">I", 0))

    with pytest.raises(EnvelopeCorruptError, match="header length"):
        read_envelope_metadata(encrypted)
    with pytest.raises(EnvelopeCorruptError, match="header length"):
        decrypt_envelope_to_path(encrypted, restored, KEY)
