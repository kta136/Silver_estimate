"""Explicit typed facade for the silver-bar management controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt

from silverestimate.infrastructure.settings import ApplicationSettings

if TYPE_CHECKING:
    from .silver_bar_list_lifecycle_controller import SilverBarListLifecycleController
    from .silver_bar_list_print_controller import SilverBarListPrintController
    from .silver_bar_load_controller import SilverBarLoadController
    from .silver_bar_management_state import SilverBarManagementStateStore
    from .silver_bar_management_ui import SilverBarManagementUiBuilder
    from .silver_bar_selection_state_controller import SilverBarSelectionStateController
    from .silver_bar_table_controller import SilverBarTableController
    from .silver_bar_transfer_controller import SilverBarTransferController


class SilverBarManagementFacade:
    """Stable dialog API with explicit controller ownership."""

    _ui_builder: SilverBarManagementUiBuilder
    _load_controller: SilverBarLoadController
    _transfer_controller: SilverBarTransferController
    _list_lifecycle_controller: SilverBarListLifecycleController
    _list_print_controller: SilverBarListPrintController
    _table_controller: SilverBarTableController
    _state_store: SilverBarManagementStateStore
    _selection_state_controller: SilverBarSelectionStateController

    def init_ui(self) -> None:
        return self._ui_builder.init_ui()

    def _schedule_available_reload(self, *args: Any, **kwargs: Any) -> None:
        return self._load_controller._schedule_available_reload(*args, **kwargs)

    def _start_bars_load(
        self, target: str, payload: dict[str, Any], *, append: bool = False
    ) -> int:
        return self._load_controller._start_bars_load(target, payload, append=append)

    def _on_bars_load_ready(self, _generation: int, value: object) -> None:
        return self._load_controller._on_bars_load_ready(_generation, value)

    def _on_bars_load_error(self, _generation: int, error: object) -> None:
        return self._load_controller._on_bars_load_error(_generation, error)

    def _on_bars_load_finished(self, generation: int) -> None:
        return self._load_controller._on_bars_load_finished(generation)

    def _cancel_active_loads(self) -> None:
        return self._load_controller._cancel_active_loads()

    def _shutdown_loads(self) -> None:
        self._list_print_controller.shutdown()
        self._load_controller._shutdown_loads()

    def load_available_bars(self, *, append: bool = False) -> None:
        return self._load_controller.load_available_bars(append=append)

    def load_lists(self) -> None:
        return self._load_controller.load_lists()

    def list_selection_changed(self, *args: Any, **kwargs: Any) -> None:
        return self._load_controller.list_selection_changed(*args, **kwargs)

    def load_bars_in_selected_list(self, *, append: bool = False) -> None:
        return self._load_controller.load_bars_in_selected_list(append=append)

    def _bulk_assign_to_list(self, bar_ids: Any, list_id: Any) -> Any:
        return self._transfer_controller._bulk_assign_to_list(bar_ids, list_id)

    def _bulk_remove_from_list(self, bar_ids: Any) -> Any:
        return self._transfer_controller._bulk_remove_from_list(bar_ids)

    def add_selected_to_list(self) -> None:
        return self._transfer_controller.add_selected_to_list()

    def remove_selected_from_list(self) -> None:
        return self._transfer_controller.remove_selected_from_list()

    def add_all_filtered_to_list(self) -> None:
        return self._transfer_controller.add_all_filtered_to_list()

    def remove_all_from_list(self) -> None:
        return self._transfer_controller.remove_all_from_list()

    def export_current_list_to_csv(self) -> None:
        return self._transfer_controller.export_current_list_to_csv()

    def create_new_list(self) -> None:
        return self._list_lifecycle_controller.create_new_list()

    def _create_list_from_selection(self) -> None:
        return self._list_lifecycle_controller._create_list_from_selection()

    def edit_list_note(self) -> None:
        return self._list_lifecycle_controller.edit_list_note()

    def delete_selected_list(self) -> None:
        return self._list_lifecycle_controller.delete_selected_list()

    def mark_list_as_issued(self) -> None:
        return self._list_lifecycle_controller.mark_list_as_issued()

    def print_selected_list(self) -> None:
        return self._list_print_controller.print_selected_list()

    def _table_cell_value(
        self, table: Any, row: int, column: int, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        return self._table_controller._table_cell_value(table, row, column, role)

    def _table_cell_text(self, table: Any, row: int, column: int) -> str:
        return str(self._table_controller._table_cell_text(table, row, column))

    def _bar_id_from_table(self, table: Any, row: int) -> Any:
        value = self._table_controller._bar_id_from_table(table, row)
        return int(value) if value is not None else None

    def _clear_management_table(self, table: Any) -> None:
        return self._table_controller._clear_management_table(table)

    def _populate_table(
        self, table: Any, bars_data: Any, *, total_rows: Any = None, append: Any = False
    ) -> None:
        return self._table_controller._populate_table(
            table, bars_data, total_rows=total_rows, append=append
        )

    def _show_available_context_menu(self, pos: Any) -> None:
        return self._table_controller._show_available_context_menu(pos)

    def _show_list_context_menu(self, pos: Any) -> None:
        return self._table_controller._show_list_context_menu(pos)

    def _copy_selected_rows(self, table: Any) -> None:
        return self._table_controller._copy_selected_rows(table)

    def _clear_filters(self) -> None:
        return self._table_controller._clear_filters()

    def _settings(self) -> ApplicationSettings:
        return self._state_store._settings()

    def _save_table_sort_state(self, which: Any, table: Any) -> None:
        return self._state_store._save_table_sort_state(which, table)

    def _save_ui_state(self) -> None:
        return self._state_store._save_ui_state()

    def _restore_ui_state(self) -> None:
        return self._state_store._restore_ui_state()

    def _restore_selected_list_from_settings(self) -> None:
        return self._state_store._restore_selected_list_from_settings()

    def _get_table_column_widths(self, table: Any) -> Any:
        return self._state_store._get_table_column_widths(table)

    def _apply_table_column_widths(self, table: Any, widths: Any) -> None:
        return self._state_store._apply_table_column_widths(table, widths)

    def _restore_table_column_widths(self) -> None:
        return self._state_store._restore_table_column_widths()

    def _current_date_range(self) -> Any:
        return self._state_store._current_date_range()

    def _find_main_window(self) -> Any:
        return self._state_store._find_main_window()

    def _is_embedded(self) -> Any:
        return bool(self._state_store._is_embedded())

    def _navigate_back_to_estimate(self) -> None:
        return self._state_store._navigate_back_to_estimate()

    def _update_transfer_buttons_state(self) -> None:
        return self._selection_state_controller._update_transfer_buttons_state()

    def _on_selection_changed(self, *args: Any, **kwargs: Any) -> None:
        return self._selection_state_controller._on_selection_changed(*args, **kwargs)

    def _update_selection_summaries(self) -> None:
        return self._selection_state_controller._update_selection_summaries()


__all__ = ["SilverBarManagementFacade"]
