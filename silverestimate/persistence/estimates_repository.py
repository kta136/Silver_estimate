"""Estimate repository handling header and item CRUD operations."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Iterable, List, Optional


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
                "SELECT MAX(voucher_no_int) FROM estimates WHERE voucher_no_int IS NOT NULL"
            )
            result = cursor.fetchone()
            if result and result[0] is not None:
                return str(int(result[0]) + 1)
            return "1"
        except (sqlite3.Error, ValueError, TypeError) as exc:
            try:
                cursor.execute(
                    "SELECT MAX(CAST(voucher_no AS INTEGER)) FROM estimates WHERE voucher_no GLOB '[0-9]*'"
                )
                result = cursor.fetchone()
                if result and result[0] is not None:
                    return str(int(result[0]) + 1)
                return "1"
            except (sqlite3.Error, ValueError, TypeError):
                self._logger.error(
                    "DB error generating voucher number: %s", exc, exc_info=True
                )
                return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def get_estimate_by_voucher(self, voucher_no: str):
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            self._logger.error(
                "Cannot get estimate %s: No active database connection", voucher_no
            )
            return None
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT * FROM estimates WHERE voucher_no = ?", (voucher_no,)
            )
            estimate = cursor.fetchone()
            if not estimate:
                conn.rollback()
                return None
            cursor.execute(
                "SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY is_return, is_silver_bar, id",
                (voucher_no,),
            )
            items = cursor.fetchall()
            conn.commit()
            return {"header": dict(estimate), "items": [dict(item) for item in items]}
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error(
                "DB Error getting estimate %s: %s", voucher_no, exc, exc_info=True
            )
            return None
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            self._logger.error(
                "Unexpected error getting estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return None

    def estimate_exists(self, voucher_no: str) -> bool:
        cursor = self._cursor
        if not cursor or not voucher_no:
            return False
        try:
            cursor.execute(
                "SELECT 1 FROM estimates WHERE voucher_no = ? LIMIT 1",
                (voucher_no,),
            )
            return cursor.fetchone() is not None
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error checking estimate existence %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return False

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
        try:
            cursor.execute(
                f"{query} ORDER BY voucher_no_int DESC, voucher_no DESC",
                params,
            )
            headers = [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error getting estimates: %s",
                exc,
                exc_info=True,
            )
            return []

        if not headers:
            return []

        voucher_nos = [
            str(row.get("voucher_no", ""))
            for row in headers
            if row.get("voucher_no") is not None
        ]
        items_by_voucher = self._load_estimate_items_by_voucher(voucher_nos)

        return [
            {
                "header": header,
                "items": items_by_voucher.get(str(header.get("voucher_no", "")), []),
            }
            for header in headers
        ]

    def _load_estimate_items_by_voucher(
        self, voucher_nos: Iterable[str]
    ) -> dict[str, list[dict[str, Any]]]:
        cursor = self._cursor
        if not cursor:
            return {}

        normalized = [str(voucher) for voucher in voucher_nos if str(voucher)]
        if not normalized:
            return {}

        items_by_voucher: dict[str, list[dict[str, Any]]] = {
            voucher_no: [] for voucher_no in normalized
        }
        chunk_size = 900  # Keep comfortably below SQLite variable limits.

        for start in range(0, len(normalized), chunk_size):
            chunk = normalized[start : start + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            try:
                cursor.execute(
                    f"SELECT * FROM estimate_items WHERE voucher_no IN ({placeholders}) ORDER BY voucher_no, id",
                    chunk,
                )
                for row in cursor.fetchall():
                    item = dict(row)
                    key = str(item.get("voucher_no", ""))
                    items_by_voucher.setdefault(key, []).append(item)
            except sqlite3.Error as exc:
                self._logger.error(
                    "DB Error loading estimate items for vouchers: %s",
                    exc,
                    exc_info=True,
                )
                return {}

        return items_by_voucher

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
        query += " ORDER BY voucher_no_int DESC, voucher_no DESC"
        try:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error getting estimate headers: %s", exc, exc_info=True
            )
            return []

    def get_first_estimate_date(self):
        """Return the earliest estimate date (yyyy-MM-dd) or None when unavailable."""
        cursor = self._cursor
        if not cursor:
            return None
        try:
            cursor.execute("SELECT MIN(date) AS first_date FROM estimates")
            row = cursor.fetchone()
            if not row:
                return None
            first_date = row["first_date"] if isinstance(row, sqlite3.Row) else row[0]
            return str(first_date) if first_date else None
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error getting first estimate date: %s", exc, exc_info=True
            )
            return None

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
            self._set_last_error(
                "Cannot save estimate: no active database connection is available."
            )
            return False
        try:
            self._set_last_error(None)
            conn.execute("BEGIN TRANSACTION")
            regular_items_list = list(regular_items or [])
            return_items_list = list(return_items or [])
            cursor.execute(
                "SELECT 1 FROM estimates WHERE voucher_no = ?", (voucher_no,)
            )
            estimate_exists = cursor.fetchone() is not None

            note = totals.get("note", "")
            last_balance_silver = totals.get("last_balance_silver", 0.0)
            last_balance_amount = totals.get("last_balance_amount", 0.0)
            voucher_no_int = self._voucher_to_int(voucher_no)

            all_items = regular_items_list + return_items_list
            missing_codes = self._find_missing_item_codes(all_items)
            if missing_codes:
                conn.rollback()
                message = self._format_missing_code_message(missing_codes, all_items)
                self._logger.warning(
                    "Estimate %s save aborted due to missing item codes: %s",
                    voucher_no,
                    ", ".join(missing_codes),
                )
                self._set_last_error(message)
                return False

            if estimate_exists:
                cursor.execute(
                    """
                    UPDATE estimates
                    SET date = ?, silver_rate = ?, total_gross = ?, total_net = ?,
                        total_fine = ?, total_wage = ?, note = ?,
                        last_balance_silver = ?, last_balance_amount = ?,
                        voucher_no_int = ?
                    WHERE voucher_no = ?
                    """,
                    (
                        date,
                        silver_rate,
                        totals.get("total_gross", 0.0),
                        totals.get("total_net", 0.0),
                        totals.get("net_fine", 0.0),
                        totals.get("net_wage", 0.0),
                        note,
                        last_balance_silver,
                        last_balance_amount,
                        voucher_no_int,
                        voucher_no,
                    ),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO estimates
                    (voucher_no, voucher_no_int, date, silver_rate, total_gross, total_net, total_fine, total_wage, note,
                     last_balance_silver, last_balance_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        voucher_no,
                        voucher_no_int,
                        date,
                        silver_rate,
                        totals.get("total_gross", 0.0),
                        totals.get("total_net", 0.0),
                        totals.get("net_fine", 0.0),
                        totals.get("net_wage", 0.0),
                        note,
                        last_balance_silver,
                        last_balance_amount,
                    ),
                )

            cursor.execute(
                "DELETE FROM estimate_items WHERE voucher_no = ?", (voucher_no,)
            )
            params = []
            for item in regular_items_list:
                params.append(
                    (
                        voucher_no,
                        item.get("code", ""),
                        item.get("name", ""),
                        float(item.get("gross", 0.0)),
                        float(item.get("poly", 0.0)),
                        float(item.get("net_wt", 0.0)),
                        float(item.get("purity", 0.0)),
                        float(item.get("wage_rate", 0.0)),
                        int(item.get("pieces", 1)),
                        float(item.get("wage", 0.0)),
                        float(item.get("fine", 0.0)),
                        0,
                        0,
                    )
                )
            for item in return_items_list:
                params.append(
                    (
                        voucher_no,
                        item.get("code", ""),
                        item.get("name", ""),
                        float(item.get("gross", 0.0)),
                        float(item.get("poly", 0.0)),
                        float(item.get("net_wt", 0.0)),
                        float(item.get("purity", 0.0)),
                        float(item.get("wage_rate", 0.0)),
                        int(item.get("pieces", 1)),
                        float(item.get("wage", 0.0)),
                        float(item.get("fine", 0.0)),
                        1 if item.get("is_return", False) else 0,
                        1 if item.get("is_silver_bar", False) else 0,
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
                            "INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            params,
                        )
                except sqlite3.Error:
                    cursor.executemany(
                        "INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        params,
                    )

            conn.commit()
            self._request_flush()
            self._set_last_error(None)
            return True
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            detail_message = self._diagnose_integrity_error(
                exc, regular_items_list + return_items_list
            )
            self._logger.error(
                "DB integrity error saving estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            if detail_message:
                self._set_last_error(detail_message)
            else:
                self._set_last_error(
                    f"Database integrity error while saving estimate '{voucher_no}': {exc}"
                )
            return False

    @staticmethod
    def _voucher_to_int(voucher_no: str) -> Optional[int]:
        raw = str(voucher_no or "").strip()
        if not raw.isdigit():
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    def delete_all_estimates(self) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute("DELETE FROM estimate_items")
            cursor.execute("DELETE FROM estimates")
            conn.commit()
            self._request_flush()
            return True
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error(
                "DB Error deleting all estimates: %s", exc, exc_info=True
            )
            return False

    def delete_single_estimate(self, voucher_no: str) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        if not voucher_no:
            self._logger.error("No voucher number provided for deletion.")
            return False
        try:
            conn.execute("BEGIN TRANSACTION")
            deleted_bars_count = 0
            affected_lists = set()
            silver_repo = getattr(self._db, "silver_bars_repo", None)
            if silver_repo is not None:
                deleted_bars_count, affected_lists = (
                    silver_repo.delete_bars_for_estimate(voucher_no)
                )
            else:
                cursor.execute(
                    "DELETE FROM silver_bars WHERE estimate_voucher_no = ?",
                    (voucher_no,),
                )
                deleted_bars_count = cursor.rowcount

            cursor.execute(
                "DELETE FROM estimate_items WHERE voucher_no = ?", (voucher_no,)
            )
            deleted_items_count = cursor.rowcount
            cursor.execute("DELETE FROM estimates WHERE voucher_no = ?", (voucher_no,))
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
            self._logger.error(
                "DB Error deleting estimate %s: %s", voucher_no, exc, exc_info=True
            )
            return False
        except Exception as exc:
            conn.rollback()
            self._logger.error(
                "Unexpected error deleting estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return False

    def _set_last_error(self, message: str | None) -> None:
        try:
            setattr(self._db, "last_error", message)
        except Exception:
            pass

    def _find_missing_item_codes(self, items: Iterable[dict]) -> List[str]:
        cursor = self._cursor
        if not cursor:
            return []
        codes = []
        for item in items:
            code = (item.get("code") or "").strip()
            if code:
                codes.append(code)
        if not codes:
            return []
        unique_codes = list(dict.fromkeys(codes))
        if not unique_codes:
            return []

        normalized_map = {code: code.upper() for code in unique_codes}
        placeholders = ",".join("?" for _ in unique_codes)
        try:
            cursor.execute(
                f"SELECT code FROM items WHERE UPPER(code) IN ({placeholders})",
                [normalized_map[code] for code in unique_codes],
            )
            rows = cursor.fetchall()
            found = {(row["code"] or "").upper() for row in rows}
        except sqlite3.Error as exc:
            self._logger.error(
                "Failed to verify item codes before saving estimate: %s",
                exc,
                exc_info=True,
            )
            return []
        return [code for code in unique_codes if normalized_map[code] not in found]

    def _collect_item_rows(self, items: Iterable[dict]) -> dict[str, int]:
        row_map: dict[str, int] = {}
        for item in items:
            code = (item.get("code") or "").strip()
            if not code or code in row_map:
                continue
            row_number = (
                item.get("row_number") or item.get("row_index") or item.get("row")
            )
            if row_number is None:
                continue
            try:
                row_map[code] = int(row_number)
            except (TypeError, ValueError):
                try:
                    row_map[code] = int(float(row_number))
                except (TypeError, ValueError):
                    continue
        return row_map

    def _format_missing_code_message(
        self, missing_codes: List[str], items: Iterable[dict]
    ) -> str:
        code_to_row = self._collect_item_rows(items)
        details: List[str] = []
        for code in missing_codes:
            row_number = code_to_row.get(code)
            if row_number is not None:
                details.append(f"'{code}' (row {row_number})")
            else:
                details.append(f"'{code}'")
        if len(details) == 1:
            return (
                f"Item code {details[0]} is not defined in the item master. "
                "Please add or correct it before saving."
            )
        joined = ", ".join(details)
        return (
            f"Item codes {joined} are not defined in the item master. "
            "Please add or correct them before saving."
        )

    def _diagnose_integrity_error(
        self, exc: sqlite3.IntegrityError, items: Iterable[dict]
    ) -> str | None:
        message = str(exc)
        if "FOREIGN KEY constraint failed" in message:
            missing_codes = self._find_missing_item_codes(items)
            if missing_codes:
                return self._format_missing_code_message(missing_codes, items)
            return (
                "Foreign key constraint failed while saving estimate items. "
                "Please verify all item codes exist in the item master."
            )
        return None

    # ------------------------------------------------------------------

    def _request_flush(self) -> None:
        try:
            requester = getattr(self._db, "request_flush", None)
            if callable(requester):
                requester()
        except Exception as exc:  # pragma: no cover - log only
            self._logger.error(
                "Exception during post-estimate flush: %s", exc, exc_info=True
            )
