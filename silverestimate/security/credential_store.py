"""Secure storage utilities for hashed credentials."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

keyring: Any | None
KeyringError: type[Exception]
PasswordDeleteError: type[Exception]

try:
    import keyring as _keyring
    from keyring.errors import (
        KeyringError as _ImportedKeyringError,
    )
    from keyring.errors import (
        PasswordDeleteError as _ImportedPasswordDeleteError,
    )
except Exception:  # pragma: no cover - keyring missing at runtime
    keyring = None

    class _FallbackKeyringError(Exception):
        """Fallback KeyringError when keyring package is unavailable."""

    class _FallbackPasswordDeleteError(_FallbackKeyringError):
        """Fallback PasswordDeleteError when keyring package is unavailable."""

    KeyringError = _FallbackKeyringError
    PasswordDeleteError = _FallbackPasswordDeleteError
else:
    keyring = _keyring
    KeyringError = _ImportedKeyringError
    PasswordDeleteError = _ImportedPasswordDeleteError


SERVICE_NAME = "SilverEstimateApp"
_backend_status_cache: Optional["CredentialBackendStatus"] = None
_backend_status_cache_keyring_id: Optional[int] = None


class CredentialStoreError(RuntimeError):
    """Raised when secure credential operations fail."""


@dataclass(frozen=True)
class CredentialBackendStatus:
    """Runtime status of the configured keyring backend."""

    available: bool
    backend_name: str
    reason: str = ""


@dataclass(frozen=True)
class _CredentialDescriptor:
    kind: str
    secure_id: str
    legacy_key: str


_ENTRIES = {
    "main": _CredentialDescriptor(
        kind="main", secure_id="main_password_hash", legacy_key="security/password_hash"
    ),
    "backup": _CredentialDescriptor(
        kind="backup",
        secure_id="backup_password_hash",
        legacy_key="security/backup_hash",
    ),
}


def get_backend_status() -> CredentialBackendStatus:
    """Report whether a secure keyring backend is usable."""
    global _backend_status_cache, _backend_status_cache_keyring_id
    current_keyring_id = id(keyring)
    if (
        _backend_status_cache is not None
        and _backend_status_cache_keyring_id == current_keyring_id
    ):
        return _backend_status_cache

    if keyring is None:
        status = CredentialBackendStatus(
            available=False,
            backend_name="missing",
            reason="Python keyring package is not installed.",
        )
        _backend_status_cache = status
        _backend_status_cache_keyring_id = current_keyring_id
        return status
    try:
        backend = keyring.get_keyring()
    except Exception as exc:  # pragma: no cover - backend init differs by platform
        status = CredentialBackendStatus(
            available=False,
            backend_name="unknown",
            reason=f"Could not initialize keyring backend: {exc}",
        )
        _backend_status_cache = status
        _backend_status_cache_keyring_id = current_keyring_id
        return status
    backend_type = type(backend)
    backend_name = f"{backend_type.__module__}.{backend_type.__name__}"
    normalized = backend_name.lower()
    if "null" in normalized or "fail" in normalized:
        status = CredentialBackendStatus(
            available=False,
            backend_name=backend_name,
            reason=(
                "Keyring backend is not secure (null/fail backend active). "
                "Install and configure an OS-backed credential vault."
            ),
        )
        _backend_status_cache = status
        _backend_status_cache_keyring_id = current_keyring_id
        return status
    status = CredentialBackendStatus(
        available=True,
        backend_name=backend_name,
    )
    _backend_status_cache = status
    _backend_status_cache_keyring_id = current_keyring_id
    return status


def _get_entry(kind: str) -> _CredentialDescriptor:
    try:
        return _ENTRIES[kind]
    except KeyError as exc:  # pragma: no cover - developer error
        raise ValueError(f"Unknown credential kind: {kind}") from exc


def _ensure_keyring() -> Any:
    status = get_backend_status()
    if not status.available:
        raise CredentialStoreError(
            f"Secure keyring backend unavailable ({status.backend_name}). {status.reason}"
        )
    return keyring


def get_password_hash(
    kind: str,
    *,
    settings: Optional[Any] = None,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Retrieve the hashed password for ``kind`` from the secure store.

    When a legacy value exists in QSettings, it is migrated to the secure store automatically.
    """
    descriptor = _get_entry(kind)
    kr = _ensure_keyring()
    try:
        value = kr.get_password(SERVICE_NAME, descriptor.secure_id)
    except KeyringError as exc:
        raise CredentialStoreError(
            f"Failed to read credential '{kind}': {exc}"
        ) from exc

    if value:
        return str(value)

    if not settings:
        return None

    legacy_value_raw = settings.value(descriptor.legacy_key)
    legacy_value = str(legacy_value_raw) if legacy_value_raw else None
    if legacy_value:
        try:
            kr.set_password(SERVICE_NAME, descriptor.secure_id, legacy_value)
        except KeyringError as exc:
            if logger:
                logger.warning(
                    "Failed to migrate legacy credential '%s': %s",
                    kind,
                    exc,
                    exc_info=True,
                )
        else:
            settings.remove(descriptor.legacy_key)
            settings.sync()
            if logger:
                logger.info("Migrated legacy credential '%s' into secure store", kind)
            return legacy_value

    return None


def set_password_hash(
    kind: str,
    value: str,
    *,
    settings: Optional[Any] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Persist ``value`` for ``kind`` in the secure store, removing legacy storage when present."""
    descriptor = _get_entry(kind)
    kr = _ensure_keyring()
    try:
        kr.set_password(SERVICE_NAME, descriptor.secure_id, value)
    except KeyringError as exc:
        raise CredentialStoreError(
            f"Failed to store credential '{kind}': {exc}"
        ) from exc

    if settings:
        settings.remove(descriptor.legacy_key)
        settings.sync()
    if logger:
        logger.debug("Stored credential '%s' in secure store", kind)


def delete_password_hash(
    kind: str,
    *,
    settings: Optional[Any] = None,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Remove ``kind`` from both secure and legacy stores."""
    descriptor = _get_entry(kind)
    if settings:
        settings.remove(descriptor.legacy_key)
        settings.sync()
    if keyring is None:
        if logger:
            logger.debug(
                "Keyring unavailable while deleting credential '%s'; legacy key removed only",
                kind,
            )
        return

    try:
        keyring.delete_password(SERVICE_NAME, descriptor.secure_id)
    except PasswordDeleteError:
        if logger:
            logger.debug(
                "Credential '%s' not present in secure store during delete", kind
            )
    except KeyringError as exc:
        if logger:
            logger.warning(
                "Failed to delete credential '%s' from secure store: %s",
                kind,
                exc,
                exc_info=True,
            )
        raise CredentialStoreError(
            f"Failed to delete credential '{kind}': {exc}"
        ) from exc
