"""Keyboard-first silver bar workspace; saved lists reserve bars automatically."""

from __future__ import annotations

import csv
import logging
from typing import Any

from PySide6.QtCore import QEvent, QObject, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QToolButton,
    QWidget,
)

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.persistence.repository_results import RepositoryResult

from .display_formatting import count_label, format_display_date
from .message_dialogs import ask, ask_text, confirm_destructive
from .models.silver_bar_entry_model import SilverBarEntryModel
from .modern_components import TableEmptyStateOverlay
from .screen_widgets import KeyHintButton, StatusPill, TotalsStrip, repolish
from .silver_bar_list_print_controller import SilverBarListPrintController
from .silver_bar_load_controller import SilverBarLoadController
from .silver_bar_management_ui import (
    COMPACT_HEADER_WIDTH,
    COMPACT_TABLE_WIDTH,
    SilverBarManagementUiBuilder,
)
from .silver_bar_optimal_dialog import OptimalListDialog
from .silver_bar_optimization_controller import SilverBarOptimizationController
from .silver_bar_shortcuts_dialog import SilverBarShortcutsDialog


class SilverBarDialog(QDialog):
    weight_search_edit: QLineEdit
    suggestions_table: QTableView
    suggestions_model: SilverBarEntryModel
    suggestions_panel: QFrame
    suggestions_hint: QLabel
    list_bars_table: QTableView
    list_bars_model: SilverBarEntryModel
    list_info_label: QLabel
    list_state_pill: StatusPill
    list_count_label: QLabel
    available_count_label: QLabel
    available_card: QFrame
    available_empty: QWidget
    available_empty_title: QLabel
    available_empty_body: QLabel
    show_all_bars_button: QPushButton
    find_in_history_button: QPushButton
    list_card: QFrame
    list_hint: QLabel
    issued_banner: QFrame
    issued_banner_label: QLabel
    reopen_button: QPushButton
    header_actions: QWidget
    header_top_row: QHBoxLayout
    header_bottom_row: QHBoxLayout
    header_bottom: QWidget
    status_label: QLabel
    list_totals_label: TotalsStrip
    new_list_button: QPushButton
    open_list_button: QPushButton
    edit_note_button: KeyHintButton
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
        issued = bool(self.snapshot and self.snapshot.issued)
        self.print_list_button.setEnabled(has_bars and not self._busy)
        self.print_list_button.setText("Reprint" if issued else "Print && Issue")
        self.issued_banner.setVisible(issued)
        self.reopen_button.setEnabled(issued and not self._busy)
        self.available_card.setVisible(not issued)
        self.list_hint.setText(
            "Read only" if issued else "Del remove selected    Shift+Tab available bars"
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
        """Available bars live in their own pane, so there is nothing to place."""

    def set_available_message(
        self, title: str, body: str = "", *, actions: bool = False
    ) -> None:
        self.available_empty_title.setText(title)
        self.available_empty_body.setText(body)
        self.available_empty_body.setVisible(bool(body))
        self.show_all_bars_button.setVisible(actions)
        self.find_in_history_button.setVisible(actions)

    def set_available_count(self, text: str) -> None:
        self.available_count_label.setText(text)

    def show_all_available(self) -> None:
        with QSignalBlocker(self.weight_search_edit):
            self.weight_search_edit.clear()
        self.focus_weight(announce=True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange_header()
        # Two narrow panes drop the bar number before they need to scroll.
        narrow = self.width() < COMPACT_TABLE_WIDTH
        for table in (self.suggestions_table, self.list_bars_table):
            table.setColumnHidden(4, narrow)

    def _arrange_header(self) -> None:
        if not hasattr(self, "header_actions"):
            return
        compact = self.width() < COMPACT_HEADER_WIDTH
        target = self.header_bottom_row if compact else self.header_top_row
        if target.indexOf(self.header_actions) >= 0:
            return
        source = self.header_top_row if compact else self.header_bottom_row
        source.removeWidget(self.header_actions)
        target.addWidget(self.header_actions)
        self.header_bottom.setVisible(compact)

    def _set_header(self, title: str, state: str, state_text: str) -> None:
        self.list_info_label.setText(title)
        self.list_state_pill.set_state(state, state_text)
        self.list_state_pill.setVisible(bool(state_text))

    def _set_totals(self, bars: int, weight, fine) -> None:
        weight_text = f"{fixed_decimal(weight, 2)} g"
        fine_text = f"{fixed_decimal(fine, 2)} g"
        self.list_totals_label.set_values(
            (str(bars), weight_text, fine_text),
            empty=bars == 0,
            summary=(
                f"{count_label(bars, 'bar')} · Total weight {weight_text} · "
                f"Total fine {fine_text}"
            ),
        )
        self.list_totals_label.set_accent(bars > 0)

    def _set_card_focus(self, frame: QFrame, focused: bool) -> None:
        if frame.property("focused") != focused:
            frame.setProperty("focused", focused)
            repolish(frame)

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
        self._set_header("New List", "new", "Not saved yet")
        self.list_info_label.setToolTip(
            "Saved automatically when you add the first bar"
        )
        self.list_count_label.setText("0 bars")
        self.update_note_hint("")
        self._set_totals(0, 0, 0)
        self.load_more_button.hide()
        self.set_status("")
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
        self._set_header(
            str(snapshot.details["list_identifier"]),
            "issued" if snapshot.issued else "active",
            "Issued" if snapshot.issued else "Active",
        )
        created = format_display_date(snapshot.details.get("creation_date"))
        issued = format_display_date(snapshot.details.get("issued_date"))
        meta = [count_label(len(snapshot.bars), "bar")]
        if created:
            meta.append(f"Created {created}")
        if issued:
            meta.append(f"Issued {issued}")
        self.list_count_label.setText(" · ".join(meta))
        self.issued_banner_label.setText(
            f"This list was issued on {issued or 'an earlier date'} and is read "
            "only. Its bars have left stock. Reopen it to make changes."
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
        self._set_totals(len(snapshot.bars), snapshot.weight, snapshot.fine_weight)
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
                f"Removed {count_label(len(ids), 'bar')} · Saved. Available again."
            )

    def open_list(self, list_id: int) -> None:
        if self._busy:
            return
        self._list_print_controller.invalidate()
        self.weight_search_edit.clear()
        self.snapshot = None
        self.list_bars_model.clear_rows()
        self._set_header("Opening list…", "new", "")
        self.list_info_label.setToolTip("Loading saved list")
        self.list_count_label.setText("Loading…")
        self.update_note_hint("")
        self.list_totals_label.set_values(
            ("…", "…", "…"), empty=True, summary="Loading totals…"
        )
        self.load_more_button.hide()
        self._load_controller.load_list(list_id)

    def open_saved_list(self) -> None:
        self.open_history()

    def update_note_hint(self, note: str) -> None:
        shown = note if len(note) <= 40 else note[:39] + "…"
        self.edit_note_button.setText((shown or "+ Add Note").replace("&", "&&"))
        self.edit_note_button.setToolTip(f"{note or 'No note'}\nEdit list note · F2")
        self.edit_note_button.setAccessibleName(f"List note: {note or 'No note'}")

    def reopen_issued_list(self) -> None:
        snapshot = self.snapshot
        if self._busy or snapshot is None or not snapshot.issued:
            return
        if not ask(
            self,
            title="Reopen Issued List",
            heading=f"Reopen {snapshot.details['list_identifier']} for editing?",
            detail="The bars stay in this list, and the list becomes active again.",
            action_label="Reopen List",
            default_to_cancel=True,
        ):
            return
        if not self.db_manager.reactivate_silver_bar_list(snapshot.list_id):
            self.set_status(
                "Could not reopen this list. Open History and try again.", error=True
            )
            return
        self.open_list(snapshot.list_id)

    def edit_list_note(self) -> None:
        if not self.editable:
            return
        existing = (
            self.snapshot.details.get("list_note") if self.snapshot else self.draft_note
        )
        note = ask_text(
            self,
            title="List Note",
            heading="Note for this list",
            detail="Shown beside the list number and printed on the list.",
            text=str(existing or ""),
            placeholder="Who the bars are for, or what they are for",
            action_label="Save Note",
        )
        if note is not None:
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
        if not confirm_destructive(
            self,
            title="Clear List",
            heading="Remove every bar from this list?",
            detail="The bars become available again. The list itself is kept.",
            action_label="Clear List",
        ):
            return
        if self.accept_change(self.db_manager.remove_list_bars(self.current_list_id)):
            self.set_status("List cleared · Saved.")
        self.focus_weight()

    def delete_selected_list(self) -> None:
        if self.current_list_id is None or not self.editable:
            return
        if not confirm_destructive(
            self,
            title="Delete List",
            heading="Delete this list?",
            detail="Its bars become available again. This cannot be undone.",
            action_label="Delete List",
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
        dialog = SilverBarShortcutsDialog(self)
        dialog.exec()
        dialog.deleteLater()

    def _handle_weight_focus(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.FocusIn:
            self._set_card_focus(self.available_card, True)
            if self._load_controller.dismissed:
                self._load_controller.schedule_search(
                    self.weight_search_edit.text(), announce=False
                )
        elif event.type() == QEvent.Type.FocusOut:
            self._set_card_focus(self.available_card, False)
            self._load_controller.cancel_search()

    def _track_panes(self, watched: QObject, event: QEvent) -> None:
        kind = event.type()
        if watched is getattr(self, "suggestions_panel", None) and kind in (
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            self.available_empty.setVisible(kind == QEvent.Type.Hide)
        elif watched is getattr(self, "list_bars_table", None) and kind in (
            QEvent.Type.FocusIn,
            QEvent.Type.FocusOut,
        ):
            self._set_card_focus(self.list_card, kind == QEvent.Type.FocusIn)
        elif watched is getattr(self, "weight_search_edit", None) and hasattr(
            self, "available_card"
        ):
            self._handle_weight_focus(event)

    def _weight_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not event.isAutoRepeat():
                self._load_controller.enter()
            return True
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._load_controller.move_match(1 if key == Qt.Key.Key_Down else -1)
            return True
        if key == Qt.Key.Key_Tab and not event.modifiers():
            self._load_controller.cancel_search()
            self.list_bars_table.setFocus(Qt.FocusReason.TabFocusReason)
            return True
        return False

    def _list_key(self, event: QKeyEvent) -> bool:
        key = event.key()
        if key == Qt.Key.Key_Delete:
            if not event.isAutoRepeat():
                self.remove_selected_from_list()
            return True
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Backtab):
            self.focus_weight()
            return True
        if (
            key == Qt.Key.Key_Down
            and self.list_bars_table.currentIndex().row()
            == self.list_bars_model.rowCount() - 1
        ):
            self.load_more_list_rows()
        return False

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        self._track_panes(watched, event)
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if watched is self.weight_search_edit and self._weight_key(event):
                return True
            if watched is self.list_bars_table and self._list_key(event):
                return True
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
