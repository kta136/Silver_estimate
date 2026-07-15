"""Async loading controller for silver-bar management."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias, cast

from PyQt6.QtWidgets import QMessageBox

from silverestimate.domain.pagination import (
    AvailableBarCursor,
    BarListCursor,
    Page,
)
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)

from ._host_proxy import HostProxy


@dataclass(frozen=True)
class _BarsLoadRequest:
    target: str
    db_path: str
    payload: dict[str, Any]
    cursor: AvailableBarCursor | BarListCursor | None
    append: bool
    started_at: float


_BarsPage: TypeAlias = (
    Page[dict[str, Any], AvailableBarCursor] | Page[dict[str, Any], BarListCursor]
)


class _BarsLoadError(RuntimeError):
    def __init__(self, target: str, cause: Exception) -> None:
        super().__init__(str(cause))
        self.target = target


def _load_bars_page(
    request: _BarsLoadRequest,
    cancel_event: threading.Event,
) -> tuple[_BarsLoadRequest, _BarsPage]:
    try:
        snapshot = SilverBarsSnapshotRepository(
            request.db_path,
            cancel_event=cancel_event,
        )
        page: _BarsPage
        if request.target == "available":
            page = snapshot.get_available_bars_keyset_page(
                weight_query=request.payload.get("weight_query"),
                weight_tolerance=request.payload.get("weight_tolerance", 0.001),
                min_purity=request.payload.get("min_purity"),
                max_purity=request.payload.get("max_purity"),
                date_range=request.payload.get("date_range"),
                cursor=cast(AvailableBarCursor | None, request.cursor),
                limit=1500,
            )
        elif request.target == "list":
            page = snapshot.get_bars_in_list_keyset_page(
                request.payload.get("list_id"),
                cursor=cast(BarListCursor | None, request.cursor),
                limit=1500,
            )
        else:
            raise ValueError(f"Unknown load target: {request.target}")
    except Exception as exc:
        raise _BarsLoadError(request.target, exc) from exc
    return request, page


class SilverBarLoadController(HostProxy):
    """Coordinate async available/list loads and stale-response handling."""

    if TYPE_CHECKING:
        _available_load_request_id: int
        _list_load_request_id: int

    def __init__(self, host) -> None:
        super().__init__(host)
        self._available_cursor: AvailableBarCursor | None = None
        self._list_cursor: BarListCursor | None = None
        self._available_rows: list[dict[str, Any]] = []
        self._list_rows: list[dict[str, Any]] = []
        self._available_runner = LatestRequestRunner(
            _load_bars_page,
            host,
            name="available-bars-loader",
        )
        self._list_runner = LatestRequestRunner(
            _load_bars_page,
            host,
            name="list-bars-loader",
        )
        for runner in (self._available_runner, self._list_runner):
            runner.result.connect(self._on_bars_load_ready)
            runner.failed.connect(self._on_bars_load_error)
            runner.settled.connect(self._on_bars_load_finished)

    def _schedule_available_reload(self, *args, **kwargs):
        del args, kwargs
        try:
            self._filter_reload_timer.start()
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Failed to start available reload timer: %s", exc)
            self.load_available_bars()

    @staticmethod
    def _refresh_widget_style(widget) -> None:
        if widget is None:
            return
        try:
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)
            widget.update()
        except AttributeError, RuntimeError, TypeError:
            return

    def _set_list_table_active_state(self, is_active: bool) -> None:
        list_table = getattr(self, "list_bars_table", None)
        if list_table is None:
            return
        state = "active" if is_active else "inactive"
        try:
            header = list_table.horizontalHeader()
        except AttributeError, RuntimeError, TypeError:
            header = None
        list_table.setProperty("listState", state)
        if header is not None:
            header.setProperty("listState", state)
        list_table.setEnabled(is_active)
        self._refresh_widget_style(list_table)
        if header is not None:
            self._refresh_widget_style(header)
        try:
            self._refresh_widget_style(list_table.viewport())
        except AttributeError, RuntimeError, TypeError:
            pass

    def _next_load_request_id(self, target: str) -> int:
        if target == "available":
            self._available_load_request_id += 1
            return self._available_load_request_id
        if target == "list":
            self._list_load_request_id += 1
            return self._list_load_request_id
        raise ValueError(f"Unknown load target: {target}")

    def _is_latest_load(self, target: str, request_id: int) -> bool:
        if target == "available":
            return request_id == self._available_load_request_id
        if target == "list":
            return request_id == self._list_load_request_id
        return False

    def _start_bars_load(
        self,
        target: str,
        payload: dict,
        *,
        append: bool = False,
    ) -> int:
        cursor: AvailableBarCursor | BarListCursor | None
        if target == "available":
            cursor = self._available_cursor
            runner = self._available_runner
            if not append:
                self._available_cursor = None
                self._available_rows = []
                cursor = None
            elif cursor is None:
                return runner.generation
            button = getattr(self, "available_load_more_button", None)
        elif target == "list":
            cursor = self._list_cursor
            runner = self._list_runner
            if not append:
                self._list_cursor = None
                self._list_rows = []
                cursor = None
            elif cursor is None:
                return runner.generation
            button = getattr(self, "list_load_more_button", None)
        else:
            raise ValueError(f"Unknown load target: {target}")
        if button is not None:
            button.setEnabled(False)

        started_at = time.perf_counter()
        page: _BarsPage
        db_path = getattr(self.db_manager, "temp_db_path", None)
        if not db_path:
            try:
                if target == "available":
                    getter = getattr(
                        self.db_manager,
                        "get_available_silver_bars_keyset_page",
                        None,
                    )
                    if callable(getter):
                        page = getter(
                            weight_query=payload.get("weight_query"),
                            weight_tolerance=payload.get("weight_tolerance", 0.001),
                            min_purity=payload.get("min_purity"),
                            max_purity=payload.get("max_purity"),
                            date_range=payload.get("date_range"),
                            cursor=cursor,
                            limit=1500,
                        )
                    else:
                        rows, total = self.db_manager.get_available_silver_bars_page(
                            weight_query=payload.get("weight_query"),
                            weight_tolerance=payload.get("weight_tolerance", 0.001),
                            min_purity=payload.get("min_purity"),
                            max_purity=payload.get("max_purity"),
                            date_range=payload.get("date_range"),
                            limit=1500,
                        )
                        page = Page(tuple(dict(row) for row in rows), total, None)
                else:
                    getter = getattr(
                        self.db_manager,
                        "get_silver_bars_in_list_keyset_page",
                        None,
                    )
                    if callable(getter):
                        page = getter(
                            payload.get("list_id"),
                            cursor=cursor,
                            limit=1500,
                        )
                    else:
                        rows, total = self.db_manager.get_silver_bars_in_list_page(
                            payload.get("list_id"),
                            limit=1500,
                            offset=0,
                        )
                        page = Page(tuple(dict(row) for row in rows), total, None)
                request = _BarsLoadRequest(
                    target,
                    "",
                    payload,
                    cursor,
                    append,
                    started_at,
                )
                self._on_bars_load_ready(0, (request, page))
            except Exception as exc:
                self._on_direct_load_error(target, exc)
            finally:
                self._finish_target_load(target)
            return 0

        return runner.submit(
            _BarsLoadRequest(
                target,
                str(db_path),
                payload,
                cursor,
                append,
                started_at,
            )
        )

    def _on_bars_load_ready(self, _generation: int, value: object) -> None:
        request, page = cast(tuple[_BarsLoadRequest, _BarsPage], value)
        target = request.target
        page_rows = [dict(row) for row in page.items]
        if target == "available":
            self._available_cursor = cast(
                AvailableBarCursor | None,
                page.next_cursor,
            )
            self._available_rows = (
                [*self._available_rows, *page_rows] if request.append else page_rows
            )
            rows = self._available_rows
            self._populate_table(
                self.available_bars_table,
                rows,
                total_rows=page.total,
            )
            self._restore_table_column_widths()
            button = getattr(self, "available_load_more_button", None)
            if button is not None:
                button.setVisible(self._available_cursor is not None)
        elif target == "list":
            self._list_cursor = cast(BarListCursor | None, page.next_cursor)
            self._list_rows = (
                [*self._list_rows, *page_rows] if request.append else page_rows
            )
            rows = self._list_rows
            self._populate_table(
                self.list_bars_table,
                rows,
                total_rows=page.total,
            )
            button = getattr(self, "list_load_more_button", None)
            if button is not None:
                button.setVisible(self._list_cursor is not None)
        else:
            return
        self._update_transfer_buttons_state()
        self._update_selection_summaries()

        elapsed_ms = (time.perf_counter() - request.started_at) * 1000.0
        self.logger.debug(
            "[perf] silver_bars.load_%s=%.2fms rows=%s total=%s",
            target,
            elapsed_ms,
            len(rows),
            page.total,
        )

    def _on_bars_load_error(self, _generation: int, error: object) -> None:
        target = error.target if isinstance(error, _BarsLoadError) else "available"
        self._on_direct_load_error(target, error)

    def _on_direct_load_error(self, target: str, error: object) -> None:
        message = str(error)
        if target == "available":
            self._populate_table(self.available_bars_table, [], total_rows=0)
            QMessageBox.critical(
                self.host, "Error", f"Failed to load available bars: {message}"
            )
        elif target == "list":
            self._populate_table(self.list_bars_table, [], total_rows=0)
            QMessageBox.critical(
                self.host,
                "Error",
                f"Failed to load bars for list {self.current_list_id}: {message}",
            )

    def _on_bars_load_finished(self, generation: int) -> None:
        if generation == self._available_runner.generation:
            self._finish_target_load("available")
        if generation == self._list_runner.generation:
            self._finish_target_load("list")

    def _finish_target_load(self, target: str) -> None:
        button = getattr(self, f"{target}_load_more_button", None)
        if button is not None:
            button.setEnabled(True)

    def _cancel_active_loads(self) -> None:
        for runner in (self._available_runner, self._list_runner):
            runner.cancel()
            runner.shutdown()

    def load_available_bars(self, *, append: bool = False):
        weight_query = self.weight_search_edit.text().strip()
        self._start_bars_load(
            "available",
            {
                "weight_query": weight_query if weight_query else None,
                "weight_tolerance": 0.0,
                "date_range": self._current_date_range(),
            },
            append=append,
        )

    def load_lists(self):
        logging.getLogger(__name__).debug("Loading lists...")
        self.list_combo.blockSignals(True)
        self.list_combo.clear()
        self.list_combo.addItem("--- Select a List ---", None)
        try:
            lists = self.db_manager.get_silver_bar_lists(include_issued=False)
            for list_row in lists:
                list_note = list_row["list_note"] or ""
                list_date = (
                    list_row["creation_date"].split()[0]
                    if "creation_date" in list_row.keys() and list_row["creation_date"]
                    else ""
                )
                display_text = f"{list_row['list_identifier']} ({list_date})"
                if list_note:
                    display_text += f" - {list_note}"
                self.list_combo.addItem(display_text, list_row["list_id"])
        except Exception as exc:
            self.logger.warning(
                "Failed to load silver bar lists: %s", exc, exc_info=True
            )
            QMessageBox.critical(self.host, "Error", f"Failed to load lists: {exc}")
        finally:
            try:
                self._restore_selected_list_from_settings()
            except Exception as exc:
                self.logger.debug(
                    "Failed to restore selected list from settings: %s", exc
                )
            self.list_combo.blockSignals(False)
            self.list_selection_changed()

    def list_selection_changed(self, *args, **kwargs):
        del args, kwargs
        selected_index = self.list_combo.currentIndex()
        self.current_list_id = self.list_combo.itemData(selected_index)

        is_list_selected = self.current_list_id is not None
        self.edit_note_button.setEnabled(is_list_selected)
        self.print_list_button.setEnabled(is_list_selected)
        export_button = getattr(self, "export_list_button", None)
        if export_button is not None:
            export_button.setEnabled(is_list_selected)
        self._set_list_table_active_state(is_list_selected)
        print_bottom_button = getattr(self, "print_bottom_button", None)
        if print_bottom_button is not None:
            print_bottom_button.setEnabled(is_list_selected)
        self.delete_list_button.setEnabled(is_list_selected)
        self.mark_issued_button.setEnabled(is_list_selected)
        self._update_transfer_buttons_state()

        if is_list_selected:
            details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
            if details:
                info = f"{details['list_identifier']}"
                try:
                    note_val = (
                        details["list_note"] if "list_note" in details.keys() else None
                    )
                except AttributeError, KeyError, TypeError:
                    note_val = getattr(details, "list_note", None)
                if note_val:
                    info += f"  –  {note_val}"
                self.list_info_label.setText(info)
            else:
                self.list_info_label.setText("Error loading list details")
            self.load_bars_in_selected_list()
        else:
            self.list_info_label.setText("No list selected")
            self._clear_management_table(self.list_bars_table)

    def load_bars_in_selected_list(self, *, append: bool = False):
        if self.current_list_id is None:
            self._list_rows = []
            self._list_cursor = None
            self._clear_management_table(self.list_bars_table)
            button = getattr(self, "list_load_more_button", None)
            if button is not None:
                button.setVisible(False)
            return

        self._start_bars_load(
            "list",
            {
                "list_id": self.current_list_id,
            },
            append=append,
        )
