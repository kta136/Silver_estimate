"""Transactional password-change orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, Literal

from silverestimate.security import credential_store
from silverestimate.security.credential_store import CredentialStoreError
from silverestimate.services import auth_service

LOGGER = logging.getLogger(__name__)

PasswordField = Literal[
    "current_password",
    "new_main_password",
    "confirm_main_password",
    "new_recovery_password",
    "confirm_recovery_password",
]

TRANSITIONAL_CREDENTIALS = (
    "pending_main",
    "pending_backup",
    "recovery_main",
    "recovery_backup",
)


class PasswordChangeStatus(Enum):
    SUCCESS = auto()
    VALIDATION_FAILED = auto()
    CREDENTIAL_STORE_UNAVAILABLE = auto()
    HASHING_FAILED = auto()
    ROLLED_BACK = auto()
    FAILED = auto()


@dataclass(frozen=True)
class PasswordChangeRequest:
    current_password: str
    new_main_password: str
    confirm_main_password: str
    new_recovery_password: str
    confirm_recovery_password: str


@dataclass(frozen=True)
class PasswordChangeResult:
    status: PasswordChangeStatus
    message: str
    focus_field: PasswordField | None = None
    clear_fields: tuple[PasswordField, ...] = ()

    @property
    def succeeded(self) -> bool:
        return self.status is PasswordChangeStatus.SUCCESS


@dataclass(frozen=True)
class PasswordChangeActions:
    get_credential: Callable[[str], str | None]
    set_credential: Callable[[str, str], None]
    delete_credential: Callable[[str], None]
    verify_password: Callable[[str, str], bool]
    hash_password: Callable[[str], str | None]
    change_database_password: Callable[[str], object]


def default_password_change_actions(
    database_provider: Callable[[], object | None],
) -> PasswordChangeActions:
    """Create production password dependencies with dynamic module dispatch."""

    return PasswordChangeActions(
        get_credential=lambda kind: credential_store.get_password_hash(kind),
        set_credential=lambda kind, value: credential_store.set_password_hash(
            kind,
            value,
            logger=LOGGER,
        ),
        delete_credential=lambda kind: credential_store.delete_password_hash(
            kind,
            logger=LOGGER,
        ),
        verify_password=lambda stored, provided: auth_service.verify_password(
            stored,
            provided,
            logger=LOGGER,
        ),
        hash_password=lambda password: auth_service.hash_password(
            password,
            logger=LOGGER,
        ),
        change_database_password=lambda password: _change_database_password(
            database_provider,
            password,
        ),
    )


class PasswordChangeService:
    """Validate, rekey, and promote credential hashes as one workflow."""

    def __init__(self, actions: PasswordChangeActions) -> None:
        self._actions = actions

    def change_passwords(
        self,
        request: PasswordChangeRequest,
    ) -> PasswordChangeResult:
        try:
            stored_main_hash = self._actions.get_credential("main")
        except CredentialStoreError as exc:
            LOGGER.error(
                "Secure credential store unavailable during password change: %s",
                exc,
                exc_info=True,
            )
            return PasswordChangeResult(
                PasswordChangeStatus.CREDENTIAL_STORE_UNAVAILABLE,
                "Secure credential storage is not available. Install and configure "
                "the system keyring, then try again.",
            )
        except Exception as exc:
            LOGGER.error(
                "Could not read the current credential: %s", exc, exc_info=True
            )
            return PasswordChangeResult(
                PasswordChangeStatus.FAILED,
                f"Failed to read the current password credential: {exc}",
            )

        try:
            validation = self._validate_request(request, stored_main_hash)
        except Exception as exc:
            LOGGER.error("Password validation failed: %s", exc, exc_info=True)
            return PasswordChangeResult(
                PasswordChangeStatus.FAILED,
                f"Failed to validate the current password: {exc}",
            )
        if validation is not None:
            return validation
        assert stored_main_hash is not None
        return self._change_validated_passwords(request, stored_main_hash)

    def _change_validated_passwords(
        self,
        request: PasswordChangeRequest,
        stored_main_hash: str,
    ) -> PasswordChangeResult:
        new_main_hash = self._actions.hash_password(request.new_main_password)
        new_recovery_hash = self._actions.hash_password(request.new_recovery_password)
        if not new_main_hash or not new_recovery_hash:
            return PasswordChangeResult(
                PasswordChangeStatus.HASHING_FAILED,
                "Failed to hash new passwords. Cannot save.",
            )

        try:
            stored_backup_hash = self._actions.get_credential("backup")
            self._stage_credentials(
                new_main_hash,
                new_recovery_hash,
                stored_main_hash,
                stored_backup_hash,
            )
            outcome = self._actions.change_database_password(request.new_main_password)
            if getattr(getattr(outcome, "status", None), "name", "") != "SUCCESS":
                self._delete_transitional_credentials()
                return PasswordChangeResult(
                    PasswordChangeStatus.ROLLED_BACK,
                    str(
                        getattr(outcome, "message", "Password change was rolled back.")
                    ),
                )

            self._actions.set_credential("main", new_main_hash)
            self._actions.set_credential("backup", new_recovery_hash)
            self._delete_transitional_credentials()
            return PasswordChangeResult(
                PasswordChangeStatus.SUCCESS,
                str(getattr(outcome, "message", "Passwords updated.")),
                clear_fields=(
                    "current_password",
                    "new_main_password",
                    "confirm_main_password",
                    "new_recovery_password",
                    "confirm_recovery_password",
                ),
            )
        except Exception as exc:
            LOGGER.error("Password change failed: %s", exc, exc_info=True)
            return PasswordChangeResult(
                PasswordChangeStatus.FAILED,
                f"Failed to save new password settings: {exc}",
            )

    def _validate_request(
        self,
        request: PasswordChangeRequest,
        stored_main_hash: str | None,
    ) -> PasswordChangeResult | None:
        result: PasswordChangeResult | None = None
        if not stored_main_hash or not self._actions.verify_password(
            stored_main_hash,
            request.current_password,
        ):
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "Incorrect current password.",
                focus_field="current_password",
                clear_fields=("current_password",),
            )
        elif not request.new_main_password:
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "New main password cannot be empty.",
                focus_field="new_main_password",
            )
        elif request.new_main_password != request.confirm_main_password:
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "New main passwords do not match.",
                focus_field="confirm_main_password",
                clear_fields=("confirm_main_password",),
            )
        elif not request.new_recovery_password:
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "New recovery password cannot be empty.",
                focus_field="new_recovery_password",
            )
        elif request.new_recovery_password != request.confirm_recovery_password:
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "New recovery passwords do not match.",
                focus_field="confirm_recovery_password",
                clear_fields=("confirm_recovery_password",),
            )
        elif request.new_main_password == request.new_recovery_password:
            result = PasswordChangeResult(
                PasswordChangeStatus.VALIDATION_FAILED,
                "New main and recovery passwords must be different.",
                focus_field="new_recovery_password",
            )
        return result

    def _stage_credentials(
        self,
        new_main_hash: str,
        new_recovery_hash: str,
        stored_main_hash: str,
        stored_backup_hash: str | None,
    ) -> None:
        self._actions.set_credential("pending_main", new_main_hash)
        self._actions.set_credential("pending_backup", new_recovery_hash)
        self._actions.set_credential("recovery_main", stored_main_hash)
        if stored_backup_hash:
            self._actions.set_credential("recovery_backup", stored_backup_hash)

    def _delete_transitional_credentials(self) -> None:
        for kind in TRANSITIONAL_CREDENTIALS:
            self._actions.delete_credential(kind)


def _change_database_password(
    database_provider: Callable[[], object | None],
    password: str,
) -> object:
    database = database_provider()
    if database is None:
        raise RuntimeError("Encrypted database connection is unavailable")
    change_passwords = getattr(database, "change_passwords", None)
    if not callable(change_passwords):
        raise RuntimeError("Database password change is unavailable")
    return change_passwords(password)


__all__ = [
    "PasswordChangeActions",
    "PasswordChangeRequest",
    "PasswordChangeResult",
    "PasswordChangeService",
    "PasswordChangeStatus",
    "PasswordField",
    "default_password_change_actions",
]
