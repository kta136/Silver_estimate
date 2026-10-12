"""Silver-bar reads: SQL builders, list snapshots and the two query repositories."""

from __future__ import annotations

import logging
import threading
from collections.abc import Mapping
from contextlib import closing
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    List,
    Optional,
    Sequence,
    cast,
)

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.pagination import (
    Page,
    SilverBarHistoryCursor,
)
from silverestimate.domain.silver_bar_workspace import (
    BarListSnapshot,
    BarWeightCursor,
    normalize_weight_prefix,
)
from silverestimate.persistence.database_driver import dbapi as sqlite3

if TYPE_CHECKING:
    from silverestimate.persistence.database_manager import DatabaseManager


class SilverBarRepositoryBase:
    """Provide connection access without sharing persistence operations."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))

    @property
    def _conn(self) -> Any:
        return getattr(self._db, "conn", None)

    @property
    def _cursor(self) -> Any:
        return getattr(self._db, "cursor", None)

    @staticmethod
    def _normalize_bar_ids(bar_ids: Iterable[int]) -> List[int]:
        normalized: List[int] = []
        seen: set[int] = set()
        for raw_bar_id in list(bar_ids or []):
            try:
                bar_id = int(raw_bar_id)
            except TypeError, ValueError:
                continue
            if bar_id <= 0 or bar_id in seen:
                continue
            seen.add(bar_id)
            normalized.append(bar_id)
        return normalized


@dataclass(frozen=True)
class SqlStatement:
    """A parametrized SQL statement."""

    query: str
    params: Sequence[Any]


def normalize_row_limit(limit: Any, *, default: int, minimum: int = 100) -> int:
    """Normalize table row limits used across silver-bar views."""

    try:
        return max(int(minimum), int(limit))
    except TypeError, ValueError:
        return max(int(minimum), int(default))


def _history_filters(
    voucher_term: str, weight_text: str, status_text: str
) -> tuple[list[str], list[Any]]:
    conditions: List[str] = []
    params: List[Any] = []

    normalized_voucher = str(voucher_term or "").strip()
    if normalized_voucher:
        pattern = f"%{normalized_voucher}%"
        conditions.append(
            "(sb.estimate_voucher_no LIKE ? OR sb.estimate_voucher_no IN (SELECT voucher_no FROM estimates WHERE note LIKE ?))"
        )
        params.extend([pattern, pattern])

    normalized_weight = str(weight_text or "").strip()
    if normalized_weight:
        try:
            weight_value = float(normalized_weight)
            conditions.append("sb.weight = ?")
            params.append(weight_value)
        except TypeError, ValueError:
            pass

    normalized_status = str(status_text or "").strip()
    if normalized_status and normalized_status != "All Statuses":
        conditions.append("sb.status = ?")
        params.append(normalized_status)

    return conditions, params


def build_history_bars_count_query(
    *, voucher_term: str = "", weight_text: str = "", status_text: str = "All Statuses"
) -> SqlStatement:
    conditions, params = _history_filters(voucher_term, weight_text, status_text)
    query = "SELECT COUNT(*) FROM silver_bars sb"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    return SqlStatement(query, tuple(params))


def build_history_bars_query(
    *,
    voucher_term: str = "",
    weight_text: str = "",
    status_text: str = "All Statuses",
    limit: int = 2000,
    after_date_added: str | None = None,
    after_bar_id: int | None = None,
) -> SqlStatement:
    """Build the history search query used by the history dialog worker."""

    conditions, params = _history_filters(voucher_term, weight_text, status_text)

    if after_date_added is not None and after_bar_id is not None:
        conditions.append(
            "COALESCE(sb.date_added, '') <= ? AND (COALESCE(sb.date_added, '') < ? OR "
            "(COALESCE(sb.date_added, '') = ? AND sb.bar_id < ?))"
        )
        params.extend(
            (after_date_added, after_date_added, after_date_added, int(after_bar_id))
        )

    query = (
        "SELECT "
        "sb.bar_id, sb.estimate_voucher_no, sb.weight, sb.purity, sb.fine_weight, "
        "sb.status, sb.date_added, sb.list_id, "
        "sbl.list_identifier, sbl.issued_date, "
        "e.note AS estimate_note "
        "FROM silver_bars sb "
        "LEFT JOIN silver_bar_lists sbl ON sb.list_id = sbl.list_id "
        "LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no"
    )
    # Substring filters scan once and test matching voucher IDs before display joins.
    # The date-order index otherwise causes costly random lookups for every bar.
    if (
        str(voucher_term or "").strip()
        and "sb.weight = ?" not in conditions
        and "sb.status = ?" not in conditions
    ):
        query = query.replace(
            "FROM silver_bars sb ", "FROM silver_bars sb NOT INDEXED "
        )
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY COALESCE(sb.date_added, '') DESC, sb.bar_id DESC LIMIT ?"
    params.append(normalize_row_limit(limit, default=2000))
    return SqlStatement(query, tuple(params))


def search_weight_prefix(
    conn: Any,
    prefix: str,
    *,
    cursor: BarWeightCursor | None = None,
    limit: int = 50,
) -> Page[dict[str, Any], BarWeightCursor]:
    prefix = normalize_weight_prefix(prefix) if prefix.strip() else ""
    page_size = max(1, min(int(limit), 500))
    query = """SELECT sb.*, e.note AS estimate_note
               FROM silver_bars sb LEFT JOIN estimates e
               ON e.voucher_no = sb.estimate_voucher_no
               WHERE sb.status = 'In Stock' AND sb.list_id IS NULL"""
    params: list[Any] = []
    if prefix:
        # Match the table's HALF_UP representation, including legacy weights.
        conn.create_function("bar_weight_text", 1, lambda n: fixed_decimal(n, 2))
        query += " AND bar_weight_text(sb.weight) LIKE ?"
        params.append(prefix + "%")
    if cursor is not None:
        query += " AND (sb.weight > ? OR (sb.weight = ? AND sb.bar_id > ?))"
        params.extend([cursor.weight, cursor.weight, cursor.bar_id])
    query += " ORDER BY sb.weight, sb.bar_id LIMIT ?"
    params.append(page_size + 1)
    fetched = [dict(row) for row in conn.execute(query, params).fetchall()]
    rows = fetched[:page_size]
    next_cursor = (
        BarWeightCursor(float(rows[-1]["weight"]), int(rows[-1]["bar_id"]))
        if len(fetched) > page_size
        else None
    )
    return Page(tuple(rows), None, next_cursor)


def read_list_snapshot(conn: Any, list_id: int) -> BarListSnapshot:
    """Caller holds a read or writer transaction for the entire snapshot."""
    details = conn.execute(
        "SELECT * FROM silver_bar_lists WHERE list_id = ?", (list_id,)
    ).fetchone()
    if details is None:
        raise ValueError("This list no longer exists. Open another list.")
    bars = conn.execute(
        """SELECT sb.*, e.note AS estimate_note FROM silver_bars sb
           LEFT JOIN estimates e ON e.voucher_no = sb.estimate_voucher_no
           WHERE sb.list_id = ? ORDER BY sb.bar_id""",
        (list_id,),
    ).fetchall()
    return BarListSnapshot(dict(details), tuple(dict(row) for row in bars))


SilverBarRow = Mapping[str, Any]


class SilverBarQueryRepository(SilverBarRepositoryBase):
    """Own every silver-bar and list read."""

    def get_list_snapshot(self, list_id: int) -> BarListSnapshot:
        conn = self._conn
        own_transaction = not conn.in_transaction
        if own_transaction:
            conn.execute("BEGIN")
        try:
            return read_list_snapshot(conn, list_id)
        finally:
            if own_transaction:
                conn.rollback()

    def get_silver_bars(
        self,
        *,
        status: Optional[str] = None,
        estimate_voucher_no: Optional[str] = None,
        unassigned_only: bool = False,
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
        if estimate_voucher_no:
            query += " AND sb.estimate_voucher_no LIKE ?"
            params.append(f"%{estimate_voucher_no}%")
        if unassigned_only:
            query += " AND sb.list_id IS NULL"
        query += " ORDER BY sb.date_added DESC, sb.bar_id DESC"
        try:
            cursor.execute(query, params)
            return cast(list[SilverBarRow], cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error("DB error getting silver bars: %s", exc, exc_info=True)
            return []


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

    def search_weight_prefix(
        self, prefix: str, *, cursor: BarWeightCursor | None = None, limit: int = 50
    ) -> Page[dict[str, Any], BarWeightCursor]:
        with closing(self._connect()) as conn:
            return search_weight_prefix(conn, prefix, cursor=cursor, limit=limit)

    def get_list_snapshot(self, list_id: int) -> BarListSnapshot:
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            return read_list_snapshot(conn, list_id)

    def get_list_history_page(
        self,
        *,
        search_term: str = "",
        state: str = "All",
        cursor: int | None = None,
        include_total: bool = True,
        limit: int = 500,
    ) -> Page[dict[str, Any], int]:
        """Search saved lists with complete inventory totals in one read snapshot."""
        conditions = ["1 = 1"]
        params: list[Any] = []
        if search_term.strip():
            conditions.append("(l.list_identifier LIKE ? OR l.list_note LIKE ?)")
            params.extend([f"%{search_term.strip()}%"] * 2)
        if state in ("Active", "Issued"):
            conditions.append(
                "l.issued_date IS NULL"
                if state == "Active"
                else "l.issued_date IS NOT NULL"
            )
        where = " AND ".join(conditions)
        size = max(1, min(int(limit), 1000))
        with closing(self._connect()) as conn:
            conn.execute("BEGIN")
            total = None
            if include_total:
                total = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM silver_bar_lists l WHERE {where}",  # noqa: S608
                        params,
                    ).fetchone()[0]
                )
            if cursor is not None:
                where += " AND l.list_id < ?"
                params.append(cursor)
            rows = [
                dict(row)
                for row in conn.execute(
                    f"""SELECT l.*, COUNT(sb.bar_id) AS bar_count,
                           COALESCE(SUM(sb.weight), 0) AS weight,
                           COALESCE(SUM(sb.fine_weight), 0) AS fine_weight
                    FROM silver_bar_lists l
                    LEFT JOIN silver_bars sb ON sb.list_id = l.list_id
                    WHERE {where} GROUP BY l.list_id ORDER BY l.list_id DESC LIMIT ?""",  # noqa: S608
                    [*params, size + 1],
                ).fetchall()
            ]
        has_more = len(rows) > size
        rows = rows[:size]
        return Page(tuple(rows), total, int(rows[-1]["list_id"]) if has_more else None)

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


__all__ = [
    "SilverBarQueryRepository",
    "SilverBarRepositoryBase",
    "SilverBarsSnapshotRepository",
    "SqlStatement",
    "build_history_bars_count_query",
    "build_history_bars_query",
    "normalize_row_limit",
    "read_list_snapshot",
    "search_weight_prefix",
]
