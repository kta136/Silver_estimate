"""Silver bar repository handling list and bar operations."""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple


class SilverBarsRepository:
    """Encapsulate silver bar list and inventory persistence logic."""

    def __init__(self, db_manager: Any) -> None:
        self._db = db_manager
        self._logger = getattr(db_manager, "logger", logging.getLogger(__name__))

    @property
    def _conn(self):
        return getattr(self._db, "conn", None)

    @property
    def _cursor(self):
        return getattr(self._db, "cursor", None)

    # --- List management -----------------------------------------------------

    def generate_list_identifier(self) -> str:
        cursor = self._cursor
        if not cursor:
            return f"ERR-L-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        today_str = datetime.now().strftime('%Y%m%d')
        seq = 1
        try:
            cursor.execute(
                "SELECT list_identifier FROM silver_bar_lists WHERE list_identifier LIKE ? "
                "ORDER BY list_identifier DESC LIMIT 1",
                (f"L-{today_str}-%",),
            )
            result = cursor.fetchone()
            if result:
                try:
                    seq = int(result['list_identifier'].split('-')[-1]) + 1
                except (IndexError, ValueError):
                    self._logger.warning("Format issue when parsing list identifier")
        except sqlite3.Error as exc:
            self._logger.error("Error generating list ID sequence: %s", exc, exc_info=True)
        return f"L-{today_str}-{seq:03d}"

    def create_list(self, note: Optional[str] = None) -> Optional[int]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return None
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        list_identifier = self.generate_list_identifier()
        try:
            cursor.execute(
                'INSERT INTO silver_bar_lists (list_identifier, creation_date, list_note) VALUES (?, ?, ?)',
                (list_identifier, creation_date, note),
            )
            conn.commit()
            list_id = cursor.lastrowid
            self._logger.info("Created silver bar list %s (ID: %s).", list_identifier, list_id)
            return list_id
        except sqlite3.Error as exc:
            self._logger.error("DB error creating silver bar list: %s", exc, exc_info=True)
            conn.rollback()
            return None

    def get_lists(self, include_issued: bool = True):
        cursor = self._cursor
        if not cursor:
            return []
        try:
            if include_issued:
                query = (
                    'SELECT list_id, list_identifier, creation_date, list_note, issued_date '
                    'FROM silver_bar_lists ORDER BY creation_date DESC'
                )
            else:
                query = (
                    'SELECT list_id, list_identifier, creation_date, list_note, issued_date '
                    'FROM silver_bar_lists WHERE issued_date IS NULL ORDER BY creation_date DESC'
                )
            cursor.execute(query)
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB error fetching silver bar lists: %s", exc, exc_info=True)
            return []

    def get_list_details(self, list_id: int):
        cursor = self._cursor
        if not cursor:
            return None
        try:
            cursor.execute('SELECT * FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            return cursor.fetchone()
        except sqlite3.Error as exc:
            self._logger.error("DB error fetching list details for ID %s: %s", list_id, exc, exc_info=True)
            return None

    def update_list_note(self, list_id: int, new_note: str) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute('UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?', (new_note, list_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            self._logger.error("DB error updating list note for ID %s: %s", list_id, exc, exc_info=True)
            conn.rollback()
            return False

    def delete_list(self, list_id: int) -> Tuple[bool, str]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False, "No database connection"
        try:
            conn.execute('BEGIN TRANSACTION')
            cursor.execute("SELECT bar_id FROM silver_bars WHERE list_id = ?", (list_id,))
            bars_to_unassign = [row['bar_id'] for row in cursor.fetchall()]

            unassign_note = f"Unassigned due to list {list_id} deletion"
            unassigned_count = 0
            for bar_id in bars_to_unassign:
                if self.remove_bar_from_list(bar_id, note=unassign_note, perform_commit=False):
                    unassigned_count += 1
                else:
                    self._logger.warning(
                        "Failed to properly unassign bar %s during list deletion.", bar_id
                    )
                    cursor.execute(
                        "UPDATE silver_bars SET list_id = NULL, status = 'In Stock' WHERE bar_id = ?",
                        (bar_id,),
                    )

            cursor.execute('DELETE FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            self._logger.info(
                "Deleted list %s. Unassigned %s bars.", list_id, unassigned_count
            )
            return deleted, "Deleted" if deleted else "List not found"
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error("DB error deleting list %s: %s", list_id, exc, exc_info=True)
            return False, str(exc)

    # --- Assignment ---------------------------------------------------------

    def assign_bar_to_list(
        self,
        bar_id: int,
        list_id: int,
        note: str = "Assigned to list",
        perform_commit: bool = True,
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        transfer_no = f"ASSIGN-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        date_assigned = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'In Stock', 'Assigned'
        try:
            cursor.execute("SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = cursor.fetchone()
            if not row or row['status'] != 'In Stock' or row['list_id'] is not None:
                self._logger.warning(
                    "Bar %s not available for assignment (status=%s, list_id=%s)",
                    bar_id,
                    row['status'] if row else None,
                    row['list_id'] if row else None,
                )
                return False

            cursor.execute("SELECT list_id FROM silver_bar_lists WHERE list_id = ?", (list_id,))
            if not cursor.fetchone():
                self._logger.warning("List ID %s not found. Cannot assign bar.", list_id)
                return False

            if perform_commit:
                conn.execute('BEGIN TRANSACTION')
            cursor.execute(
                "UPDATE silver_bars SET status = ?, list_id = ? WHERE bar_id = ?",
                (to_status, list_id, bar_id),
            )
            cursor.execute(
                '''
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (transfer_no, date_assigned, bar_id, list_id, from_status, to_status, note),
            )
            if perform_commit:
                conn.commit()
            return True
        except sqlite3.Error as exc:
            if perform_commit:
                conn.rollback()
            self._logger.error(
                "DB error assigning bar %s to list %s: %s", bar_id, list_id, exc, exc_info=True
            )
            return False

    def remove_bar_from_list(
        self,
        bar_id: int,
        note: str = "Removed from list",
        perform_commit: bool = True,
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        date_removed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'Assigned', 'In Stock'
        transfer_no = f"REMOVE-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            cursor.execute("SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = cursor.fetchone()
            if not row or row['status'] != 'Assigned' or row['list_id'] is None:
                self._logger.warning(
                    "Bar %s not found or not assigned to a list. Cannot remove.", bar_id
                )
                return False
            current_list_id = row['list_id']

            if perform_commit:
                conn.execute('BEGIN TRANSACTION')
            cursor.execute(
                "UPDATE silver_bars SET status = ?, list_id = NULL WHERE bar_id = ?",
                (to_status, bar_id),
            )
            cursor.execute(
                '''
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (transfer_no, date_removed, bar_id, current_list_id, from_status, to_status, note),
            )
            if perform_commit:
                conn.commit()
            return True
        except sqlite3.Error as exc:
            if perform_commit:
                conn.rollback()
            self._logger.error("DB error removing bar %s from list: %s", bar_id, exc, exc_info=True)
            return False

    # --- Queries ------------------------------------------------------------

    def get_bars_in_list(self, list_id: int):
        cursor = self._cursor
        if not cursor:
            return []
        try:
            cursor.execute('SELECT * FROM silver_bars WHERE list_id = ? ORDER BY bar_id', (list_id,))
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB error fetching bars for list %s: %s", list_id, exc, exc_info=True)
            return []

    def get_available_bars(self):
        cursor = self._cursor
        if not cursor:
            return []
        try:
            cursor.execute(
                "SELECT * FROM silver_bars WHERE status = 'In Stock' AND list_id IS NULL "
                "ORDER BY date_added DESC, bar_id DESC"
            )
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB error fetching available bars: %s", exc, exc_info=True)
            return []

    def add_silver_bar(self, estimate_voucher_no: str, weight: float, purity: float) -> Optional[int]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return None
        date_added = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        fine_weight = weight * (purity / 100)
        try:
            cursor.execute(
                '''
                INSERT INTO silver_bars
                (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                ''',
                (estimate_voucher_no, weight, purity, fine_weight, date_added, 'In Stock'),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error adding silver bar for estimate %s: %s",
                estimate_voucher_no,
                exc,
                exc_info=True,
            )
            conn.rollback()
            return None

    def update_silver_bar_values(self, bar_id: int, weight: float, purity: float) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            fine_weight = float(weight) * (float(purity) / 100.0)
        except Exception:
            fine_weight = 0.0
        try:
            cursor.execute(
                "UPDATE silver_bars SET weight = ?, purity = ?, fine_weight = ? WHERE bar_id = ?",
                (weight, purity, fine_weight, bar_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as exc:
            self._logger.error("DB Error updating silver bar %s: %s", bar_id, exc, exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return False

    def get_silver_bars(
        self,
        *,
        status: Optional[str] = None,
        weight_query: Optional[float] = None,
        estimate_voucher_no: Optional[str] = None,
        weight_tolerance: float = 0.001,
        min_purity: Optional[float] = None,
        max_purity: Optional[float] = None,
        date_range: Optional[Tuple[Optional[str], Optional[str]]] = None,
    ):
        cursor = self._cursor
        if not cursor:
            return []
        query = "SELECT * FROM silver_bars WHERE 1=1"
        params: List[Any] = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if weight_query is not None:
            try:
                target = float(weight_query)
                tol = float(weight_tolerance) if weight_tolerance is not None else 0.001
                query += " AND weight BETWEEN ? AND ?"
                params.extend([target - tol, target + tol])
            except ValueError:
                self._logger.warning("Invalid weight query '%s'. Ignoring weight filter.", weight_query)
        if estimate_voucher_no:
            query += " AND estimate_voucher_no LIKE ?"
            params.append(f"%{estimate_voucher_no}%")
        if min_purity is not None:
            try:
                query += " AND purity >= ?"
                params.append(float(min_purity))
            except (TypeError, ValueError):
                pass
        if max_purity is not None:
            try:
                query += " AND purity <= ?"
                params.append(float(max_purity))
            except (TypeError, ValueError):
                pass
        if date_range and isinstance(date_range, (tuple, list)) and len(date_range) == 2:
            start_iso, end_iso = date_range
            if start_iso:
                query += " AND date_added >= ?"
                params.append(start_iso)
            if end_iso:
                query += " AND date_added <= ?"
                params.append(end_iso)
        query += " ORDER BY date_added DESC, bar_id DESC"
        try:
            cursor.execute(query, params)
            return cursor.fetchall()
        except sqlite3.Error as exc:
            self._logger.error("DB error getting silver bars: %s", exc, exc_info=True)
            return []

    def delete_bars_for_estimate(self, voucher_no: str) -> Tuple[int, set]:
        cursor = self._cursor
        if not cursor:
            return 0, set()
        cursor.execute("SELECT bar_id, list_id FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
        bars = cursor.fetchall()
        affected_lists = {row['list_id'] for row in bars if row['list_id'] is not None}
        cursor.execute("DELETE FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
        deleted_count = cursor.rowcount
        return deleted_count, affected_lists

    def cleanup_empty_lists(self, list_ids: Iterable[int]) -> None:
        cursor = self._cursor
        if not cursor:
            return
        for list_id in list_ids:
            try:
                cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE list_id = ?", (list_id,))
                remaining = cursor.fetchone()[0]
                if remaining == 0:
                    cursor.execute('DELETE FROM silver_bar_lists WHERE list_id = ?', (list_id,))
                    if cursor.rowcount > 0:
                        self._logger.info("Deleted empty list ID %s after removing its bars.", list_id)
            except sqlite3.Error as exc:
                self._logger.error("DB error cleaning list %s: %s", list_id, exc, exc_info=True)

    def delete_silver_bars_for_estimate(self, voucher_no: str) -> bool:
        if not voucher_no:
            self._logger.warning("delete_silver_bars_for_estimate called with empty voucher_no")
            return True
        cursor = self._cursor
        if not cursor:
            return True
        self._logger.info(
            "delete_silver_bars_for_estimate called for %s but silver bars are now permanent.",
            voucher_no,
        )
        self._logger.info(
            "Silver bars are preserved and should be managed through the Silver Bar Management interface."
        )
        try:
            cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
            total_bars = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ? AND list_id IS NOT NULL",
                (voucher_no,),
            )
            bars_in_lists = cursor.fetchone()[0]
            self._logger.info(
                "Estimate %s has %s silver bars total, %s in lists.",
                voucher_no,
                total_bars,
                bars_in_lists,
            )
            return True
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error checking silver bars for estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return True

    # ------------------------------------------------------------------

    def _request_flush(self) -> None:
        try:
            requester = getattr(self._db, "request_flush", None)
            if callable(requester):
                requester()
        except Exception as exc:  # pragma: no cover - log only
            self._logger.error("Exception during silver-bar flush: %s", exc, exc_info=True)
