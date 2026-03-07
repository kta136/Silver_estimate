"""Lifecycle workflows for silver-bar management lists."""

from __future__ import annotations

import logging

from PyQt5.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from ._host_proxy import HostProxy


class SilverBarListLifecycleController(HostProxy):
    """Handle create/edit/delete/issue flows for silver-bar lists."""

    def create_new_list(self):
        logging.getLogger(__name__).info("Creating new list...")
        note, ok = QInputDialog.getText(
            self.host,
            "Create New List",
            "Enter a note for the new list:",
            QLineEdit.Normal,
        )
        if not ok:
            return
        new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
        if not new_list_id:
            QMessageBox.critical(self.host, "Error", "Failed to create new list.")
            return
        QMessageBox.information(self.host, "Success", "New list created.")
        self.load_lists()
        index = self.list_combo.findData(new_list_id)
        if index >= 0:
            self.list_combo.setCurrentIndex(index)

    def _create_list_from_selection(self):
        selected = self._selected_rows(self.available_bars_table)
        if not selected:
            QMessageBox.warning(
                self.host,
                "Selection",
                "Select one or more available bars first.",
            )
            return
        note, ok = QInputDialog.getText(
            self.host,
            "Create List from Selection",
            "Enter a note for the new list:",
            QLineEdit.Normal,
        )
        if not ok:
            return
        new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
        if not new_list_id:
            QMessageBox.critical(self.host, "Error", "Failed to create new list.")
            return
        self.load_lists()
        idx = self.list_combo.findData(new_list_id)
        if idx >= 0:
            self.list_combo.setCurrentIndex(idx)
        bar_ids = self._bar_ids_from_indexes(self.available_bars_table, selected)
        added_count, failed = self._run_with_wait_cursor(
            lambda: self._bulk_assign_to_list(bar_ids, new_list_id),
            enable_log="Could not enable wait cursor for list creation: %s",
            restore_log="Could not restore cursor after list creation: %s",
        )
        self.load_available_bars()
        self.load_bars_in_selected_list()
        if added_count:
            QMessageBox.information(
                self.host,
                "Success",
                f"Created list and added {added_count} bar(s).",
            )
        if failed:
            QMessageBox.warning(
                self.host,
                "Partial",
                f"Failed to add bars: {', '.join(failed)}",
            )

    def edit_list_note(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(
                self.host,
                "Error",
                "Could not retrieve current list details.",
            )
            return

        current_note = details["list_note"] or ""
        new_note, ok = QInputDialog.getText(
            self.host,
            "Edit List Note",
            f"Enter new note for list '{details['list_identifier']}':",
            QLineEdit.Normal,
            current_note,
        )

        if not ok or new_note == current_note:
            return

        if not self.db_manager.update_silver_bar_list_note(
            self.current_list_id,
            new_note,
        ):
            QMessageBox.critical(self.host, "Error", "Failed to update list note.")
            return

        QMessageBox.information(self.host, "Success", "List note updated.")
        details_label = getattr(self, "list_details_label", None)
        if details_label is not None:
            details_label.setText(
                f"Selected List: {details['list_identifier']} (Note: {new_note or 'N/A'})"
            )
        index = self.list_combo.findData(self.current_list_id)
        if index >= 0:
            list_date = (
                details["creation_date"].split()[0]
                if "creation_date" in details.keys() and details["creation_date"]
                else ""
            )
            display_text = f"{details['list_identifier']} ({list_date})"
            if new_note:
                display_text += f" - {new_note}"
            self.list_combo.setItemText(index, display_text)

    def delete_selected_list(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = (
            details["list_identifier"] if details else f"ID {self.current_list_id}"
        )

        reply = QMessageBox.warning(
            self.host,
            "Confirm Delete",
            f"Are you sure you want to delete list '{list_name}'?\n"
            "All bars currently assigned to this list will be unassigned (status set to 'In Stock').\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply != QMessageBox.Yes:
            return

        success, message = self.db_manager.delete_silver_bar_list(self.current_list_id)
        if success:
            QMessageBox.information(
                self.host,
                "Success",
                f"List '{list_name}' deleted successfully.",
            )
            self.load_lists()
            return
        QMessageBox.critical(
            self.host,
            "Error",
            f"Failed to delete list: {message}",
        )

    def mark_list_as_issued(self):
        if self.current_list_id is None:
            QMessageBox.warning(self.host, "Error", "No list selected.")
            return

        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = (
            details["list_identifier"] if details else f"ID {self.current_list_id}"
        )

        reply = QMessageBox.question(
            self.host,
            "Mark as Issued",
            f"Are you sure you want to mark list '{list_name}' as issued?\n\n"
            "This will:\n"
            "• Remove the list from the active lists menu\n"
            "• Move it to Silver Bar History\n"
            "• Set all bars in the list to 'Issued' status\n\n"
            "This action can be reversed from the History window.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply != QMessageBox.Yes:
            return

        try:
            success = self.db_manager.mark_silver_bar_list_as_issued(
                self.current_list_id
            )
            if not success:
                raise RuntimeError("Failed to mark the selected list as issued.")

            QMessageBox.information(
                self.host,
                "Success",
                f"List '{list_name}' has been marked as issued.\n"
                "It has been moved to Silver Bar History.",
            )

            self.load_lists()
            self.load_available_bars()

        except Exception as exc:
            self.logger.warning(
                "Failed to mark list %s as issued: %s",
                self.current_list_id,
                exc,
                exc_info=True,
            )
            QMessageBox.critical(
                self.host,
                "Error",
                f"Failed to mark list as issued: {exc}",
            )

    def _selected_rows(self, table):
        selection_model = table.selectionModel()
        return selection_model.selectedRows() if selection_model is not None else []
