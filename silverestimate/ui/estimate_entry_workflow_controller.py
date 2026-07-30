"""Workflow controller for estimate entry actions and state transitions."""

from __future__ import annotations

import time
from dataclasses import replace
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional, cast

from PySide6.QtCore import (
    QDate,
    QLocale,
    QObject,
    QSignalBlocker,
    Qt,
    QThread,
    QTimer,
)
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QProgressDialog,
    QVBoxLayout,
)

from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.presenter import LoadedEstimate
from silverestimate.services.dda_rate_fetcher import DdaCurrentRatesClient
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)

from .estimate_entry_logic.constants import COL_CODE, COL_GROSS
from .estimate_entry_theme import refresh_widget_style
from .item_selection_dialog import ItemSelectionDialog
from .preview_build_worker import PreviewBuildCallbackRouter, PreviewBuildWorker
from .themed_controls import ThemedDoubleSpinBox

_EstimatePreviewBuildWorker = PreviewBuildWorker


class EstimateEntryWorkflowController:
    """Handle estimate-entry workflow actions outside table/totals mechanics."""

    def __init__(self, host: Any) -> None:
        self.host = host

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
        if self.host.presenter:
            self.host.presenter.generate_voucher()
        if hasattr(self.host, "delete_estimate_button"):
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
                self.host._status(
                    f"Estimate {voucher_no} not found. Starting new entry.", 4000
                )
                self.host._estimate_loaded = False
                if hasattr(self.host, "delete_estimate_button"):
                    self.host.delete_estimate_button.setEnabled(False)
                self.host.table_controller.focus_on_code_column(0)
        except Exception as exc:
            self.host.logger.warning("Failed to load estimate %s: %s", voucher_no, exc)
            self.host._status(f"Error loading estimate: {exc}", 4000)

    def safe_load_estimate(self):
        if self.host._loading_estimate or self.host.initializing:
            return

        voucher_text = self.host.voucher_edit.text().strip()
        if not voucher_text:
            return

        if self.host.has_unsaved_changes():
            reply = QMessageBox.question(
                self._parent_widget(),
                "Discard Unsaved Changes?",
                "You have unsaved changes. Loading another estimate will discard them.\n\nContinue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.host._loading_estimate = True
        blocker = QSignalBlocker(self.host.voucher_edit)
        try:
            self.load_estimate()
        except Exception as exc:
            self.host.logger.warning("Unexpected load failure: %s", exc, exc_info=True)
        finally:
            del blocker
            self.host._loading_estimate = False

    def save_estimate(self):
        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(
                self._parent_widget(), "Input Error", "Voucher number is required."
            )
            return

        if not self.host.presenter:
            return

        self.host._status(f"Saving estimate {voucher_no}...", 2000)
        self._update_view_model_snapshot()

        service = EstimateEntryPersistenceService(self.host.view_model)
        try:
            outcome, preparation = service.execute_save(
                voucher_no=voucher_no,
                date=self.host.date_edit.date().toString("yyyy-MM-dd"),
                note=self.host.note_edit.text().strip()
                if hasattr(self.host, "note_edit")
                else "",
                presenter=self.host.presenter,
            )

            if outcome.success:
                self.host._last_saved_status = datetime.now().strftime(
                    "%d-%m-%Y %I:%M %p"
                )
                if hasattr(self.host, "refresh_bottom_status"):
                    self.host.refresh_bottom_status()
                self.host._status(outcome.message, 5000)
                QMessageBox.information(
                    self._parent_widget(), "Success", outcome.message
                )
                self.print_estimate()
                self.clear_form(confirm=False)
            else:
                QMessageBox.critical(
                    self._parent_widget(), "Save Error", outcome.message
                )
                self.host._status(outcome.message, 5000)
            del preparation
        except Exception as exc:
            self.host.logger.error(
                "Failed to save estimate %s: %s", voucher_no, exc, exc_info=True
            )
            QMessageBox.critical(self._parent_widget(), "Save Error", str(exc))

    def delete_current_estimate(self):
        voucher_no = self.host.voucher_edit.text().strip()
        if not voucher_no:
            return

        reply = QMessageBox.warning(
            self._parent_widget(),
            "Confirm Delete",
            f"Are you sure you want to delete estimate '{voucher_no}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes and self.host.presenter:
            if self.host.presenter.delete_estimate(voucher_no):
                self.host._status(f"Estimate {voucher_no} deleted.", 3000)
                self.clear_form(confirm=False)
            else:
                QMessageBox.warning(
                    self._parent_widget(), "Error", "Could not delete estimate."
                )

    def print_estimate(self):
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

    def _next_print_preview_request_id(self) -> int:
        next_id = int(getattr(self.host, "_print_preview_request_id", 0)) + 1
        self.host._print_preview_request_id = next_id
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
        progress.setWindowModality(Qt.WindowModality.WindowModal)
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

        active_workers = getattr(self.host, "_active_print_preview_workers", None)
        if active_workers is None:
            self.host._active_print_preview_workers = {}
            active_workers = self.host._active_print_preview_workers
        active_workers[thread] = worker

        callback_router = PreviewBuildCallbackRouter(
            on_ready=lambda rid, payload: self._on_estimate_print_preview_ready(
                rid,
                payload,
                print_manager=print_manager,
                progress=progress,
            ),
            on_error=lambda rid, message: self._on_estimate_print_preview_error(
                rid,
                message,
                progress=progress,
            ),
            on_finished=lambda rid: self._finalize_estimate_print_preview_build(
                rid,
                thread=thread,
                worker=worker,
                progress=progress,
                callback_router=callback_router,
            ),
            parent=self.host,
        )

        thread.started.connect(worker.run)
        worker.preview_ready.connect(callback_router.handle_ready)
        worker.preview_error.connect(callback_router.handle_error)
        worker.finished.connect(callback_router.handle_finished)
        thread.start()

    def _on_estimate_print_preview_ready(
        self,
        request_id: int,
        payload,
        *,
        print_manager,
        progress: QProgressDialog,
    ) -> None:
        if request_id != getattr(self.host, "_print_preview_request_id", 0):
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
            self.host.logger.debug(
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
        if request_id != getattr(self.host, "_print_preview_request_id", 0):
            return
        try:
            progress.close()
        except Exception as exc:
            self.host.logger.debug(
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
        callback_router: QObject | None = None,
    ) -> None:
        del request_id
        try:
            progress.close()
            progress.deleteLater()
        except Exception as exc:
            self.host.logger.debug(
                "Failed to dispose estimate print preview progress dialog: %s",
                exc,
            )
        active_workers = getattr(self.host, "_active_print_preview_workers", {})
        active_workers.pop(thread, None)
        try:
            thread.quit()
            thread.wait(2000)
        except Exception as exc:
            self.host.logger.debug(
                "Failed to stop print preview worker thread: %s", exc
            )
        try:
            worker.deleteLater()
            if callback_router is not None:
                callback_router.deleteLater()
            thread.deleteLater()
        except Exception as exc:
            self.host.logger.debug(
                "Failed to schedule estimate preview worker deletion: %s",
                exc,
            )

    def clear_form(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self._parent_widget(),
                "Confirm New Estimate",
                "Start a new estimate? Unsaved changes will be lost.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
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
            if hasattr(self.host, "note_edit"):
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
            if hasattr(self.host, "delete_estimate_button"):
                self.host.delete_estimate_button.setEnabled(False)
        finally:
            self.host.processing_cell = False
            self.host.item_table.blockSignals(False)
            self.host._pop_unsaved_block()
            QTimer.singleShot(
                50, lambda: self.host.table_controller.focus_on_code_column(0)
            )
        self.host._set_unsaved(False, force=True)

    def confirm_exit(self) -> bool:
        if not self.host.has_unsaved_changes():
            return True
        reply = QMessageBox.question(
            self._parent_widget(),
            "Discard Changes?",
            "You have unsaved changes. Exit anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

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
            self.host.return_toggle_button.setProperty("modeState", "return")
        else:
            self.host.return_toggle_button.setProperty("modeState", "idle")

        if self.host.silver_bar_mode:
            self.host.silver_bar_toggle_button.setProperty("modeState", "silver_bar")
        else:
            self.host.silver_bar_toggle_button.setProperty("modeState", "idle")

        if self.host.return_mode:
            self.host.mode_indicator_label.setText("Mode: Return Items")
            self.host.mode_indicator_label.setProperty("modeState", "return")
        elif self.host.silver_bar_mode:
            self.host.mode_indicator_label.setText("Mode: Silver Bars")
            self.host.mode_indicator_label.setProperty("modeState", "silver_bar")
        else:
            self.host.mode_indicator_label.setText("Mode: Regular")
            self.host.mode_indicator_label.setProperty("modeState", "regular")

        refresh_widget_style(self.host.return_toggle_button)
        refresh_widget_style(self.host.silver_bar_toggle_button)
        refresh_widget_style(self.host.mode_indicator_label)

    def _finalize_mode_change(self) -> None:
        self.host.table_controller._get_table_adapter().refresh_empty_row_type()
        self.host.focus_on_empty_row(update_visuals=True)
        self.host.view_model.set_modes(
            return_mode=self.host.return_mode,
            silver_bar_mode=self.host.silver_bar_mode,
        )
        self.host._update_mode_tooltip()

    def delete_current_row(self):
        row = self.host.item_table.currentRow()
        if row < 0:
            return
        if self.host.item_table.rowCount() <= 1:
            QMessageBox.warning(
                self._parent_widget(), "Error", "Cannot delete the only row."
            )
            return

        reply = QMessageBox.question(
            self._parent_widget(),
            "Delete Row",
            f"Delete row {row + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.host.item_table.delete_row(row)
            if self.host.totals_controller._totals_incremental_is_active():
                try:
                    self.host.totals_controller._remove_incremental_row(row)
                except Exception as exc:
                    self.host.totals_controller._disable_incremental_totals_and_fallback(
                        exc
                    )
            self.host.totals_controller.calculate_totals()
            self.host._mark_unsaved()
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
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.selected_voucher
        return None

    def show_silver_bar_management(self) -> None:
        if hasattr(self.host.main_window, "show_silver_bars"):
            self.host.main_window.show_silver_bars()

    def show_silver_bars(self):
        self.show_silver_bar_management()

    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        start = time.perf_counter()
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
            if hasattr(self.host, "note_edit"):
                self.host.note_edit.setText(loaded.note or "")

            self.host.last_balance_silver = loaded.last_balance_silver
            self.host.last_balance_amount = loaded.last_balance_amount

            row_states = EstimateEntryPersistenceService.build_row_states_from_items(
                loaded.items
            )
            prepared_rows = []
            for index, row_state in enumerate(row_states):
                code = (row_state.code or "").strip()
                wage_type = self.host._normalize_wage_type(
                    getattr(row_state, "wage_type", "WT")
                )
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

            self.host.item_table.replace_all_rows(prepared_rows)

            self.host.table_controller.add_empty_row()
            self.host.totals_controller.calculate_totals()
            self.host.layout_controller._schedule_columns_autofit(force=True)
            self.host._estimate_loaded = True

            if hasattr(self.host, "delete_estimate_button"):
                self.host.delete_estimate_button.setEnabled(True)

            self.host.set_voucher_number(loaded.voucher_no)
            self.host.totals_controller._log_perf_metric(
                "estimate_entry.apply_loaded_estimate",
                start,
                threshold_ms=25.0,
                rows=len(row_states),
            )
            return True
        except Exception as exc:
            self.host.logger.error("Failed to apply estimate: %s", exc, exc_info=True)
            return False
        finally:
            self.host.processing_cell = False
            self.host.item_table.blockSignals(False)
            self.host._pop_unsaved_block()
            self.host._set_unsaved(False, force=True)

    def refresh_silver_rate(self):
        button = getattr(self.host, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(False)
        if hasattr(self.host, "live_rate_value_label"):
            self.host.live_rate_value_label.setText("Refreshing…")
        if hasattr(self.host, "live_rate_meta_label"):
            self.host.live_rate_meta_label.setText("Updating")
        self.host._status("Refreshing live silver rate...", 2000)
        live_rate_controller = getattr(
            self.host.main_window, "live_rate_controller", None
        )
        if live_rate_controller is not None:
            live_rate_controller.refresh_now()
            if button is not None:
                button.setEnabled(True)
            return

        runner = getattr(self.host, "_live_rate_runner", None)
        if runner is None:
            client = DdaCurrentRatesClient(timeout=7.0)

            def fetch_rate(_request, cancel_event):
                if cancel_event.is_set():
                    return None
                snapshot = client.fetch_current()
                return None if cancel_event.is_set() else snapshot.final_rate

            runner = LatestRequestRunner(
                fetch_rate,
                parent=self.host,
                name="estimate-live-rate",
            )
            runner.result.connect(
                lambda _generation, rate: self.host.live_rate_fetched.emit(rate)
            )
            runner.failed.connect(self._handle_live_rate_failure)
            self.host._live_rate_runner = runner
        runner.submit(None)

    def _handle_live_rate_failure(self, _generation: int, error: object) -> None:
        self.host.logger.warning("Live silver rate refresh failed: %s", error)
        self.host.live_rate_fetched.emit(None)

    def _apply_refreshed_live_rate(self, rate) -> None:
        button = getattr(self.host, "refresh_rate_button", None)
        if button is not None:
            button.setEnabled(True)
        if rate:
            try:
                gram_rate = float(rate) / 1000.0
            except TypeError, ValueError:
                gram_rate = None
            if gram_rate is None:
                if hasattr(self.host, "live_rate_value_label"):
                    self.host.live_rate_value_label.setText("Unavailable")
                if hasattr(self.host, "live_rate_meta_label"):
                    self.host.live_rate_meta_label.setText("Retry")
                self.host._status("Live rate unavailable.", 3000)
                return
            if hasattr(self.host, "live_rate_value_label"):
                self.host.live_rate_value_label.setText(f"₹ {gram_rate:.2f} /g")
            if hasattr(self.host, "live_rate_meta_label"):
                self.host.live_rate_meta_label.setText("Updated")
            self.host._status("Live rate refreshed.", 2000)
            return
        if hasattr(self.host, "live_rate_value_label"):
            self.host.live_rate_value_label.setText("Unavailable")
        if hasattr(self.host, "live_rate_meta_label"):
            self.host.live_rate_meta_label.setText("Retry")
        self.host._status("Live rate unavailable.", 3000)

    def _handle_silver_rate_changed(self, *_):
        self.host.totals_controller._schedule_totals_recalc()
        self.host._mark_unsaved()

    def _update_view_model_snapshot(self):
        start = time.perf_counter()
        rows = list(self.host.item_table.get_all_rows())

        self.host.view_model.set_rows(rows)
        self.host.view_model.set_voucher_metadata(
            voucher_number=self.host.voucher_edit.text().strip(),
            voucher_date=self.host.date_edit.date().toString("yyyy-MM-dd"),
            voucher_note=(
                self.host.note_edit.text().strip()
                if hasattr(self.host, "note_edit")
                else ""
            ),
        )
        self.host.view_model.set_totals_inputs(
            silver_rate=self.host.silver_rate_spin.value(),
            last_balance_silver=self.host.last_balance_silver,
            last_balance_amount=self.host.last_balance_amount,
        )
        self.host.view_model.set_modes(
            return_mode=self.host.return_mode, silver_bar_mode=self.host.silver_bar_mode
        )
        self.host.totals_controller._log_perf_metric(
            "estimate_entry.sync_view_model",
            start,
            threshold_ms=15.0,
            rows=len(rows),
        )

    def _build_current_estimate_preview_data(self, voucher_no: str) -> Dict:
        self._update_view_model_snapshot()
        metadata = self.host.view_model.get_voucher_metadata()
        service = EstimateEntryPersistenceService(self.host.view_model)
        preparation = service.prepare_save_payload(
            voucher_no=voucher_no,
            date=metadata.get("voucher_date", ""),
            note=metadata.get("voucher_note", ""),
        )
        if preparation.skipped_rows:
            skipped = ", ".join(str(row) for row in preparation.skipped_rows)
            self.host._status(f"Preview skipped invalid rows: {skipped}", 5000)

        item_codes = [item.code for item in preparation.payload.items if item.code]
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
                "tunch": current_tunch(item.code),
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
        return self.host.item_table.get_cell_text(row, COL_CODE).strip()

    def _get_cell_str(self, row, col):
        return self.host.item_table.get_cell_text(row, col)

    def show_last_balance_dialog(self):
        dialog = QDialog(self._parent_widget())
        dialog.setWindowTitle("Enter Last Balance")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        lb_silver = ThemedDoubleSpinBox()
        lb_silver.setRange(0, 1000000)
        lb_silver.setValue(self.host.last_balance_silver)
        form.addRow("Silver Weight (g):", lb_silver)

        lb_amount = ThemedDoubleSpinBox()
        lb_amount.setRange(0, 10000000)
        lb_amount.setValue(self.host.last_balance_amount)
        form.addRow("Amount:", lb_amount)

        layout.addLayout(form)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        if dialog.exec():
            self.host.last_balance_silver = lb_silver.value()
            self.host.last_balance_amount = lb_amount.value()
            self.host.totals_controller.calculate_totals()
            self.host._mark_unsaved()
