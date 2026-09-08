"""Read-only silver-bar repository backed by an independent SQLite connection."""

from __future__ import annotations

import threading
from contextlib import closing
from typing import Any, Callable

from silverestimate.domain.pagination import (
    AvailableBarCursor,
    BarListCursor,
    Page,
    SilverBarHistoryCursor,
)
from silverestimate.persistence.silver_bars_queries import (
    build_available_bars_queries,
    build_bars_in_list_queries,
    build_history_bars_count_query,
    build_history_bars_query,
)


class SilverBarsSnapshotRepository:
    """Execute read-only silver-bar queries against a standalone DB snapshot."""

    def __init__(
        self,
        connection_factory: Callable[[threading.Event | None], Any],
        *,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self._connection_factory = connection_factory
        self._cancel_event = cancel_event

    def _connect(self) -> Any:
        return self._connection_factory(self._cancel_event)

    def get_available_bars_page(
        self,
        *,
        weight_query: Any = None,
        weight_tolerance: float = 0.001,
        min_purity: Any = None,
        max_purity: Any = None,
        date_range: Any = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        statements = build_available_bars_queries(
            weight_query=weight_query,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
            limit=limit,
        )
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                statements.count_query.query,
                tuple(statements.count_query.params),
            )
            count_row = cursor.fetchone()
            total_count = int(count_row[0]) if count_row else 0
            cursor.execute(statements.query.query, tuple(statements.query.params))
            rows = [dict(row) for row in cursor.fetchall()]
        return rows, total_count

    def get_available_bars_keyset_page(
        self,
        *,
        weight_query: Any = None,
        weight_tolerance: float = 0.001,
        min_purity: Any = None,
        max_purity: Any = None,
        date_range: Any = None,
        cursor: AvailableBarCursor | None = None,
        include_total: bool = True,
        limit: int = 1500,
    ) -> Page[dict[str, Any], AvailableBarCursor]:
        page_size = max(1, min(int(limit), 5000))
        statements = build_available_bars_queries(
            weight_query=weight_query,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
            limit=page_size + 1,
            after_date_added=cursor.date_added if cursor else None,
            after_bar_id=cursor.bar_id if cursor else None,
        )
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            db_cursor = conn.cursor()
            total = None
            if include_total:
                db_cursor.execute(
                    statements.count_query.query,
                    tuple(statements.count_query.params),
                )
                count_row = db_cursor.fetchone()
                total = int(count_row[0]) if count_row else 0
            db_cursor.execute(statements.query.query, tuple(statements.query.params))
            fetched = [dict(row) for row in db_cursor.fetchall()]
        has_more = len(fetched) > page_size
        rows = fetched[:page_size]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = AvailableBarCursor(
                str(last.get("date_added", "") or ""),
                int(last["bar_id"]),
            )
        return Page(tuple(rows), total, next_cursor)

    def get_bars_in_list_page(
        self,
        list_id: int | None,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        statements = build_bars_in_list_queries(list_id, limit=limit, offset=offset)
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                statements.count_query.query,
                tuple(statements.count_query.params),
            )
            count_row = cursor.fetchone()
            total_count = int(count_row[0]) if count_row else 0
            cursor.execute(statements.query.query, tuple(statements.query.params))
            rows = [dict(row) for row in cursor.fetchall()]
        return rows, total_count

    def get_bars_in_list_keyset_page(
        self,
        list_id: int | None,
        *,
        cursor: BarListCursor | None = None,
        include_total: bool = True,
        limit: int = 1500,
    ) -> Page[dict[str, Any], BarListCursor]:
        page_size = max(1, min(int(limit), 5000))
        statements = build_bars_in_list_queries(
            list_id,
            limit=page_size + 1,
            after_bar_id=cursor.bar_id if cursor else None,
        )
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            db_cursor = conn.cursor()
            total = None
            if include_total:
                db_cursor.execute(
                    statements.count_query.query,
                    tuple(statements.count_query.params),
                )
                count_row = db_cursor.fetchone()
                total = int(count_row[0]) if count_row else 0
            db_cursor.execute(statements.query.query, tuple(statements.query.params))
            fetched = [dict(row) for row in db_cursor.fetchall()]
        has_more = len(fetched) > page_size
        rows = fetched[:page_size]
        next_cursor = (
            BarListCursor(int(rows[-1]["bar_id"])) if has_more and rows else None
        )
        return Page(tuple(rows), total, next_cursor)

    def search_history_bars(
        self,
        *,
        voucher_term: str = "",
        weight_text: str = "",
        status_text: str = "All Statuses",
        limit: int = 2000,
    ) -> list[dict[str, Any]]:
        statement = build_history_bars_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=limit,
        )
        with closing(self._connect()) as conn:
            cursor = conn.cursor()
            cursor.execute(statement.query, tuple(statement.params))
            return [dict(row) for row in cursor.fetchall()]

    def search_history_bars_page(
        self,
        *,
        voucher_term: str = "",
        weight_text: str = "",
        status_text: str = "All Statuses",
        cursor: SilverBarHistoryCursor | None = None,
        include_total: bool = True,
        limit: int = 1000,
    ) -> Page[dict[str, Any], SilverBarHistoryCursor]:
        page_size = max(1, min(int(limit), 5000))
        count_statement = build_history_bars_count_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
        )
        statement = build_history_bars_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=page_size + 1,
            after_date_added=cursor.date_added if cursor else None,
            after_bar_id=cursor.bar_id if cursor else None,
        )
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            db_cursor = conn.cursor()
            total = None
            if include_total:
                db_cursor.execute(
                    count_statement.query,
                    tuple(count_statement.params),
                )
                count_row = db_cursor.fetchone()
                total = int(count_row[0]) if count_row else 0
            db_cursor.execute(statement.query, tuple(statement.params))
            fetched = [dict(row) for row in db_cursor.fetchall()]
        has_more = len(fetched) > page_size
        rows = fetched[:page_size]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = SilverBarHistoryCursor(
                str(last.get("date_added", "") or ""),
                int(last["bar_id"]),
            )
        return Page(tuple(rows), total, next_cursor)
