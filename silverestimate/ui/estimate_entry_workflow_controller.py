"""Workflow controller for estimate entry actions and state transitions."""

from __future__ import annotations

import threading
import time
from dataclasses import replace
from typing import TYPE_CHECKING, Callable, Dict, Optional, cast

from PyQt5.QtCore import (
    QDate,
    QLocale,
    QObject,
    QSignalBlocker,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
)

from silverestimate.presenter import LoadedEstimate
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)

from ._host_proxy import HostProxy
from .estimate_entry_logic.constants import COL_CODE, COL_GROSS
from .estimate_entry_theme import refresh_widget_style
from .item_selection_dialog import ItemSelectionDialog


class _EstimatePreviewBuildWorker(QObject):
    """Background worker that prepares print-preview HTML off the UI thread."""

    preview_ready = pyqtSignal(int, object)
    preview_error = pyqtSignal(int, str)
    finished = pyqtSignal(int)

    def __init__(
        self,
        request_id: int,
        build_preview: Callable[[], object],
    ) -> None:
        super().__init__()
        self._request_id = request_id
        self._build_preview = build_preview

    def run(self) -> None:
        try:
            payload = self._build_preview()
            self.preview_ready.emit(self._request_id, payload)
        except Exception as exc:
            self.preview_error.emit(self._request_id, str(exc))
        finally:
            self.finished.emit(self._request_id)


