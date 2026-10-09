"""Read-only silver-bar persistence component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, List, Optional, Tuple, cast

from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.silver_bar_repository_base import (
    _SilverBarRepositoryBase,
)
from silverestimate.persistence.silver_bar_workspace_queries import (
    read_list_snapshot,
)

SilverBarRow = Mapping[str, Any]


class SilverBarQueryRepository(_SilverBarRepositoryBase):
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


__all__ = ["SilverBarQueryRepository"]
