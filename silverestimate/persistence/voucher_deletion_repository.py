"""Snapshot preview and atomic, inventory-aware range deletion."""

from __future__ import annotations

import hashlib
import json

from silverestimate.domain.voucher_deletion import (
    VoucherDeletionPreview,
    VoucherDeletionRange,
    VoucherDeletionResult,
    VoucherDeletionRow,
    numeric_voucher_key,
)
from silverestimate.persistence.database_driver import Cursor
from silverestimate.persistence.database_protocols import RepositoryDatabase

# Shared with single-voucher deletion. The query must alias silver_bars as bars.
PROTECTED_BAR_SQL = """(
    COALESCE(bars.status, '') != 'In Stock'
    OR bars.list_id IS NOT NULL
    OR EXISTS (SELECT 1 FROM bar_transfers AS transfers
               WHERE transfers.silver_bar_id = bars.bar_id)
)"""
PROTECTED_REASON = "Silver bars are assigned, issued, or have transfer history."
BATCH_SIZE = 400


def fetch_voucher_deletion_preview(
    cursor: Cursor, criteria: VoucherDeletionRange
) -> VoucherDeletionPreview:
    params: tuple[str, ...] = ()
    where = "1=1"
    if criteria.mode == "date":
        where = "date >= ? AND date <= ?"
        params = (criteria.start, criteria.end)
    cursor.execute(f"SELECT * FROM estimates WHERE {where} ORDER BY voucher_no", params)  # noqa: S608
    headers = [dict(row) for row in cursor.fetchall()]
    if criteria.mode == "voucher":
        low, high = (
            numeric_voucher_key(criteria.start),
            numeric_voucher_key(criteria.end),
        )
        headers = [
            row for row in headers if _in_numeric_range(row["voucher_no"], low, high)
        ]
        headers.sort(
            key=lambda row: (numeric_voucher_key(row["voucher_no"]), row["voucher_no"])
        )
    digest = hashlib.sha256()
    digest.update(json.dumps(headers, sort_keys=True).encode())
    rows = []
    for offset in range(0, len(headers), BATCH_SIZE):
        batch = headers[offset : offset + BATCH_SIZE]
        vouchers = tuple(row["voucher_no"] for row in batch)
        placeholders = ",".join("?" for _ in vouchers)
        cursor.execute(
            f"""SELECT bars.estimate_voucher_no, COUNT(*) AS bar_count,
                       MAX(CASE WHEN {PROTECTED_BAR_SQL} THEN 1 ELSE 0 END) AS protected
                FROM silver_bars AS bars
                WHERE bars.estimate_voucher_no IN ({placeholders})
                GROUP BY bars.estimate_voucher_no""",  # noqa: S608
            vouchers,
        )
        inventory = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        for header in batch:
            count, protected = inventory.get(header["voucher_no"], (0, 0))
            rows.append(
                VoucherDeletionRow(
                    header["voucher_no"],
                    header["date"],
                    count,
                    PROTECTED_REASON if protected else "",
                )
            )
        # Include line and inventory content, so edits with unchanged totals still
        # invalidate the reviewed snapshot. Only fixed table names enter SQL.
        queries = (
            f"SELECT * FROM estimate_items WHERE voucher_no IN ({placeholders}) ORDER BY id",  # noqa: S608
            f"SELECT * FROM silver_bars WHERE estimate_voucher_no IN ({placeholders}) ORDER BY bar_id",  # noqa: S608
            f"SELECT * FROM bar_transfers WHERE silver_bar_id IN (SELECT bar_id FROM silver_bars WHERE estimate_voucher_no IN ({placeholders})) ORDER BY id",  # noqa: S608
        )
        for query in queries:
            cursor.execute(query, vouchers)
            for record in cursor:
                digest.update(json.dumps(tuple(record)).encode())
                digest.update(b"\n")
    return VoucherDeletionPreview(criteria, tuple(rows), digest.hexdigest())


def _in_numeric_range(value: str, low: tuple[int, str], high: tuple[int, str]) -> bool:
    try:
        return low <= numeric_voucher_key(value) <= high
    except ValueError:
        return False


class VoucherDeletionRepository:
    def __init__(self, database: RepositoryDatabase) -> None:
        self._db = database

    def preview(self, criteria: VoucherDeletionRange) -> VoucherDeletionPreview:
        conn = self._db.conn
        if conn is None:
            raise RuntimeError("Database is unavailable.")
        if conn.in_transaction:
            raise RuntimeError("Finish the current database transaction first.")
        conn.execute("BEGIN")
        try:
            return fetch_voucher_deletion_preview(conn.cursor(), criteria)
        finally:
            conn.rollback()

    def delete(self, preview: VoucherDeletionPreview) -> VoucherDeletionResult:
        conn = self._db.conn
        if conn is None:
            raise RuntimeError("Database is unavailable.")
        if conn.in_transaction:
            raise RuntimeError("Finish the current database transaction first.")
        conn.execute("BEGIN IMMEDIATE")
        try:
            cursor = conn.cursor()
            current = fetch_voucher_deletion_preview(cursor, preview.criteria)
            if current != preview:
                return VoucherDeletionResult(
                    False,
                    stale=True,
                    message="Matching vouchers or inventory changed. Preview the range again.",
                )
            vouchers = tuple(row.voucher_no for row in current.eligible)
            draft_token = self._delete_matching_draft(cursor, set(vouchers))
            for offset in range(0, len(vouchers), BATCH_SIZE):
                batch = vouchers[offset : offset + BATCH_SIZE]
                placeholders = ",".join("?" for _ in batch)
                for table, column in (
                    ("silver_bars", "estimate_voucher_no"),
                    ("estimate_items", "voucher_no"),
                    ("estimates", "voucher_no"),
                ):
                    cursor.execute(
                        f"DELETE FROM {table} WHERE {column} IN ({placeholders})",  # noqa: S608
                        batch,
                    )
            conn.commit()
            self._db.logger.info(
                "Range deletion committed: %s deleted, %s skipped",
                len(vouchers),
                len(current.skipped),
            )
            return VoucherDeletionResult(True, vouchers, current.skipped, draft_token)
        finally:
            if conn.in_transaction:
                conn.rollback()

    @staticmethod
    def _delete_matching_draft(cursor: Cursor, vouchers: set[str]) -> str | None:
        cursor.execute(
            "SELECT token, voucher_no, payload FROM estimate_draft WHERE slot=1"
        )
        record = cursor.fetchone()
        if record is None:
            return None
        identity = record[1]
        try:
            payload = json.loads(record[2])
            if isinstance(payload, dict):
                active = payload.get("active_voucher_no")
                if isinstance(active, str) and active.strip():
                    identity = active.strip()
        except ValueError, TypeError:
            pass
        if identity not in vouchers:
            return None
        cursor.execute("DELETE FROM estimate_draft WHERE token=?", (record[0],))
        return str(record[0])
