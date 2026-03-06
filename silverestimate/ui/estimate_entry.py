#!/usr/bin/env python
"""Estimate entry widget - refactored to use controller components."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, replace
from typing import Dict, Optional

from PyQt5 import sip
from PyQt5.QtCore import QDate, QLocale, QSignalBlocker, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.estimate_models import EstimateLineCategory, TotalsResult
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryViewState,
    LoadedEstimate,
)
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
)

from .estimate_entry_layout_controller import EstimateEntryLayoutController
from .estimate_entry_table_controller import EstimateEntryTableController
from .estimate_entry_totals_controller import EstimateEntryTotalsController
from .estimate_entry_ui import (
    COL_CODE,
    COL_GROSS,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from .inline_status import InlineStatusController
from .item_selection_dialog import ItemSelectionDialog
from .view_models import EstimateEntryRowState, EstimateEntryViewModel


@dataclass(frozen=True)
class _RowContribution:
    category: EstimateLineCategory = EstimateLineCategory.REGULAR
    gross: float = 0.0
    poly: float = 0.0
    net: float = 0.0
    fine: float = 0.0
    wage: float = 0.0
    is_active: bool = False


@dataclass
class _RunningCategoryTotals:
    gross: float = 0.0
    net: float = 0.0
    fine: float = 0.0
    wage: float = 0.0


class EstimateEntryWidget(QWidget):
    """Widget for silver estimate entry and management."""

    live_rate_fetched = pyqtSignal(object)
    EDITABLE_ENTRY_COLS = (
        COL_CODE,
        COL_GROSS,
        COL_POLY,
        COL_PURITY,
        COL_WAGE_RATE,
        COL_PIECES,
    )

    @staticmethod
    def _normalize_wage_type(value: object) -> str:
        return "PC" if str(value or "").strip().upper() == "PC" else "WT"

    def __init__(self, db_manager, main_window, repository):
        super().__init__()

        self.logger = logging.getLogger(__name__)
        self._layout_controller = EstimateEntryLayoutController(self)
        self._table_controller = EstimateEntryTableController(self)
        self._totals_controller = EstimateEntryTotalsController(self)

        self.db_manager = db_manager
        self.main_window = main_window
        self.presenter = EstimateEntryPresenter(self, repository)
        self.live_rate_fetched.connect(self._apply_refreshed_live_rate)

        self.initializing = True
        self._loading_estimate = False
        self._estimate_loaded = False
        self._unsaved_changes = False
        self._unsaved_block = 0
        self._enforcing_code_nav = False
        self.processing_cell = False
        self.current_row = -1
        self.current_column = COL_CODE
        self.last_balance_silver = 0.0
        self.last_balance_amount = 0.0

        self._table_adapter = None
        self._last_manual_row_nav_ts = 0.0
        self._edit_request_token = 0
        self._manual_row_nav_edit_delay_ms = 35

        self.return_mode = False
        self.silver_bar_mode = False
        self.view_model = EstimateEntryViewModel()
        self.view_model.set_modes(
            return_mode=self.return_mode,
            silver_bar_mode=self.silver_bar_mode,
        )
        self._incremental_totals_enabled = True
        self._incremental_totals_failed = False
        try:
            self._incremental_totals_enabled = bool(
                self._settings().value(
                    "perf/incremental_totals_enabled",
                    defaultValue=True,
                    type=bool,
                )
            )
        except (AttributeError, TypeError, ValueError):
            self._incremental_totals_enabled = True
        self._row_contrib_cache: dict[int, _RowContribution] = {}
        self._agg_regular = _RunningCategoryTotals()
        self._agg_returns = _RunningCategoryTotals()
        self._agg_silver_bars = _RunningCategoryTotals()
        self._agg_overall_gross = 0.0
        self._agg_overall_poly = 0.0

        self._use_stretch_for_item_name = False
        self._programmatic_resizing = False
        self._column_autofit_mode = self._read_column_autofit_mode_setting()
        self._auto_fit_columns_by_content = self._column_autofit_mode in (
            "explicit",
            "continuous",
        )
        self._pending_autofit_columns: set[int] = set()
        self._column_autofit_timer = QTimer(self)
        self._column_autofit_timer.setSingleShot(True)
        self._column_autofit_timer.setInterval(70)
        self._column_autofit_timer.timeout.connect(self._apply_pending_column_autofit)

        self._setup_ui()
        self._load_totals_section_order_setting()
        self._load_totals_position_setting()
        self._setup_table_delegates()

        self._column_save_timer = QTimer(self)
        self._column_save_timer.setSingleShot(True)
        self._column_save_timer.setInterval(350)
        self._column_save_timer.timeout.connect(self._save_column_widths_setting)
        self._load_column_widths_setting()

        if self._use_stretch_for_item_name:
            QTimer.singleShot(0, self._auto_stretch_item_name)

        self._status_helper = InlineStatusController(
            parent=self,
            label_getter=lambda: getattr(self.toolbar, "status_message_label", None),
            logger=self.logger,
        )

        self.clear_all_rows()
        self.add_empty_row()

        if self.presenter:
            try:
                self.presenter.generate_voucher(silent=True)
                self.logger.info("Generated new voucher silently.")
                self.secondary_actions.enable_delete_estimate(False)
                self._estimate_loaded = False
            except Exception as exc:
                self.logger.error(
                    "Error generating voucher number silently: %s", exc, exc_info=True
                )

        self.connect_signals(skip_load_estimate=True)
        self._wire_component_signals()

        self._totals_timer = QTimer(self)
        self._totals_timer.setSingleShot(True)
        self._totals_timer.setInterval(100)
        self._totals_timer.timeout.connect(self.calculate_totals)

        self._setup_keyboard_shortcuts()

        self._on_unsaved_state_changed(False)
        self._update_mode_tooltip()

        self._load_table_font_size_setting()
        self._load_breakdown_font_size_setting()
        self._load_final_calc_font_size_setting()

        self.initializing = False
        QTimer.singleShot(100, self.force_focus_to_first_cell)
        QTimer.singleShot(100, self.reconnect_load_estimate)

    def _setup_keyboard_shortcuts(self):
        pass

    def show_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def show_inline_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def _status(self, message, timeout=3000):
        self.show_status(message, timeout)

    def has_unsaved_changes(self) -> bool:
        return bool(getattr(self, "_unsaved_changes", False))

    def _push_unsaved_block(self) -> None:
        self._unsaved_block = getattr(self, "_unsaved_block", 0) + 1

    def _pop_unsaved_block(self) -> None:
        if getattr(self, "_unsaved_block", 0) > 0:
            self._unsaved_block -= 1

    def _set_unsaved(self, dirty: bool, *, force: bool = False) -> None:
        if not force and dirty and getattr(self, "_unsaved_block", 0) > 0:
            return
        previous = getattr(self, "_unsaved_changes", False)
        self._unsaved_changes = dirty
        if previous != dirty or force:
            self._on_unsaved_state_changed(dirty)

    def _mark_unsaved(self, *_, **__) -> None:
        self._set_unsaved(True)

    def _on_unsaved_state_changed(self, dirty: bool) -> None:
        self.toolbar.show_unsaved_badge(dirty)
        if self.main_window and hasattr(self.main_window, "setWindowModified"):
            try:
                self.main_window.setWindowModified(bool(dirty))
            except Exception as exc:
                self.logger.debug("Could not update window modified state: %s", exc)

    def _update_mode_tooltip(self) -> None:
        if self.return_mode:
            mode = "Return Items"
        elif self.silver_bar_mode:
            mode = "Silver Bars"
        else:
            mode = "Regular Items"
        tip = f"Current mode: {mode}\nCtrl+R: Return Items\nCtrl+B: Silver Bars"
        try:
            self.mode_indicator_label.setToolTip(tip)
        except Exception as exc:
            self.logger.debug("Could not update mode tooltip: %s", exc)

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
            self.logger.debug("Could not reconnect voucher returnPressed handler: %s", exc)

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
                self,
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
            QMessageBox.warning(self, "Input Error", "Voucher number is required.")
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
                note=self.note_edit.text().strip() if hasattr(self, "note_edit") else "",
                presenter=self.presenter,
            )

            if outcome.success:
                self._status(outcome.message, 5000)
                QMessageBox.information(self, "Success", outcome.message)
                self.print_estimate()
                self.clear_form(confirm=False)
            else:
                QMessageBox.critical(self, "Save Error", outcome.message)
                self._status(outcome.message, 5000)
            del preparation
        except Exception as exc:
            self.logger.error("Failed to save estimate %s: %s", voucher_no, exc, exc_info=True)
            QMessageBox.critical(self, "Save Error", str(exc))

    def delete_current_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        reply = QMessageBox.warning(
            self,
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
                QMessageBox.warning(self, "Error", "Could not delete estimate.")

    def print_estimate(self):
        from silverestimate.ui.print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            return

        current_font = getattr(self.main_window, "print_font", None)
        pm = PrintManager(self.db_manager, print_font=current_font)
        pm.print_estimate(voucher_no, self)

    def clear_form(self, confirm: bool = True):
        if confirm:
            reply = QMessageBox.question(
                self,
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
            self,
            "Discard Changes?",
            "You have unsaved changes. Exit anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def show_history(self):
        if self.presenter:
            self.presenter.open_history()

    def toggle_return_mode(self):
        if not self.return_mode and self.silver_bar_mode:
            self.toggle_silver_bar_mode()

        self.return_mode = not self.return_mode
        self.return_toggle_button.setChecked(self.return_mode)

        if self.return_mode:
            self.return_toggle_button.setText("↩ RETURN ON")
            self.return_toggle_button.setStyleSheet(
                "background-color: #e8f4fd; border: 2px solid #0066cc; font-weight: bold; color: #003d7a;"
            )
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet(
                "font-weight: bold; color: #0066cc;"
            )
        else:
            self.return_toggle_button.setText("↩ Return Items")
            self.return_toggle_button.setStyleSheet("")
            self.mode_indicator_label.setText("Mode: Regular")
            self.mode_indicator_label.setStyleSheet("")

        self._get_table_adapter().refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )
        self._update_mode_tooltip()

    def toggle_silver_bar_mode(self):
        if not self.silver_bar_mode and self.return_mode:
            self.toggle_return_mode()

        self.silver_bar_mode = not self.silver_bar_mode
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("🥈 BAR ON")
            self.silver_bar_toggle_button.setStyleSheet(
                "background-color: #fff4e6; border: 2px solid #cc6600; font-weight: bold; color: #994d00;"
            )
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet(
                "font-weight: bold; color: #cc6600;"
            )
        else:
            self.silver_bar_toggle_button.setText("🥈 Silver Bars")
            self.silver_bar_toggle_button.setStyleSheet("")
            self.mode_indicator_label.setText("Mode: Regular")
            self.mode_indicator_label.setStyleSheet("")

        self._get_table_adapter().refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self.view_model.set_modes(
            return_mode=self.return_mode, silver_bar_mode=self.silver_bar_mode
        )
        self._update_mode_tooltip()

    def delete_current_row(self):
        row = self.item_table.currentRow()
        if row < 0:
            return
        if self.item_table.rowCount() <= 1:
            QMessageBox.warning(self, "Error", "Cannot delete the only row.")
            return

        reply = QMessageBox.question(
            self,
            "Delete Row",
            f"Delete row {row+1}?",
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

    def focus_on_empty_row(self, update_visuals=False):
        self._get_table_adapter().focus_on_empty_row(update_visuals=update_visuals)

    def capture_state(self) -> EstimateEntryViewState:
        self._update_view_model_snapshot()
        return self.view_model.as_view_state()

    def apply_totals(self, totals: TotalsResult) -> None:
        self.totals_panel.set_totals(totals)

    def set_voucher_number(self, voucher_no: str) -> None:
        self.voucher_edit.blockSignals(True)
        self.voucher_edit.setText(voucher_no)
        self.voucher_edit.blockSignals(False)

    def populate_row(self, row_index: int, item_data: Dict) -> None:
        self._get_table_adapter().populate_row(row_index, item_data)
        self._schedule_columns_autofit()

    def prompt_item_selection(self, code: str) -> Optional[Dict]:
        dialog = ItemSelectionDialog(self.db_manager, code, self)
        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_selected_item()
        return None

    def focus_after_item_lookup(self, row_index: int) -> None:
        self._schedule_cell_edit(row_index, COL_GROSS)

    def open_history_dialog(self) -> Optional[str]:
        from silverestimate.ui.estimate_history import EstimateHistoryDialog

        dialog = EstimateHistoryDialog(
            self.db_manager, main_window_ref=self.main_window, parent=self
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

            prepared_rows: list[EstimateEntryRowState] = []
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

    def _get_row_code(self, row):
        return self.item_table.get_cell_text(row, COL_CODE).strip()

    def _get_cell_str(self, row, col):
        return self.item_table.get_cell_text(row, col)

    def show_last_balance_dialog(self):
        dialog = QDialog(self)
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

    def _apply_table_font_size(self, size: int) -> bool:
        return self.apply_table_font_size(size)

    def _apply_breakdown_font_size(self, size: int) -> bool:
        return self.apply_breakdown_font_size(size)

    def _apply_final_calc_font_size(self, size: int) -> bool:
        return self.apply_final_calc_font_size(size)

    def resizeEvent(self, event):
        self._auto_stretch_item_name()
        super().resizeEvent(event)

    def closeEvent(self, event):
        if not self.confirm_exit():
            event.ignore()
            return
        self._save_column_widths_setting()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.ControlModifier:
            if key == Qt.Key_R:
                self.toggle_return_mode()
                event.accept()
                return
            if key == Qt.Key_B:
                self.toggle_silver_bar_mode()
                event.accept()
                return

        focus_widget = QApplication.focusWidget()
        table_has_focus = focus_widget is self.item_table or (
            focus_widget is not None and self.item_table.isAncestorOf(focus_widget)
        )

        if table_has_focus and key in [Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab]:
            self.move_to_next_cell()
            event.accept()
        elif table_has_focus and key == Qt.Key_Backtab:
            self.move_to_previous_cell()
            event.accept()
        elif table_has_focus and key in [Qt.Key_Up, Qt.Key_Down]:
            self._mark_manual_row_navigation()
            super().keyPressEvent(event)
        elif table_has_focus and key == Qt.Key_Escape:
            self.confirm_exit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def force_focus_to_first_cell(self):
        if self.item_table.rowCount() > 0:
            self.item_table.setCurrentCell(0, COL_CODE)
            QTimer.singleShot(10, lambda: self._safe_edit_item(0, COL_CODE))

    def reconnect_load_estimate(self):
        try:
            self.voucher_edit.returnPressed.disconnect(self.safe_load_estimate)
        except (TypeError, RuntimeError) as exc:
            self.logger.debug(
                "Could not disconnect voucher returnPressed handler: %s", exc
            )
        self.voucher_edit.returnPressed.connect(self.safe_load_estimate)


def _delegate(controller_attr: str, method_name: str):
    def _method(self, *args, **kwargs):
        controller = getattr(self, controller_attr)
        return object.__getattribute__(controller, method_name)(*args, **kwargs)

    _method.__name__ = method_name
    _method.__qualname__ = f"EstimateEntryWidget.{method_name}"
    return _method


for _method_name in (
    "_setup_ui",
    "_move_live_rate_card_to_summary_top",
    "_sync_live_rate_card_placement",
    "_setup_table_delegates",
    "_wire_component_signals",
    "_bind_totals_panel_labels",
    "_normalize_totals_position",
    "_normalize_totals_section_order",
    "_apply_totals_section_order",
    "_load_totals_section_order_setting",
    "_on_totals_section_order_changed",
    "_apply_totals_position",
    "_load_totals_position_setting",
    "_on_totals_position_requested",
    "apply_totals_position",
    "connect_signals",
    "_settings",
    "_read_column_autofit_mode_setting",
    "_is_continuous_column_autofit_enabled",
    "_column_width_limits",
    "_schedule_columns_autofit",
    "_apply_pending_column_autofit",
    "_save_column_widths_setting",
    "_load_column_widths_setting",
    "_on_item_table_section_resized",
    "_auto_stretch_item_name",
    "_reset_columns_layout",
    "_load_table_font_size_setting",
    "_load_breakdown_font_size_setting",
    "_load_final_calc_font_size_setting",
    "apply_table_font_size",
    "apply_breakdown_font_size",
    "apply_final_calc_font_size",
):
    setattr(
        EstimateEntryWidget,
        _method_name,
        _delegate("_layout_controller", _method_name),
    )

for _method_name in (
    "_get_table_adapter",
    "populate_item_row",
    "add_empty_row",
    "clear_all_rows",
    "_on_table_cell_edited",
    "_on_table_row_delete_requested",
    "cell_clicked",
    "selection_changed",
    "current_cell_changed",
    "handle_cell_changed",
    "_schedule_auto_advance_from",
    "_auto_advance_if_origin_unchanged",
    "_schedule_focus_code_from",
    "_focus_code_if_origin_unchanged",
    "_mark_manual_row_navigation",
    "_manual_row_nav_recent",
    "process_item_code",
    "_is_code_empty",
    "_enforce_code_required",
    "move_to_next_cell",
    "move_to_previous_cell",
    "_next_edit_target",
    "_previous_edit_target",
    "focus_on_code_column",
    "_safe_edit_item",
    "_is_table_valid",
    "_is_pieces_editable_for_row",
    "_should_force_code_focus",
    "_get_cell_float",
    "_get_cell_int",
    "_schedule_cell_edit",
    "_request_edit_cell",
    "_run_edit_request",
):
    setattr(
        EstimateEntryWidget,
        _method_name,
        _delegate("_table_controller", _method_name),
    )

for _method_name in (
    "calculate_net_weight",
    "calculate_fine",
    "calculate_wage",
    "_row_wage_type",
    "_recompute_row_derived_values",
    "_schedule_totals_recalc",
    "_log_perf_metric",
    "_inactive_row_contribution",
    "_totals_incremental_is_active",
    "_category_bucket_for",
    "_row_contribution_from_row_state",
    "_apply_signed_contribution",
    "_apply_contribution_delta",
    "_reset_incremental_aggregates",
    "_rebuild_incremental_totals_from_table",
    "_update_incremental_for_row",
    "_remove_incremental_row",
    "_frozen_category_totals",
    "_build_totals_result_from_aggregates",
    "_calculate_totals_full_legacy",
    "_disable_incremental_totals_and_fallback",
    "calculate_totals",
):
    setattr(
        EstimateEntryWidget,
        _method_name,
        _delegate("_totals_controller", _method_name),
    )


EstimateEntryWidget.table_adapter = property(  # type: ignore[attr-defined]
    lambda self: self._get_table_adapter()
)
