"""Keyboard-first silver bar workspace; saved lists reserve bars automatically."""

from __future__ import annotations

import csv
import logging
from typing import Any

from PySide6.QtCore import QEvent, QObject, QPoint, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QToolButton,
)

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.persistence.repository_results import RepositoryResult

from .models.silver_bar_entry_model import SilverBarEntryModel
from .modern_components import TableEmptyStateOverlay
from .silver_bar_list_print_controller import SilverBarListPrintController
from .silver_bar_load_controller import SilverBarLoadController
from .silver_bar_management_ui import SilverBarManagementUiBuilder
from .silver_bar_optimal_dialog import OptimalListDialog
from .silver_bar_optimization_controller import SilverBarOptimizationController


class SilverBarDialog(QDialog):
    weight_search_edit: QLineEdit
    suggestions_table: QTableView
    suggestions_model: SilverBarEntryModel
    suggestions_panel: QFrame
    suggestions_hint: QLabel
    list_bars_table: QTableView
    list_bars_model: SilverBarEntryModel
    list_info_label: QLabel
    status_label: QLabel
    list_totals_label: QLabel
    new_list_button: QPushButton
    open_list_button: QPushButton
    edit_note_button: QPushButton
    print_list_button: QPushButton
    generate_optimal_button: QPushButton
    retry_issue_button: QPushButton
    load_more_button: QPushButton
    more_button: QToolButton
    export_action: QAction
    clear_action: QAction
    delete_action: QAction
    _empty_state: TableEmptyStateOverlay

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.current_list_id: int | None = None
        self.snapshot: BarListSnapshot | None = None
        self.draft_note = ""
        self._loading_list = False
        self._busy = False
        self._closed = False
        self._load_controller = SilverBarLoadController(self)
        self._list_print_controller = SilverBarListPrintController(self)
        self._optimization_controller = SilverBarOptimizationController(self)
        SilverBarManagementUiBuilder(self).init_ui()
        self.create_new_list()
        QTimer.singleShot(0, self.focus_weight)

    @property
    def editable(self) -> bool:
        return (
            not self._loading_list
            and not self._busy
            and not (self.snapshot and self.snapshot.issued)
        )

    def set_status(self, text: str, *, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(text)
        self.status_label.setWordWrap(error)
        self.status_label.setProperty("error", error)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _update_actions(self) -> None:
        loaded = self.snapshot is not None and not self._loading_list
        has_bars = loaded and bool(self.snapshot.bars if self.snapshot else ())
        for button in (
            self.new_list_button,
            self.open_list_button,
            self.generate_optimal_button,
        ):
            button.setEnabled(not self._busy)
        self.weight_search_edit.setEnabled(self.editable)
        self.edit_note_button.setEnabled(self.editable)
        self.print_list_button.setEnabled(has_bars and not self._busy)
        self.print_list_button.setText(
            "Reprint" if self.snapshot and self.snapshot.issued else "Print && new"
        )
        self.print_list_button.setToolTip(
            "Reprint issued list · Ctrl+P"
            if self.snapshot and self.snapshot.issued
            else "Print, issue, and start a new list · Ctrl+P"
        )
        self.clear_action.setEnabled(has_bars and self.editable)
        self.delete_action.setEnabled(loaded and self.editable)
        self.export_action.setEnabled(has_bars and not self._busy)
        self.retry_issue_button.setVisible(
            self._list_print_controller.printed is not None
        )
        self.retry_issue_button.setEnabled(self.editable)

    def focus_weight(self, *, announce: bool = False) -> None:
        if self._closed:
            return
        if self.weight_search_edit.isEnabled():
            self.weight_search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
            self._load_controller.schedule_search(
                self.weight_search_edit.text(), announce=announce
            )
        else:
            self.list_bars_table.setFocus()

    def run_shortcut(self, callback) -> None:
        modal = QApplication.activeModalWidget()
        if modal is None or modal is self:
            callback()

    def position_suggestions(self) -> None:
        origin = self.weight_search_edit.mapTo(
            self, QPoint(0, self.weight_search_edit.height() + 2)
        )
        rows = min(4, max(1, self.suggestions_model.rowCount()))
        height = self.suggestions_table.horizontalHeader().height() + rows * 30 + 38
        self.suggestions_panel.setGeometry(
            self.list_bars_table.x(), origin.y(), self.list_bars_table.width(), height
        )
        self.suggestions_panel.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "suggestions_panel") and self.suggestions_panel.isVisible():
            QTimer.singleShot(0, self.position_suggestions)

    def create_new_list(self) -> None:
        if self._busy:
            return
        self._load_controller.list_runner.cancel()
        self._load_controller.cancel_search()
        self.current_list_id = None
        self.snapshot = None
        self.draft_note = ""
        self._loading_list = False
        self._list_print_controller.invalidate()
        self.weight_search_edit.clear()
        self.list_bars_model.clear_rows()
        self.list_info_label.setText("New list")
        self.list_info_label.setToolTip(
            "Saved automatically when you add the first bar"
        )
        self.update_note_hint("")
        self.list_totals_label.setText(
            "0 bars     Total weight  0.00 g     Total fine  0.00 g"
        )
        self.load_more_button.hide()
        self.set_status("Enter Add · Tab List · Delete Remove · F1 Help")
        self._update_actions()
        self.focus_weight()

    def apply_snapshot(
        self, snapshot: BarListSnapshot, *, select_bar_id: int | None = None
    ) -> None:
        self._load_controller.list_runner.cancel()
        self._loading_list = False
        self.snapshot = snapshot
        self.current_list_id = snapshot.list_id
        if (
            self._list_print_controller.printed
            and self._list_print_controller.printed.signature != snapshot.signature
        ):
            self._list_print_controller.invalidate()
        self.list_info_label.setText(
            str(snapshot.details["list_identifier"])
            + (" · Issued" if snapshot.issued else " · Active")
        )
        self.update_note_hint(str(snapshot.details.get("list_note") or ""))
        self.list_info_label.setToolTip(
            "Issued list · Read only" if snapshot.issued else "Saved automatically"
        )
        selected_row = next(
            (
                i
                for i, bar in enumerate(snapshot.bars)
                if bar["bar_id"] == select_bar_id
            ),
            0,
        )
        shown = min(len(snapshot.bars), max(1500, selected_row + 1))
        self.list_bars_model.set_rows(
            list(snapshot.bars[:shown]), total_count=len(snapshot.bars)
        )
        if shown:
            self.list_bars_table.selectRow(selected_row)
            self.list_bars_table.scrollTo(self.list_bars_model.index(selected_row, 0))
        self.load_more_button.setVisible(shown < len(snapshot.bars))
        self.list_totals_label.setText(
            f"{len(snapshot.bars)} bars     Total weight  {fixed_decimal(snapshot.weight, 2)} g"
            f"     Total fine  {fixed_decimal(snapshot.fine_weight, 2)} g"
        )
        self._update_actions()

    def load_more_list_rows(self) -> None:
        if self.snapshot is None:
            return
        shown = self.list_bars_model.rowCount()
        self.list_bars_model.append_rows(
            list(self.snapshot.bars[shown : shown + 1500]),
            total_count=len(self.snapshot.bars),
        )
        self.load_more_button.setVisible(
            self.list_bars_model.rowCount() < len(self.snapshot.bars)
        )

    def accept_change(
        self,
        result: RepositoryResult[BarListSnapshot],
        *,
        select_bar_id: int | None = None,
    ) -> bool:
        if result.failure:
            self.set_status(result.failure.message, error=True)
            return False
        self.apply_snapshot(result.unwrap(), select_bar_id=select_bar_id)
        return True

    def add_current_match(self, *args: Any) -> None:
        if (
            not self.editable
            or self._load_controller.dismissed
            or not self.suggestions_panel.isVisible()
            or self._load_controller.prefix is None
            or self._load_controller.ready_prefix != self._load_controller.prefix
        ):
            return
        row = self.suggestions_table.currentIndex().row()
        bar_id = self.suggestions_model.bar_id_at(row)
        if bar_id is None:
            return
        bar = self.suggestions_model.row_payload(row)
        self._busy = True
        try:
            result = self.db_manager.add_bars_to_list(
                [bar_id], self.current_list_id, self.draft_note
            )
            self._busy = False
            if self.accept_change(result, select_bar_id=bar_id):
                self.weight_search_edit.clear()
                self._load_controller.schedule_search("", announce=False)
                weight = fixed_decimal(bar["weight"], 2) if bar else ""
                self.set_status(
                    f"Added {weight} g · Saved. Choose a bar or filter by weight."
                )
            else:
                self._load_controller.cancel_search(dismiss=False)
        finally:
            self._busy = False
            self._update_actions()
            self.weight_search_edit.setFocus()

    def remove_selected_from_list(self) -> None:
        if not self.editable or self.current_list_id is None:
            return
        indexes = self.list_bars_table.selectionModel().selectedRows()
        ids = [self.list_bars_model.bar_id_at(index.row()) for index in indexes]
        if not ids:
            return
        row = min(index.row() for index in indexes)
        if self.accept_change(
            self.db_manager.remove_list_bars(self.current_list_id, ids)
        ):
            if self.list_bars_model.rowCount():
                self.list_bars_table.selectRow(
                    min(row, self.list_bars_model.rowCount() - 1)
                )
            self._load_controller.cancel_search()
            self.set_status(
                f"Removed {len(ids)} bar(s) · Saved. Bars are available again."
            )

    def open_list(self, list_id: int) -> None:
        if self._busy:
            return
        self._list_print_controller.invalidate()
        self.weight_search_edit.clear()
        self.snapshot = None
        self.list_bars_model.clear_rows()
        self.list_info_label.setText("Opening list…")
        self.list_info_label.setToolTip("Loading saved list")
        self.update_note_hint("")
        self.list_totals_label.setText("Loading totals…")
        self.load_more_button.hide()
        self._load_controller.load_list(list_id)

    def open_saved_list(self) -> None:
        self.open_history()

    def update_note_hint(self, note: str) -> None:
        self.edit_note_button.setText("Note*" if note else "Note")
        self.edit_note_button.setToolTip(f"{note or 'No note'}\nEdit list note · F2")
        self.edit_note_button.setAccessibleName(f"List note: {note or 'No note'}")

    def edit_list_note(self) -> None:
        if not self.editable:
            return
        existing = (
            self.snapshot.details.get("list_note") if self.snapshot else self.draft_note
        )
        note, ok = QInputDialog.getText(
            self, "List note", "Note:", QLineEdit.EchoMode.Normal, str(existing or "")
        )
        if ok:
            if self.current_list_id is None:
                self.draft_note = note.strip()
                self.update_note_hint(self.draft_note)
            else:
                self.accept_change(
                    self.db_manager.save_active_list_note(
                        self.current_list_id, note.strip()
                    )
                )
        self.focus_weight()

    def clear_current_list(self) -> None:
        if self.current_list_id is None or not self.editable:
            return
        if (
            QMessageBox.question(
                self,
                "Clear list",
                "Remove all bars from this list? They will become available again.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        if self.accept_change(self.db_manager.remove_list_bars(self.current_list_id)):
            self.set_status("List cleared · Saved.")
        self.focus_weight()

    def delete_selected_list(self) -> None:
        if self.current_list_id is None or not self.editable:
            return
        if (
            QMessageBox.question(
                self,
                "Delete list",
                "Delete this list and release its bars?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        result = self.db_manager.delete_active_list(self.current_list_id)
        if result.failure:
            self.set_status(result.failure.message, error=True)
        else:
            self.create_new_list()
            self.set_status("List deleted. Its bars are available again.")

    def export_current_list_to_csv(self) -> None:
        if self.snapshot is None or self._busy:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export list",
            f"{self.snapshot.details['list_identifier']}.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            snapshot = self.db_manager.get_silver_bar_list_snapshot(
                self.snapshot.list_id
            )
            with open(path, "w", newline="", encoding="utf-8-sig") as output:
                writer = csv.writer(output)
                writer.writerow(
                    ["Bar ID", "Voucher", "Weight (g)", "Purity (%)", "Fine weight (g)"]
                )
                for bar in snapshot.bars:
                    voucher = str(bar["estimate_voucher_no"])
                    if voucher.startswith(("=", "+", "-", "@", "\t", "\r")):
                        voucher = "'" + voucher
                    writer.writerow(
                        [
                            bar["bar_id"],
                            voucher,
                            *(
                                fixed_decimal(bar[key], 2)
                                for key in ("weight", "purity", "fine_weight")
                            ),
                        ]
                    )
            self.set_status("List exported.")
        except Exception as exc:
            self.set_status(f"Export failed: {exc}", error=True)

    def print_selected_list(self) -> None:
        self._list_print_controller.print_selected_list()

    def preview_selected_list(self) -> None:
        self._list_print_controller.print_selected_list(preview=True)

    def retry_issue(self) -> None:
        self._list_print_controller.complete_issue()

    def generate_optimal_list(self) -> None:
        if not self._busy:
            self._optimization_controller.generate_optimal_list(OptimalListDialog)

    def open_history(self) -> None:
        if self._busy:
            return
        from .silver_bar_history import SilverBarHistoryDialog

        history = SilverBarHistoryDialog(self.db_manager, self)
        history.exec()
        chosen = history.selected_list_id
        history.deleteLater()
        if chosen is not None:
            self.open_list(chosen)
        elif self.current_list_id is not None:
            self.open_list(self.current_list_id)
        else:
            self.focus_weight()

    def show_keyboard_help(self) -> None:
        QMessageBox.information(
            self,
            "Silver bar keyboard shortcuts",
            "Available bars appear automatically. Type a weight to filter (optional).\n↑/↓ choose → Enter add and save\n\nTab: Current list\nDelete: Remove selected list rows and save\nCtrl+F: Available bars / weight filter\nCtrl+N: New list\nCtrl+O / Ctrl+H: Lists and bar history\nF2: Edit note\nCtrl+P: Print, issue, and start a new list\nCtrl+Shift+P: Preview / PDF / printer settings\nAlt+I: Retry issuing after a print without printing again\nCtrl+G: Generate optimal list\nAlt+M: More actions\nEsc: Dismiss suggestions / clear weight / close",
        )

    def _handle_weight_focus(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.FocusIn and self._load_controller.dismissed:
            self._load_controller.schedule_search(
                self.weight_search_edit.text(), announce=False
            )
        elif event.type() == QEvent.Type.FocusOut:
            self._load_controller.cancel_search()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.weight_search_edit:
            self._handle_weight_focus(event)
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            key = event.key()
            if watched is self.weight_search_edit:
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    if not event.isAutoRepeat():
                        self._load_controller.enter()
                    return True
                if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                    self._load_controller.move_match(
                        1 if key == Qt.Key.Key_Down else -1
                    )
                    return True
                if key == Qt.Key.Key_Tab and not event.modifiers():
                    self._load_controller.cancel_search()
                    self.list_bars_table.setFocus(Qt.FocusReason.TabFocusReason)
                    return True
            if watched is self.list_bars_table:
                if key == Qt.Key.Key_Delete:
                    if not event.isAutoRepeat():
                        self.remove_selected_from_list()
                    return True
                if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                    self.focus_weight()
                    return True
                if (
                    key == Qt.Key.Key_Down
                    and self.list_bars_table.currentIndex().row()
                    == self.list_bars_model.rowCount() - 1
                ):
                    self.load_more_list_rows()
        return super().eventFilter(watched, event)

    def accept(self) -> None:
        # A stray Enter must never activate QDialog's default close behavior.
        return

    def reject(self) -> None:
        if self._busy:
            super().reject()
            return
        if (
            self.suggestions_panel.isVisible()
            or self._load_controller.loading
            or self._load_controller.timer.isActive()
        ):
            self._load_controller.cancel_search()
        elif self.weight_search_edit.text():
            with QSignalBlocker(self.weight_search_edit):
                self.weight_search_edit.clear()
            self._load_controller.cancel_search()
        else:
            super().reject()

    def done(self, result: int) -> None:
        if not self._closed:
            self._closed = True
            self._load_controller.shutdown()
            self._list_print_controller.shutdown()
        super().done(result)

    def closeEvent(self, event) -> None:
        self.done(QDialog.DialogCode.Rejected)
        event.accept()
