"""Async loading controller for silver-bar management."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from PyQt5.QtCore import QObject, QThread, pyqtSignal
from PyQt5.QtWidgets import QMessageBox

from silverestimate.infrastructure.settings import get_app_settings
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)

from ._host_proxy import HostProxy


class _BarsLoadWorker(QObject):
    """Background loader for available/list bars to keep UI responsive."""

    data_ready = pyqtSignal(str, int, list, int)
    error = pyqtSignal(str, int, str)
    finished = pyqtSignal(str, int)

    def __init__(self, target: str, request_id: int, db_path: str, payload: dict):
        super().__init__()
        self.target = target
        self.request_id = request_id
        self.db_path = db_path
        self.payload = payload

    def run(self):
        try:
            snapshot = SilverBarsSnapshotRepository(self.db_path)

            if self.target == "available":
                rows, total_count = snapshot.get_available_bars_page(
                    weight_query=(self.payload or {}).get("weight_query"),
                    weight_tolerance=(self.payload or {}).get(
                        "weight_tolerance", 0.001
                    ),
                    min_purity=(self.payload or {}).get("min_purity"),
                    max_purity=(self.payload or {}).get("max_purity"),
                    date_range=(self.payload or {}).get("date_range"),
                    limit=(self.payload or {}).get("limit"),
                )
            elif self.target == "list":
                rows, total_count = snapshot.get_bars_in_list_page(
                    (self.payload or {}).get("list_id"),
                    limit=(self.payload or {}).get("limit"),
                    offset=(self.payload or {}).get("offset", 0),
                )
            else:
                raise ValueError(f"Unknown load target: {self.target}")

            self.data_ready.emit(
                self.target,
                self.request_id,
                list(rows),
                int(total_count),
            )
        except Exception as exc:
            self.error.emit(self.target, self.request_id, str(exc))
        finally:
            self.finished.emit(self.target, self.request_id)


class SilverBarLoadController(HostProxy):
    """Coordinate async available/list loads and stale-response handling."""

    if TYPE_CHECKING:
        _available_load_request_id: int
        _list_load_request_id: int

    def _schedule_available_reload(self, *args, **kwargs):
        del args, kwargs
        try:
            self._filter_reload_timer.start()
        except (AttributeError, RuntimeError, TypeError) as exc:
            self.logger.debug("Failed to start available reload timer: %s", exc)
            self.load_available_bars()

    def _save_available_limit_setting(self, value):
        try:
            get_app_settings().setValue("silver_bar/available_max_rows", int(value))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Could not persist available row limit: %s", exc)

    def _table_result_limit(self) -> int:
        try:
            return max(100, int(self.available_limit_spin.value()))
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Invalid available table row limit value: %s", exc)
            return 1500

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

    def _start_bars_load(self, target: str, payload: dict) -> int:
        request_id = self._next_load_request_id(target)
        self._load_started_at[(target, request_id)] = time.perf_counter()
        db_path = getattr(self.db_manager, "temp_db_path", None)
        if not db_path:
            try:
                if target == "available":
                    rows, total_count = self.db_manager.get_available_silver_bars_page(
                        weight_query=payload.get("weight_query"),
                        weight_tolerance=payload.get("weight_tolerance", 0.001),
                        min_purity=payload.get("min_purity"),
                        max_purity=payload.get("max_purity"),
                        date_range=payload.get("date_range"),
                        limit=payload.get("limit"),
                    )
                else:
                    rows, total_count = self.db_manager.get_silver_bars_in_list_page(
                        payload.get("list_id"),
                        limit=payload.get("limit"),
                        offset=payload.get("offset", 0),
                    )
                normalized_rows = [
                    dict(row) if not isinstance(row, dict) else row
                    for row in rows or []
                ]
                self._on_bars_load_ready(
                    target, request_id, normalized_rows, total_count
                )
            except Exception as exc:
                self._on_bars_load_error(target, request_id, str(exc))
            return request_id

        worker = _BarsLoadWorker(target, request_id, db_path, payload)
        thread = QThread(self.host)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(self._on_bars_load_ready)
        worker.error.connect(self._on_bars_load_error)
        worker.finished.connect(
            lambda t=target, r=request_id, th=thread, w=worker: (
                self._on_bars_load_finished(t, r, th, w)
            )
        )
        self._active_load_workers[thread] = worker
        thread.start()
        return request_id

    def _on_bars_load_ready(
        self, target: str, request_id: int, rows: list, total_count: int
    ) -> None:
        if not self._is_latest_load(target, request_id):
            return
        if target == "available":
            self._populate_table(
                self.available_bars_table,
                rows,
                total_rows=total_count,
            )
            self._restore_table_column_widths()
        elif target == "list":
            self._populate_table(
                self.list_bars_table,
                rows,
                total_rows=total_count,
            )
        else:
            return
        self._update_transfer_buttons_state()
        self._update_selection_summaries()

        started_at = self._load_started_at.pop((target, request_id), None)
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            self.logger.debug(
                "[perf] silver_bars.load_%s=%.2fms rows=%s total=%s",
                target,
                elapsed_ms,
                len(rows),
                total_count,
            )

    def _on_bars_load_error(self, target: str, request_id: int, message: str) -> None:
        if not self._is_latest_load(target, request_id):
            return
        self._load_started_at.pop((target, request_id), None)
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

    def _on_bars_load_finished(
        self, target: str, request_id: int, thread: QThread, worker: QObject
    ) -> None:
        del target, request_id
        self._active_load_workers.pop(thread, None)
        try:
            thread.quit()
            thread.wait(1000)
        except (AttributeError, RuntimeError) as exc:
            self.logger.debug("Failed to stop load thread cleanly: %s", exc)
        try:
            worker.deleteLater()
        except (AttributeError, RuntimeError) as exc:
            self.logger.debug("Failed to dispose load worker cleanly: %s", exc)

    def _cancel_active_loads(self, timeout_ms: int = 3000) -> None:
        self._available_load_request_id += 1
        self._list_load_request_id += 1
        active = list(self._active_load_workers.items())
        self._active_load_workers.clear()
        self._load_started_at.clear()

        for thread, worker in active:
            try:
                worker.deleteLater()
            except (AttributeError, RuntimeError) as exc:
                self.logger.debug("Failed to queue worker cleanup: %s", exc)
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        thread.terminate()
                        thread.wait(1000)
            except (AttributeError, RuntimeError) as exc:
                self.logger.debug("Failed to cancel load thread: %s", exc)

    def load_available_bars(self):
        weight_query = self.weight_search_edit.text().strip()
        try:
            tol = float(self.weight_tol_spin.value())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            tol = 0.001
        try:
            min_purity = float(self.purity_min_spin.value())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            min_purity = None
        try:
            max_purity = float(self.purity_max_spin.value())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            max_purity = None
        self._start_bars_load(
            "available",
            {
                "weight_query": weight_query if weight_query else None,
                "weight_tolerance": tol,
                "min_purity": min_purity,
                "max_purity": max_purity,
                "date_range": self._current_date_range(),
                "limit": self._table_result_limit(),
            },
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
                except (AttributeError, KeyError, TypeError):
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

    def load_bars_in_selected_list(self):
        if self.current_list_id is None:
            self._clear_management_table(self.list_bars_table)
            return

        self._start_bars_load(
            "list",
            {
                "list_id": self.current_list_id,
                "limit": self._table_result_limit(),
                "offset": 0,
            },
        )
