"""Estimate-to-inventory silver-bar synchronization component."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Tuple

from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.silver_bar_repository_base import (
    _SilverBarRepositoryBase,
)


@dataclass(frozen=True)
class SilverBarSyncResult:
    added: int
    failed: int

    @property
    def succeeded(self) -> bool:
        return self.failed == 0


class SilverBarSynchronizationRepository(_SilverBarRepositoryBase):
    """Own reconciliation of estimate rows with mutable inventory rows."""

    @staticmethod
    def _normalize_sync_bar_payload(
        bar: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        try:
            weight = float(bar.get("weight", bar.get("net_wt", 0.0)) or 0.0)
            purity = float(bar.get("purity", 0.0) or 0.0)
        except Exception:
            return None
        line_key = str(bar.get("line_key", "") or "").strip()
        return {
            "weight": weight,
            "purity": purity,
            "line_key": line_key or None,
        }

    @staticmethod
    def _row_value(row: Mapping[str, Any], key: str, default: Any = None) -> Any:
        try:
            return row[key]
        except Exception:
            getter = getattr(row, "get", None)
            if callable(getter):
                return getter(key, default)
            return default

    @classmethod
    def _synced_bar_values_match(
        cls,
        row: Mapping[str, Any],
        weight: float,
        purity: float,
    ) -> bool:
        old_weight = float(cls._row_value(row, "weight", 0.0) or 0.0)
        old_purity = float(cls._row_value(row, "purity", 0.0) or 0.0)
        return abs(weight - old_weight) <= 1e-6 and abs(purity - old_purity) <= 1e-6

    @classmethod
    def _bar_row_is_mutable(cls, row: Mapping[str, Any]) -> bool:
        return (
            cls._row_value(row, "status") == "In Stock"
            and cls._row_value(row, "list_id") is None
        )

    def _sync_silver_bars_for_estimate_by_order(
        self,
        cursor: sqlite3.Cursor,
        voucher_no: str,
        desired: list[Mapping[str, Any]],
    ) -> tuple[int, int]:
        cursor.execute(
            "SELECT bar_id, weight, purity FROM silver_bars "
            "WHERE estimate_voucher_no = ? ORDER BY bar_id",
            (voucher_no,),
        )
        existing_rows = cursor.fetchall()

        added = 0
        failed = 0
        overlap = min(len(existing_rows), len(desired))
        for idx in range(overlap):
            existing = existing_rows[idx]
            new_weight = float(desired[idx]["weight"])
            new_purity = float(desired[idx]["purity"])
            if self._synced_bar_values_match(existing, new_weight, new_purity):
                continue
            fine_weight = new_weight * (new_purity / 100.0)
            cursor.execute(
                "UPDATE silver_bars SET weight = ?, purity = ?, fine_weight = ? "
                "WHERE bar_id = ?",
                (new_weight, new_purity, fine_weight, existing["bar_id"]),
            )
            if cursor.rowcount <= 0:
                failed += 1

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for desired_entry in desired[overlap:]:
            new_weight = float(desired_entry["weight"])
            new_purity = float(desired_entry["purity"])
            fine_weight = new_weight * (new_purity / 100.0)
            cursor.execute(
                "INSERT INTO silver_bars "
                "(estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id, source_line_key) "
                "VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)",
                (
                    voucher_no,
                    new_weight,
                    new_purity,
                    fine_weight,
                    now,
                    "In Stock",
                ),
            )
            added += 1

        return added, failed

    def _synchronize_counts(
        self,
        voucher_no: str,
        bars: Iterable[Mapping[str, Any]],
    ) -> Tuple[int, int]:
        conn, cursor = self._conn, self._cursor
        if not conn or not cursor or not voucher_no:
            return 0, 0

        desired: list[Mapping[str, Any]] = []
        parse_failures = 0
        seen_line_keys: set[str] = set()
        for bar in list(bars or []):
            normalized = self._normalize_sync_bar_payload(bar)
            if normalized is None:
                parse_failures += 1
                continue
            line_key = normalized.get("line_key")
            if isinstance(line_key, str) and line_key:
                if line_key in seen_line_keys:
                    parse_failures += 1
                    continue
                seen_line_keys.add(line_key)
            desired.append(normalized)

        added = 0
        failed = parse_failures

        try:
            conn.execute("BEGIN TRANSACTION")
            use_line_keys = any(
                isinstance(entry.get("line_key"), str) and entry.get("line_key")
                for entry in desired
            )
            if not use_line_keys:
                added, sync_failed = self._sync_silver_bars_for_estimate_by_order(
                    cursor,
                    voucher_no,
                    desired,
                )
                failed += sync_failed
            else:
                cursor.execute(
                    "SELECT bar_id, weight, purity, status, list_id, source_line_key "
                    "FROM silver_bars WHERE estimate_voucher_no = ? ORDER BY bar_id",
                    (voucher_no,),
                )
                existing_rows = cursor.fetchall()
                existing_by_key: dict[str, Any] = {}
                unkeyed_rows: list[Any] = []
                for row in existing_rows:
                    source_line_key = str(row["source_line_key"] or "").strip()
                    if source_line_key:
                        existing_by_key[source_line_key] = row
                    else:
                        unkeyed_rows.append(row)

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for desired_entry in desired:
                    new_weight = float(desired_entry["weight"])
                    new_purity = float(desired_entry["purity"])
                    line_key = str(desired_entry.get("line_key") or "").strip() or None

                    existing = existing_by_key.get(line_key) if line_key else None
                    matched_unkeyed = False
                    if existing is None and unkeyed_rows:
                        existing = unkeyed_rows.pop(0)
                        matched_unkeyed = True

                    if existing is not None:
                        if matched_unkeyed and line_key:
                            cursor.execute(
                                "UPDATE silver_bars SET source_line_key = ? WHERE bar_id = ?",
                                (line_key, existing["bar_id"]),
                            )
                            if cursor.rowcount <= 0:
                                failed += 1

                        if self._synced_bar_values_match(
                            existing, new_weight, new_purity
                        ):
                            continue

                        if not self._bar_row_is_mutable(existing):
                            failed += 1
                            continue

                        fine_weight = new_weight * (new_purity / 100.0)
                        if line_key:
                            cursor.execute(
                                "UPDATE silver_bars SET weight = ?, purity = ?, fine_weight = ?, source_line_key = ? "
                                "WHERE bar_id = ?",
                                (
                                    new_weight,
                                    new_purity,
                                    fine_weight,
                                    line_key,
                                    existing["bar_id"],
                                ),
                            )
                        else:
                            cursor.execute(
                                "UPDATE silver_bars SET weight = ?, purity = ?, fine_weight = ? "
                                "WHERE bar_id = ?",
                                (
                                    new_weight,
                                    new_purity,
                                    fine_weight,
                                    existing["bar_id"],
                                ),
                            )
                        if cursor.rowcount <= 0:
                            failed += 1
                        continue

                    fine_weight = new_weight * (new_purity / 100.0)
                    cursor.execute(
                        "INSERT INTO silver_bars "
                        "(estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id, source_line_key) "
                        "VALUES (?, ?, ?, ?, ?, ?, NULL, ?)",
                        (
                            voucher_no,
                            new_weight,
                            new_purity,
                            fine_weight,
                            now,
                            "In Stock",
                            line_key,
                        ),
                    )
                    added += 1

            conn.commit()
            return added, failed
        except sqlite3.Error as exc:
            conn.rollback()
            self._logger.error(
                "DB error syncing silver bars for estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return 0, failed + len(desired)
        except Exception as exc:
            try:
                conn.rollback()
            except Exception as rollback_error:
                self._logger.debug(
                    "Failed to roll back silver-bar sync transaction for estimate %s: %s",
                    voucher_no,
                    rollback_error,
                )
            self._logger.error(
                "Unexpected error syncing silver bars for estimate %s: %s",
                voucher_no,
                exc,
                exc_info=True,
            )
            return 0, failed + len(desired)

    def synchronize(
        self,
        voucher_no: str,
        bars: Iterable[Mapping[str, Any]],
    ) -> SilverBarSyncResult:
        added, failed = self._synchronize_counts(voucher_no, bars)
        return SilverBarSyncResult(added=int(added), failed=int(failed))


__all__ = ["SilverBarSynchronizationRepository", "SilverBarSyncResult"]
