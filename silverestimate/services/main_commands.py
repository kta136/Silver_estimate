"""Main window command helpers."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QCheckBox, QFileDialog, QInputDialog, QMessageBox


class _ItemCatalogExportWorker(QObject):
    finished = pyqtSignal(int)
    error = pyqtSignal(str)

    def __init__(self, *, db_path: str, file_path: str) -> None:
        super().__init__()
        self.db_path = db_path
        self.file_path = file_path

    def run(self) -> None:
        from silverestimate.services.item_catalog_transfer import (
            export_item_catalog_rows,
            load_item_catalog_rows_from_db_path,
        )

        try:
            rows = load_item_catalog_rows_from_db_path(self.db_path)
            count = export_item_catalog_rows(rows, self.file_path)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(count)


class MainCommands:
    """Encapsulate high-level commands triggered from the main window."""

    def __init__(
        self, main_window, db_manager, logger: Optional[logging.Logger] = None
    ) -> None:
        self.main_window = main_window
        self.db = db_manager
        self.logger = logger or logging.getLogger(__name__)
        self._catalog_export_thread = None
        self._catalog_export_worker = None

    def update_db(self, db_manager) -> None:
        self.db = db_manager
        self._catalog_export_thread = None
        self._catalog_export_worker = None

    # --- File commands --------------------------------------------------
    def save_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, "estimate_widget", None)
            if widget:
                widget.save_estimate()
            else:
                QMessageBox.information(
                    self.main_window, "Save", "Estimate view is not available."
                )
        except Exception as exc:
            self.logger.error("Save action failed: %s", exc, exc_info=True)
            QMessageBox.critical(self.main_window, "Save Error", str(exc))

    def print_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, "estimate_widget", None)
            if widget:
                widget.print_estimate()
            else:
                QMessageBox.information(
                    self.main_window, "Print", "Estimate view is not available."
                )
        except Exception as exc:
            self.logger.error("Print action failed: %s", exc, exc_info=True)
            QMessageBox.critical(self.main_window, "Print Error", str(exc))

    # --- Data management ------------------------------------------------
    def delete_all_data(self) -> None:
        if not self._ensure_db():
            return

        reply = QMessageBox.warning(
            self.main_window,
            "CONFIRM DELETE ALL DATA",
            "Are you absolutely sure you want to delete ALL data?\n"
            "This includes all items, estimates, silver bars, and lists.\n"
            "THIS ACTION CANNOT BE UNDONE.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        text, ok = QInputDialog.getText(
            self.main_window,
            "Type DELETE to Confirm",
            "This will permanently erase ALL data.\n\nType DELETE to proceed:",
        )
        if not ok or text.strip().upper() != "DELETE":
            QMessageBox.information(
                self.main_window, "Cancelled", "Delete all data cancelled."
            )
            return

        try:
            if not self.db.drop_tables():
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    "Failed to delete all data (dropping tables failed).",
                )
                return

            self.db.setup_database()
            self._refresh_views_after_data_reset()
            QMessageBox.information(
                self.main_window, "Success", "All data has been deleted successfully."
            )
        except Exception as exc:
            self.logger.error("Error deleting all data: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Failed to delete all data: {exc}",
            )

    def restore_item_catalog(self) -> None:
        """Restore a native Silver Estimate item catalog backup."""
        if not self._ensure_db():
            return

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
            return

        message_box = QMessageBox(self.main_window)
        message_box.setIcon(QMessageBox.Question)
        message_box.setWindowTitle("Restore Item Catalog Backup")
        message_box.setText(
            "This restores a native Silver Estimate item catalog backup."
        )
        message_box.setInformativeText(
            "Existing item codes from the file will be updated.\n"
            "New item codes from the file will be added.\n"
            "Items not present in the file will be kept unless you enable full replace.\n\n"
            "If full replace removes item codes that older estimates still reference,\n"
            "those estimate rows will lose their item-code link.\n\n"
            "Continue?"
        )
        replace_checkbox = QCheckBox(
            "Replace the entire current item master with this backup"
        )
        message_box.setCheckBox(replace_checkbox)
        message_box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        message_box.setDefaultButton(QMessageBox.Cancel)
        if message_box.exec_() != QMessageBox.Yes:
            return
        replace_existing = replace_checkbox.isChecked()

        try:
            summary = import_item_catalog(
                self.db,
                file_path,
                replace_existing=replace_existing,
            )
        except Exception as exc:
            self.logger.error("Item catalog restore failed: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Restore Failed",
                str(exc),
            )
            return

        item_master = getattr(self.main_window, "item_master_widget", None)
        if item_master is not None and item_master.isVisible():
            try:
                item_master.load_items()
            except Exception as exc:
                self.logger.warning(
                    "Could not refresh item master after import: %s", exc
                )

        QMessageBox.information(
            self.main_window,
            "Restore Complete",
            "Item catalog backup restored successfully.\n\n"
            f"Total records: {summary['total']}\n"
            f"Inserted: {summary['inserted']}\n"
            f"Updated: {summary['updated']}\n"
            f"Deleted: {summary['deleted']}",
        )

    def create_item_catalog_backup(self) -> None:
        """Create a native Silver Estimate item catalog backup."""
        if not self._ensure_db():
            return

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
            return

        db_path = getattr(self.db, "temp_db_path", None)
        if not isinstance(db_path, str) or not db_path:
            QMessageBox.critical(
                self.main_window,
                "Export Failed",
                "Temporary database path not available.",
            )
            return

        self._start_item_catalog_export_worker(
            db_path=db_path,
            file_path=ensure_catalog_file_suffix(file_path),
        )

    def delete_all_estimates(self) -> None:
        if not self._ensure_db():
            return

        reply = QMessageBox.warning(
            self.main_window,
            "Confirm Delete All Estimates",
            "Are you absolutely sure you want to delete ALL estimates?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            if self.db.delete_all_estimates():
                QMessageBox.information(
                    self.main_window,
                    "Success",
                    "All estimates have been deleted successfully.",
                )
                widget = getattr(self.main_window, "estimate_widget", None)
                if widget:
                    try:
                        widget.clear_form(confirm=False)
                    except Exception as form_exc:
                        self.logger.error(
                            "Error clearing estimate form: %s", form_exc, exc_info=True
                        )
            else:
                QMessageBox.critical(
                    self.main_window,
                    "Error",
                    "Failed to delete all estimates (database error).",
                )
        except Exception as exc:
            self.logger.error("Error deleting all estimates: %s", exc, exc_info=True)
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"An unexpected error occurred: {exc}",
            )

    def _start_item_catalog_export_worker(self, *, db_path: str, file_path: str) -> None:
        if getattr(self, "_catalog_export_thread", None) is not None:
            QMessageBox.information(
                self.main_window,
                "Catalog Backup",
                "A catalog backup is already in progress.",
            )
            return

        worker = _ItemCatalogExportWorker(db_path=db_path, file_path=file_path)
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

    def _on_item_catalog_export_finished(self, exported_count: int) -> None:
        QMessageBox.information(
            self.main_window,
            "Export Successful",
            "Item catalog backup created successfully.\n\n"
            f"Records written: {exported_count}",
        )

    def _on_item_catalog_export_failed(self, message: str) -> None:
        QMessageBox.critical(self.main_window, "Export Failed", message)

    def _clear_item_catalog_export_worker(self) -> None:
        self._catalog_export_worker = None
        self._catalog_export_thread = None

    # --- Helpers --------------------------------------------------------
    def _ensure_db(self) -> bool:
        if not self.db:
            self.logger.error("Database connection is not available")
            QMessageBox.critical(
                self.main_window,
                "Error",
                "Database connection is not available. Please restart the application.",
            )
            return False
        return True

    def _refresh_views_after_data_reset(self) -> None:
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