class EstimateEntryWorkflowController(HostProxy):
    """Handle estimate-entry workflow actions outside table/totals mechanics."""

    if TYPE_CHECKING:
        _loading_estimate: bool
        return_mode: bool
        silver_bar_mode: bool
        _print_preview_request_id: int
        _active_print_preview_workers: dict[QThread, QObject]

    def _parent_widget(self):
        return self.host

    def _format_currency(self, value):
        try:
            locale = QLocale.system()
            return locale.toCurrencyString(float(round(value)))
        except Exception:
            try:
                return f"₹ {int(round(value)):,}"
            except Exception:
                return str(value)

    def generate_voucher(self):
        try:
            self.voucher_edit.returnPressed.disconnect(self.safe_load_estimate)
        except (TypeError, RuntimeError) as exc:
            self.logger.debug(
                "Could not disconnect voucher returnPressed handler: %s", exc
            )

        if self.presenter:
            self.presenter.generate_voucher()
        if hasattr(self, "delete_estimate_button"):
            self.delete_estimate_button.setEnabled(False)
        self._estimate_loaded = False

        try:
            self.voucher_edit.returnPressed.connect(self.safe_load_estimate)
        except (TypeError, RuntimeError) as exc:
            self.logger.debug(
                "Could not reconnect voucher returnPressed handler: %s", exc
            )

    def load_estimate(self):
        if self.initializing or not self.presenter:
            return

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        self._status(f"Loading estimate {voucher_no}...", 2000)
        try:
            loaded = self.presenter.load_estimate(voucher_no)
            if loaded:
                if self.apply_loaded_estimate(loaded):
                    self._status(f"Estimate {voucher_no} loaded successfully.", 3000)
            else:
                self._status(
                    f"Estimate {voucher_no} not found. Starting new entry.", 4000
                )
                self._estimate_loaded = False
                if hasattr(self, "delete_estimate_button"):
                    self.delete_estimate_button.setEnabled(False)
                self.focus_on_code_column(0)
        except Exception as exc:
            self.logger.warning("Failed to load estimate %s: %s", voucher_no, exc)
            self._status(f"Error loading estimate: {exc}", 4000)

    def safe_load_estimate(self):
        if self._loading_estimate or self.initializing:
            return

        voucher_text = self.voucher_edit.text().strip()
        if not voucher_text:
            return

        if self.has_unsaved_changes():
            reply = QMessageBox.question(
                self._parent_widget(),
                "Discard Unsaved Changes?",
                "You have unsaved changes. Loading another estimate will discard them.\n\nContinue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._loading_estimate = True
        blocker = QSignalBlocker(self.voucher_edit)
        try:
            self.load_estimate()
        except Exception as exc:
            self.logger.warning("Unexpected load failure: %s", exc, exc_info=True)
        finally:
            del blocker
            self._loading_estimate = False

    def save_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(
                self._parent_widget(), "Input Error", "Voucher number is required."
            )
            return

        if not self.presenter:
            return

        self._status(f"Saving estimate {voucher_no}...", 2000)
        self._update_view_model_snapshot()

        service = EstimateEntryPersistenceService(self.view_model)
        try:
            outcome, preparation = service.execute_save(
                voucher_no=voucher_no,
                date=self.date_edit.date().toString("yyyy-MM-dd"),
                note=self.note_edit.text().strip()
                if hasattr(self, "note_edit")
                else "",
                presenter=self.presenter,
            )

            if outcome.success:
                self._status(outcome.message, 5000)
                QMessageBox.information(
                    self._parent_widget(), "Success", outcome.message
                )
                self.print_estimate()
                self.clear_form(confirm=False)
            else:
                QMessageBox.critical(
                    self._parent_widget(), "Save Error", outcome.message
                )
                self._status(outcome.message, 5000)
            del preparation
        except Exception as exc:
            self.logger.error(
                "Failed to save estimate %s: %s", voucher_no, exc, exc_info=True
            )
            QMessageBox.critical(self._parent_widget(), "Save Error", str(exc))

    def delete_current_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        reply = QMessageBox.warning(
            self._parent_widget(),
            "Confirm Delete",
            f"Are you sure you want to delete estimate '{voucher_no}'?",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes and self.presenter:
            if self.presenter.delete_estimate(voucher_no):
                self._status(f"Estimate {voucher_no} deleted.", 3000)
                self.clear_form(confirm=False)
            else:
                QMessageBox.warning(
                    self._parent_widget(), "Error", "Could not delete estimate."
                )

    def print_estimate(self):
        from silverestimate.ui.print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        current_font = getattr(self.main_window, "print_font", None)
        pm = PrintManager(self.db_manager, print_font=current_font)
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
            self.logger.error(
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

        self._status("Preparing print preview...", 2000)
        self._start_estimate_print_preview_build(
            print_manager=pm,
            voucher_no=voucher_no,
            estimate_data=estimate_data,
        )

    def _next_print_preview_request_id(self) -> int:
        next_id = int(getattr(self, "_print_preview_request_id", 0)) + 1
        self._print_preview_request_id = next_id
        return next_id

    def _start_estimate_print_preview_build(
        self,
        *,
        print_manager,
        voucher_no: str,
        estimate_data,
    ) -> None:
        request_id = self._next_print_preview_request_id()
        progress = QProgressDialog(
            "Preparing print preview...",
            "",
            0,
            0,
            self._parent_widget(),
        )
        progress.setCancelButton(None)
        progress.setWindowTitle("Print Preview")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        worker = _EstimatePreviewBuildWorker(
            request_id,
            lambda: print_manager.build_estimate_preview_payload(
                voucher_no,
                estimate_data=estimate_data,
            ),
        )
        thread = QThread(self.host)
        worker.moveToThread(thread)

        active_workers = getattr(self, "_active_print_preview_workers", None)
        if active_workers is None:
            self._active_print_preview_workers = {}
            active_workers = self._active_print_preview_workers
        active_workers[thread] = worker

        thread.started.connect(worker.run)
        worker.preview_ready.connect(
            lambda rid, payload: self._on_estimate_print_preview_ready(
                rid,
                payload,
                print_manager=print_manager,
                progress=progress,
            )
        )
        worker.preview_error.connect(
            lambda rid, message: self._on_estimate_print_preview_error(
                rid,
                message,
                progress=progress,
            )
        )
        worker.finished.connect(
            lambda rid: self._finalize_estimate_print_preview_build(
                rid,
                thread=thread,
                worker=worker,
                progress=progress,
            )
        )
        thread.start()

    def _on_estimate_print_preview_ready(
        self,
        request_id: int,
        payload,
        *,
        print_manager,
        progress: QProgressDialog,
    ) -> None:
        if request_id != getattr(self, "_print_preview_request_id", 0):
            return
        if payload is None:
            self._on_estimate_print_preview_error(
                request_id,
                "Estimate preview data could not be prepared.",
                progress=progress,
            )
            return
        try:
            progress.close()
        except Exception as exc:
            self.logger.debug(
                "Failed to close estimate print preview progress: %s", exc
            )
        print_manager.show_preview(payload, parent_widget=self._parent_widget())

    def _on_estimate_print_preview_error(
        self,
        request_id: int,
        message: str,
        *,
        progress: QProgressDialog,
    ) -> None:
        if request_id != getattr(self, "_print_preview_request_id", 0):
            return
        try:
            progress.close()
        except Exception as exc:
            self.logger.debug(
                "Failed to close estimate print preview progress after error: %s",
                exc,
            )
        QMessageBox.critical(
            self._parent_widget(),
            "Print Error",
            f"Error preparing print preview: {message}",
        )

    def _finalize_estimate_print_preview_build(
        self,
        request_id: int,
        *,
        thread: QThread,
        worker: QObject,
        progress: QProgressDialog,
    ) -> None:
        del request_id
        try:
            progress.close()
            progress.deleteLater()
        except Exception as exc:
            self.logger.debug(
                "Failed to dispose estimate print preview progress dialog: %s",
                exc,
            )
        active_workers = getattr(self, "_active_print_preview_workers", {})
        active_workers.pop(thread, None)
        try:
            thread.quit()
            thread.wait(2000)
        except Exception as exc:
            self.logger.debug("Failed to stop print preview worker thread: %s", exc)
        try:
            worker.deleteLater()
            thread.deleteLater()
        except Exception as exc:
            self.logger.debug(
                "Failed to schedule estimate preview worker deletion: %s",
                exc,
            )

    def clear_form(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self._parent_widget(),
                "Confirm New Estimate",
                "Start a new estimate? Unsaved changes will be lost.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            self.voucher_edit.clear()
            if self.presenter:
                self.presenter.generate_voucher()
            self.date_edit.setDate(QDate.currentDate())
            self.silver_rate_spin.setValue(0)
            if hasattr(self, "note_edit"):
                self.note_edit.clear()

            self.last_balance_silver = 0.0
            self.last_balance_amount = 0.0

            if self.return_mode:
                self.toggle_return_mode()
            if self.silver_bar_mode:
                self.toggle_silver_bar_mode()

            self.clear_all_rows()
            self.add_empty_row()
            self.calculate_totals()

            self._estimate_loaded = False
            if hasattr(self, "delete_estimate_button"):
                self.delete_estimate_button.setEnabled(False)
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            QTimer.singleShot(50, lambda: self.focus_on_code_column(0))
        self._set_unsaved(False, force=True)

    def confirm_exit(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        reply = QMessageBox.question(
            self._parent_widget(),
            "Discard Changes?",
            "You have unsaved changes. Exit anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def show_history(self):
        if self.presenter:
            self.presenter.open_history()

    def toggle_return_mode(self, *_args):
        if not self.return_mode and self.silver_bar_mode:
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)

        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        self._sync_mode_controls()
        self._finalize_mode_change()

    def toggle_silver_bar_mode(self, *_args):
        if not self.silver_bar_mode and self.return_mode:
            self.return_mode = False
            self.return_toggle_button.setChecked(False)

        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        self._sync_mode_controls()
        self._finalize_mode_change()

    def _sync_mode_controls(self) -> None:
        if self.return_mode:
            self.return_toggle_button.setProperty("modeState", "return")
        else:
            self.return_toggle_button.setProperty("modeState", "idle")

        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setProperty("modeState", "silver_bar")
        else:
            self.silver_bar_toggle_button.setProperty("modeState", "idle")

        if self.return_mode:
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setProperty("modeState", "return")
        elif self.silver_bar_mode:
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setProperty("modeState", "silver_bar")
        else:
            self.mode_indicator_label.setText("Mode: Regular")
            self.mode_indicator_label.setProperty("modeState", "regular")

        refresh_widget_style(self.return_toggle_button)
        refresh_widget_style(self.silver_bar_toggle_button)
        refresh_widget_style(self.mode_indicator_label)

    def _finalize_mode_change(self) -> None:
        self._get_table_adapter().refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self.view_model.set_modes(
            return_mode=self.return_mode,
            silver_bar_mode=self.silver_bar_mode,
        )
        self._update_mode_tooltip()

    def delete_current_row(self):
        row = self.item_table.currentRow()
        if row < 0:
            return
        if self.item_table.rowCount() <= 1:
            QMessageBox.warning(
                self._parent_widget(), "Error", "Cannot delete the only row."
            )
            return

        reply = QMessageBox.question(
            self._parent_widget(),
            "Delete Row",
            f"Delete row {row + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.item_table.delete_row(row)
            if self._totals_incremental_is_active():
                try:
                    self._remove_incremental_row(row)
                except Exception as exc:
                    self._disable_incremental_totals_and_fallback(exc)
            self.calculate_totals()
            self._mark_unsaved()
            if self.item_table.rowCount() == 0:
                self.add_empty_row()

            new_row = min(row, self.item_table.rowCount() - 1)
            QTimer.singleShot(
                0, lambda: self.item_table.setCurrentCell(new_row, COL_CODE)
            )

    def prompt_item_selection(self, code: str) -> Optional[Dict]:
        dialog = ItemSelectionDialog(
            self.db_manager, code, parent=self._parent_widget()
        )
        if dialog.exec_() == QDialog.Accepted:
            return cast(Optional[Dict], dialog.get_selected_item())
        return None

    def focus_after_item_lookup(self, row_index: int) -> None:
        self._schedule_cell_edit(row_index, COL_GROSS)

    def open_history_dialog(self) -> Optional[str]:
        from silverestimate.ui.estimate_history import EstimateHistoryDialog

        dialog = EstimateHistoryDialog(
            self.db_manager,
            main_window_ref=self.main_window,
            parent=self._parent_widget(),
        )
        if dialog.exec_() == QDialog.Accepted:
            return dialog.selected_voucher
        return None

    def show_silver_bar_management(self) -> None:
        if hasattr(self.main_window, "show_silver_bars"):
            self.main_window.show_silver_bars()

    def show_silver_bars(self):
        self.show_silver_bar_management()

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        start = time.perf_counter()
        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            self.clear_all_rows()

            try:
                date = QDate.fromString(loaded.date, "yyyy-MM-dd")
                self.date_edit.setDate(date if date.isValid() else QDate.currentDate())
            except Exception as exc:
                self.logger.debug(
                    "Failed to parse loaded estimate date '%s': %s",
                    loaded.date,
                    exc,
                )
                self.date_edit.setDate(QDate.currentDate())

            self.silver_rate_spin.setValue(loaded.silver_rate)
            if hasattr(self, "note_edit"):
                self.note_edit.setText(loaded.note or "")

            self.last_balance_silver = loaded.last_balance_silver
            self.last_balance_amount = loaded.last_balance_amount

            row_states = EstimateEntryPersistenceService.build_row_states_from_items(
                loaded.items
            )
            wage_type_by_code: dict[str, str] = {}
            repo = getattr(self.presenter, "repository", None)
            if repo:
                for row_state in row_states:
                    code = (row_state.code or "").strip()
                    if not code or code in wage_type_by_code:
                        continue
                    try:
                        item_data = repo.fetch_item(code)
                    except Exception:
                        item_data = None
                    if item_data and item_data.get("wage_type") is not None:
                        wage_type_by_code[code] = self._normalize_wage_type(
                            item_data.get("wage_type")
                        )
                    else:
                        wage_type_by_code[code] = "WT"

            prepared_rows = []
            for index, row_state in enumerate(row_states):
                code = (row_state.code or "").strip()
                wage_type = wage_type_by_code.get(code, "WT")
                normalized_pieces = int(row_state.pieces)
                if wage_type == "WT":
                    normalized_pieces = 0
                elif normalized_pieces <= 0:
                    normalized_pieces = 1

                prepared_rows.append(
                    replace(
                        row_state,
                        code=code.upper(),
                        wage_type=wage_type,
                        pieces=normalized_pieces,
                        row_index=index + 1,
                    )
                )

            self.item_table.replace_all_rows(prepared_rows)

            self.add_empty_row()
            self.calculate_totals()
            self._schedule_columns_autofit(force=True)
            self._estimate_loaded = True

            if hasattr(self, "delete_estimate_button"):
                self.delete_estimate_button.setEnabled(True)

            self.set_voucher_number(loaded.voucher_no)
            self._log_perf_metric(
                "estimate_entry.apply_loaded_estimate",
                start,
                threshold_ms=25.0,
                rows=len(row_states),
            )
            return True
        except Exception as exc:
            self.logger.error("Failed to apply estimate: %s", exc, exc_info=True)
            return False
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            self._set_unsaved(False, force=True)

    def refresh_silver_rate(self):
        button = getattr(self, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(False)
        self._status("Refreshing live silver rate...", 2000)

        def worker():
            try:
                from silverestimate.services.dda_rate_fetcher import (
                    fetch_broadcast_rate_exact,
                    fetch_silver_agra_local_mohar_rate,
                )

                rate, _, _ = fetch_broadcast_rate_exact(timeout=7)
                if rate is None:
                    rate, _ = fetch_silver_agra_local_mohar_rate(timeout=7)
                self.live_rate_fetched.emit(rate)
            except Exception as exc:
                self.logger.warning(
                    "Live silver rate refresh failed: %s", exc, exc_info=True
                )
                self.live_rate_fetched.emit(None)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_refreshed_live_rate(self, rate) -> None:
        button = getattr(self, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(True)
        if rate:
            try:
                gram_rate = float(rate) / 1000.0
            except (TypeError, ValueError):
                gram_rate = None
            if gram_rate is None:
                if hasattr(self, "live_rate_value_label"):
                    self.live_rate_value_label.setText("N/A")
                self._status("Live rate unavailable.", 3000)
                return
            if hasattr(self, "live_rate_value_label"):
                self.live_rate_value_label.setText(f"₹ {gram_rate:.2f} /g")
            self._status("Live rate refreshed.", 2000)
            return
        if hasattr(self, "live_rate_value_label"):
            self.live_rate_value_label.setText("N/A")
        self._status("Live rate unavailable.", 3000)

    def _handle_silver_rate_changed(self, *_):
        self._schedule_totals_recalc()
        self._mark_unsaved()

    def _update_view_model_snapshot(self):
        start = time.perf_counter()
        rows = list(self.item_table.get_all_rows())

        self.view_model.set_rows(rows)
        self.view_model.set_voucher_metadata(
            voucher_number=self.voucher_edit.text().strip(),
            voucher_date=self.date_edit.date().toString("yyyy-MM-dd"),
            voucher_note=(
                self.note_edit.text().strip() if hasattr(self, "note_edit") else ""
            ),
        )
        self.view_model.set_totals_inputs(
            silver_rate=self.silver_rate_spin.value(),
            last_balance_silver=self.last_balance_silver,
            last_balance_amount=self.last_balance_amount,
        )
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )
        self._log_perf_metric(
            "estimate_entry.sync_view_model",
            start,
            threshold_ms=15.0,
            rows=len(rows),
        )

    def _build_current_estimate_preview_data(self, voucher_no: str) -> Dict:
        self._update_view_model_snapshot()
        metadata = self.view_model.get_voucher_metadata()
        service = EstimateEntryPersistenceService(self.view_model)
        preparation = service.prepare_save_payload(
            voucher_no=voucher_no,
            date=metadata.get("voucher_date", ""),
            note=metadata.get("voucher_note", ""),
        )
        if preparation.skipped_rows:
            skipped = ", ".join(str(row) for row in preparation.skipped_rows)
            self._status(f"Preview skipped invalid rows: {skipped}", 5000)

        items = []
        for item in preparation.payload.items:
            items.append(
                {
                    "id": item.row_number,
                    "item_code": item.code,
                    "item_name": item.name,
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
            )

        return {
            "header": {
                "voucher_no": metadata.get("voucher_number", voucher_no) or voucher_no,
                "date": metadata.get("voucher_date", ""),
                "silver_rate": preparation.payload.silver_rate,
                "note": preparation.payload.note,
                "last_balance_silver": preparation.payload.last_balance_silver,
                "last_balance_amount": preparation.payload.last_balance_amount,
            },
            "items": items,
        }

    def _get_row_code(self, row):
        return self.item_table.get_cell_text(row, COL_CODE).strip()

    def _get_cell_str(self, row, col):
        return self.item_table.get_cell_text(row, col)

    def show_last_balance_dialog(self):
        dialog = QDialog(self._parent_widget())
        dialog.setWindowTitle("Enter Last Balance")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        lb_silver = QDoubleSpinBox()
        lb_silver.setRange(0, 1000000)
        lb_silver.setValue(self.last_balance_silver)
        form.addRow("Silver Weight (g):", lb_silver)

        lb_amount = QDoubleSpinBox()
        lb_amount.setRange(0, 10000000)
        lb_amount.setValue(self.last_balance_amount)
        form.addRow("Amount:", lb_amount)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec_():
            self.last_balance_silver = lb_silver.value()
            self.last_balance_amount = lb_amount.value()
            self.calculate_totals()
            self._mark_unsaved()
