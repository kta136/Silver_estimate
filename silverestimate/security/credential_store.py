"""Windows Credential Manager storage for password hashes and device binding."""

from __future__ import annotations

import base64
import logging
import secrets
from dataclasses import dataclass
from typing import Optional

from silverestimate.security.windows_vault import (
    LOCAL_MACHINE,
    ROAMING,
    Vault,
    VaultEntry,
    load_vault,
)

vault: Vault | None = load_vault()
# The vault and service name whose entries this process has already checked.
_checked: tuple[Vault, str] | None = None

SERVICE_NAME = "SilverEstimateApp"
BACKEND_NAME = "Windows Credential Manager"
DEVICE_BINDING_BYTES = 32
DEVICE_BINDING_VERSION = "v1"

_TIDY_ATTEMPTS = 6
# Recorded in the vault once its entries are known to be stored one way only.
_LAYOUT = "2"


class CredentialStoreError(RuntimeError):
    """Raised when secure credential operations fail."""


@dataclass(frozen=True)
class CredentialBackendStatus:
    """Runtime status of the credential vault."""

    available: bool
    backend_name: str
    reason: str = ""


SUPPORTED_CREDENTIAL_KINDS = (
    "main",
    "backup",
    "pending_main",
    "pending_backup",
    "recovery_main",
    "recovery_backup",
    "device_binding",
)

_ENTRIES = {
    "main": "main_password_hash",
    "backup": "backup_password_hash",
    "pending_main": "pending_main_password_hash",
    "pending_backup": "pending_backup_password_hash",
    "recovery_main": "recovery_main_password_hash",
    "recovery_backup": "recovery_backup_password_hash",
    "device_binding": "database_device_binding_v1",
}


def get_backend_status() -> CredentialBackendStatus:
    """Report whether Windows Credential Manager is usable."""
    if vault is None:
        return CredentialBackendStatus(
            available=False,
            backend_name="missing",
            reason="Windows Credential Manager is not available on this system.",
        )
    try:
        vault.read(SERVICE_NAME)
    except OSError as exc:
        return CredentialBackendStatus(
            available=False,
            backend_name=BACKEND_NAME,
            reason=f"Windows Credential Manager did not respond: {exc}",
        )
    return CredentialBackendStatus(available=True, backend_name=BACKEND_NAME)


def _get_secure_id(kind: str) -> str:
    try:
        return _ENTRIES[kind]
    except KeyError as exc:  # pragma: no cover - developer error
        raise ValueError(f"Unknown credential kind: {kind}") from exc


# Every entry is one local-machine credential named "<entry>@<service>". The
# keyring package used those names too, so its versions of the app still read
# them, but it also kept the entry written last under the bare service name and
# wrote hashes to the roaming store. `_tidy` undoes that.
def _entry_target(entry: str) -> str:
    return f"{entry}@{SERVICE_NAME}"


def _open_vault() -> Vault:
    """Return the vault with every entry stored once under its own name."""
    if vault is None:
        status = get_backend_status()
        raise CredentialStoreError(
            f"Secure credential storage unavailable ({status.backend_name}). "
            f"{status.reason}"
        )
    global _checked
    if _checked != (vault, SERVICE_NAME):
        # Checking every copy takes about a fifth of a second, so it is done
        # once per installation and recorded.
        layout = vault.read(_entry_target("layout"))
        if layout is None or layout.secret != _LAYOUT:
            _tidy(vault)
            vault.write(_entry_target("layout"), "layout", _LAYOUT, LOCAL_MACHINE)
        _checked = (vault, SERVICE_NAME)
    # An older version of the app that ran since always leaves this name.
    if vault.read(SERVICE_NAME) is not None:
        _tidy(vault)
    return vault


