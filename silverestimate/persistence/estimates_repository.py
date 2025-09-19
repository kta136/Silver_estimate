"""Estimate repository handling header and item CRUD operations."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Iterable, List


class EstimatesRepository:
    """Encapsulate estimate header/item persistence logic."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))

    @property
    def _conn(self):
        return getattr(self._db, "conn", None)

    @property
    def _cursor(self):
        return getattr(self._db, "cursor", None)

    def generate_voucher_no(self) -> str:
        cursor = self._cursor
        if not cursor:
            return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            cursor.execute(
                "SELECT MAX(CAST(voucher_no AS INTEGER)) FROM estimates WHERE voucher_no GLOB '[0-9]*'"
            )
            result = cursor.fetchone()
            if result and result[0] is not None:
                return str(int(result[0]) + 1)
            return "1"
        except (sqlite3.Error, ValueError, TypeError) as exc:
            self._logger.error("DB error generating voucher number: %s", exc, exc_info=True)
            return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_estimate_by_voucher(self, voucher_no: str):
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            self._logger.error("Cannot get estimate %s: No active database connection", voucher_no)
            return None
        try:
            conn.execute('BEGIN TRANSACTION')
            cursor.execute('SELECT * FROM estimates WHERE voucher_no = ?', (voucher_no,))
            estimate = cursor.fetchone()
            if not estimate:
                conn.rollback()
                return None
            cursor.execute(
                'SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY is_return, is_silver_bar, id',
                (voucher_no,),
            )
            items = cursor.fetchall()
            conn.commit()
            return {'header': dict(estimate), 'items': [dict(item) for item in items]}
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error("DB Error getting estimate %s: %s", voucher_no, exc, exc_info=True)
            return None
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            self._logger.error("Unexpected error getting estimate %s: %s", voucher_no, exc, exc_info=True)
            return None

    def get_estimates(self, date_from=None, date_to=None, voucher_search=None):
        cursor = self._cursor
        if not cursor:
            return []
        query = "SELECT * FROM estimates WHERE 1=1"
        params: List[Any] = []
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        if voucher_search:
            query += " AND voucher_no LIKE ?"
            params.append(f"%{voucher_search}%")
        query += " ORDER BY CAST(voucher_no AS INTEGER) DESC"
        try:
            cursor.execute(query, params)
            headers = cursor.fetchall()
            results = []
            for header in headers:
                voucher_no = header['voucher_no']
                cursor.execute('SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY id', (voucher_no,))
                items = cursor.fetchall()
                results.append({'header': dict(header), 'items': [dict(item) for item in items]})
            return results
        except sqlite3.Error as exc:
            self._logger.error("DB Error getting estimates: %s", exc, exc_info=True)
            return []

    def get_estimate_headers(self, date_from=None, date_to=None, voucher_search=None):
        cursor = self._cursor
        if not cursor:
            return []
        query = "SELECT * FROM estimates WHERE 1=1"
        params: List[Any] = []
        if date_from:
            query += " AND date >= ?"
            params.append(date_from)
        if date_to:
            query += " AND date <= ?"
            params.append(date_to)
        if voucher_search:
            query += " AND voucher_no LIKE ?"
            params.append(f"%{voucher_search}%")
        query += " ORDER BY CAST(voucher_no AS INTEGER) DESC"
        try:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            self._logger.error("DB Error getting estimate headers: %s", exc, exc_info=True)
            return []

    def save_estimate_with_returns(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[dict],
        return_items: Iterable[dict],
        totals: dict,
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            conn.execute('BEGIN TRANSACTION')
            cursor.execute('SELECT 1 FROM estimates WHERE voucher_no = ?', (voucher_no,))
            estimate_exists = cursor.fetchone() is not None

            note = totals.get('note', '')
            last_balance_silver = totals.get('last_balance_silver', 0.0)
            last_balance_amount = totals.get('last_balance_amount', 0.0)

            if estimate_exists:
                cursor.execute(
                    '''
                    UPDATE estimates
                    SET date = ?, silver_rate = ?, total_gross = ?, total_net = ?,
                        total_fine = ?, total_wage = ?, note = ?,
                        last_balance_silver = ?, last_balance_amount = ?
                    WHERE voucher_no = ?
                    ''',
                    (
                        date,
                        silver_rate,
                        totals.get('total_gross', 0.0),
                        totals.get('total_net', 0.0),
                        totals.get('net_fine', 0.0),
                        totals.get('net_wage', 0.0),
                        note,
                        last_balance_silver,
                        last_balance_amount,
                        voucher_no,
                    ),
                )
            else:
                cursor.execute(
                    '''
                    INSERT INTO estimates
                    (voucher_no, date, silver_rate, total_gross, total_net, total_fine, total_wage, note,
                     last_balance_silver, last_balance_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        voucher_no,
                        date,
                        silver_rate,
                        totals.get('total_gross', 0.0),
                        totals.get('total_net', 0.0),
                        totals.get('net_fine', 0.0),
                        totals.get('net_wage', 0.0),
                        note,
                        last_balance_silver,
                        last_balance_amount,
                    ),
                )

            cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            params = []
            for item in regular_items:
                params.append(
                    (
                        voucher_no,
                        item.get('code', ''),
                        item.get('name', ''),
                        float(item.get('gross', 0.0)),
                        float(item.get('poly', 0.0)),
                        float(item.get('net_wt', 0.0)),
                        float(item.get('purity', 0.0)),
                        float(item.get('wage_rate', 0.0)),
                        int(item.get('pieces', 1)),
                        float(item.get('wage', 0.0)),
                        float(item.get('fine', 0.0)),
                        0,
                        0,
                    )
                )
            for item in return_items:
                params.append(
                    (
                        voucher_no,
                        item.get('code', ''),
                        item.get('name', ''),
                        float(item.get('gross', 0.0)),
                        float(item.get('poly', 0.0)),
                        float(item.get('net_wt', 0.0)),
                        float(item.get('purity', 0.0)),
                        float(item.get('wage_rate', 0.0)),
                        int(item.get('pieces', 1)),
                        float(item.get('wage', 0.0)),
                        float(item.get('fine', 0.0)),
                        1 if item.get('is_return', False) else 0,
                        1 if item.get('is_silver_bar', False) else 0,
                    )
                )
            if params:
                try:
                    prepared = getattr(self._db, "_c_insert_estimate_item", None)
                    stmt = getattr(self._db, "_sql_insert_estimate_item", None)
                    if prepared and stmt:
                        prepared.executemany(stmt, params)
                    else:
                        cursor.executemany(
                            'INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                            params,
                        )
                except sqlite3.Error:
                    cursor.executemany(
                        'INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        params,
                    )

            conn.commit()
            self._request_flush()
            return True
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error("DB Error saving estimate %s: %s", voucher_no, exc, exc_info=True)
            return False
        except Exception as exc:
            conn.rollback()
            self._logger.error("Unexpected error saving estimate %s: %s", voucher_no, exc, exc_info=True)
            return False

    def delete_all_estimates(self) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute('DELETE FROM estimate_items')
            cursor.execute('DELETE FROM estimates')
            conn.commit()
            self._request_flush()
            return True
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error("DB Error deleting all estimates: %s", exc, exc_info=True)
            return False

    def delete_single_estimate(self, voucher_no: str) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        if not voucher_no:
            self._logger.error("No voucher number provided for deletion.")
            return False
        try:
            conn.execute('BEGIN TRANSACTION')
            deleted_bars_count = 0
            affected_lists = set()
            silver_repo = getattr(self._db, 'silver_bars_repo', None)
            if silver_repo is not None:
                deleted_bars_count, affected_lists = silver_repo.delete_bars_for_estimate(voucher_no)
            else:
                cursor.execute("DELETE FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
                deleted_bars_count = cursor.rowcount

            cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            deleted_items_count = cursor.rowcount
            cursor.execute('DELETE FROM estimates WHERE voucher_no = ?', (voucher_no,))
            deleted_estimate_count = cursor.rowcount

            if silver_repo is not None and affected_lists:
                silver_repo.cleanup_empty_lists(affected_lists)

            conn.commit()
            self._request_flush()
            if deleted_estimate_count > 0:
                self._logger.info(
                    "Deleted estimate %s with %s items and %s silver bars.",
                    voucher_no,
                    deleted_items_count,
                    deleted_bars_count,
                )
                return True
            self._logger.warning("Estimate %s not found for deletion.", voucher_no)
            return False
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error("DB Error deleting estimate %s: %s", voucher_no, exc, exc_info=True)
            return False
        except Exception as exc:
            conn.rollback()
            self._logger.error("Unexpected error deleting estimate %s: %s", voucher_no, exc, exc_info=True)
            return False

    # ------------------------------------------------------------------

    def _request_flush(self) -> None:
        try:
            requester = getattr(self._db, "request_flush", None)
            if callable(requester):
                requester()
        except Exception as exc:  # pragma: no cover - log only
            self._logger.error("Exception during post-estimate flush: %s", exc, exc_info=True)

