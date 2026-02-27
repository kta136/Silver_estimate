"""Shared SQL builders for silver-bar repository queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence


@dataclass(frozen=True)
class SqlStatement:
    """A parametrized SQL statement."""

    query: str
    params: Sequence[Any]


@dataclass(frozen=True)
class PagedSqlStatements:
    """A data query plus a paired count query."""

    query: SqlStatement
    count_query: SqlStatement


def normalize_row_limit(limit: Any, *, default: int, minimum: int = 100) -> int:
    """Normalize table row limits used across silver-bar views."""

    try:
        return max(int(minimum), int(limit))
    except (TypeError, ValueError):
        return max(int(minimum), int(default))


def build_available_bars_queries(
    *,
    weight_query: Any = None,
    weight_tolerance: float = 0.001,
    min_purity: Any = None,
    max_purity: Any = None,
    date_range: Any = None,
    limit: int | None = None,
) -> PagedSqlStatements:
    """Build paired queries for unassigned in-stock silver bars."""

    query = (
        "SELECT sb.*, e.note AS estimate_note "
        "FROM silver_bars sb "
        "LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no "
        "WHERE sb.status = 'In Stock' AND sb.list_id IS NULL"
    )
    count_query = (
        "SELECT COUNT(*) FROM silver_bars sb "
        "WHERE sb.status = 'In Stock' AND sb.list_id IS NULL"
    )
    params: List[Any] = []
    count_params: List[Any] = []

    if weight_query not in (None, ""):
        try:
            target = float(weight_query)
            tolerance = float(weight_tolerance or 0.001)
            bounds = [target - tolerance, target + tolerance]
            query += " AND sb.weight BETWEEN ? AND ?"
            count_query += " AND sb.weight BETWEEN ? AND ?"
            params.extend(bounds)
            count_params.extend(bounds)
        except (TypeError, ValueError):
            pass

    if min_purity is not None:
        try:
            purity_floor = float(min_purity)
            query += " AND sb.purity >= ?"
            count_query += " AND sb.purity >= ?"
            params.append(purity_floor)
            count_params.append(purity_floor)
        except (TypeError, ValueError):
            pass

    if max_purity is not None:
        try:
            purity_ceiling = float(max_purity)
            query += " AND sb.purity <= ?"
            count_query += " AND sb.purity <= ?"
            params.append(purity_ceiling)
            count_params.append(purity_ceiling)
        except (TypeError, ValueError):
            pass

    if (
        date_range
        and isinstance(date_range, (tuple, list))
        and len(date_range) == 2
    ):
        start_iso, end_iso = date_range
        if start_iso:
            query += " AND sb.date_added >= ?"
            count_query += " AND sb.date_added >= ?"
            params.append(start_iso)
            count_params.append(start_iso)
        if end_iso:
            query += " AND sb.date_added <= ?"
            count_query += " AND sb.date_added <= ?"
            params.append(end_iso)
            count_params.append(end_iso)

    query += " ORDER BY sb.date_added DESC, sb.bar_id DESC"
    if isinstance(limit, int) and limit > 0:
        query += " LIMIT ?"
        params.append(int(limit))

    return PagedSqlStatements(
        query=SqlStatement(query, tuple(params)),
        count_query=SqlStatement(count_query, tuple(count_params)),
    )


def build_bars_in_list_queries(
    list_id: int | None,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> PagedSqlStatements:
    """Build paired queries for bars assigned to a specific list."""

    params: List[Any] = [list_id]
    query = (
        "SELECT sb.*, e.note AS estimate_note "
        "FROM silver_bars sb "
        "LEFT JOIN estimates e ON sb.estimate_voucher_no = e.voucher_no "
        "WHERE sb.list_id = ? "
        "ORDER BY sb.bar_id"
    )
    if isinstance(limit, int) and limit > 0:
        query += " LIMIT ?"
        params.append(int(limit))
        if isinstance(offset, int) and offset > 0:
            query += " OFFSET ?"
            params.append(int(offset))

    return PagedSqlStatements(
        query=SqlStatement(query, tuple(params)),
        count_query=SqlStatement(
            "SELECT COUNT(*) FROM silver_bars WHERE list_id = ?",
            (list_id,),
        ),
    )


def build_history_bars_query(
    *,
    voucher_term: str = "",
    weight_text: str = "",
    status_text: str = "All Statuses",
    limit: int = 2000,
) -> SqlStatement:
    """Build the history search query used by the history dialog worker."""

    conditions: List[str] = []
    params: List[Any] = []

    normalized_voucher = str(voucher_term or "").strip()
    if normalized_voucher:
        pattern = f"%{normalized_voucher}%"
        conditions.append("(sb.estimate_voucher_no LIKE ? OR e.note LIKE ?)")
        params.extend([pattern, pattern])

    normalized_weight = str(weight_text or "").strip()
    if normalized_weight:
        try:
            weight_value = float(normalized_weight)
            conditions.append("sb.weight = ?")
            params.append(weight_value)
        except (TypeError, ValueError):
            pass

    normalized_status = str(status_text or "").strip()
    if normalized_status and normalized_status != "All Statuses":
        conditions.append("sb.status = ?")
        params.append(normalized_status)

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
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY sb.date_added DESC, sb.bar_id DESC LIMIT ?"
    params.append(normalize_row_limit(limit, default=2000))
    return SqlStatement(query, tuple(params))
