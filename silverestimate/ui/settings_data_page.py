"""Data-management settings page and maintenance boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol

from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.ui.maintenance_progress import MaintenanceProgressDialog

LOGGER = logging.getLogger(__name__)
DATABASE_BACKUP_FILTER = "Silver Estimate Encrypted Backup (*.sedbbackup)"


class DatabaseMaintenanceGateway(Protocol):
    """Database operations exposed to the settings data controller."""

    def create_encrypted_backup(self, destination: str) -> object: ...

    def stage_encrypted_restore(
        self,
        archive_path: str,
        archive_password: str,
    ) -> object: ...


@dataclass(frozen=True)
class DataManagementActions:
    """High-level application commands surfaced by the data page."""

    delete_all_estimates: Callable[[], object]
    delete_all_data: Callable[[], object]
    restore_item_catalog: Callable[[], object]
    create_item_catalog_backup: Callable[[], object]


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
        database_provider: Callable[[], DatabaseMaintenanceGateway | None],
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
        layout.setSpacing(12)

        description = QLabel(
            "<b>WARNING:</b> These actions permanently delete data and cannot "
            "be undone. Ensure you have backups if necessary."
        )
        description.setWordWrap(True)
        description.setObjectName("SettingsWarningLabel")
        title = QLabel("Backups")
        title.setObjectName("SettingsTitleLabel")
        layout.addWidget(title)
        layout.addWidget(self._create_item_backup_group())
        layout.addWidget(self._create_database_backup_group())
        danger = QGroupBox("DANGER ZONE")
        danger.setStyleSheet("QGroupBox { border: 1px solid #ff9ca4; color: #cf2434; }")
        danger_layout = QVBoxLayout(danger)
        danger_layout.addWidget(description)
        danger_layout.addLayout(self._create_delete_actions())
        layout.addWidget(danger)
        layout.addStretch()

    def _create_delete_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.delete_estimates_button = QPushButton("Delete All Estimates...")
        self.delete_estimates_button.setObjectName("SettingsDangerButton")
        self.delete_estimates_button.setToolTip(
            "Remove all estimate records\n"
            "Keeps item master and silver bar data intact\n"
            "Requires confirmation"
        )
        self.delete_estimates_button.clicked.connect(
            lambda: self._run_command(
                self._controller.delete_all_estimates,
                "Delete All Estimates",
            )
        )
        layout.addWidget(self.delete_estimates_button)

        self.delete_all_data_button = QPushButton("DELETE ALL DATA")
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
        layout.addWidget(self.delete_all_data_button)
        return layout

    def _create_item_backup_group(self) -> QGroupBox:
        group = QGroupBox("Item catalog")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.restore_item_backup_button = QPushButton("Restore catalog")
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
        layout.addWidget(self.restore_item_backup_button)

        self.create_item_backup_button = QPushButton("Create catalog backup")
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
        layout.addWidget(self.create_item_backup_button)
        return group

    def _create_database_backup_group(self) -> QGroupBox:
        group = QGroupBox("Encrypted Database Backup")
        layout = QVBoxLayout(group)
        recovery = QLabel(
            "Backups require this installation's original device secret and the "
            "main password used when the backup was created. They cannot be "
            "restored on another PC. Losing or resetting Windows credentials "
            "or the device secret can make backups unusable. Keep a separate "
            "copy of the archive; it cannot recover data if the device secret "
            "is lost. Backups include saved data and any preserved draft recovery copy.",
            group,
        )
        recovery.setWordWrap(True)
        layout.addWidget(recovery)
        self.backup_status_label = QLabel(group)
        self.backup_status_label.setWordWrap(True)
        self._refresh_backup_status()
        layout.addWidget(self.backup_status_label)

        self.create_database_backup_button = QPushButton(
            "Create Encrypted Database Backup..."
        )
        self.create_database_backup_button.setToolTip(
            "Create a validated .sedbbackup containing only SQLCipher-encrypted data"
        )
        self.create_database_backup_button.clicked.connect(self._create_database_backup)
        layout.addWidget(self.create_database_backup_button)

        self.restore_database_backup_button = QPushButton(
            "Stage Encrypted Database Restore..."
        )
        self.restore_database_backup_button.setToolTip(
            "Validate and stage an encrypted restore; activation requires restart"
        )
        self.restore_database_backup_button.clicked.connect(
            self._stage_database_restore
        )
        layout.addWidget(self.restore_database_backup_button)
        return group

    def _refresh_backup_status(self) -> None:
        stamp = get_app_settings().get_text(SettingsKey.BACKUP_LAST_VALIDATED_UTC)
        self.backup_status_label.setText(
            f"Last successful backup and validation (UTC): {stamp}"
            if stamp
            else "No successful database backup recorded on this installation."
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
                "Encrypted Backup Created",
                result.message,
            )
        else:
            QMessageBox.critical(self, "Backup Error", result.message)

    def _stage_database_restore(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Restore Encrypted Database Backup",
            "",
            DATABASE_BACKUP_FILTER,
        )
        if not path:
            return
        password, accepted = QInputDialog.getText(
            self,
            "Backup Password",
            "Enter the main password that protected this backup:",
            QLineEdit.EchoMode.Password,
        )
        if not accepted:
            return
        controller = self._controller.for_worker()
        result = self._run_maintenance(
            lambda: controller.stage_database_restore(path, password),
            "Validating and Staging Restore",
        )
        if result.succeeded:
            QMessageBox.information(self, "Restore Staged", result.message)
        else:
            QMessageBox.critical(self, "Restore Error", result.message)

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
    "DatabaseMaintenanceGateway",
    "SettingsDataController",
]
