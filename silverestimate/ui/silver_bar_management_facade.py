"""Explicit typed facade for the silver-bar management controllers."""

from __future__ import annotations

from typing import Any


class SilverBarManagementFacade:
    """Stable dialog API with explicit controller ownership."""

    _ui_builder: Any
    _load_controller: Any
    _transfer_controller: Any
    _list_lifecycle_controller: Any
    _list_print_controller: Any
    _table_controller: Any
    _state_store: Any
    _selection_state_controller: Any

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

    def init_ui(self) -> Any:
        return self._facade_call("_ui_builder", "init_ui")

    def _schedule_available_reload(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "_schedule_available_reload", *args, **kwargs
        )

    def _next_load_request_id(self, *args: Any, **kwargs: Any) -> int:
        return int(
            self._facade_call(
                "_load_controller", "_next_load_request_id", *args, **kwargs
            )
        )

    def _is_latest_load(self, *args: Any, **kwargs: Any) -> bool:
        return bool(
            self._facade_call("_load_controller", "_is_latest_load", *args, **kwargs)
        )

    def _start_bars_load(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "_start_bars_load", *args, **kwargs
        )

    def _on_bars_load_ready(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "_on_bars_load_ready", *args, **kwargs
        )

    def _on_bars_load_error(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "_on_bars_load_error", *args, **kwargs
        )

    def _on_bars_load_finished(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "_on_bars_load_finished", *args, **kwargs
        )

    def _cancel_active_loads(self) -> Any:
        return self._facade_call("_load_controller", "_cancel_active_loads")

    def _shutdown_loads(self) -> Any:
        return self._facade_call("_load_controller", "_shutdown_loads")

    def load_available_bars(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "load_available_bars", *args, **kwargs
        )

    def load_lists(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call("_load_controller", "load_lists", *args, **kwargs)

    def list_selection_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "list_selection_changed", *args, **kwargs
        )

    def load_bars_in_selected_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_load_controller", "load_bars_in_selected_list", *args, **kwargs
        )

    def _bulk_assign_to_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "_bulk_assign_to_list", *args, **kwargs
        )

    def _bulk_remove_from_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "_bulk_remove_from_list", *args, **kwargs
        )

    def add_selected_to_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "add_selected_to_list", *args, **kwargs
        )

    def remove_selected_from_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "remove_selected_from_list", *args, **kwargs
        )

    def add_all_filtered_to_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "add_all_filtered_to_list", *args, **kwargs
        )

    def remove_all_from_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "remove_all_from_list", *args, **kwargs
        )

    def export_current_list_to_csv(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_transfer_controller", "export_current_list_to_csv", *args, **kwargs
        )

    def create_new_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_lifecycle_controller", "create_new_list", *args, **kwargs
        )

    def _create_list_from_selection(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_lifecycle_controller", "_create_list_from_selection", *args, **kwargs
        )

    def edit_list_note(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_lifecycle_controller", "edit_list_note", *args, **kwargs
        )

    def delete_selected_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_lifecycle_controller", "delete_selected_list", *args, **kwargs
        )

    def mark_list_as_issued(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_lifecycle_controller", "mark_list_as_issued", *args, **kwargs
        )

    def print_selected_list(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_print_controller", "print_selected_list", *args, **kwargs
        )

    def _next_print_preview_request_id(self) -> int:
        return int(
            self._facade_call(
                "_list_print_controller", "_next_print_preview_request_id"
            )
        )

    def _start_list_print_preview_build(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_print_controller", "_start_list_print_preview_build", *args, **kwargs
        )

    def _on_list_print_preview_ready(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_print_controller", "_on_list_print_preview_ready", *args, **kwargs
        )

    def _on_list_print_preview_error(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_print_controller", "_on_list_print_preview_error", *args, **kwargs
        )

    def _finish_list_print_preview_build(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_list_print_controller",
            "_finish_list_print_preview_build",
            *args,
            **kwargs,
        )

    def _table_cell_value(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_table_cell_value", *args, **kwargs
        )

    def _table_cell_text(self, *args: Any, **kwargs: Any) -> str:
        return str(
            self._facade_call("_table_controller", "_table_cell_text", *args, **kwargs)
        )

    def _bar_id_from_table(self, *args: Any, **kwargs: Any) -> int | None:
        value = self._facade_call(
            "_table_controller", "_bar_id_from_table", *args, **kwargs
        )
        return int(value) if value is not None else None

    def _clear_management_table(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_clear_management_table", *args, **kwargs
        )

    def _populate_table(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_populate_table", *args, **kwargs
        )

    def _show_available_context_menu(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_show_available_context_menu", *args, **kwargs
        )

    def _show_list_context_menu(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_show_list_context_menu", *args, **kwargs
        )

    def _copy_selected_rows(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_table_controller", "_copy_selected_rows", *args, **kwargs
        )

    def _clear_filters(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call("_table_controller", "_clear_filters", *args, **kwargs)

    def _settings(self) -> Any:
        return self._facade_call("_state_store", "_settings")

    def _save_table_sort_state(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_state_store", "_save_table_sort_state", *args, **kwargs
        )

    def _save_ui_state(self) -> Any:
        return self._facade_call("_state_store", "_save_ui_state")

    def _restore_ui_state(self) -> Any:
        return self._facade_call("_state_store", "_restore_ui_state")

    def _restore_selected_list_from_settings(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_state_store", "_restore_selected_list_from_settings", *args, **kwargs
        )

    def _get_table_column_widths(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_state_store", "_get_table_column_widths", *args, **kwargs
        )

    def _apply_table_column_widths(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_state_store", "_apply_table_column_widths", *args, **kwargs
        )

    def _restore_table_column_widths(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_state_store", "_restore_table_column_widths", *args, **kwargs
        )

    def _current_date_range(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call("_state_store", "_current_date_range", *args, **kwargs)

    def _find_main_window(self) -> Any:
        return self._facade_call("_state_store", "_find_main_window")

    def _is_embedded(self) -> bool:
        return bool(self._facade_call("_state_store", "_is_embedded"))

    def _navigate_back_to_estimate(self) -> Any:
        return self._facade_call("_state_store", "_navigate_back_to_estimate")

    def _update_transfer_buttons_state(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_selection_state_controller",
            "_update_transfer_buttons_state",
            *args,
            **kwargs,
        )

    def _on_selection_changed(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_selection_state_controller", "_on_selection_changed", *args, **kwargs
        )

    def _update_selection_summaries(self, *args: Any, **kwargs: Any) -> Any:
        return self._facade_call(
            "_selection_state_controller",
            "_update_selection_summaries",
            *args,
            **kwargs,
        )


__all__ = ["SilverBarManagementFacade"]
