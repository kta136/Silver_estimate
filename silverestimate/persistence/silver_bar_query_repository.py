"""Read-only silver-bar persistence component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable, List, Optional, Tuple, cast

from silverestimate.domain.pagination import (
    AvailableBarCursor,
    BarListCursor,
    Page,
    SilverBarHistoryCursor,
)
from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)
from silverestimate.persistence.silver_bar_repository_base import (
    _SilverBarRepositoryBase,
)
from silverestimate.persistence.silver_bars_queries import (
    build_available_bars_queries,
    build_bars_in_list_queries,
    build_history_bars_query,
)

SilverBarRow = Mapping[str, Any]


class SilverBarQueryRepository(_SilverBarRepositoryBase):
    """Own every silver-bar and list read."""

    def get_lists(self, include_issued: bool = True) -> list[SilverBarRow]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            if include_issued:
                query = (
                    "SELECT list_id, list_identifier, creation_date, list_note, issued_date "
                    "FROM silver_bar_lists ORDER BY creation_date DESC"
                )
            else:
                query = (
                    "SELECT list_id, list_identifier, creation_date, list_note, issued_date "
                    "FROM silver_bar_lists WHERE issued_date IS NULL ORDER BY creation_date DESC"
                )
            cursor.execute(query)
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching silver bar lists: %s", exc, exc_info=True
            )
            return []

    def get_list_details(self, list_id: int) -> SilverBarRow | None:
        cursor = self._cursor
        if not cursor:
            return None
        try:
            cursor.execute(
                "SELECT * FROM silver_bar_lists WHERE list_id = ?", (list_id,)
            )
            return cast(SilverBarRow | None, cursor.fetchone())
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching list details for ID %s: %s",
                list_id,
                exc,
                exc_info=True,
            )
            return None

    def get_available_bars_page(
        self,
        *,
        weight_query: Optional[float] = None,
        weight_tolerance: float = 0.001,
        min_purity: Optional[float] = None,
        max_purity: Optional[float] = None,
        date_range: Optional[Tuple[Optional[str], Optional[str]]] = None,
        limit: Optional[int] = None,
    ) -> tuple[list[SilverBarRow], int]:
        cursor = self._cursor
        if not cursor:
            return [], 0
        statements = build_available_bars_queries(
            weight_query=weight_query,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
            limit=limit,
        )
        try:
            cursor.execute(
                statements.count_query.query,
                tuple(statements.count_query.params),
            )
            count_row = cursor.fetchone()
            total_count = int(count_row[0]) if count_row else 0
            cursor.execute(statements.query.query, tuple(statements.query.params))
            return cast(list[SilverBarRow], cursor.fetchall()), total_count
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching available silver bars page: %s",
                exc,
                exc_info=True,
            )
            return [], 0

    def get_available_bars_keyset_page(
        self,
        *,
        weight_query: Optional[float] = None,
        weight_tolerance: float = 0.001,
        min_purity: Optional[float] = None,
        max_purity: Optional[float] = None,
        date_range: Optional[Tuple[Optional[str], Optional[str]]] = None,
        cursor: AvailableBarCursor | None = None,
        limit: int = 1500,
    ) -> Page[dict[str, Any], AvailableBarCursor]:
        db_cursor = self._cursor
        if not db_cursor:
            return Page(items=(), total=0, next_cursor=None)
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
        list_id: int,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> tuple[list[SilverBarRow], int]:
        cursor = self._cursor
        if not cursor:
            return [], 0
        statements = build_bars_in_list_queries(list_id, limit=limit, offset=offset)
        try:
            cursor.execute(
                statements.count_query.query,
                tuple(statements.count_query.params),
            )
            count_row = cursor.fetchone()
            total_count = int(count_row[0]) if count_row else 0
            cursor.execute(statements.query.query, tuple(statements.query.params))
            return cast(list[SilverBarRow], cursor.fetchall()), total_count
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching bars page for list %s: %s",
                list_id,
                exc,
                exc_info=True,
            )
            return [], 0

    def get_bars_in_list_keyset_page(
        self,
        list_id: int,
        *,
        cursor: BarListCursor | None = None,
        limit: int = 1500,
    ) -> Page[dict[str, Any], BarListCursor]:
        db_cursor = self._cursor
        if not db_cursor:
            return Page(items=(), total=0, next_cursor=None)
        page_size = max(1, min(int(limit), 5000))
        statements = build_bars_in_list_queries(
            list_id,
            limit=page_size + 1,
            after_bar_id=cursor.bar_id if cursor else None,
        )
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

    def get_bars_in_list(
        self,
        list_id: int,
        *,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[SilverBarRow]:
        rows, _total_count = self.get_bars_in_list_page(
            list_id,
            limit=limit,
            offset=offset,
        )
        return rows

    def get_available_bars(self) -> list[SilverBarRow]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            cursor.execute(
                "SELECT * FROM silver_bars WHERE status = 'In Stock' AND list_id IS NULL "
                "ORDER BY date_added DESC, bar_id DESC"
            )
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching available bars: %s", exc, exc_info=True
            )
            return []

    def search_history_bars(
        self,
        *,
        voucher_term: str = "",
        weight_text: str = "",
        status_text: str = "All Statuses",
        limit: int = 2000,
    ) -> list[SilverBarRow]:
        cursor = self._cursor
        if not cursor:
            return []
        statement = build_history_bars_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=limit,
        )
        try:
            cursor.execute(statement.query, tuple(statement.params))
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error searching silver-bar history: %s",
                exc,
                exc_info=True,
            )
            return []

    def search_history_bars_page(
        self,
        *,
        voucher_term: str = "",
        weight_text: str = "",
        status_text: str = "All Statuses",
        cursor: SilverBarHistoryCursor | None = None,
        limit: int = 1000,
    ) -> Page[dict[str, Any], SilverBarHistoryCursor]:
        db_cursor = self._cursor
        if not db_cursor:
            return Page(items=(), total=0, next_cursor=None)
        page_size = max(1, min(int(limit), 5000))
        count_statement = build_history_bars_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=1,
        )
        count_base = count_statement.query.rsplit(" ORDER BY ", 1)[0]
        db_cursor.execute(
            f"SELECT COUNT(*) FROM ({count_base})",  # nosec B608
            tuple(count_statement.params[:-1]),
        )
        count_row = db_cursor.fetchone()
        total = int(count_row[0]) if count_row else 0

        statement = build_history_bars_query(
            voucher_term=voucher_term,
            weight_text=weight_text,
            status_text=status_text,
            limit=page_size + 1,
            after_date_added=cursor.date_added if cursor else None,
            after_bar_id=cursor.bar_id if cursor else None,
        )
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

    def count_bars_by_list_ids(self, list_ids: Iterable[int]) -> dict[int, int]:
        cursor = self._cursor
        if not cursor:
            return {}
        normalized_ids = self._normalize_bar_ids(list_ids)
        if not normalized_ids:
            return {}
        placeholders = ",".join("?" for _ in normalized_ids)
        try:
            # Placeholder count is generated locally; values remain parameterized.
            cursor.execute(
                f"SELECT list_id, COUNT(*) AS count FROM silver_bars "  # nosec B608
                f"WHERE list_id IN ({placeholders}) GROUP BY list_id",
                normalized_ids,
            )
            return {
                int(row["list_id"]): int(row["count"])
                for row in cursor.fetchall()
                if row["list_id"] is not None
            }
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error counting silver bars by list ids: %s",
                exc,
                exc_info=True,
            )
            return {}

    def get_silver_bars_for_estimate(self, voucher_no: str) -> list[SilverBarRow]:
        cursor = self._cursor
        if not cursor or not voucher_no:
            return []
        try:
            cursor.execute(
                "SELECT sb.*, e.note AS estimate_note "
                "FROM silver_bars sb "
                "LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no "
                "WHERE sb.estimate_voucher_no = ? "
                "ORDER BY sb.bar_id",
                (voucher_no,),
            )
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error fetching bars for estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return []

    def get_silver_bars(
        self,
        *,
        status: Optional[str] = None,
        weight_query: Optional[float] = None,
        estimate_voucher_no: Optional[str] = None,
        unassigned_only: bool = False,
        weight_tolerance: float = 0.001,
        min_purity: Optional[float] = None,
        max_purity: Optional[float] = None,
        date_range: Optional[Tuple[Optional[str], Optional[str]]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> list[SilverBarRow]:
        cursor = self._cursor
        if not cursor:
            return []
        query = (
            "SELECT sb.*, e.note AS estimate_note "
            "FROM silver_bars sb "
            "LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no "
            "WHERE 1=1"
        )
        params: List[Any] = []
        if status:
            query += " AND sb.status = ?"
            params.append(status)
        if weight_query is not None:
            try:
                target = float(weight_query)
                tol = 0.001 if weight_tolerance is None else float(weight_tolerance)
                query += " AND sb.weight BETWEEN ? AND ?"
                params.extend([target - tol, target + tol])
            except ValueError:
                self._logger.warning(
                    "Invalid weight query '%s'. Ignoring weight filter.", weight_query
                )
        if estimate_voucher_no:
            query += " AND sb.estimate_voucher_no LIKE ?"
            params.append(f"%{estimate_voucher_no}%")
        if unassigned_only:
            query += " AND sb.list_id IS NULL"
        if min_purity is not None:
            try:
                query += " AND sb.purity >= ?"
                params.append(float(min_purity))
            except TypeError, ValueError:
                pass
        if max_purity is not None:
            try:
                query += " AND sb.purity <= ?"
                params.append(float(max_purity))
            except TypeError, ValueError:
                pass
        if (
            date_range
            and isinstance(date_range, (tuple, list))
            and len(date_range) == 2
        ):
            start_iso, end_iso = date_range
            if start_iso:
                query += " AND sb.date_added >= ?"
                params.append(start_iso)
            if end_iso:
                query += " AND sb.date_added <= ?"
                params.append(end_iso)
        query += " ORDER BY sb.date_added DESC, sb.bar_id DESC"
        if isinstance(limit, int) and limit > 0:
            query += " LIMIT ?"
            params.append(int(limit))
            if isinstance(offset, int) and offset > 0:
                query += " OFFSET ?"
                params.append(int(offset))
        try:
            cursor.execute(query, params)
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error("DB error getting silver bars: %s", exc, exc_info=True)
            return []

    def get_list_details_result(self, list_id: int) -> RepositoryResult[dict[str, Any]]:
        details = self.get_list_details(list_id)
        if details is not None:
            return RepositoryResult.success(dict(details))
        return RepositoryResult.failed(
            RepositoryFailureKind.NOT_FOUND,
            f"Silver-bar list {list_id} was not found.",
        )


__all__ = ["SilverBarQueryRepository"]
