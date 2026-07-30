from __future__ import annotations

from types import SimpleNamespace

from silverestimate.ui.settings_data_page import (
    DataManagementActions,
    SettingsDataController,
)


class _DatabaseStub:
    def __init__(self) -> None:
        self.backup_destinations: list[str] = []
        self.restore_requests: list[tuple[str, str]] = []

    def create_encrypted_backup(self, destination: str) -> object:
        self.backup_destinations.append(destination)
        return SimpleNamespace(
            message="Backup created.",
            path=destination,
        )

    def stage_encrypted_restore(
        self,
        archive_path: str,
        archive_password: str,
    ) -> object:
        self.restore_requests.append((archive_path, archive_password))
        return SimpleNamespace(
            message="Restore staged.",
            path="database.restore.staged",
        )


def _actions(calls: list[str]) -> DataManagementActions:
    return DataManagementActions(
        delete_all_estimates=lambda: calls.append("delete_estimates"),
        delete_all_data=lambda: calls.append("delete_data"),
        restore_item_catalog=lambda: calls.append("restore_catalog"),
        create_item_catalog_backup=lambda: calls.append("backup_catalog"),
    )


def test_high_level_data_commands_use_narrow_injected_actions() -> None:
    calls: list[str] = []
    controller = SettingsDataController(lambda: None, _actions(calls))

    outcomes = (
        controller.delete_all_estimates(),
        controller.delete_all_data(),
        controller.restore_item_catalog(),
        controller.create_item_catalog_backup(),
    )

    assert all(outcome.succeeded for outcome in outcomes)
    assert calls == [
        "delete_estimates",
        "delete_data",
        "restore_catalog",
        "backup_catalog",
    ]


def test_database_backup_and_restore_return_explicit_outcomes() -> None:
    database = _DatabaseStub()
    controller = SettingsDataController(lambda: database, _actions([]))

    backup = controller.create_database_backup("counter-backup")
    restore = controller.stage_database_restore(
        "counter-backup.sedbbackup",
        "main-password",
    )

    assert backup.succeeded
    assert backup.message == "Backup created."
    assert backup.path == "counter-backup.sedbbackup"
    assert database.backup_destinations == ["counter-backup.sedbbackup"]
    assert restore.succeeded
    assert restore.message == "Restore staged."
    assert restore.path == "database.restore.staged"
    assert database.restore_requests == [("counter-backup.sedbbackup", "main-password")]


def test_database_actions_report_unavailable_or_failed_dependencies() -> None:
    unavailable = SettingsDataController(lambda: None, _actions([]))

    assert not unavailable.create_database_backup("backup").succeeded
    assert not unavailable.stage_database_restore("backup", "password").succeeded

    failing_actions = DataManagementActions(
        delete_all_estimates=lambda: False,
        delete_all_data=lambda: (_ for _ in ()).throw(RuntimeError("wipe failed")),
        restore_item_catalog=lambda: None,
        create_item_catalog_backup=lambda: None,
    )
    controller = SettingsDataController(lambda: None, failing_actions)

    assert not controller.delete_all_estimates().succeeded
    failed = controller.delete_all_data()
    assert not failed.succeeded
    assert failed.message == "wipe failed"


def test_cancelled_application_command_is_not_reported_as_an_error() -> None:
    cancelled_command = SimpleNamespace(
        succeeded=False,
        cancelled=True,
        message="",
    )
    actions = DataManagementActions(
        delete_all_estimates=lambda: cancelled_command,
        delete_all_data=lambda: None,
        restore_item_catalog=lambda: None,
        create_item_catalog_backup=lambda: None,
    )

    result = SettingsDataController(lambda: None, actions).delete_all_estimates()

    assert result.cancelled
    assert not result.succeeded
