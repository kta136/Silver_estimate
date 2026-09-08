"""Estimate repository handling header and item CRUD operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Iterable, List, Optional

from silverestimate.domain.estimate_save import EstimateSaveResult
from silverestimate.domain.estimate_validation import (
    SQLITE_MAX_INTEGER,
    validate_estimate,
)
from silverestimate.domain.pagination import EstimateHistoryCursor, Page
from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.database_protocols import RepositoryDatabase
from silverestimate.persistence.silver_bar_synchronization_repository import (
    BarReconciliationPlan,
    SilverBarSynchronizationRepository,
)


def fetch_estimate_history_rows(
    cursor: sqlite3.Cursor,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    voucher_search: str | None = None,
) -> list[dict[str, Any]]:
    """Return estimate-history rows with regular-item aggregates in one query."""
    query = """
        WITH filtered_estimates AS (
            SELECT
                voucher_no,
                voucher_no_int,
                date,
                note,
                silver_rate,
                total_fine,
                total_wage,
                last_balance_silver,
                last_balance_amount
            FROM estimates
            WHERE 1=1
    """
    params: list[Any] = []
    if date_from:
        query += " AND date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND date <= ?"
        params.append(date_to)
    if voucher_search:
        query += " AND voucher_no LIKE ?"
        params.append(f"%{voucher_search}%")

    query += """
        )
        SELECT
            e.voucher_no,
            e.date,
            e.note,
            e.silver_rate,
            e.total_fine,
            e.total_wage,
            e.last_balance_silver,
            e.last_balance_amount,
            COALESCE(
                SUM(
                    CASE
                        WHEN ei.is_return = 0 AND ei.is_silver_bar = 0
                        THEN ei.gross
                        ELSE 0
                    END
                ),
                0
            ) AS total_gross,
            COALESCE(
                SUM(
                    CASE
                        WHEN ei.is_return = 0 AND ei.is_silver_bar = 0
                        THEN ei.net_wt
                        ELSE 0
                    END
                ),
                0
            ) AS total_net
        FROM filtered_estimates e
        LEFT JOIN estimate_items ei ON ei.voucher_no = e.voucher_no
        GROUP BY
            e.voucher_no,
            e.voucher_no_int,
            e.date,
            e.note,
            e.silver_rate,
            e.total_fine,
            e.total_wage,
            e.last_balance_silver,
            e.last_balance_amount
        ORDER BY e.voucher_no_int DESC, e.voucher_no DESC
    """
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def fetch_estimate_history_page(
    cursor: sqlite3.Cursor,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    voucher_search: str | None = None,
    page_cursor: EstimateHistoryCursor | None = None,
    include_total: bool = True,
    limit: int = 500,
) -> Page[dict[str, Any], EstimateHistoryCursor]:
    """Return a keyset page using persisted estimate-header summaries."""
    page_size = max(1, min(int(limit), 2000))
    conditions = ["1=1"]
    params: list[Any] = []
    if date_from:
        conditions.append("date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("date <= ?")
        params.append(date_to)
    normalized_search = str(voucher_search or "").strip()
    if normalized_search:
        conditions.append("voucher_no LIKE ? COLLATE NOCASE")
        params.append(f"%{normalized_search}%")

    where_sql = " AND ".join(conditions)
    total = None
    if include_total:
        cursor.execute(f"SELECT COUNT(*) FROM estimates WHERE {where_sql}", params)  # nosec B608
        count_row = cursor.fetchone()
        total = int(count_row[0]) if count_row else 0

    keyset_sql = ""
    query_params = list(params)
    if page_cursor is not None:
        numeric_cursor = (
            int(page_cursor.voucher_no_int)
            if page_cursor.voucher_no_int is not None
            else -1
        )
        keyset_sql = (
            " AND COALESCE(voucher_no_int, -1) <= ? AND (COALESCE(voucher_no_int, -1) < ? OR "
            "(COALESCE(voucher_no_int, -1) = ? AND voucher_no < ?))"
        )
        query_params.extend(
            (numeric_cursor, numeric_cursor, numeric_cursor, page_cursor.voucher_no)
        )
    query_params.append(page_size + 1)
    cursor.execute(
        f"""
        SELECT
            voucher_no,
            voucher_no_int,
            date,
            note,
            silver_rate,
            total_gross,
            total_net,
            total_fine,
            total_wage,
            last_balance_silver,
            last_balance_amount
        FROM estimates
        WHERE {where_sql}{keyset_sql}
        ORDER BY COALESCE(voucher_no_int, -1) DESC, voucher_no DESC
        LIMIT ?
        """,  # nosec B608
        query_params,
    )
    fetched = [dict(row) for row in cursor.fetchall()]
    has_more = len(fetched) > page_size
    rows = fetched[:page_size]
    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        raw_numeric = last.get("voucher_no_int")
        next_cursor = EstimateHistoryCursor(
            int(raw_numeric) if raw_numeric is not None else None,
            str(last.get("voucher_no", "") or ""),
        )
    return Page(items=tuple(rows), total=total, next_cursor=next_cursor)


class EstimatesRepository:
    """Encapsulate estimate header/item persistence logic."""

    def __init__(self, db_manager: RepositoryDatabase) -> None:
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
            except sqlite3.Error, ValueError, TypeError:
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
                "SELECT ei.* "
                "FROM estimate_items ei "
                "WHERE ei.voucher_no = ? "
                "ORDER BY ei.is_return, ei.is_silver_bar, ei.id",
                (voucher_no,),
            )
            items = cursor.fetchall()
            conn.commit()
            return {
                "header": dict(estimate),
                "items": [self._snapshot_item(item) for item in items],
            }
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

    def get_estimate_history_rows(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        voucher_search: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._cursor
        if not cursor:
            return []
        try:
            return fetch_estimate_history_rows(
                cursor,
                date_from=date_from,
                date_to=date_to,
                voucher_search=voucher_search,
            )
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error getting estimate history rows: %s",
                exc,
                exc_info=True,
            )
            return []

    def get_estimate_history_page(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        voucher_search: str | None = None,
        cursor: EstimateHistoryCursor | None = None,
        limit: int = 500,
    ) -> Page[dict[str, Any], EstimateHistoryCursor]:
        db_cursor = self._cursor
        if not db_cursor:
            return Page(items=(), total=0, next_cursor=None)
        try:
            return fetch_estimate_history_page(
                db_cursor,
                date_from=date_from,
                date_to=date_to,
                voucher_search=voucher_search,
                page_cursor=cursor,
                limit=limit,
            )
        except sqlite3.Error:
            self._logger.exception("DB Error getting estimate-history page")
            raise

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
        """Compatibility boolean API; inventory participates in the same save."""
        return self.save_estimate_atomic(
            voucher_no, date, silver_rate, regular_items, return_items, totals
        ).success

    def save_estimate_atomic(
        self,
        voucher_no: str,
        date: str,
        silver_rate: float,
        regular_items: Iterable[dict],
        return_items: Iterable[dict],
        totals: dict,
    ) -> EstimateSaveResult:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            self._set_last_error(
                "Cannot save estimate: no active database connection is available."
            )
            return EstimateSaveResult(False, error_detail=self._db.last_error)
        transaction_started = False
        regular_items_list: list[dict] = []
        return_items_list: list[dict] = []
        try:
            self._set_last_error(None)
            regular_items_list = [dict(item) for item in regular_items or []]
            return_items_list = [dict(item) for item in return_items or []]
            conn.execute("BEGIN IMMEDIATE")
            transaction_started = True
            cursor.execute(
                "SELECT 1 FROM estimates WHERE voucher_no = ?", (voucher_no,)
            )
            estimate_exists = cursor.fetchone() is not None

            note = totals.get("note", "")
            last_balance_silver = totals.get("last_balance_silver", 0.0)
            last_balance_amount = totals.get("last_balance_amount", 0.0)
            voucher_no_int = self._voucher_to_int(voucher_no)

            all_items = regular_items_list + return_items_list
            missing_code_keys = self._prepare_snapshots(cursor, voucher_no, all_items)
            validate_estimate(
                voucher_no,
                silver_rate,
                all_items,
                totals,
                missing_code_keys=missing_code_keys,
            )

            inventory_plan = self._prepare_inventory(
                cursor, voucher_no, regular_items_list, return_items_list
            )

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
            params = [
                (
                    voucher_no,
                    item.get("_catalog_code"),
                    item.get("name", ""),
                    float(item.get("gross", 0.0)),
                    float(item.get("poly", 0.0)),
                    float(item.get("net_wt", 0.0)),
                    float(item.get("purity", 0.0)),
                    float(item.get("wage_rate", 0.0)),
                    int(item.get("pieces", 1)),
                    str(item.get("wage_type", "WT") or "WT"),
                    float(item.get("wage", 0.0)),
                    float(item.get("fine", 0.0)),
                    0,
                    0,
                    str(item.get("line_key", "") or ""),
                    item.get("code") or None,
                    item.get("tunch"),
                )
                for item in regular_items_list
            ]
            params.extend(
                (
                    voucher_no,
                    item.get("_catalog_code"),
                    item.get("name", ""),
                    float(item.get("gross", 0.0)),
                    float(item.get("poly", 0.0)),
                    float(item.get("net_wt", 0.0)),
                    float(item.get("purity", 0.0)),
                    float(item.get("wage_rate", 0.0)),
                    int(item.get("pieces", 1)),
                    str(item.get("wage_type", "WT") or "WT"),
                    float(item.get("wage", 0.0)),
                    float(item.get("fine", 0.0)),
                    1 if item.get("is_return", False) else 0,
                    1 if item.get("is_silver_bar", False) else 0,
                    str(item.get("line_key", "") or ""),
                    item.get("code") or None,
                    item.get("tunch"),
                )
                for item in return_items_list
            )
            if params:
                cursor.executemany(
                    "INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage_type, wage, fine, is_return, is_silver_bar, line_key, item_code_snapshot, tunch) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    params,
                )

            inventory = SilverBarSynchronizationRepository.apply(
                cursor, voucher_no, inventory_plan
            )
            cursor.execute(
                "DELETE FROM estimate_draft WHERE voucher_no = ?", (voucher_no,)
            )
            conn.commit()
            transaction_started = False
            self._set_last_error(None)
            return EstimateSaveResult(
                True,
                bars_added=inventory.added,
                bars_updated=inventory.updated,
                bars_removed=inventory.removed,
            )
        except sqlite3.IntegrityError as exc:
            detail_message = self._diagnose_integrity_error(
                exc, regular_items_list + return_items_list
            )
            self._logger.error(
                "DB integrity error saving estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            self._set_last_error(
                detail_message
                or f"Database integrity error while saving estimate '{voucher_no}': {exc}"
            )
            return EstimateSaveResult(False, error_detail=self._db.last_error)
        except Exception as exc:
            self._logger.error(
                "Failed saving estimate %s: %s", voucher_no, exc, exc_info=True
            )
            self._set_last_error(f"Could not save estimate '{voucher_no}': {exc}")
            return EstimateSaveResult(False, error_detail=self._db.last_error)
        finally:
            if transaction_started:
                conn.rollback()

    @staticmethod
    def _snapshot_item(row) -> dict:
        item = dict(row)
        item["item_code"] = (
            item.get("item_code_snapshot")
            if item.get("item_code_snapshot") is not None
            else item.get("item_code")
        )
        return item

    def _prepare_snapshots(
        self, cursor, voucher_no: str, items: list[dict]
    ) -> set[str]:
        """Resolve new catalog links while retaining same-line historical metadata."""
        from uuid import uuid4

        cursor.execute(
            "SELECT * FROM estimate_items WHERE voucher_no = ?", (voucher_no,)
        )
        existing: dict[str, dict] = {}
        for row in cursor.fetchall():
            key = str(row["line_key"] or "").strip()
            if key:
                if key in existing:
                    raise ValueError("Saved estimate contains duplicate line keys.")
                existing[key] = dict(row)
        codes = sorted(
            {str(item.get("code") or "").strip().upper() for item in items} - {""}
        )
        catalog: dict[str, dict] = {}
        for start in range(0, len(codes), 900):
            chunk = codes[start : start + 900]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT code, tunch FROM items WHERE UPPER(code) IN ({placeholders})",  # nosec B608
                chunk,
            )
            catalog.update(
                {str(row["code"]).upper(): dict(row) for row in cursor.fetchall()}
            )
        missing = []
        missing_code_keys = set()
        for item in items:
            code = str(item.get("code") or "").strip()
            key = str(item.get("line_key") or "").strip()
            previous = existing.get(key)
            same_line = (
                previous is not None
                and str(previous["item_code_snapshot"] or "").upper() == code.upper()
            )
            master = catalog.get(code.upper())
            if not master and not same_line:
                if code:
                    missing.append(code)
                else:
                    raise ValueError("Item code is required for new lines.")
            item["_catalog_code"] = master["code"] if master else None
            item["tunch"] = (
                previous["tunch"]
                if same_line and previous is not None
                else (master or {}).get("tunch")
            )
            if same_line and not code:
                missing_code_keys.add(key)
            # Bar keys are assigned by inventory reconciliation to preserve legacy identity.
            if not key and not item.get("is_silver_bar"):
                item["line_key"] = uuid4().hex
        if missing:
            raise ValueError(self._format_missing_code_message(missing, items))
        return missing_code_keys

    def _prepare_inventory(
        self,
        cursor: sqlite3.Cursor,
        voucher_no: str,
        regular_items: list[dict],
        return_items: list[dict],
    ) -> BarReconciliationPlan:
        bars = [
            item
            for item in return_items
            if item.get("is_silver_bar") and not item.get("is_return")
        ]
        plan = SilverBarSynchronizationRepository(self._db).prepare(
            cursor, voucher_no, bars
        )
        line_keys = []
        for item in regular_items + return_items:
            item["line_key"] = str(item.get("line_key") or "").strip()
            if item["line_key"]:
                line_keys.append(item["line_key"])
        if len(line_keys) != len(set(line_keys)):
            raise ValueError("Estimate contains duplicate line keys.")
        return plan

    @staticmethod
    def _voucher_to_int(voucher_no: str) -> Optional[int]:
        raw = str(voucher_no or "").strip()
        if not raw.isdigit():
            return None
        try:
            value = int(raw)
            return value if value <= SQLITE_MAX_INTEGER else None
        except TypeError, ValueError:
            return None

    def delete_all_estimates(self) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute("DELETE FROM estimate_items")
            cursor.execute("DELETE FROM estimate_draft")
            cursor.execute("DELETE FROM estimates")
            conn.commit()
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
        transaction_started = False
        try:
            self._set_last_error(None)
            conn.execute("BEGIN IMMEDIATE")
            transaction_started = True
            cursor.execute(
                """
                SELECT 1 FROM silver_bars AS bars
                WHERE bars.estimate_voucher_no = ?
                  AND (COALESCE(bars.status, '') != 'In Stock'
                       OR bars.list_id IS NOT NULL
                       OR EXISTS (SELECT 1 FROM bar_transfers AS transfers
                                  WHERE transfers.silver_bar_id = bars.bar_id))
                LIMIT 1
                """,
                (voucher_no,),
            )
            if cursor.fetchone():
                self._set_last_error(
                    f"Estimate '{voucher_no}' cannot be deleted because its silver bars "
                    "are assigned, issued, or have transfer history. "
                    "Keep this estimate to preserve the inventory records."
                )
                return False
            deleted_bars_count = 0
            affected_lists: set[int] = set()
            silver_repo = getattr(self._db, "silver_bar_command_repo", None)
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
            cursor.execute(
                "DELETE FROM estimate_draft WHERE voucher_no = ?", (voucher_no,)
            )
            cursor.execute("DELETE FROM estimates WHERE voucher_no = ?", (voucher_no,))
            deleted_estimate_count = cursor.rowcount

            if silver_repo is not None and affected_lists:
                silver_repo.cleanup_empty_lists(affected_lists)

            cursor.execute(
                "DELETE FROM estimate_draft WHERE voucher_no = ?", (voucher_no,)
            )
            conn.commit()
            transaction_started = False
            if deleted_estimate_count > 0:
                self._logger.info(
                    "Deleted estimate %s with %s items and %s silver bars.",
                    voucher_no,
                    deleted_items_count,
                    deleted_bars_count,
                )
                return True
            self._logger.warning("Estimate %s not found for deletion.", voucher_no)
            self._set_last_error(f"Estimate '{voucher_no}' was not found.")
            return False
        except Exception as exc:
            self._set_last_error(f"Could not delete estimate '{voucher_no}': {exc}")
            self._logger.error(
                "Unexpected error deleting estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return False
        finally:
            if transaction_started:
                conn.rollback()

    def _set_last_error(self, message: str | None) -> None:
        try:
            self._db.last_error = message
        except Exception as exc:
            self._logger.debug(
                "Failed to store estimate repository error state: %s", exc
            )

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
            # Placeholder count is generated locally; values remain parameterized.
            cursor.execute(
                f"SELECT code FROM items WHERE UPPER(code) IN ({placeholders})",  # nosec B608
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
            except TypeError, ValueError:
                try:
                    row_map[code] = int(float(row_number))
                except TypeError, ValueError:
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
