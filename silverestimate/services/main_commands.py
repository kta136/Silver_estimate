"""Main window command helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, cast

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox

from silverestimate.persistence.database_protocols import (
    MainCommandsDatabase,
    ReadConnectionFactory,
)
from silverestimate.ui.database_maintenance import run_database_maintenance
from silverestimate.ui.message_dialogs import (
    ask_with_option,
    confirm_by_typing,
    confirm_destructive,
    with_details,
)


class MainCommandStatus(Enum):
    SUCCESS = auto()
    STARTED = auto()
    CANCELLED = auto()
    FAILED = auto()


@dataclass(frozen=True)
class MainCommandOutcome:
    status: MainCommandStatus
    message: str = ""

    @property
    def succeeded(self) -> bool:
        return self.status in {
            MainCommandStatus.SUCCESS,
            MainCommandStatus.STARTED,
        }

    @property
    def cancelled(self) -> bool:
        return self.status is MainCommandStatus.CANCELLED


class _ItemCatalogExportWorker(QObject):
    finished = Signal(int)
    error = Signal(str)

    def __init__(
        self, *, connection_factory: ReadConnectionFactory, file_path: str
    ) -> None:
        super().__init__()
        self.connection_factory = connection_factory
        self.file_path = file_path

    def run(self) -> None:
        from silverestimate.services.item_catalog_transfer import (
            export_item_catalog_rows,
            load_item_catalog_rows_from_connection_factory,
        )

        try:
            rows = load_item_catalog_rows_from_connection_factory(
                self.connection_factory
            )
            count = export_item_catalog_rows(rows, self.file_path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(count)


class MainCommands:
    """Encapsulate high-level commands triggered from the main window."""

    def __init__(
        self,
        main_window,
        db_manager: MainCommandsDatabase,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.main_window = main_window
        self.db = db_manager
        self.logger = logger or logging.getLogger(__name__)
        self._catalog_import_active = False
        self._catalog_export_thread: QThread | None = None
        self._catalog_export_worker: _ItemCatalogExportWorker | None = None

    # --- File commands --------------------------------------------------
    def save_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, "estimate_widget", None)
            if widget:
                if widget.save_estimate():
                    self._refresh_sales_report()
            else:
                QMessageBox.information(
                    self.main_window,
                    "Estimate Entry Unavailable",
                    "Open Estimate Entry to save an estimate.",
                )
        except Exception as exc:
            self.logger.error("Save action failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Estimate Not Saved",
                with_details("The estimate could not be saved.", exc),
            )

    def print_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, "estimate_widget", None)
            if widget:
                widget.print_estimate()
            else:
                QMessageBox.information(
                    self.main_window,
                    "Estimate Entry Unavailable",
                    "Open Estimate Entry to print an estimate.",
                )
        except Exception as exc:
            self.logger.error("Print action failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Estimate Not Printed",
                with_details("The print preview could not be opened.", exc),
            )

    # --- Data management ------------------------------------------------
    def delete_all_data(self) -> MainCommandOutcome:
        if not self._ensure_db():
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                "Database connection is not available.",
            )

        if not confirm_destructive(
            self._dialog_parent(),
            title="Delete All Data",
            heading="Delete all data?",
            detail=(
                "Every item, estimate, silver bar and list will be removed. "
                "This cannot be undone.\n\n"
                "Back up the database first if you may need any of it."
            ),
            action_label="Delete All Data",
        ) or not self._typed_delete(
            "Delete All Data",
            "Type DELETE to delete all data",
            "Delete All Data",
        ):
            return MainCommandOutcome(MainCommandStatus.CANCELLED)

        try:
            if not self.db.drop_tables():
                QMessageBox.critical(
                    self.main_window,
                    "Data Not Deleted",
                    "The data could not be deleted. Nothing was changed.",
                )
                return MainCommandOutcome(
                    MainCommandStatus.FAILED,
                    "Failed to delete all data (dropping tables failed).",
                )

            self.db.setup_database()
            self._refresh_views_after_data_reset()
            message = "All data has been deleted."
            QMessageBox.information(
                self.main_window,
                "All Data Deleted",
                message,
            )
            return MainCommandOutcome(MainCommandStatus.SUCCESS, message)
        except Exception as exc:
            self.logger.error("Error deleting all data: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Data Not Deleted",
                with_details("The data could not be deleted.", exc),
            )
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                f"Failed to delete all data: {exc}",
            )

    def restore_item_catalog(self) -> MainCommandOutcome:
        """Restore a native Silver Estimate item catalog backup."""
        if self._catalog_import_active:
            return MainCommandOutcome(
                MainCommandStatus.FAILED, "Catalog import is already running."
            )
        if not self._ensure_db():
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                "Database connection is not available.",
            )

        from silverestimate.services.item_catalog_transfer import (
            ITEM_CATALOG_FILE_FILTER,
            import_item_catalog,
        )

        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Restore Item Catalog Backup",
            "",
            ITEM_CATALOG_FILE_FILTER,
        )
        if not file_path:
            return MainCommandOutcome(MainCommandStatus.CANCELLED)

        confirmed, replace_existing = ask_with_option(
            self._dialog_parent(),
            title="Restore Item Catalog",
            heading="Restore the item catalog from this backup?",
            detail=(
                "Items in the backup are added, and items with the same code "
                "are updated. Items that are not in the backup are kept.\n\n"
                "Tick the box to remove those as well. Estimate rows that used "
                "a removed item keep their figures but lose the link to the "
                "item."
            ),
            option_label="Also remove items that are not in the backup",
            action_label="Restore Catalog",
        )
        if not confirmed:
            return MainCommandOutcome(MainCommandStatus.CANCELLED)

        self._catalog_import_active = True
        try:
            summary = run_database_maintenance(
                self.db,
                lambda worker: import_item_catalog(
                    worker, file_path, replace_existing=replace_existing
                ),
                "Restoring Item Catalog",
                self.main_window,
            )
        except Exception as exc:
            self.logger.error("Item catalog restore failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Restore Failed",
                with_details("The item catalog could not be restored.", exc),
            )
            return MainCommandOutcome(MainCommandStatus.FAILED, str(exc))
        finally:
            self._catalog_import_active = False

        item_master = getattr(self.main_window, "item_master_widget", None)
        if item_master is not None and item_master.isVisible():
            try:
                item_master.load_items()
            except Exception as exc:
                self.logger.warning(
                    "Could not refresh item master after import: %s", exc
                )

        message = (
            "Item catalog restored.\n\n"
            f"Total records: {summary['total']}\n"
            f"Inserted: {summary['inserted']}\n"
            f"Updated: {summary['updated']}\n"
            f"Deleted: {summary['deleted']}"
        )
        QMessageBox.information(
            self.main_window,
            "Restore Complete",
            message,
        )
        return MainCommandOutcome(MainCommandStatus.SUCCESS, message)

    def create_item_catalog_backup(self) -> MainCommandOutcome:
        """Create a native Silver Estimate item catalog backup."""
        if not self._ensure_db():
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                "Database connection is not available.",
            )

        from silverestimate.services.item_catalog_transfer import (
            ITEM_CATALOG_FILE_FILTER,
            ensure_catalog_file_suffix,
        )

        default_filename = "item_catalog_backup.seitems.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Create Item Catalog Backup",
            default_filename,
            ITEM_CATALOG_FILE_FILTER,
        )
        if not file_path:
            return MainCommandOutcome(MainCommandStatus.CANCELLED)

        connection_factory = getattr(self.db, "open_read_connection", None)
        if not callable(connection_factory):
            QMessageBox.critical(
                self.main_window,
                "Catalog Not Backed Up",
                "The database is not available. Please restart the application.",
            )
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                "Encrypted database connection not available.",
            )

        return self._start_item_catalog_export_worker(
            connection_factory=cast(ReadConnectionFactory, connection_factory),
            file_path=ensure_catalog_file_suffix(file_path),
        )

    def delete_vouchers_by_range(self) -> MainCommandOutcome:
        from PySide6.QtWidgets import QApplication

        from silverestimate.services.voucher_deletion import VoucherDeletionController
        from silverestimate.ui.voucher_range_deletion_dialog import (
            VoucherRangeDeletionDialog,
        )

        if not self._ensure_db():
            return MainCommandOutcome(
                MainCommandStatus.FAILED, "Database is unavailable."
            )
        dialog = VoucherRangeDeletionDialog(
            VoucherDeletionController(self.db, self.main_window),
            QApplication.activeModalWidget() or self.main_window,
        )
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()
        return MainCommandOutcome(MainCommandStatus.SUCCESS)

    def delete_all_estimates(self) -> MainCommandOutcome:
        if not self._ensure_db():
            return MainCommandOutcome(
                MainCommandStatus.FAILED,
                "Database connection is not available.",
            )

        if not confirm_destructive(
            self._dialog_parent(),
            title="Delete All Estimates",
            heading="Delete every estimate?",
            detail=(
                "All saved estimates will be removed. The item catalog is "
                "kept. This cannot be undone.\n\n"
                "Back up the database first if you may need them."
            ),
            action_label="Delete All Estimates",
        ) or not self._typed_delete(
            "Delete All Estimates",
            "Type DELETE to delete every estimate",
            "Delete All Estimates",
        ):
            return MainCommandOutcome(MainCommandStatus.CANCELLED)

        try:
            if self.db.delete_all_estimates():
                message = "All estimates have been deleted."
                QMessageBox.information(
                    self.main_window,
                    "All Estimates Deleted",
                    message,
                )
                widget = getattr(self.main_window, "estimate_widget", None)
                if widget:
                    try:
                        widget.clear_form(confirm=False)
                    except Exception as form_exc:
                        self.logger.error(
                            "Error clearing estimate form: %s", form_exc, exc_info=True
                        )
                return MainCommandOutcome(MainCommandStatus.SUCCESS, message)
            else:
                message = "The estimates could not be deleted. Nothing was changed."
                QMessageBox.critical(
                    self.main_window,
                    "Estimates Not Deleted",
                    message,
                )
                return MainCommandOutcome(MainCommandStatus.FAILED, message)
        except Exception as exc:
            self.logger.error("Error deleting all estimates: %s", exc, exc_info=True)
            message = with_details("The estimates could not be deleted.", exc)
            QMessageBox.critical(
                self.main_window,
                "Estimates Not Deleted",
                message,
            )
            return MainCommandOutcome(MainCommandStatus.FAILED, message)

    def _start_item_catalog_export_worker(
        self,
        *,
        connection_factory: ReadConnectionFactory,
        file_path: str,
    ) -> MainCommandOutcome:
        if getattr(self, "_catalog_export_thread", None) is not None:
            message = "A catalog backup is already in progress."
            QMessageBox.information(
                self.main_window,
                "Catalog Backup Running",
                message,
            )
            return MainCommandOutcome(MainCommandStatus.CANCELLED, message)

        worker = _ItemCatalogExportWorker(
            connection_factory=connection_factory, file_path=file_path
        )
        thread = QThread(self.main_window)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_item_catalog_export_finished)
        worker.error.connect(self._on_item_catalog_export_failed)
        worker.finished.connect(thread.quit)
        worker.error.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._clear_item_catalog_export_worker)
        self._catalog_export_worker = worker
        self._catalog_export_thread = thread
        thread.start()
        return MainCommandOutcome(
            MainCommandStatus.STARTED,
            "Item catalog backup started.",
        )

    def _on_item_catalog_export_finished(self, exported_count: int) -> None:
        QMessageBox.information(
            self.main_window,
            "Catalog Backed Up",
            f"Item catalog backup created with {exported_count} items.",
        )

    def _on_item_catalog_export_failed(self, message: str) -> None:
        QMessageBox.critical(
            self.main_window,
            "Catalog Not Backed Up",
            with_details("The item catalog backup could not be created.", message),
        )

    def _clear_item_catalog_export_worker(self) -> None:
        self._catalog_export_worker = None
        self._catalog_export_thread = None

    # --- Helpers --------------------------------------------------------
    def _dialog_parent(self):
        """The open dialog (Settings) if there is one, else the main window."""
        from PySide6.QtWidgets import QApplication

        return QApplication.activeModalWidget() or self.main_window

    def _typed_delete(self, title: str, heading: str, action_label: str) -> bool:
        """Second step for mass deletion: the user types the word DELETE."""
        return confirm_by_typing(
            self._dialog_parent(),
            title=title,
            heading=heading,
            detail="This is the last step. It cannot be undone.",
            action_label=action_label,
        )

    def _ensure_db(self) -> bool:
        if not self.db:
            self.logger.error("Database connection is not available")
            QMessageBox.critical(
                self.main_window,
                "Database Unavailable",
                "The database is not available. Please restart the application.",
            )
            return False
        return True

    def _refresh_views_after_data_reset(self) -> None:
        self._refresh_sales_report()
        item_master = getattr(self.main_window, "item_master_widget", None)
        if item_master is not None:
            try:
                item_master.load_items()
            except Exception as exc:
                self.logger.warning("Could not refresh item master: %s", exc)

        estimate_widget = getattr(self.main_window, "estimate_widget", None)
        if estimate_widget is not None:
            try:
                estimate_widget.clear_form(confirm=False)
            except Exception as exc:
                self.logger.warning("Could not clear estimate form: %s", exc)

    def _refresh_sales_report(self) -> None:
        report = getattr(self.main_window, "sales_report_widget", None)
        if report is not None and report.isVisible():
            report.refresh()
