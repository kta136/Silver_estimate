"""Data-management settings page and maintenance boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
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
        return DataActionResult(
            succeeded=True,
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
        layout.addWidget(description)
        layout.addLayout(self._create_delete_actions())
        layout.addWidget(self._create_item_backup_group())
        layout.addWidget(self._create_database_backup_group())
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
        group = QGroupBox("Item Master Backup")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)

        self.restore_item_backup_button = QPushButton("Restore Item Backup...")
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

        self.create_item_backup_button = QPushButton("Create Item Backup...")
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

    def _create_database_backup(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Create Encrypted Database Backup",
            "silverestimate.sedbbackup",
            DATABASE_BACKUP_FILTER,
        )
        if not path:
            return
        result = self._controller.create_database_backup(path)
        if result.succeeded:
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
        result = self._controller.stage_database_restore(path, password)
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
