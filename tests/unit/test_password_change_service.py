from __future__ import annotations

from types import SimpleNamespace

from silverestimate.security.credential_store import CredentialStoreError
from silverestimate.services.password_change_service import (
    PasswordChangeActions,
    PasswordChangeRequest,
    PasswordChangeService,
    PasswordChangeStatus,
)


class _PasswordHarness:
    def __init__(self, *, database_status: str = "SUCCESS") -> None:
        self.credentials = {
            "main": "hash-old-main",
            "backup": "hash-old-recovery",
        }
        self.database_status = database_status
        self.database_passwords: list[str] = []

    def actions(self) -> PasswordChangeActions:
        return PasswordChangeActions(
            get_credential=lambda kind: self.credentials.get(kind),
            set_credential=self._set_credential,
            delete_credential=lambda kind: self.credentials.pop(kind, None),
            verify_password=lambda stored, provided: (
                stored == "hash-old-main" and provided == "current-password"
            ),
            hash_password=lambda password: f"hash-{password}",
            change_database_password=self._change_database_password,
        )

    def _set_credential(self, kind: str, value: str) -> None:
        self.credentials[kind] = value

    def _change_database_password(self, password: str) -> object:
        self.database_passwords.append(password)
        return SimpleNamespace(
            status=SimpleNamespace(name=self.database_status),
            message=(
                "Passwords updated."
                if self.database_status == "SUCCESS"
                else "Database rekey rolled back."
            ),
        )


def _valid_request() -> PasswordChangeRequest:
    return PasswordChangeRequest(
        current_password="current-password",
        new_main_password="new-main",
        confirm_main_password="new-main",
        new_recovery_password="new-recovery",
        confirm_recovery_password="new-recovery",
    )


def test_successful_change_rekeys_then_promotes_credentials() -> None:
    harness = _PasswordHarness()
    service = PasswordChangeService(harness.actions())

    result = service.change_passwords(_valid_request())

    assert result.succeeded
    assert result.status is PasswordChangeStatus.SUCCESS
    assert harness.database_passwords == ["new-main"]
    assert harness.credentials["main"] == "hash-new-main"
    assert harness.credentials["backup"] == "hash-new-recovery"
    for kind in (
        "pending_main",
        "pending_backup",
        "recovery_main",
        "recovery_backup",
    ):
        assert kind not in harness.credentials


def test_validation_failure_names_the_field_without_mutating_credentials() -> None:
    harness = _PasswordHarness()
    service = PasswordChangeService(harness.actions())
    request = PasswordChangeRequest(
        current_password="wrong",
        new_main_password="new-main",
        confirm_main_password="different",
        new_recovery_password="new-recovery",
        confirm_recovery_password="new-recovery",
    )

    result = service.change_passwords(request)

    assert result.status is PasswordChangeStatus.VALIDATION_FAILED
    assert result.focus_field == "current_password"
    assert result.clear_fields == ("current_password",)
    assert harness.database_passwords == []
    assert harness.credentials == {
        "main": "hash-old-main",
        "backup": "hash-old-recovery",
    }


def test_database_rollback_clears_transitional_credentials() -> None:
    harness = _PasswordHarness(database_status="ROLLED_BACK")
    service = PasswordChangeService(harness.actions())

    result = service.change_passwords(_valid_request())

    assert result.status is PasswordChangeStatus.ROLLED_BACK
    assert harness.credentials["main"] == "hash-old-main"
    assert harness.credentials["backup"] == "hash-old-recovery"
    assert set(harness.credentials) == {"main", "backup"}


def test_credential_store_failure_returns_explicit_error() -> None:
    actions = PasswordChangeActions(
        get_credential=lambda _kind: (_ for _ in ()).throw(
            CredentialStoreError("vault unavailable")
        ),
        set_credential=lambda _kind, _value: None,
        delete_credential=lambda _kind: None,
        verify_password=lambda _stored, _provided: False,
        hash_password=lambda _password: None,
        change_database_password=lambda _password: None,
    )

    result = PasswordChangeService(actions).change_passwords(_valid_request())

    assert result.status is PasswordChangeStatus.CREDENTIAL_STORE_UNAVAILABLE
    assert not result.succeeded
