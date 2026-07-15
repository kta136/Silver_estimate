"""Explicit typed facade forwarding estimate-entry widget actions to controllers."""

from __future__ import annotations

from typing import Any


class EstimateEntryFacade:
    """Stable widget API; controller composition is explicit and discoverable."""

    _workflow_controller: Any
    _layout_controller: Any
    _table_controller: Any
    _totals_controller: Any

    def _facade_call(
        self,
        controller_name: str,
        method_name: str,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        controller = object.__getattribute__(self, controller_name)
        method = object.__getattribute__(controller, method_name)
        return method(*args, **kwargs)

    # Workflow facade
    def _format_currency(self, value: object) -> str:
        return str(self._facade_call("_workflow_controller", "_format_currency", value))

    def generate_voucher(self) -> Any:
        return self._facade_call("_workflow_controller", "generate_voucher")

    def load_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "load_estimate", *args, **kwargs
        )

    def safe_load_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "safe_load_estimate", *args, **kwargs
        )

    def save_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "save_estimate", *args, **kwargs
        )

    def delete_current_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "delete_current_estimate", *args, **kwargs
        )

    def print_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "print_estimate", *args, **kwargs
        )

    def clear_form(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call("_workflow_controller", "clear_form", *args, **kwargs)

    def confirm_exit(self, *args: Any, **kwargs: Any) -> bool:
        return bool(
            self._facade_call("_workflow_controller", "confirm_exit", *args, **kwargs)
        )

    def show_history(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "show_history", *args, **kwargs
        )

    def toggle_return_mode(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "toggle_return_mode", *args, **kwargs
        )

    def toggle_silver_bar_mode(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "toggle_silver_bar_mode", *args, **kwargs
        )

    def delete_current_row(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "delete_current_row", *args, **kwargs
        )

    def prompt_item_selection(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "prompt_item_selection", *args, **kwargs
        )

    def focus_after_item_lookup(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "focus_after_item_lookup", *args, **kwargs
        )

    def open_history_dialog(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "open_history_dialog", *args, **kwargs
        )

    def show_silver_bar_management(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "show_silver_bar_management", *args, **kwargs
        )

    def show_silver_bars(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "show_silver_bars", *args, **kwargs
        )

    def apply_loaded_estimate(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "apply_loaded_estimate", *args, **kwargs
        )

    def refresh_silver_rate(self) -> Any:
        return self._facade_call("_workflow_controller", "refresh_silver_rate")

    def _apply_refreshed_live_rate(self, rate: object) -> Any:
        return self._facade_call(
            "_workflow_controller", "_apply_refreshed_live_rate", rate
        )

    def _handle_silver_rate_changed(self, *args: Any) -> Any:
        return self._facade_call(
            "_workflow_controller", "_handle_silver_rate_changed", *args
        )

    def _update_view_model_snapshot(self) -> Any:
        return self._facade_call("_workflow_controller", "_update_view_model_snapshot")

    def _get_row_code(self, row: int) -> str:
        return str(self._facade_call("_workflow_controller", "_get_row_code", row))

    def _get_cell_str(self, row: int, column: int) -> str:
        return str(
            self._facade_call("_workflow_controller", "_get_cell_str", row, column)
        )

    def show_last_balance_dialog(self) -> Any:
        return self._facade_call("_workflow_controller", "show_last_balance_dialog")

    # Layout facade
    def _setup_ui(self) -> Any:
        return self._facade_call("_layout_controller", "_setup_ui")

    def _move_live_rate_card_to_summary_top(self) -> Any:
        return self._facade_call(
            "_layout_controller", "_move_live_rate_card_to_summary_top"
        )

    def _sync_live_rate_card_placement(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_sync_live_rate_card_placement", *args, **kwargs
        )

    def _setup_table_delegates(self) -> Any:
        return self._facade_call("_layout_controller", "_setup_table_delegates")

    def _wire_component_signals(self) -> Any:
        return self._facade_call("_layout_controller", "_wire_component_signals")

    def _bind_totals_panel_labels(self) -> Any:
        return self._facade_call("_layout_controller", "_bind_totals_panel_labels")

    def _normalize_totals_position(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_normalize_totals_position", *args, **kwargs
        )

    def _normalize_totals_section_order(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_normalize_totals_section_order", *args, **kwargs
        )

    def _apply_totals_section_order(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_apply_totals_section_order", *args, **kwargs
        )

    def _load_totals_section_order_setting(self) -> Any:
        return self._facade_call(
            "_layout_controller", "_load_totals_section_order_setting"
        )

    def _on_totals_section_order_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_on_totals_section_order_changed", *args, **kwargs
        )

    def _apply_totals_position(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_apply_totals_position", *args, **kwargs
        )

    def _load_totals_position_setting(self) -> Any:
        return self._facade_call("_layout_controller", "_load_totals_position_setting")

    def _on_totals_position_requested(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_on_totals_position_requested", *args, **kwargs
        )

    def apply_totals_position(self, position: str) -> Any:
        return self._facade_call(
            "_layout_controller", "apply_totals_position", position
        )

    def connect_signals(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "connect_signals", *args, **kwargs
        )

    def _settings(self) -> Any:
        return self._facade_call("_layout_controller", "_settings")

    def _read_column_autofit_mode_setting(self) -> Any:
        return self._facade_call(
            "_layout_controller", "_read_column_autofit_mode_setting"
        )

    def _is_continuous_column_autofit_enabled(self) -> bool:
        return bool(
            self._facade_call(
                "_layout_controller", "_is_continuous_column_autofit_enabled"
            )
        )

    def _column_width_limits(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_column_width_limits", *args, **kwargs
        )

    def _schedule_columns_autofit(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_schedule_columns_autofit", *args, **kwargs
        )

    def _apply_pending_column_autofit(self) -> Any:
        return self._facade_call("_layout_controller", "_apply_pending_column_autofit")

    def _ensure_column_can_fit_content(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_ensure_column_can_fit_content", *args, **kwargs
        )

    def _save_column_widths_setting(self) -> Any:
        return self._facade_call("_layout_controller", "_save_column_widths_setting")

    def _load_column_widths_setting(self) -> Any:
        return self._facade_call("_layout_controller", "_load_column_widths_setting")

    def _on_item_table_section_resized(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_layout_controller", "_on_item_table_section_resized", *args, **kwargs
        )

    def _auto_stretch_item_name(self) -> Any:
        return self._facade_call("_layout_controller", "_auto_stretch_item_name")

    def _reset_columns_layout(self) -> Any:
        return self._facade_call("_layout_controller", "_reset_columns_layout")

    def _load_table_font_size_setting(self) -> Any:
        return self._facade_call("_layout_controller", "_load_table_font_size_setting")

    def _load_breakdown_font_size_setting(self) -> Any:
        return self._facade_call(
            "_layout_controller", "_load_breakdown_font_size_setting"
        )

    def _load_final_calc_font_size_setting(self) -> Any:
        return self._facade_call(
            "_layout_controller", "_load_final_calc_font_size_setting"
        )

    def apply_table_font_size(self, size: int) -> Any:
        return self._facade_call("_layout_controller", "apply_table_font_size", size)

    def apply_breakdown_font_size(self, size: int) -> Any:
        return self._facade_call(
            "_layout_controller", "apply_breakdown_font_size", size
        )

    def apply_final_calc_font_size(self, size: int) -> Any:
        return self._facade_call(
            "_layout_controller", "apply_final_calc_font_size", size
        )

    # Table facade
    def _get_table_adapter(self) -> Any:
        return self._facade_call("_table_controller", "_get_table_adapter")

    @property
    def table_adapter(self) -> Any:
        return self._get_table_adapter()

    def populate_item_row(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "populate_item_row", *args, **kwargs
        )

    def add_empty_row(self) -> Any:
        return self._facade_call("_table_controller", "add_empty_row")

    def clear_all_rows(self) -> Any:
        return self._facade_call("_table_controller", "clear_all_rows")

    def _on_table_cell_edited(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_on_table_cell_edited", *args, **kwargs
        )

    def _on_table_row_delete_requested(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_on_table_row_delete_requested", *args, **kwargs
        )

    def cell_clicked(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call("_table_controller", "cell_clicked", *args, **kwargs)

    def selection_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "selection_changed", *args, **kwargs
        )

    def current_cell_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "current_cell_changed", *args, **kwargs
        )

    def handle_cell_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "handle_cell_changed", *args, **kwargs
        )

    def _schedule_auto_advance_from(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_schedule_auto_advance_from", *args, **kwargs
        )

    def _auto_advance_if_origin_unchanged(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_auto_advance_if_origin_unchanged", *args, **kwargs
        )

    def _schedule_focus_code_from(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_schedule_focus_code_from", *args, **kwargs
        )

    def _focus_code_if_origin_unchanged(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_focus_code_if_origin_unchanged", *args, **kwargs
        )

    def _mark_manual_row_navigation(self) -> Any:
        return self._facade_call("_table_controller", "_mark_manual_row_navigation")

    def _manual_row_nav_recent(self) -> bool:
        return bool(self._facade_call("_table_controller", "_manual_row_nav_recent"))

    def process_item_code(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "process_item_code", *args, **kwargs
        )

    def _is_code_empty(self, *args: Any, **kwargs: Any) -> bool:
        return bool(
            self._facade_call("_table_controller", "_is_code_empty", *args, **kwargs)
        )

    def _enforce_code_required(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_enforce_code_required", *args, **kwargs
        )

    def move_to_next_cell(self) -> Any:
        return self._facade_call("_table_controller", "move_to_next_cell")

    def move_to_previous_cell(self) -> Any:
        return self._facade_call("_table_controller", "move_to_previous_cell")

    def _next_edit_target(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_next_edit_target", *args, **kwargs
        )

    def _previous_edit_target(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_previous_edit_target", *args, **kwargs
        )

    def focus_on_code_column(self, row: int) -> Any:
        return self._facade_call("_table_controller", "focus_on_code_column", row)

    def _safe_edit_item(self, row: int, column: int) -> Any:
        return self._facade_call("_table_controller", "_safe_edit_item", row, column)

    def _is_table_valid(self) -> bool:
        return bool(self._facade_call("_table_controller", "_is_table_valid"))

    def _is_pieces_editable_for_row(self, *args: Any, **kwargs: Any) -> bool:
        return bool(
            self._facade_call(
                "_table_controller", "_is_pieces_editable_for_row", *args, **kwargs
            )
        )

    def _should_force_code_focus(self, *args: Any, **kwargs: Any) -> bool:
        return bool(
            self._facade_call(
                "_table_controller", "_should_force_code_focus", *args, **kwargs
            )
        )

    def _get_cell_float(self, *args: Any, **kwargs: Any) -> float:
        return float(
            self._facade_call("_table_controller", "_get_cell_float", *args, **kwargs)
        )

    def _get_cell_int(self, *args: Any, **kwargs: Any) -> int:
        return int(
            self._facade_call("_table_controller", "_get_cell_int", *args, **kwargs)
        )

    def _schedule_cell_edit(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_schedule_cell_edit", *args, **kwargs
        )

    def _request_edit_cell(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_request_edit_cell", *args, **kwargs
        )

    def _run_edit_request(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_run_edit_request", *args, **kwargs
        )

    # Totals facade
    def calculate_net_weight(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "calculate_net_weight", *args, **kwargs
        )

    def calculate_fine(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "calculate_fine", *args, **kwargs
        )

    def calculate_wage(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "calculate_wage", *args, **kwargs
        )

    def _row_wage_type(self, *args: Any, **kwargs: Any) -> str:
        return str(
            self._facade_call("_totals_controller", "_row_wage_type", *args, **kwargs)
        )

    def _recompute_row_derived_values(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_recompute_row_derived_values", *args, **kwargs
        )

    def _schedule_totals_recalc(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_schedule_totals_recalc", *args, **kwargs
        )

    def _apply_incremental_totals_now(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_apply_incremental_totals_now", *args, **kwargs
        )

    def _refresh_totals_after_row_edit(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_refresh_totals_after_row_edit", *args, **kwargs
        )

    def _log_perf_metric(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_log_perf_metric", *args, **kwargs
        )

    def _inactive_row_contribution(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_inactive_row_contribution", *args, **kwargs
        )

    def _totals_incremental_is_active(self) -> bool:
        return bool(
            self._facade_call("_totals_controller", "_totals_incremental_is_active")
        )

    def _category_bucket_for(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_category_bucket_for", *args, **kwargs
        )

    def _row_contribution_from_row_state(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_row_contribution_from_row_state", *args, **kwargs
        )

    def _apply_signed_contribution(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_apply_signed_contribution", *args, **kwargs
        )

    def _apply_contribution_delta(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_apply_contribution_delta", *args, **kwargs
        )

    def _reset_incremental_aggregates(self) -> Any:
        return self._facade_call("_totals_controller", "_reset_incremental_aggregates")

    def _rebuild_incremental_totals_from_table(self) -> Any:
        return self._facade_call(
            "_totals_controller", "_rebuild_incremental_totals_from_table"
        )

    def _update_incremental_for_row(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_update_incremental_for_row", *args, **kwargs
        )

    def _remove_incremental_row(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_remove_incremental_row", *args, **kwargs
        )

    def _frozen_category_totals(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "_frozen_category_totals", *args, **kwargs
        )

    def _build_totals_result_from_aggregates(self) -> Any:
        return self._facade_call(
            "_totals_controller", "_build_totals_result_from_aggregates"
        )

    def _disable_incremental_totals_and_fallback(
        self, *args: Any, **kwargs: Any
    ) -> Any:
        return self._facade_call(
            "_totals_controller",
            "_disable_incremental_totals_and_fallback",
            *args,
            **kwargs,
        )

    def calculate_totals(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_totals_controller", "calculate_totals", *args, **kwargs
        )


__all__ = ["EstimateEntryFacade"]
