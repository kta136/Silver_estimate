"""Data-management settings page and maintenance boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Callable

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.ui.display_formatting import format_local_timestamp
from silverestimate.ui.maintenance_progress import MaintenanceProgressDialog
from silverestimate.ui.message_dialogs import ask_text

if TYPE_CHECKING:
    from silverestimate.persistence.database_manager import DatabaseManager

LOGGER = logging.getLogger(__name__)
DATABASE_BACKUP_FILTER = "Silver Estimate Encrypted Backup (*.sedbbackup)"
ACTION_BUTTON_WIDTH = 240


def format_backup_time(stamp: str | None) -> str:
    """Return the stored backup time in local time, or ``""`` when there is none."""
    return format_local_timestamp(stamp)


def with_restart_note(message: str) -> str:
    """Say plainly that a checked restore is applied at the next start."""
    note = "The backup was checked. Restart the app to load its data."
    message = (message or "").strip()
    return f"{note}\n\n{message}" if message and note not in message else note


@dataclass(frozen=True)
class DataManagementActions:
    """High-level application commands surfaced by the data page."""

    delete_all_estimates: Callable[[], object]
    delete_all_data: Callable[[], object]
    restore_item_catalog: Callable[[], object]
    create_item_catalog_backup: Callable[[], object]
    delete_vouchers_by_range: Callable[[], object]


@dataclass(frozen=True)
class DataActionResult:
    """Explicit result for a data-management action."""

    succeeded: bool
    message: str = ""
    path: str | None = None
    cancelled: bool = False


class SettingsDataController:
    """Invoke data commands through narrow, testable dependencies."""

    def __init__(
        self,
        database_provider: Callable[[], DatabaseManager | None],
        actions: DataManagementActions,
    ) -> None:
        self._database_provider = database_provider
        self._actions = actions

    def for_worker(self) -> SettingsDataController:
        """Resolve the UI-owned database provider before dispatching work."""
        database = self._database_provider()
        return SettingsDataController(lambda: database, self._actions)

    def delete_all_estimates(self) -> DataActionResult:
        return self._run_command(
            self._actions.delete_all_estimates,
            "Delete-all-estimates command",
        )

    def delete_vouchers_by_range(self) -> DataActionResult:
        return self._run_command(
            self._actions.delete_vouchers_by_range,
            "Delete-vouchers-by-range command",
        )

    def delete_all_data(self) -> DataActionResult:
        return self._run_command(
            self._actions.delete_all_data,
            "Delete-all-data command",
        )

    def restore_item_catalog(self) -> DataActionResult:
        return self._run_command(
            self._actions.restore_item_catalog,
            "Item-catalog restore command",
        )

    def create_item_catalog_backup(self) -> DataActionResult:
        return self._run_command(
            self._actions.create_item_catalog_backup,
            "Item-catalog backup command",
        )

    def create_database_backup(self, destination: str) -> DataActionResult:
        database = self._database_provider()
        if database is None:
            return DataActionResult(False, "Database is unavailable.")
        destination = self.ensure_backup_suffix(destination)
        try:
            outcome = database.create_encrypted_backup(destination)
        except Exception as exc:
            LOGGER.error("Encrypted database backup failed: %s", exc, exc_info=True)
            return DataActionResult(False, str(exc))
        return self._maintenance_result(outcome, destination)

    def stage_database_restore(
        self,
        archive_path: str,
        password: str,
    ) -> DataActionResult:
        database = self._database_provider()
        if database is None:
            return DataActionResult(False, "Database is unavailable.")
        try:
            outcome = database.stage_encrypted_restore(archive_path, password)
        except Exception as exc:
            LOGGER.error("Encrypted database restore failed: %s", exc, exc_info=True)
            return DataActionResult(False, str(exc))
        return self._maintenance_result(outcome, archive_path)

    @staticmethod
    def ensure_backup_suffix(path: str) -> str:
        return path if path.lower().endswith(".sedbbackup") else f"{path}.sedbbackup"

    @staticmethod
    def _maintenance_result(outcome: object, fallback_path: str) -> DataActionResult:
        message = str(getattr(outcome, "message", "") or "")
        path = getattr(outcome, "path", None)
        status = getattr(outcome, "status", None)
        succeeded = status is None or getattr(status, "name", "") in {
            "SUCCESS",
            "STAGED_RESTART_REQUIRED",
        }
        return DataActionResult(
            succeeded=succeeded,
            message=message,
            path=str(path or fallback_path),
        )

    @staticmethod
    def _run_command(
        command: Callable[[], object],
        label: str,
    ) -> DataActionResult:
        try:
            result = command()
        except Exception as exc:
            LOGGER.error("%s failed: %s", label, exc, exc_info=True)
            return DataActionResult(False, str(exc))
        message = str(getattr(result, "message", "") or "")
        if bool(getattr(result, "cancelled", False)):
            return DataActionResult(
                succeeded=False,
                message=message,
                cancelled=True,
            )
        succeeded = getattr(result, "succeeded", None)
        if result is False or succeeded is False:
            return DataActionResult(False, message or f"{label} failed.")
        return DataActionResult(True, message=message)


class DataManagementPage(QWidget):
    """Own data-management controls and their user feedback."""

    def __init__(
        self,
        controller: SettingsDataController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._maintenance_active = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Tight enough that the page fits the dialog on a 1366x768 screen
        # without a scrollbar.
        layout.setSpacing(6)

        title = QLabel("Data & Backups")
        title.setObjectName("SettingsTitleLabel")
        layout.addWidget(title)
        layout.addWidget(self._create_database_backup_group())
        layout.addWidget(self._create_item_backup_group())
        layout.addWidget(self._create_danger_group())
        layout.addStretch()

    @staticmethod
    def _action_row(button: QPushButton, description: str) -> QHBoxLayout:
        """A button sized to its label with what it does written beside it."""
        row = QHBoxLayout()
        row.setSpacing(12)
        button.setMinimumWidth(ACTION_BUTTON_WIDTH)
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        row.addWidget(button)
        label = QLabel(description)
        label.setObjectName("SettingsMutedDescription")
        label.setWordWrap(True)
        row.addWidget(label, 1)
        return row

    def _create_danger_group(self) -> QGroupBox:
        danger = QGroupBox("Delete data")
        danger.setObjectName("SettingsDangerGroup")
        danger.setStyleSheet(
            "QGroupBox#SettingsDangerGroup { border: 1px solid #ff9ca4; color: #cf2434; }"
        )
        layout = QVBoxLayout(danger)
        layout.setContentsMargins(12, 4, 12, 6)
        layout.setSpacing(4)
        warning = QLabel(
            "These actions permanently delete data and cannot be undone. "
            "Back up the database first."
        )
        warning.setWordWrap(True)
        warning.setObjectName("SettingsDangerNote")
        warning.setStyleSheet(
            "QLabel#SettingsDangerNote { color: #991b1b; font-weight: 600; }"
        )
        layout.addWidget(warning)

        self.delete_range_button = QPushButton("Delete Vouchers by Range...")
        self.delete_range_button.setObjectName("SettingsDangerButton")
        self.delete_range_button.setToolTip(
            "Preview and delete vouchers by date or voucher number range.\n"
            "Vouchers with protected silver bars are skipped."
        )
        self.delete_range_button.clicked.connect(
            lambda: self._run_command(
                self._controller.delete_vouchers_by_range,
                "Delete Vouchers by Range",
            )
        )
        layout.addLayout(
            self._action_row(
                self.delete_range_button,
                "Preview the vouchers in a date or number range, then delete them.",
            )
        )

        self.delete_estimates_button = QPushButton("Delete All Estimates...")
        self.delete_estimates_button.setObjectName("SettingsDangerButton")
        self.delete_estimates_button.setToolTip(
            "Remove every estimate\nKeeps the item catalog\n"
            "Requires typing DELETE to confirm"
        )
        self.delete_estimates_button.clicked.connect(
            lambda: self._run_command(
                self._controller.delete_all_estimates,
                "Delete All Estimates",
            )
        )
        layout.addLayout(
            self._action_row(
                self.delete_estimates_button,
                "Removes every estimate. The item catalog is kept.",
            )
        )

        self.delete_all_data_button = QPushButton("Delete All Data...")
        self.delete_all_data_button.setObjectName("SettingsDangerButton")
        self.delete_all_data_button.setToolTip(
            "Reset all application data\n"
            "Includes: estimates, items, silver bars, lists\n"
            "Requires typing DELETE to confirm"
        )
        self.delete_all_data_button.clicked.connect(
            lambda: self._run_command(
                self._controller.delete_all_data,
                "Delete All Data",
            )
        )
        layout.addLayout(
            self._action_row(
                self.delete_all_data_button,
                "Removes estimates, items, silver bars and lists.",
            )
        )
        return danger

    def _create_item_backup_group(self) -> QGroupBox:
        group = QGroupBox("Item catalog")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 4, 12, 6)
        layout.setSpacing(4)

        self.create_item_backup_button = QPushButton("Back Up Item Catalog...")
        self.create_item_backup_button.setToolTip(
            "Create a native Silver Estimate item catalog backup file\n"
            "Format: .seitems.json\n"
            "Round-trip safe for future imports"
        )
        self.create_item_backup_button.clicked.connect(
            lambda: self._run_command(
                self._controller.create_item_catalog_backup,
                "Create Item Backup",
            )
        )
        layout.addLayout(
            self._action_row(
                self.create_item_backup_button,
                "Saves every item to a file you can restore or move to another PC.",
            )
        )

        self.restore_item_backup_button = QPushButton("Restore Item Catalog...")
        self.restore_item_backup_button.setToolTip(
            "Restore a native Silver Estimate item catalog backup\n"
            "Format: .seitems.json\n"
            "Updates existing item codes and adds missing ones\n"
            "Does not remove items that are not in the file"
        )
        self.restore_item_backup_button.clicked.connect(
            lambda: self._run_command(
                self._controller.restore_item_catalog,
                "Restore Item Backup",
            )
        )
        layout.addLayout(
            self._action_row(
                self.restore_item_backup_button,
                "Updates and adds items from a catalog backup file.",
            )
        )
        return group

    def _create_database_backup_group(self) -> QGroupBox:
        group = QGroupBox("Database backup")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 4, 12, 6)
        layout.setSpacing(4)
        self.backup_status_label = QLabel(group)
        self.backup_status_label.setWordWrap(True)
        self.backup_status_label.setObjectName("SettingsBackupStatus")
        self._refresh_backup_status()
        layout.addWidget(self.backup_status_label)

        self.create_database_backup_button = QPushButton("Back Up Database...")
        self.create_database_backup_button.setObjectName("SettingsPrimaryButton")
        self.create_database_backup_button.setStyleSheet(
            "QPushButton { color: white; }"
        )
        self.create_database_backup_button.setToolTip(
            "Create a validated .sedbbackup containing only SQLCipher-encrypted data"
        )
        self.create_database_backup_button.clicked.connect(self._create_database_backup)
        layout.addLayout(
            self._action_row(
                self.create_database_backup_button,
                "Saves all estimates, items, silver bars and any unfinished "
                "estimate to one encrypted file.",
            )
        )

        self.restore_database_backup_button = QPushButton(
            "Restore Database from Backup..."
        )
        self.restore_database_backup_button.setToolTip(
            "Validate and stage an encrypted restore; activation requires restart"
        )
        self.restore_database_backup_button.clicked.connect(
            self._stage_database_restore
        )
        layout.addLayout(
            self._action_row(
                self.restore_database_backup_button,
                "Checks a backup file now and replaces the current data the next "
                "time the app starts.",
            )
        )

        limits = QLabel(
            "A backup opens only on this PC, with the main password in use when "
            "it was made. If this PC's Windows credentials are reset or lost, it "
            "cannot be opened, so keep a copy of the file somewhere else too.",
            group,
        )
        limits.setObjectName("SettingsMutedDescription")
        limits.setWordWrap(True)
        layout.addWidget(limits)
        return group

    def _refresh_backup_status(self) -> None:
        stamp = get_app_settings().get_text(SettingsKey.BACKUP_LAST_VALIDATED_UTC)
        backed_up = format_backup_time(stamp)
        self.backup_status_label.setText(
            f"Last backup: {backed_up}"
            if backed_up
            else "No database backup has been made on this PC yet."
        )
        # A missing backup is the one state here worth drawing the eye to.
        self.backup_status_label.setStyleSheet(
            "QLabel#SettingsBackupStatus { font-weight: 600; }"
            if backed_up
            else "QLabel#SettingsBackupStatus { color: #9a3412; font-weight: 600; }"
        )

    def _run_maintenance(
        self,
        operation: Callable[[], DataActionResult],
        title: str,
    ) -> DataActionResult:
        if self._maintenance_active:
            return DataActionResult(False, "Database maintenance is already active.")
        self._maintenance_active = True
        dialog = MaintenanceProgressDialog(operation, title, self)
        try:
            result = dialog.run_operation()
            if not isinstance(result, DataActionResult):
                return DataActionResult(
                    False, "Maintenance returned an invalid result."
                )
            return result
        except Exception as exc:
            LOGGER.exception("Database maintenance failed")
            return DataActionResult(False, str(exc))
        finally:
            dialog.deleteLater()
            self._maintenance_active = False

    def _create_database_backup(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Create Encrypted Database Backup",
            "silverestimate.sedbbackup",
            DATABASE_BACKUP_FILTER,
        )
        if not path:
            return
        controller = self._controller.for_worker()
        result = self._run_maintenance(
            lambda: controller.create_database_backup(path),
            "Creating Encrypted Backup",
        )
        if result.succeeded:
            settings = get_app_settings()
            settings.set(
                SettingsKey.BACKUP_LAST_VALIDATED_UTC,
                datetime.now(UTC).isoformat(timespec="seconds"),
            )
            settings.sync()
            self._refresh_backup_status()
            QMessageBox.information(
                self,
                "Backup Created",
                result.message,
            )
        else:
            QMessageBox.critical(self, "Backup Not Created", result.message)

    def _stage_database_restore(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Restore Encrypted Database Backup",
            "",
            DATABASE_BACKUP_FILTER,
        )
        if not path:
            return
        password = ask_text(
            self,
            title="Backup Password",
            heading="Main password of this backup",
            detail=(
                "Enter the main password that was in use when the backup was "
                "made. It can differ from today's password."
            ),
            action_label="Check Backup",
            password=True,
        )
        if password is None:
            return
        controller = self._controller.for_worker()
        result = self._run_maintenance(
            lambda: controller.stage_database_restore(path, password),
            "Validating and Staging Restore",
        )
        if result.succeeded:
            QMessageBox.information(
                self,
                "Restore Ready",
                with_restart_note(result.message),
            )
        else:
            QMessageBox.critical(self, "Backup Not Restored", result.message)

    def _run_command(
        self,
        command: Callable[[], DataActionResult],
        title: str,
    ) -> None:
        result = command()
        if not result.succeeded and not result.cancelled:
            QMessageBox.critical(self, title, result.message)


__all__ = [
    "DataActionResult",
    "DataManagementActions",
    "DataManagementPage",
    "SettingsDataController",
]