def _stored_in(store: Vault, persist: int, targets: list[str]) -> dict[str, VaultEntry]:
    """Return the copies of ``targets`` held in one of Windows' two stores."""
    check = _entry_target("layout-check")
    for _attempt in range(_TIDY_ATTEMPTS):
        # Any write brings that store's copies into view for every name.
        store.write(check, "", "", persist)
        found = {target: store.read(target) for target in targets}
        seen = store.read(check)
        # Another program writing to the other store would have switched the view.
        if seen is not None and seen.persist == persist:
            return {
                target: entry
                for target, entry in found.items()
                if entry is not None and entry.persist == persist
            }
    raise CredentialStoreError(
        "Windows Credential Manager kept changing while it was being read."
    )


def _all_copies(
    store: Vault, targets: list[str]
) -> tuple[dict[str, VaultEntry], dict[str, VaultEntry]]:
    """Return the local-machine and roaming copies, read twice and found equal."""
    for _attempt in range(_TIDY_ATTEMPTS):
        readings = [
            (
                _stored_in(store, LOCAL_MACHINE, targets),
                _stored_in(store, ROAMING, targets),
            )
            for _reading in range(2)
        ]
        if readings[0] == readings[1]:
            return readings[0]
    raise CredentialStoreError(
        "Windows Credential Manager kept changing while it was being read."
    )


def _drop(store: Vault, target: str, persist: int, user: str, secret: str) -> None:
    """Remove one store's copy of ``target``; a delete takes the copy written last."""
    store.write(target, user, secret, persist)
    store.delete(target)


def _tidy(store: Vault) -> None:
    """Leave one local-machine copy of each entry and nothing under the bare name.

    Windows shows whichever copy of a name sits in the store written to last
    by any program, so the older layout could return a superseded hash, and a
    delete could leave a copy behind. Nothing is removed until every current
    value has been read back from its own local-machine entry, and only copies
    that were read are replaced or removed.
    """
    check = _entry_target("layout-check")
    targets = [SERVICE_NAME, *(_entry_target(entry) for entry in _ENTRIES.values())]
    # The check entry needs a copy in both stores to reveal a switched view.
    store.write(check, "", "", ROAMING)
    for _attempt in range(_TIDY_ATTEMPTS):
        local, roaming = _all_copies(store, targets)
        current = _newest_values(local, roaming)
        entries_tidy = all(
            _entry_target(entry) not in roaming
            and current.get(entry) == _secret(local, entry)
            for entry in _ENTRIES.values()
        )
        if entries_tidy:
            # A third pass clears the check entry even if another program
            # wrote between one of these writes and its delete.
            for persist in (LOCAL_MACHINE, ROAMING, LOCAL_MACHINE):
                _drop(store, check, persist, "", "")
            # Last, so an interrupted tidy still finds this name and resumes.
            if SERVICE_NAME in roaming:
                _drop(store, SERVICE_NAME, ROAMING, "", "")
            if SERVICE_NAME in local:
                _drop(store, SERVICE_NAME, LOCAL_MACHINE, "", "")
            return
        for entry in _ENTRIES.values():
            _keep_one_local_copy(store, entry, current.get(entry), local, roaming)
    raise CredentialStoreError(
        "Stored credentials could not be tidied; nothing still needed was removed."
    )


def _secret(copies: dict[str, VaultEntry], entry: str) -> str | None:
    copy = copies.get(_entry_target(entry))
    return copy.secret if copy is not None and copy.user_name == entry else None


def _newest_values(*stores: dict[str, VaultEntry]) -> dict[str, str]:
    """Return each entry's most recently written value across every copy."""
    newest: dict[str, VaultEntry] = {}
    for copies in stores:
        for target, copy in copies.items():
            entry = copy.user_name
            if entry not in _ENTRIES.values():
                continue
            if target not in (SERVICE_NAME, _entry_target(entry)):
                continue
            if entry not in newest or copy.last_written > newest[entry].last_written:
                newest[entry] = copy
    return {entry: copy.secret for entry, copy in newest.items()}


