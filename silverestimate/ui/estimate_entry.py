#!/usr/bin/env python
"""Estimate entry widget - refactored to use controller components."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, cast

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QWidget

from silverestimate.domain.estimate_models import EstimateLineCategory, TotalsResult
from silverestimate.presenter import (
    EstimateEntryPresenter,
    EstimateEntryView,
    EstimateEntryViewState,
)

from .estimate_entry_logic.constants import (
    COL_CODE,
    COL_GROSS,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
)
from .estimate_entry_layout_controller import EstimateEntryLayoutController
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


class EstimateEntryWidget(QWidget):
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
    "_format_currency",
    "generate_voucher",
    "load_estimate",
    "safe_load_estimate",
    "save_estimate",
    "delete_current_estimate",
    "print_estimate",
    "clear_form",
    "confirm_exit",
    "show_history",
    "toggle_return_mode",
    "toggle_silver_bar_mode",
    "delete_current_row",
    "prompt_item_selection",
    "focus_after_item_lookup",
    "open_history_dialog",
    "show_silver_bar_management",
    "show_silver_bars",
    "apply_loaded_estimate",
    "refresh_silver_rate",
    "_apply_refreshed_live_rate",
    "_handle_silver_rate_changed",
    "_update_view_model_snapshot",
    "_get_row_code",
    "_get_cell_str",
    "show_last_balance_dialog",
):
    setattr(
        EstimateEntryWidget,
        _method_name,
        _delegate("_workflow_controller", _method_name),
    )

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
    "_ensure_column_can_fit_content",
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
    "_apply_incremental_totals_now",
    "_refresh_totals_after_row_edit",
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
