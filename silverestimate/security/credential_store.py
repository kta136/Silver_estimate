"""Secure storage utilities for hashed credentials."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError
except Exception:  # pragma: no cover - keyring missing at runtime
    keyring = None  # type: ignore[assignment]

    class KeyringError(Exception):
        """Fallback KeyringError when keyring package is unavailable."""

    class PasswordDeleteError(KeyringError):
        """Fallback PasswordDeleteError when keyring package is unavailable."""


SERVICE_NAME = "SilverEstimateApp"


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


def is_available() -> bool:
    """Return True when the runtime has access to a keyring backend."""
    return get_backend_status().available


def get_backend_status() -> CredentialBackendStatus:
    """Report whether a secure keyring backend is usable."""
    if keyring is None:
        return CredentialBackendStatus(
            available=False,
            backend_name="missing",
            reason="Python keyring package is not installed.",
        )
    try:
        backend = keyring.get_keyring()
    except Exception as exc:  # pragma: no cover - backend init differs by platform
        return CredentialBackendStatus(
            available=False,
            backend_name="unknown",
            reason=f"Could not initialize keyring backend: {exc}",
        )
    backend_type = type(backend)
    backend_name = f"{backend_type.__module__}.{backend_type.__name__}"
    normalized = backend_name.lower()
    if "null" in normalized or "fail" in normalized:
        return CredentialBackendStatus(
            available=False,
            backend_name=backend_name,
            reason=(
                "Keyring backend is not secure (null/fail backend active). "
                "Install and configure an OS-backed credential vault."
            ),
        )
    return CredentialBackendStatus(
        available=True,
        backend_name=backend_name,
    )


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
        return value

    if not settings:
        return None

    legacy_value = settings.value(descriptor.legacy_key)
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