def _keep_one_local_copy(
    store: Vault,
    entry: str,
    secret: str | None,
    local: dict[str, VaultEntry],
    roaming: dict[str, VaultEntry],
) -> None:
    target = _entry_target(entry)
    # The current value goes into the local store before anything is removed.
    # A copy that already holds it is left alone, so only a value known to be
    # the newest ever gets a fresh write time.
    if secret is not None and _secret(local, entry) != secret:
        store.write(target, entry, secret, LOCAL_MACHINE)
    if target in roaming:
        if secret is None:
            _drop(store, target, ROAMING, "", "")
            return
        _drop(store, target, ROAMING, entry, secret)
        store.write(target, entry, secret, LOCAL_MACHINE)


def get_password_hash(kind: str) -> Optional[str]:
    """Retrieve a credential value for ``kind`` from the secure store."""
    secure_id = _get_secure_id(kind)
    try:
        store = _open_vault()
        entry = store.read(_entry_target(secure_id))
        if entry is not None and entry.persist != LOCAL_MACHINE:
            # A roaming copy is in view, so an older layout left its mark.
            _tidy(store)
            entry = store.read(_entry_target(secure_id))
    except (OSError, UnicodeDecodeError) as exc:
        raise CredentialStoreError(
            f"Failed to read credential '{kind}': {exc}"
        ) from exc

    if entry is None or entry.user_name != secure_id:
        return None
    return entry.secret or None


def set_password_hash(
    kind: str,
    value: str,
    *,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Persist ``value`` for ``kind`` in the secure store."""
    secure_id = _get_secure_id(kind)
    try:
        _open_vault().write(_entry_target(secure_id), secure_id, value, LOCAL_MACHINE)
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as exc:
        raise CredentialStoreError(
            f"Failed to store credential '{kind}': {exc}"
        ) from exc

    if logger:
        logger.debug("Stored credential '%s' in secure store", kind)


def delete_password_hash(
    kind: str,
    *,
    logger: Optional[logging.Logger] = None,
) -> None:
    """Remove ``kind`` from the secure store."""
    secure_id = _get_secure_id(kind)
    if vault is None:
        if logger:
            logger.debug(
                "Credential vault unavailable while deleting credential '%s'", kind
            )
        return

    try:
        store = _open_vault()
        target = _entry_target(secure_id)
        deleted = store.read(target) is not None
        # Clear both stores, so no copy from an older layout can come back.
        _drop(store, target, ROAMING, "", "")
        _drop(store, target, LOCAL_MACHINE, "", "")
    except (OSError, UnicodeDecodeError) as exc:
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

    if not deleted and logger:
        logger.debug("Credential '%s' not present in secure store during delete", kind)


def get_device_binding_secret() -> bytes | None:
    """Return the installation's device-bound database secret, if registered."""
    encoded = get_password_hash("device_binding")
    if encoded is None:
        return None
    prefix = f"{DEVICE_BINDING_VERSION}:"
    if not encoded.startswith(prefix):
        raise CredentialStoreError("Device-binding credential has an unknown version")
    try:
        secret = base64.b64decode(encoded[len(prefix) :], validate=True)
    except (ValueError, TypeError) as exc:
        raise CredentialStoreError("Device-binding credential is malformed") from exc
    if len(secret) != DEVICE_BINDING_BYTES:
        raise CredentialStoreError("Device-binding credential has an invalid length")
    return secret


def create_device_binding_secret(
    *,
    logger: Optional[logging.Logger] = None,
) -> bytes:
    """Create or reassert the device secret using local-machine persistence."""
    existing = get_device_binding_secret()
    if existing is not None:
        encoded = (
            f"{DEVICE_BINDING_VERSION}:{base64.b64encode(existing).decode('ascii')}"
        )
        set_password_hash("device_binding", encoded, logger=logger)
        return existing
    secret = secrets.token_bytes(DEVICE_BINDING_BYTES)
    encoded = f"{DEVICE_BINDING_VERSION}:{base64.b64encode(secret).decode('ascii')}"
    set_password_hash("device_binding", encoded, logger=logger)
    return secret
