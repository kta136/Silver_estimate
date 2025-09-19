"""Main window command helpers."""
from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtWidgets import QMessageBox, QInputDialog

from silverestimate.services.auth_service import perform_data_wipe


class MainCommands:
    """Encapsulate high-level commands triggered from the main window."""

    def __init__(self, main_window, db_manager, logger: Optional[logging.Logger] = None) -> None:
        self.main_window = main_window
        self.db = db_manager
        self.logger = logger or logging.getLogger(__name__)

    def update_db(self, db_manager) -> None:
        self.db = db_manager

    # --- File commands --------------------------------------------------
    def save_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, 'estimate_widget', None)
            if widget:
                widget.save_estimate()
            else:
                QMessageBox.information(self.main_window, "Save", "Estimate view is not available.")
        except Exception as exc:
            self.logger.error("Save action failed: %s", exc, exc_info=True)
            QMessageBox.critical(self.main_window, "Save Error", str(exc))

    def print_estimate(self) -> None:
        try:
            widget = getattr(self.main_window, 'estimate_widget', None)
            if widget:
                widget.print_estimate()
            else:
                QMessageBox.information(self.main_window, "Print", "Estimate view is not available.")
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
            QMessageBox.information(self.main_window, "Cancelled", "Delete all data cancelled.")
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

    def import_items(self) -> None:
        """Show the item import dialog and orchestrate the import workflow."""
        if not self._ensure_db():
            return

        from silverestimate.ui.item_import_dialog import ItemImportDialog
        from silverestimate.ui.item_import_manager import ItemImportManager
        from PyQt5.QtCore import QThread

        dialog = ItemImportDialog(self.main_window)
        manager = ItemImportManager(self.db)

        worker_thread = QThread(self.main_window)
        manager.moveToThread(worker_thread)
        worker_thread.start()

        dialog.importStarted.connect(manager.import_from_file)
        manager.progress_updated.connect(dialog.update_progress)
        manager.status_updated.connect(dialog.update_status)
        manager.import_finished.connect(dialog.import_finished)
        dialog.rejected.connect(manager.cancel_import)
        dialog.rejected.connect(worker_thread.quit)

        try:
            dialog.exec_()
        finally:
            try:
                worker_thread.quit()
                worker_thread.wait(2000)
            except Exception:
                pass

        item_master = getattr(self.main_window, 'item_master_widget', None)
        if item_master is not None and item_master.isVisible():
            try:
                item_master.load_items()
            except Exception as exc:
                self.logger.warning("Could not refresh item master after import: %s", exc)

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
                    self.main_window, "Success", "All estimates have been deleted successfully."
                )
                widget = getattr(self.main_window, 'estimate_widget', None)
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
        item_master = getattr(self.main_window, 'item_master_widget', None)
        if item_master is not None:
            try:
                item_master.load_items()
            except Exception as exc:
                self.logger.warning("Could not refresh item master: %s", exc)

        estimate_widget = getattr(self.main_window, 'estimate_widget', None)
        if estimate_widget is not None:
            try:
                estimate_widget.clear_form(confirm=False)
            except Exception as exc:
                self.logger.warning("Could not clear estimate form: %s", exc)
