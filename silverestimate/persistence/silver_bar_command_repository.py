"""Transactional silver-bar command persistence component."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, List, Optional, Tuple

from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.repository_results import (
    RepositoryFailureKind,
    RepositoryResult,
)
from silverestimate.persistence.silver_bar_repository_base import (
    _SilverBarRepositoryBase,
)


class SilverBarCommandRepository(_SilverBarRepositoryBase):
    """Own list lifecycle and inventory mutation commands."""

    def generate_list_identifier(self) -> str:
        cursor = self._cursor
        if not cursor:
            return f"ERR-L-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        today_str = datetime.now().strftime("%Y%m%d")
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
                    seq = int(result["list_identifier"].split("-")[-1]) + 1
                except IndexError, ValueError:
                    self._logger.warning("Format issue when parsing list identifier")
        except sqlite3.Error as exc:
            self._logger.error(
                "Error generating list ID sequence: %s", exc, exc_info=True
            )
        return f"L-{today_str}-{seq:03d}"

    def create_list(self, note: Optional[str] = None) -> Optional[int]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return None
        creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        list_identifier = self.generate_list_identifier()
        try:
            cursor.execute(
                "INSERT INTO silver_bar_lists (list_identifier, creation_date, list_note) VALUES (?, ?, ?)",
                (list_identifier, creation_date, note),
            )
            conn.commit()
            list_id = cursor.lastrowid
            self._logger.info(
                "Created silver bar list %s (ID: %s).", list_identifier, list_id
            )
            return int(list_id) if list_id is not None else None
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error creating silver bar list: %s", exc, exc_info=True
            )
            conn.rollback()
            return None

    def update_list_note(self, list_id: int, new_note: str) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            cursor.execute(
                "UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?",
                (new_note, list_id),
            )
            conn.commit()
            return bool(int(cursor.rowcount) > 0)
        except sqlite3.Error as exc:
            self._logger.error(
                "DB error updating list note for ID %s: %s", list_id, exc, exc_info=True
            )
            conn.rollback()
            return False

    def mark_list_as_issued(
        self, list_id: int, issued_date: Optional[str] = None
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        issued_at = issued_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "UPDATE silver_bar_lists SET issued_date = ? WHERE list_id = ?",
                (issued_at, list_id),
            )
            if cursor.rowcount <= 0:
                conn.rollback()
                return False
            cursor.execute(
                "UPDATE silver_bars SET status = 'Issued' WHERE list_id = ?",
                (list_id,),
            )
            conn.commit()
            return True
        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except Exception as rollback_error:
                self._logger.debug(
                    "Failed to roll back issue-list transaction for list %s: %s",
                    list_id,
                    rollback_error,
                )
            self._logger.error(
                "DB error marking list %s as issued: %s",
                list_id,
                exc,
                exc_info=True,
            )
            return False

    def reactivate_list(self, list_id: int) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "UPDATE silver_bar_lists SET issued_date = NULL WHERE list_id = ?",
                (list_id,),
            )
            if cursor.rowcount <= 0:
                conn.rollback()
                return False
            cursor.execute(
                "UPDATE silver_bars SET status = 'Assigned' WHERE list_id = ?",
                (list_id,),
            )
            conn.commit()
            return True
        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except Exception as rollback_error:
                self._logger.debug(
                    "Failed to roll back reactivate-list transaction for list %s: %s",
                    list_id,
                    rollback_error,
                )
            self._logger.error(
                "DB error reactivating list %s: %s",
                list_id,
                exc,
                exc_info=True,
            )
            return False

    def delete_list(self, list_id: int) -> Tuple[bool, str]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False, "No database connection"
        try:
            conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "SELECT bar_id FROM silver_bars WHERE list_id = ?", (list_id,)
            )
            bars_to_unassign = [row["bar_id"] for row in cursor.fetchall()]

            unassign_note = f"Unassigned due to list {list_id} deletion"
            unassigned_count = 0
            for bar_id in bars_to_unassign:
                if self.remove_bar_from_list(
                    bar_id, note=unassign_note, perform_commit=False
                ):
                    unassigned_count += 1
                else:
                    self._logger.warning(
                        "Failed to properly unassign bar %s during list deletion.",
                        bar_id,
                    )
                    cursor.execute(
                        "UPDATE silver_bars SET list_id = NULL, status = 'In Stock' WHERE bar_id = ?",
                        (bar_id,),
                    )

            cursor.execute("DELETE FROM silver_bar_lists WHERE list_id = ?", (list_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            self._logger.info(
                "Deleted list %s. Unassigned %s bars.", list_id, unassigned_count
            )
            return deleted, "Deleted" if deleted else "List not found"
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error(
                "DB error deleting list %s: %s", list_id, exc, exc_info=True
            )
            return False, str(exc)

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
        date_assigned = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        from_status, to_status = "In Stock", "Assigned"
        try:
            cursor.execute(
                "SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,)
            )
            row = cursor.fetchone()
            if not row or row["status"] != "In Stock" or row["list_id"] is not None:
                self._logger.warning(
                    "Bar %s not available for assignment (status=%s, list_id=%s)",
                    bar_id,
                    row["status"] if row else None,
                    row["list_id"] if row else None,
                )
                return False

            cursor.execute(
                "SELECT list_id FROM silver_bar_lists WHERE list_id = ?", (list_id,)
            )
            if not cursor.fetchone():
                self._logger.warning(
                    "List ID %s not found. Cannot assign bar.", list_id
                )
                return False

            if perform_commit:
                conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "UPDATE silver_bars SET status = ?, list_id = ? WHERE bar_id = ?",
                (to_status, list_id, bar_id),
            )
            cursor.execute(
                """
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer_no,
                    date_assigned,
                    bar_id,
                    list_id,
                    from_status,
                    to_status,
                    note,
                ),
            )
            if perform_commit:
                conn.commit()
            return True
        except sqlite3.Error as exc:
            if perform_commit:
                conn.rollback()
            self._logger.error(
                "DB error assigning bar %s to list %s: %s",
                bar_id,
                list_id,
                exc,
                exc_info=True,
            )
            return False

    def assign_bars_to_list_bulk(
        self,
        bar_ids: Iterable[int],
        list_id: int,
        note: str = "Assigned to list",
    ) -> Tuple[int, List[int]]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return 0, []

        normalized = self._normalize_bar_ids(bar_ids)
        if not normalized:
            return 0, []

        failed: List[int] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute(
                "SELECT list_id FROM silver_bar_lists WHERE list_id = ?",
                (list_id,),
            )
            if not cursor.fetchone():
                return 0, normalized

            placeholders = ",".join("?" for _ in normalized)
            # Placeholder count is generated locally; values remain parameterized.
            cursor.execute(
                f"SELECT bar_id, status, list_id FROM silver_bars "  # nosec B608
                f"WHERE bar_id IN ({placeholders})",
                normalized,
            )
            rows = {int(row["bar_id"]): row for row in cursor.fetchall()}

            valid_ids: List[int] = []
            for bar_id in normalized:
                row = rows.get(bar_id)
                if not row or row["status"] != "In Stock" or row["list_id"] is not None:
                    failed.append(bar_id)
                    continue
                valid_ids.append(bar_id)

            if not valid_ids:
                return 0, failed

            conn.execute("BEGIN TRANSACTION")
            update_payload = [("Assigned", list_id, bar_id) for bar_id in valid_ids]
            cursor.executemany(
                "UPDATE silver_bars SET status = ?, list_id = ? WHERE bar_id = ?",
                update_payload,
            )

            transfer_rows = [
                (
                    f"ASSIGN-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    now,
                    bar_id,
                    list_id,
                    "In Stock",
                    "Assigned",
                    note,
                )
                for bar_id in valid_ids
            ]
            cursor.executemany(
                """
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                transfer_rows,
            )
            conn.commit()
            return len(valid_ids), failed
        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except Exception as rollback_error:
                self._logger.debug(
                    "Failed to roll back bulk assign transaction for list %s: %s",
                    list_id,
                    rollback_error,
                )
            self._logger.error(
                "DB error assigning bars to list %s in bulk: %s",
                list_id,
                exc,
                exc_info=True,
            )
            return 0, normalized

    def remove_bar_from_list(
        self,
        bar_id: int,
        note: str = "Removed from list",
        perform_commit: bool = True,
    ) -> bool:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return False
        date_removed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        from_status, to_status = "Assigned", "In Stock"
        transfer_no = f"REMOVE-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            cursor.execute(
                "SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,)
            )
            row = cursor.fetchone()
            if not row or row["status"] != "Assigned" or row["list_id"] is None:
                self._logger.warning(
                    "Bar %s not found or not assigned to a list. Cannot remove.", bar_id
                )
                return False
            current_list_id = row["list_id"]

            if perform_commit:
                conn.execute("BEGIN TRANSACTION")
            cursor.execute(
                "UPDATE silver_bars SET status = ?, list_id = NULL WHERE bar_id = ?",
                (to_status, bar_id),
            )
            cursor.execute(
                """
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transfer_no,
                    date_removed,
                    bar_id,
                    current_list_id,
                    from_status,
                    to_status,
                    note,
                ),
            )
            if perform_commit:
                conn.commit()
            return True
        except sqlite3.Error as exc:
            if perform_commit:
                conn.rollback()
            self._logger.error(
                "DB error removing bar %s from list: %s", bar_id, exc, exc_info=True
            )
            return False

    def remove_bars_from_list_bulk(
        self,
        bar_ids: Iterable[int],
        note: str = "Removed from list",
    ) -> Tuple[int, List[int]]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return 0, []

        normalized = self._normalize_bar_ids(bar_ids)
        if not normalized:
            return 0, []

        failed: List[int] = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            placeholders = ",".join("?" for _ in normalized)
            # Placeholder count is generated locally; values remain parameterized.
            cursor.execute(
                f"SELECT bar_id, status, list_id FROM silver_bars "  # nosec B608
                f"WHERE bar_id IN ({placeholders})",
                normalized,
            )
            rows = {int(row["bar_id"]): row for row in cursor.fetchall()}

            valid_rows: List[Tuple[int, int]] = []
            for bar_id in normalized:
                row = rows.get(bar_id)
                if not row or row["status"] != "Assigned" or row["list_id"] is None:
                    failed.append(bar_id)
                    continue
                valid_rows.append((bar_id, int(row["list_id"])))

            if not valid_rows:
                return 0, failed

            conn.execute("BEGIN TRANSACTION")
            cursor.executemany(
                "UPDATE silver_bars SET status = ?, list_id = NULL WHERE bar_id = ?",
                [("In Stock", bar_id) for bar_id, _ in valid_rows],
            )
            transfer_rows = [
                (
                    f"REMOVE-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                    now,
                    bar_id,
                    list_id,
                    "Assigned",
                    "In Stock",
                    note,
                )
                for bar_id, list_id in valid_rows
            ]
            cursor.executemany(
                """
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                transfer_rows,
            )
            conn.commit()
            return len(valid_rows), failed
        except sqlite3.Error as exc:
            try:
                conn.rollback()
            except Exception as rollback_error:
                self._logger.debug(
                    "Failed to roll back bulk remove transaction: %s",
                    rollback_error,
                )
            self._logger.error(
                "DB error removing bars from list in bulk: %s",
                exc,
                exc_info=True,
            )
            return 0, normalized

    def add_silver_bar(
        self, estimate_voucher_no: str, weight: float, purity: float
    ) -> Optional[int]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor:
            return None
        date_added = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fine_weight = weight * (purity / 100)
        try:
            cursor.execute(
                """
                INSERT INTO silver_bars
                (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    estimate_voucher_no,
                    weight,
                    purity,
                    fine_weight,
                    date_added,
                    "In Stock",
                ),
            )
            conn.commit()
            bar_id = cursor.lastrowid
            return int(bar_id) if bar_id is not None else None
        except sqlite3.Error as exc:
            self._logger.error(
                "DB Error adding silver bar for estimate %s: %s",
                estimate_voucher_no,
                exc,
                exc_info=True,
            )
            conn.rollback()
            return None

    def delete_bars_for_estimate(self, voucher_no: str) -> Tuple[int, set[Any]]:
        cursor = self._cursor
        if not cursor:
            return 0, set()
        cursor.execute(
            "SELECT bar_id, list_id FROM silver_bars WHERE estimate_voucher_no = ?",
            (voucher_no,),
        )
        bars = cursor.fetchall()
        affected_lists = {row["list_id"] for row in bars if row["list_id"] is not None}
        cursor.execute(
            "DELETE FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,)
        )
        deleted_count = cursor.rowcount
        return deleted_count, affected_lists

    def cleanup_empty_lists(self, list_ids: Iterable[int]) -> None:
        cursor = self._cursor
        if not cursor:
            return
        for list_id in list_ids:
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM silver_bars WHERE list_id = ?", (list_id,)
                )
                remaining = cursor.fetchone()[0]
                if remaining == 0:
                    cursor.execute(
                        "DELETE FROM silver_bar_lists WHERE list_id = ?", (list_id,)
                    )
                    if cursor.rowcount > 0:
                        self._logger.info(
                            "Deleted empty list ID %s after removing its bars.", list_id
                        )
            except sqlite3.Error as exc:
                self._logger.error(
                    "DB error cleaning list %s: %s", list_id, exc, exc_info=True
                )

    def delete_list_result(self, list_id: int) -> RepositoryResult[str]:
        success, message = self.delete_list(list_id)
        detail = str(message or "Silver-bar list deletion failed.")
        if success:
            return RepositoryResult.success(detail)
        normalized = detail.casefold()
        kind = (
            RepositoryFailureKind.NOT_FOUND
            if "not found" in normalized
            else RepositoryFailureKind.CONFLICT
            if "cannot" in normalized or "assigned" in normalized
            else RepositoryFailureKind.STORAGE
        )
        return RepositoryResult.failed(kind, detail)


__all__ = ["SilverBarCommandRepository"]
