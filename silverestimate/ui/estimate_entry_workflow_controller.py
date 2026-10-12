"""Workflow controller for estimate entry actions and state transitions."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Dict, Optional, cast

from PySide6.QtCore import (
    QDate,
    QSignalBlocker,
    QTimer,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from silverestimate.domain.estimate_entry import (
    EstimateEntryRowState,
    EstimateEntrySnapshot,
    LoadedEstimate,
)
from silverestimate.domain.numeric_policy import MONEY_PLACES, WEIGHT_PLACES
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
    SaveValidationError,
)
from silverestimate.ui.estimate_deletion_dialog import confirm_estimate_deletion

from .estimate_entry_logic.constants import COL_CODE, COL_GROSS
from .estimate_entry_theme import refresh_widget_style
from .item_selection_dialog import ItemSelectionDialog
from .message_dialogs import ask, ask_save_discard, with_details
from .preview_build_worker import PreviewBuildController
from .themed_controls import ThemedDoubleSpinBox

if TYPE_CHECKING:
    from .estimate_entry import EstimateEntryWidget


# Pairs with Ctrl+D (delete row). Ctrl+Z belongs to the open cell editor.
ROW_UNDO_SHORTCUT = "Ctrl+Shift+D"


class EstimateEntryWorkflowController:
    """Handle estimate-entry workflow actions outside table/totals mechanics."""

    def __init__(self, host: EstimateEntryWidget) -> None:
        self.host = host
        self._preview_builder: PreviewBuildController | None = None
        self._deleted_rows: list[tuple[int, EstimateEntryRowState]] = []

    def _commit_entry_editor(self) -> bool:
        commit = getattr(self.host.item_table, "commit_active_editor", None)
        if callable(commit):
            was_dirty = self.host.has_unsaved_changes()
            before = self.host.item_table.get_model().get_all_rows()
            if not commit():
                self.host._notify(
                    "Finish or correct the highlighted cell first.",
                    5000,
                    level="warning",
                )
                return False
            if (
                not was_dirty
                and self.host.item_table.get_model().get_all_rows() == before
            ):
                self.host._set_unsaved(False, force=True)
        return True

    def _update_row_undo_action(self) -> None:
        self.host.command_undo_row_action.setEnabled(bool(self._deleted_rows))

    def _clear_row_undo(self) -> None:
        self._deleted_rows.clear()
        self._update_row_undo_action()

    def undo_row_deletion(self) -> bool:
        if not self._deleted_rows or not self._commit_entry_editor():
            return False
        row_index, deleted = self._deleted_rows.pop()
        rows = self.host.item_table.get_all_rows()
        row_index = min(row_index, len(rows))
        rows.insert(row_index, deleted)
        self.host.item_table.replace_all_rows(rows)
        self.host.totals_controller.calculate_totals()
        self.host._mark_unsaved()
        self.host.item_table.setCurrentCell(row_index, COL_CODE)
        self._update_row_undo_action()
        self.host._notify("Deleted row restored.", 3000)
        return True

    def _parent_widget(self):
        return self.host

    def generate_voucher(self):
        if self.host.presenter:
            self.host.presenter.generate_voucher()
        self.host.delete_estimate_button.setEnabled(False)
        self.host._estimate_loaded = False

    def load_estimate(self):
        if self.host.initializing or not self.host.presenter:
            return

        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            return

        self.host._status(f"Loading estimate {voucher_no}...", 2000)
        try:
            loaded = self.host.presenter.load_estimate(voucher_no)
            if loaded:
                if self.apply_loaded_estimate(loaded):
                    self.host._status(
                        f"Estimate {voucher_no} loaded successfully.", 3000
                    )
                else:
                    self.host.set_voucher_number(
                        getattr(self.host, "_active_voucher_no", voucher_no)
                    )
                    self.host._notify(
                        f"Estimate {voucher_no} could not be opened.",
                        5000,
                        level="error",
                    )
            else:
                self.host._notify(
                    f"No estimate {voucher_no}. Your current entry was kept.",
                    5000,
                    level="warning",
                )
                active_voucher = getattr(self.host, "_active_voucher_no", voucher_no)
                self.host.set_voucher_number(active_voucher)
        except Exception as exc:
            self.host.logger.warning("Failed to load estimate %s: %s", voucher_no, exc)
            self.host.set_voucher_number(
                getattr(self.host, "_active_voucher_no", voucher_no)
            )
            self.host._notify(
                f"Estimate {voucher_no} could not be opened: {exc}",
                6000,
                level="error",
            )

    def safe_load_estimate(self):
        if self.host._loading_estimate or self.host.initializing:
            return

        if not self._commit_entry_editor():
            return
        voucher_text = self.host.voucher_edit.text().strip()
        if not voucher_text:
            return

        active_voucher = getattr(self.host, "_active_voucher_no", voucher_text)
        if not self._confirm_unsaved(
            "loading another estimate", save_voucher=active_voucher
        ):
            self.host.set_voucher_number(active_voucher)
            return
        blocker = QSignalBlocker(self.host.voucher_edit)
        self.host.voucher_edit.setText(voucher_text)
        del blocker
        self.host._loading_estimate = True
        blocker = QSignalBlocker(self.host.voucher_edit)
        try:
            self.load_estimate()
        except Exception as exc:
            self.host.logger.warning("Unexpected load failure: %s", exc, exc_info=True)
        finally:
            del blocker
            self.host._loading_estimate = False

    def save_estimate(self, *, continue_editing: bool = False) -> bool:
        if not self._commit_entry_editor():
            return False
        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(
                self._parent_widget(),
                "Voucher Number Needed",
                "Enter a voucher number before saving.",
            )
            self.host.voucher_edit.setFocus()
            return False

        if not self.host.presenter:
            return False

        snapshot = self._capture_snapshot()
        if not self._confirm_rows_without_weight(snapshot.rows):
            return False
        self.host._status(f"Saving estimate {voucher_no}...", 2000)

        service = EstimateEntryPersistenceService(snapshot)
        try:
            outcome, preparation = service.execute_save(
                voucher_no=voucher_no,
                date=self.host.date_edit.date().toString("yyyy-MM-dd"),
                note=self.host.note_edit.text().strip(),
                save=self.host.presenter.save_estimate,
            )

            if outcome.success:
                self._refresh_saved_line_metadata(voucher_no, snapshot.rows)
                self.host._last_saved_status = datetime.now().strftime(
                    "%d/%m/%Y %I:%M %p"
                )
                self.host.refresh_status_line()
                self.host._status(outcome.message, 5000)
                self._clear_row_undo()
                self.host._active_voucher_no = voucher_no
                self.host._estimate_loaded = True
                self.host._set_unsaved(False, force=True)
                if not continue_editing:
                    self.print_estimate()
                    self.clear_form(confirm=False)
                    # No message box: a brief toast names the saved voucher
                    # while the preview opens and the form clears.
                    self.host._notify(outcome.message, 5000)
                return True
            else:
                message = outcome.message
                if outcome.error_detail and outcome.error_detail not in message:
                    message = f"{message}\n\n{outcome.error_detail}"
                QMessageBox.critical(
                    self._parent_widget(), "Estimate Not Saved", message
                )
                self.host._status(outcome.message, 5000)
                self._focus_invalid_row(preparation.row_errors)
        except SaveValidationError as exc:
            QMessageBox.warning(
                self._parent_widget(), "Check the Estimate Rows", str(exc)
            )
            self._focus_invalid_row(exc.row_errors)
        except Exception as exc:
            self.host.logger.error(
                "Failed to save estimate %s: %s", voucher_no, exc, exc_info=True
            )
            QMessageBox.critical(
                self._parent_widget(),
                "Estimate Not Saved",
                with_details("The estimate could not be saved.", exc),
            )
        return False

    def _confirm_rows_without_weight(
        self, rows: tuple[EstimateEntryRowState, ...]
    ) -> bool:
        """Ask before saving item rows whose gross weight was left at zero."""
        unweighed = [
            index + 1
            for index, row in enumerate(rows)
            if not row.is_empty() and row.gross <= 0
        ]
        if not unweighed:
            return True
        listed = ", ".join(str(number) for number in unweighed[:8])
        if len(unweighed) > 8:
            listed += f" and {len(unweighed) - 8} more"
        subject = f"Row {listed} has" if len(unweighed) == 1 else f"Rows {listed} have"
        if ask(
            self._parent_widget(),
            title="Rows Without Weight",
            heading=f"{subject} no gross weight.",
            detail="Save the estimate anyway?",
            action_label="Save Anyway",
            cancel_label="Go Back",
            default_to_cancel=True,
        ):
            return True
        self.host.item_table.setCurrentCell(unweighed[0] - 1, COL_GROSS)
        self.host.item_table.setFocus()
        return False

    def _confirm_unsaved(self, action: str, *, save_voucher: str | None = None) -> bool:
        if not self._commit_entry_editor():
            return False
        if not self.host.has_unsaved_changes():
            return True
        reply = ask_save_discard(
            self._parent_widget(),
            title="Unsaved Estimate",
            heading=f"Save this estimate before {action}?",
            detail="It has changes that are not saved yet.",
        )
        if reply == "discard":
            recovery = self.host.draft_recovery
            if recovery is not None and not recovery.discard_current():
                self.host._notify(
                    "The recovery copy could not be discarded. Try again.",
                    5000,
                    level="error",
                )
                return False
            return True
        if reply != "save":
            return False
        if save_voucher:
            self.host.set_voucher_number(save_voucher)
        return self.save_estimate(continue_editing=True)

    def _refresh_saved_line_metadata(
        self, voucher_no: str, saved_rows: tuple[EstimateEntryRowState, ...]
    ) -> None:
        """Keep a continuing draft's snapshots aligned with the committed save."""
        presenter = self.host.presenter
        if presenter is None:
            return
        try:
            loaded = presenter.load_estimate(voucher_no)
            if loaded is None:
                return
            saved = {item.line_key: item for item in loaded.items if item.line_key}
            rows = [
                replace(
                    row,
                    tunch=saved[row.line_key].tunch,
                    snapshot_version=saved[row.line_key].snapshot_version,
                )
                if row.line_key in saved
                else row
                for row in saved_rows
            ]
            self.host.item_table.replace_all_rows(rows)
        except Exception as exc:
            self.host.logger.warning(
                "Estimate saved, but refreshing line metadata failed: %s", exc
            )

    def _focus_invalid_row(self, row_errors: Dict[int, str]) -> None:
        if row_errors:
            self.host.item_table.setCurrentCell(min(row_errors) - 1, COL_CODE)
            self.host.item_table.setFocus()

    def _estimate_summary(self) -> str:
        """Date and total of the open estimate, for confirmations."""
        parts = [self.host.date_edit.date().toString("dd/MM/yyyy")]
        total = self.host.grand_total_label.text().strip()
        if total:
            parts.append(f"Grand total {total}")
        return " · ".join(parts)

    def delete_current_estimate(self):
        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            return

        if (
            confirm_estimate_deletion(
                self._parent_widget(), voucher_no, self._estimate_summary()
            )
            and self.host.presenter
        ):
            if self.host.presenter.delete_estimate(voucher_no):
                self.host._notify(f"Estimate {voucher_no} deleted.", 3000)
                self.clear_form(confirm=False)
            else:
                QMessageBox.warning(
                    self._parent_widget(),
                    "Estimate Not Deleted",
                    with_details(
                        f"Estimate {voucher_no} could not be deleted.",
                        getattr(self.host.db_manager, "last_error", None),
                    ),
                )

    def print_estimate(self):
        if not self._commit_entry_editor():
            return
        from silverestimate.ui.print_manager import PrintManager

        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            return

        current_font = getattr(self.host.main_window, "print_font", None)
        pm = PrintManager(self.host.db_manager, print_font=current_font)
        try:
            estimate_data = self._build_current_estimate_preview_data(voucher_no)
        except ValueError as exc:
            message = str(exc)
            if message == "No valid items found to save.":
                message = "Add at least one valid item before opening print preview."
            QMessageBox.warning(
                self._parent_widget(),
                "Print Error",
                message,
            )
            return
        except Exception as exc:
            self.host.logger.error(
                "Failed to build estimate preview data for %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            QMessageBox.critical(
                self._parent_widget(),
                "Print Error",
                "Could not prepare the current estimate for print preview.",
            )
            return

        self.host._status("Preparing print preview...", 2000)
        self._start_estimate_print_preview_build(
            print_manager=pm,
            voucher_no=voucher_no,
            estimate_data=estimate_data,
        )

    def _start_estimate_print_preview_build(
        self, *, print_manager, voucher_no: str, estimate_data
    ) -> None:
        if self._preview_builder is None:
            self._preview_builder = PreviewBuildController(self.host, modal=True)
        self._preview_builder.start(
            lambda: print_manager.build_estimate_preview_payload(
                voucher_no, estimate_data=estimate_data
            ),
            on_ready=lambda payload: print_manager.show_preview(
                payload, parent_widget=self.host
            ),
            on_error=lambda message: QMessageBox.critical(
                self.host, "Print Error", f"Error preparing print preview: {message}"
            ),
            empty_message="Could not prepare the estimate print preview.",
        )

    def shutdown_print_previews(self) -> None:
        if self._preview_builder is not None:
            self._preview_builder.shutdown()
            self._preview_builder = None

    def clear_form(self, confirm: bool = True):
        if confirm and not self._confirm_unsaved("starting a new estimate"):
            return

        self.host._push_unsaved_block()
        self.host.item_table.blockSignals(True)
        self.host.processing_cell = True
        try:
            self.host.voucher_edit.clear()
            if self.host.presenter:
                self.host.presenter.generate_voucher()
            self.host.date_edit.setDate(QDate.currentDate())
            self.host.silver_rate_spin.setValue(0)
            self.host.note_edit.clear()

            self.host.last_balance_silver = 0.0
            self.host.last_balance_amount = 0.0

            if self.host.return_mode:
                self.toggle_return_mode()
            if self.host.silver_bar_mode:
                self.toggle_silver_bar_mode()

            self.host.table_controller.clear_all_rows()
            self.host.table_controller.add_empty_row()
            self.host.totals_controller.calculate_totals()

            self.host._estimate_loaded = False
            self.host.delete_estimate_button.setEnabled(False)
        finally:
            self.host.processing_cell = False
            self.host.item_table.blockSignals(False)
            self.host._pop_unsaved_block()
            QTimer.singleShot(
                50, lambda: self.host.table_controller.focus_on_code_column(0)
            )
        self.host._set_unsaved(False, force=True)
        self._clear_row_undo()

    def confirm_exit(self) -> bool:
        return self._confirm_unsaved("exiting")

    def show_history(self):
        if self.host.presenter:
            self.host.presenter.open_history()

    def toggle_return_mode(self, *_args):
        if not self.host.return_mode and self.host.silver_bar_mode:
            self.host.silver_bar_mode = False
            self.host.silver_bar_toggle_button.setChecked(False)

        self.host.return_mode = not self.host.return_mode
        self.host.return_toggle_button.setChecked(self.host.return_mode)

        self._sync_mode_controls()
        self._finalize_mode_change()

    def toggle_silver_bar_mode(self, *_args):
        if not self.host.silver_bar_mode and self.host.return_mode:
            self.host.return_mode = False
            self.host.return_toggle_button.setChecked(False)

        self.host.silver_bar_mode = not self.host.silver_bar_mode
        self.host.silver_bar_toggle_button.setChecked(self.host.silver_bar_mode)

        self._sync_mode_controls()
        self._finalize_mode_change()

    def _sync_mode_controls(self) -> None:
        if self.host.return_mode:
            self.host.mode_indicator_label.setText("Mode: Return Items")
            self.host.mode_indicator_label.setProperty("modeState", "return")
        elif self.host.silver_bar_mode:
            self.host.mode_indicator_label.setText("Mode: Silver Bars")
            self.host.mode_indicator_label.setProperty("modeState", "silver_bar")
        else:
            self.host.mode_indicator_label.setText("Mode: Regular")
            self.host.mode_indicator_label.setProperty("modeState", "regular")

        refresh_widget_style(self.host.mode_indicator_label)

    def _finalize_mode_change(self) -> None:
        self.host.table_controller._get_table_adapter().refresh_empty_row_type()
        self.host.layout_controller.grow_columns_to_content()
        self.host.focus_on_empty_row(update_visuals=True)
        self.host._update_mode_tooltip()

    def delete_current_row(self):
        row = self.host.item_table.currentRow()
        if row < 0:
            return
        rows = self.host.item_table.get_all_rows()
        # Nothing was entered on the entry row; keep it in place.
        if (
            row < len(rows)
            and rows[row].is_empty()
            and (self.host.item_table.rowCount() <= 1 or row == len(rows) - 1)
        ):
            self.host._notify("This row is already empty.", 3000)
            return
        # No confirmation: the deletion can be undone until the estimate is
        # saved or cleared.
        if row < len(rows):
            self._deleted_rows.append((row, rows[row]))
            del self._deleted_rows[:-20]
            self._update_row_undo_action()
        self.host.item_table.delete_row(row)
        self.host.totals_controller.calculate_totals()
        self.host._mark_unsaved()
        self.host._notify(
            f"Row {row + 1} deleted. Press {ROW_UNDO_SHORTCUT} to undo.", 5000
        )
        if self.host.item_table.rowCount() == 0:
            self.host.table_controller.add_empty_row()

        new_row = min(row, self.host.item_table.rowCount() - 1)
        QTimer.singleShot(
            0, lambda: self.host.item_table.setCurrentCell(new_row, COL_CODE)
        )

    def prompt_item_selection(self, code: str) -> Optional[Dict]:
        dialog = ItemSelectionDialog(
            self.host.db_manager, code, parent=self._parent_widget()
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return cast(Optional[Dict], dialog.get_selected_item())
        return None

    def focus_after_item_lookup(self, row_index: int) -> None:
        self.host.table_controller._schedule_cell_edit(row_index, COL_GROSS)

    def open_history_dialog(self) -> Optional[str]:
        from silverestimate.ui.estimate_history import EstimateHistoryDialog

        dialog = EstimateHistoryDialog(
            self.host.db_manager,
            main_window_ref=self.host.main_window,
            parent=self._parent_widget(),
        )
        try:
            voucher = (
                dialog.selected_voucher
                if dialog.exec() == QDialog.DialogCode.Accepted
                else None
            )
        finally:
            dialog.shutdown_workers()
            dialog.deleteLater()
        if voucher and self._confirm_history_replacement():
            return str(voucher)
        return None

    def _confirm_history_replacement(self) -> bool:
        return self._confirm_unsaved("opening the selected estimate")

    def open_saved_estimate(self, voucher_no: str) -> bool:
        """Open a report voucher without overwriting an unconfirmed entry draft."""
        presenter = self.host.presenter
        if presenter is None:
            return False
        if not self._confirm_history_replacement():
            return False
        try:
            loaded = presenter.load_estimate(voucher_no)
            if loaded is None:
                self.host._notify(
                    f"No estimate {voucher_no}. Your current entry was kept.",
                    5000,
                    level="warning",
                )
                return False
            return self.apply_loaded_estimate(loaded)
        except Exception as exc:
            self.host.logger.warning(
                "Could not open report voucher %s: %s", voucher_no, exc
            )
            self.host._notify(
                f"Estimate {voucher_no} could not be opened: {exc}",
                6000,
                level="error",
            )
            return False

    def show_silver_bar_management(self) -> None:
        if hasattr(self.host.main_window, "show_silver_bars"):
            self.host.main_window.show_silver_bars()

    def show_silver_bars(self):
        self.show_silver_bar_management()

    def _restore_entry_after_failed_load(self, previous_rows, previous_header) -> None:
        voucher, date, rate, note, silver, amount, was_loaded = previous_header
        self.host.item_table.replace_all_rows(previous_rows)
        self.host.set_voucher_number(voucher)
        self.host.date_edit.setDate(date)
        self.host.silver_rate_spin.setValue(rate)
        self.host.note_edit.setText(note)
        self.host.note_edit.setCursorPosition(0)
        self.host.last_balance_silver = silver
        self.host.last_balance_amount = amount
        self.host._estimate_loaded = was_loaded
        self.host.delete_estimate_button.setEnabled(was_loaded)
        self.host.totals_controller.calculate_totals()

    def _prepare_loaded_rows(self, loaded: LoadedEstimate):
        row_states = EstimateEntryPersistenceService.build_row_states_from_items(
            loaded.items
        )
        prepared_rows = []
        for index, row_state in enumerate(row_states):
            code = (row_state.code or "").strip()
            wage_type = self.host._normalize_wage_type(row_state.wage_type)
            normalized_pieces = int(row_state.pieces)

            prepared_rows.append(
                replace(
                    row_state,
                    code=code,
                    wage_type=wage_type,
                    pieces=normalized_pieces,
                    row_index=index + 1,
                )
            )

        return row_states, prepared_rows

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        # Build and normalize the loaded rows before touching the current draft.
        try:
            row_states, prepared_rows = self._prepare_loaded_rows(loaded)
        except Exception as exc:
            self.host.logger.error("Failed to prepare estimate: %s", exc, exc_info=True)
            return False
        previous_dirty = self.host.has_unsaved_changes()
        previous_rows = self.host.item_table.get_all_rows()
        previous_header = (
            getattr(self.host, "_active_voucher_no", self.host.voucher_edit.text()),
            self.host.date_edit.date(),
            self.host.silver_rate_spin.value(),
            self.host.note_edit.text(),
            self.host.last_balance_silver,
            self.host.last_balance_amount,
            self.host._estimate_loaded,
        )
        applied = False
        self.host._push_unsaved_block()
        self.host.item_table.blockSignals(True)
        self.host.processing_cell = True
        try:
            self.host.table_controller.clear_all_rows()

            try:
                date = QDate.fromString(loaded.date, "yyyy-MM-dd")
                self.host.date_edit.setDate(
                    date if date.isValid() else QDate.currentDate()
                )
            except Exception as exc:
                self.host.logger.debug(
                    "Failed to parse loaded estimate date '%s': %s",
                    loaded.date,
                    exc,
                )
                self.host.date_edit.setDate(QDate.currentDate())

            self.host.silver_rate_spin.setValue(loaded.silver_rate)
            self.host.note_edit.setText(loaded.note or "")
            self.host.note_edit.setCursorPosition(0)

            self.host.last_balance_silver = loaded.last_balance_silver
            self.host.last_balance_amount = loaded.last_balance_amount

            self.host.item_table.replace_all_rows(prepared_rows)

            self.host.table_controller.add_empty_row()
            self.host.totals_controller.calculate_totals()
            self.host.layout_controller._schedule_columns_autofit(force=True)
            self.host._estimate_loaded = True

            self.host.delete_estimate_button.setEnabled(True)

            self.host.set_voucher_number(loaded.voucher_no)
            self._clear_row_undo()
            applied = True
            return True
        except Exception as exc:
            self.host.logger.error("Failed to apply estimate: %s", exc, exc_info=True)
            try:
                self._restore_entry_after_failed_load(previous_rows, previous_header)
            except Exception:
                self.host.logger.exception(
                    "Could not restore entry after a display failure"
                )
            return False
        finally:
            self.host.processing_cell = False
            self.host.item_table.blockSignals(False)
            self.host._pop_unsaved_block()
            self.host._set_unsaved(False if applied else previous_dirty, force=True)

    def refresh_silver_rate(self):
        """Ask the live-rate controller, which owns the feed, for a fresh rate."""
        live_rate_controller = getattr(
            self.host.main_window, "live_rate_controller", None
        )
        if live_rate_controller is None:
            return
        self.host.refresh_rate_button.setEnabled(False)
        self.host.live_rate_value_label.setText("Refreshing…")
        self.host.live_rate_meta_label.setText("Updating")
        self.host._status("Refreshing live silver rate...", 2000)
        live_rate_controller.refresh_now()
        self.host.refresh_rate_button.setEnabled(True)

    def _handle_silver_rate_changed(self, *_):
        self.host.totals_controller._schedule_totals_recalc()
        self.host._mark_unsaved()

    def _capture_snapshot(self) -> EstimateEntrySnapshot:
        """Detach the rows and totals inputs on screen as the save input."""
        return EstimateEntrySnapshot.capture(
            self.host.item_table.get_all_rows(),
            silver_rate=self.host.silver_rate_spin.value(),
            last_balance_silver=self.host.last_balance_silver,
            last_balance_amount=self.host.last_balance_amount,
        )

    def _build_current_estimate_preview_data(self, voucher_no: str) -> Dict:
        snapshot = self._capture_snapshot()
        shown_voucher = self.host.voucher_edit.text().strip()
        voucher_date = self.host.date_edit.date().toString("yyyy-MM-dd")
        voucher_note = self.host.note_edit.text().strip()
        service = EstimateEntryPersistenceService(snapshot)
        preparation = service.prepare_save_payload(
            voucher_no=voucher_no,
            date=voucher_date,
            note=voucher_note,
        )
        if preparation.skipped_rows:
            skipped = ", ".join(str(row) for row in preparation.skipped_rows)
            self.host._notify(
                f"Left out of the preview, rows with errors: {skipped}",
                6000,
                level="warning",
            )

        item_codes = [
            item.code
            for item in preparation.payload.items
            if item.code and not item.snapshot_version
        ]
        catalog_items: dict[str, dict] = {}
        try:
            getter = getattr(self.host.db_manager, "get_items_by_codes", None)
            if callable(getter):
                catalog_items = {
                    str(code or "").strip().upper(): dict(row or {})
                    for code, row in dict(getter(item_codes) or {}).items()
                }
        except Exception as exc:
            self.host.logger.warning(
                "Could not resolve current Tunch values for preview: %s",
                exc,
                exc_info=True,
            )

        def current_tunch(code: str):
            row = catalog_items.get(str(code or "").strip().upper())
            return None if row is None else row.get("tunch")

        items = [
            {
                "id": item.row_number,
                "item_code": item.code,
                "item_name": item.name,
                "tunch": item.tunch
                if item.snapshot_version
                else current_tunch(item.code),
                "gross": item.gross,
                "poly": item.poly,
                "net_wt": item.net_wt,
                "purity": item.purity,
                "wage_rate": item.wage_rate,
                "pieces": item.pieces,
                "wage": item.wage,
                "fine": item.fine,
                "is_return": 1 if item.is_return else 0,
                "is_silver_bar": 1 if item.is_silver_bar else 0,
            }
            for item in preparation.payload.items
        ]

        return {
            "_preview_state": (
                "Unsaved draft"
                if self.host.has_unsaved_changes() or not self.host._estimate_loaded
                else "Saved estimate"
            ),
            "header": {
                "voucher_no": shown_voucher or voucher_no,
                "date": voucher_date,
                "silver_rate": preparation.payload.silver_rate,
                "note": preparation.payload.note,
                "last_balance_silver": preparation.payload.last_balance_silver,
                "last_balance_amount": preparation.payload.last_balance_amount,
            },
            "items": items,
        }

    def show_last_balance_dialog(self):
        dialog = QDialog(self._parent_widget())
        dialog.setWindowTitle("Enter Last Balance")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(18)
        title = QLabel("Last Balance")
        title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        layout.addWidget(title)
        hint = QLabel("Carry a previous silver weight or amount into this estimate.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        form.setSpacing(12)

        lb_silver = ThemedDoubleSpinBox()
        lb_silver.setRange(-1000000, 1000000)
        lb_silver.setDecimals(WEIGHT_PLACES)
        lb_silver.setValue(self.host.last_balance_silver)
        form.addRow("Silver Weight (g):", lb_silver)

        lb_amount = ThemedDoubleSpinBox()
        lb_amount.setRange(-10000000, 10000000)
        lb_amount.setDecimals(MONEY_PLACES)
        lb_amount.setValue(self.host.last_balance_amount)
        form.addRow("Amount:", lb_amount)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Apply Balance")
        btns.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(
            "background: #007f89; color: white; padding: 8px 16px;"
        )
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec():
            self.host.last_balance_silver = lb_silver.value()
            self.host.last_balance_amount = lb_amount.value()
            self.host.totals_controller.calculate_totals()
            self.host._mark_unsaved()
