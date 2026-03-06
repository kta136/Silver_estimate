"""Read-only silver-bar repository backed by an independent SQLite connection."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from silverestimate.persistence.silver_bars_queries import (
    build_available_bars_queries,
    build_bars_in_list_queries,
    build_history_bars_query,
)


class SilverBarsSnapshotRepository:
    """Execute read-only silver-bar queries against a standalone DB snapshot."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        if not self._db_path:
            raise RuntimeError("Temporary database path is unavailable.")
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
