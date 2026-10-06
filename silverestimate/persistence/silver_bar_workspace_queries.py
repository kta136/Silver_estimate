"""Full-inventory prefix searches and consistent list snapshots."""

from __future__ import annotations

from typing import Any

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.pagination import Page
from silverestimate.domain.silver_bar_workspace import (
    BarListSnapshot,
    BarWeightCursor,
    normalize_weight_prefix,
)


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
