"""Cancellable prefix searches and whole-list reads with stale-result guards."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from PySide6.QtCore import QTimer

from silverestimate.domain.silver_bar_workspace import (
    BarWeightCursor,
    normalize_weight_prefix,
)
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


@dataclass(frozen=True)
class _SearchRequest:
    factory: Callable
    prefix: str
    cursor: BarWeightCursor | None = None


def _search(request: _SearchRequest, cancel: threading.Event):
    repo = SilverBarsSnapshotRepository(request.factory, cancel_event=cancel)
    return request, repo.search_weight_prefix(request.prefix, cursor=request.cursor)


def _load_list(request: tuple[Callable, int], cancel: threading.Event):
    factory, list_id = request
    return SilverBarsSnapshotRepository(factory, cancel_event=cancel).get_list_snapshot(
        list_id
    )


class SilverBarLoadController:
    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host
        self.timer = QTimer(host)
        self.timer.setSingleShot(True)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.search)
        self.search_runner = LatestRequestRunner(
            _search, host, name="bar-weight-search"
        )
        self.list_runner = LatestRequestRunner(_load_list, host, name="bar-list-reader")
        self.search_runner.result.connect(self._search_ready)
        self.search_runner.failed.connect(self._search_failed)
        self.list_runner.result.connect(self._list_ready)
        self.list_runner.failed.connect(self._list_failed)
        self.prefix: str | None = None
        self.dismissed = True
        self.announce_results = True
        self.ready_prefix: str | None = None
        self.cursor: BarWeightCursor | None = None
        self.pending_add = False
        self.loading = False
        self.shutdown_called = False
        self.advance_on_page = False

    def cancel_search(self, *, dismiss: bool = True) -> None:
        self.timer.stop()
        self.search_runner.cancel()
        self.ready_prefix = None
        self.pending_add = False
        self.loading = False
        self.cursor = None
        self.advance_on_page = False
        self.dismissed = dismiss
        self.host.suggestions_panel.hide()

    def schedule_search(self, text: str, *, announce: bool = True) -> None:
        self.cancel_search()
        self.host.suggestions_model.clear_rows()
        self.prefix = None
        if self.shutdown_called or not self.host.editable:
            return
        try:
            self.prefix = normalize_weight_prefix(text) if text.strip() else ""
        except ValueError as exc:
            self.host.set_status(str(exc), error=True)
            return
        self.dismissed = False
        self.announce_results = announce
        if announce:
            self.host.set_status(
                "Finding matching bars…" if self.prefix else "Loading available bars…"
            )
        self.timer.start()

    def search(self, *, append: bool = False) -> None:
        if (
            self.shutdown_called
            or self.prefix is None
            or self.dismissed
            or not self.host.editable
            or (append and (self.loading or self.cursor is None))
        ):
            return
        self.timer.stop()
        self.loading = True
        request = _SearchRequest(
            self.host.db_manager.open_read_connection,
            self.prefix,
            self.cursor if append else None,
        )
        self.search_runner.submit(request)

    def enter(self) -> None:
        if self.prefix is None or self.dismissed or not self.host.editable:
            return
        if self.ready_prefix == self.prefix and not self.loading:
            self.host.add_current_match()
        elif self.prefix:
            # Fast typed Enter may wait for its exact query. Blank browsing only
            # adds a visible selection, never an unseen result arriving later.
            self.pending_add = True
            if self.timer.isActive() or not self.loading:
                self.search()
        elif not self.loading:
            self.search()

    def _search_ready(self, generation: int, value: Any) -> None:
        if (
            generation != self.search_runner.generation
            or self.dismissed
            or not self.host.editable
        ):
            return
        request, page = value
        if request.prefix != self.prefix:
            return
        self.loading = False
        self.ready_prefix = request.prefix
        self.cursor = page.next_cursor
        old_count = self.host.suggestions_model.rowCount()
        if request.cursor is None:
            self.host.suggestions_model.set_rows(list(page.items))
            target = 0
        else:
            self.host.suggestions_model.append_rows(list(page.items))
            target = old_count if self.advance_on_page else max(0, old_count - 1)
        self.advance_on_page = False
        count = self.host.suggestions_model.rowCount()
        self.host.position_suggestions()
        self.host.suggestions_panel.setVisible(count > 0)
        noun = "matching" if request.prefix else "available"
        self.host.suggestions_hint.setText(
            f"  {count}{'+' if page.has_more else ''} {noun} bars · ↑ ↓ Choose · Enter Add · Esc Dismiss"
            + ("     ↓ at end: more matches" if page.has_more else "")
        )
        if count:
            self.host.suggestions_table.selectRow(min(target, count - 1))
            self.host.suggestions_table.scrollTo(
                self.host.suggestions_table.currentIndex()
            )
            if self.announce_results:
                self.host.set_status(
                    f"{count}{'+' if page.has_more else ''} {noun} bars · Enter adds the highlighted bar."
                )
        elif self.announce_results or not self.host.status_label.property("error"):
            self.host.set_status(
                "No available bars match this weight. Try different digits."
                if request.prefix
                else "No available bars."
            )
        if self.pending_add:
            self.pending_add = False
            if count:
                self.host.add_current_match()

    def _search_failed(self, generation: int, error: Any) -> None:
        if generation == self.search_runner.generation:
            self.loading = False
            self.pending_add = False
            self.ready_prefix = None
            self.host.suggestions_panel.hide()
            self.host.set_status(
                f"Could not find bars: {error}. Ctrl+F retries.", error=True
            )

    def move_match(self, step: int) -> None:
        if self.dismissed or self.prefix is None or self.ready_prefix != self.prefix:
            return
        row = self.host.suggestions_table.currentIndex().row()
        count = self.host.suggestions_model.rowCount()
        if step > 0 and row == count - 1 and self.cursor is not None:
            self.advance_on_page = True
            self.search(append=True)
            return
        self.host.suggestions_table.selectRow(max(0, min(count - 1, row + step)))
        self.host.suggestions_table.scrollTo(self.host.suggestions_table.currentIndex())

    def load_list(self, list_id: int) -> None:
        self.cancel_search()
        self.host._loading_list = True
        self.host.current_list_id = list_id
        self.host._update_actions()
        self.host.set_status("Loading saved list…")
        self.list_runner.submit((self.host.db_manager.open_read_connection, list_id))

    def _list_ready(self, generation: int, snapshot: Any) -> None:
        if (
            generation == self.list_runner.generation
            and snapshot.list_id == self.host.current_list_id
        ):
            self.host.apply_snapshot(snapshot)
            self.host.focus_weight()
            self.host.set_status(
                "List opened. Changes save automatically."
                if not snapshot.issued
                else "Issued list · Read only. Reprint or reactivate from history."
            )

    def _list_failed(self, generation: int, error: Any) -> None:
        if generation == self.list_runner.generation:
            self.host.create_new_list()
            self.host.set_status(f"Could not open list: {error}", error=True)

    def shutdown(self) -> None:
        self.shutdown_called = True
        self.timer.stop()
        self.search_runner.shutdown()
        self.list_runner.shutdown()
