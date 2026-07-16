#!/usr/bin/env python
"""Estimate entry widget - refactored to use controller components."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, cast

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from silverestimate.domain.estimate_models import EstimateLineCategory, TotalsResult
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryView,
    EstimateEntryViewState,
)

from .estimate_entry_facade import EstimateEntryFacade
from .estimate_entry_layout_controller import EstimateEntryLayoutController
from .estimate_entry_logic.constants import (
    COL_CODE,
    COL_GROSS,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
)
from .estimate_entry_table_controller import EstimateEntryTableController
from .estimate_entry_totals_controller import EstimateEntryTotalsController
from .estimate_entry_workflow_controller import EstimateEntryWorkflowController
from .inline_status import InlineStatusController
from .view_models import EstimateEntryViewModel


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


class EstimateEntryWidget(EstimateEntryFacade, QWidget):
    """Widget for silver estimate entry and management."""

    if TYPE_CHECKING:
        item_table: Any
        mode_indicator_label: Any
        secondary_actions: Any
        toolbar: Any
        totals_panel: Any
        voucher_edit: Any

        def __getattr__(self, name: str) -> Any: ...

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
        self._workflow_controller = EstimateEntryWorkflowController(self)

        self.db_manager = db_manager
        self.main_window = main_window
        self.presenter = EstimateEntryPresenter(
            cast(EstimateEntryView, self), repository
        )
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
        self._initial_focus_scheduled = False

        self.return_mode = False
        self.silver_bar_mode = False
        self.view_model = EstimateEntryViewModel()
        self.view_model.set_modes(
            return_mode=self.return_mode,
            silver_bar_mode=self.silver_bar_mode,
        )
        self._incremental_totals_failed = False
        self._row_contrib_cache: dict[int, _RowContribution] = {}
        self._agg_regular = _RunningCategoryTotals()
        self._agg_returns = _RunningCategoryTotals()
        self._agg_silver_bars = _RunningCategoryTotals()
        self._agg_overall_gross = 0.0
        self._agg_overall_poly = 0.0

        self._programmatic_resizing = False
        self._column_autofit_mode = self._read_column_autofit_mode_setting()
        self._auto_fit_columns_by_content = self._column_autofit_mode == "continuous"
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

        self._on_unsaved_state_changed(False)
        self._update_mode_tooltip()

        self._load_table_font_size_setting()
        self._load_breakdown_font_size_setting()
        self._load_final_calc_font_size_setting()

        self.initializing = False
        self.reconnect_load_estimate()

    def showEvent(self, event):
        super().showEvent(event)
        if self._initial_focus_scheduled:
            return
        self._initial_focus_scheduled = True
        QTimer.singleShot(0, self.force_focus_to_first_cell)

    def show_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def show_inline_status(self, message, timeout=3000, level="info"):
        self._status_helper.show(message, timeout=timeout, level=level)

    def refresh_bottom_status(self) -> None:
        refresher = getattr(self._layout_controller, "refresh_bottom_status", None)
        if callable(refresher):
            refresher()

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
        try:
            self.refresh_bottom_status()
        except Exception as exc:
            self.logger.debug("Could not refresh estimate status strip: %s", exc)
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

    def resizeEvent(self, event):
        self._auto_stretch_item_name()
        super().resizeEvent(event)

    def closeEvent(self, event):
        if not self.confirm_exit():
            event.ignore()
            return
        live_rate_runner = getattr(self, "_live_rate_runner", None)
        if live_rate_runner is not None:
            live_rate_runner.shutdown()
        self._save_column_widths_setting()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if modifiers & Qt.KeyboardModifier.ControlModifier:
            if key == Qt.Key.Key_R:
                self.toggle_return_mode()
                event.accept()
                return
            if key == Qt.Key.Key_B:
                self.toggle_silver_bar_mode()
                event.accept()
                return

        focus_widget = QApplication.focusWidget()
        table_has_focus = focus_widget is self.item_table or (
            focus_widget is not None and self.item_table.isAncestorOf(focus_widget)
        )

        if table_has_focus and key in [
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Tab,
        ]:
            self.move_to_next_cell()
            event.accept()
        elif table_has_focus and key == Qt.Key.Key_Backtab:
            self.move_to_previous_cell()
            event.accept()
        elif table_has_focus and key in [Qt.Key.Key_Up, Qt.Key.Key_Down]:
            self._mark_manual_row_navigation()
            super().keyPressEvent(event)
        elif table_has_focus and key == Qt.Key.Key_Escape:
            self.confirm_exit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def force_focus_to_first_cell(self):
        if self.item_table.rowCount() <= 0 or not self._should_force_code_focus():
            return
        current_index = self.item_table.currentIndex()
        if current_index.isValid() and (
            current_index.row() != 0 or current_index.column() != COL_CODE
        ):
            return
        self.item_table.setFocus(Qt.FocusReason.OtherFocusReason)
        self.item_table.setCurrentCell(0, COL_CODE)
        QTimer.singleShot(0, lambda: self._safe_edit_item(0, COL_CODE))

    def reconnect_load_estimate(self):
        try:
            self.voucher_edit.returnPressed.disconnect(self.safe_load_estimate)
        except (TypeError, RuntimeError) as exc:
            self.logger.debug(
                "Could not disconnect voucher returnPressed handler: %s", exc
            )
        self.voucher_edit.returnPressed.connect(self.safe_load_estimate)
