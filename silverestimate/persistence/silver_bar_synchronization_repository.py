"""Plan and apply estimate inventory changes inside the caller's transaction."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from silverestimate.domain.estimate_validation import finite_number
from silverestimate.domain.numeric_policy import fine_weight
from silverestimate.persistence.database_driver import Cursor
from silverestimate.persistence.silver_bar_repository_base import (
    _SilverBarRepositoryBase,
)


@dataclass(frozen=True)
class SilverBarSyncResult:
    added: int
    failed: int
    updated: int = 0
    removed: int = 0
    error_detail: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.failed == 0


@dataclass(frozen=True)
class BarReconciliationPlan:
    inserts: list[dict[str, Any]]
    updates: list[tuple[int, dict[str, Any]]]
    removals: list[int]
    links: list[tuple[int, str]]


class SilverBarSynchronizationRepository(_SilverBarRepositoryBase):
    """Preserve bar identity and reject edits to inventory with a lifecycle history."""

    @staticmethod
    def _values(bar: Mapping[str, Any]) -> tuple[float, float]:
        return float(bar["weight"]), float(bar["purity"])

    @staticmethod
    def _mutable(bar: Mapping[str, Any]) -> bool:
        return (
            bar["status"] == "In Stock"
            and bar["list_id"] is None
            and not bar["has_transfers"]
        )

    @staticmethod
    def _normalize(item: Mapping[str, Any]) -> dict[str, Any]:
        weight = finite_number(item.get("weight", item.get("net_wt", 0)), "Bar weight")
        purity = finite_number(item.get("purity", 0), "Bar purity")
        if weight < 0:
            raise ValueError("Bar weight cannot be negative.")
        if not 0 <= purity <= 100:
            raise ValueError("Bar purity must be between 0 and 100.")
        return {
            "weight": weight,
            "purity": purity,
            "fine_weight": finite_number(
                item.get("fine", fine_weight(weight, purity)), "Bar fine weight"
            ),
            "line_key": str(item.get("line_key") or "").strip(),
        }

    def prepare(
        self, cursor: Cursor, voucher_no: str, items: list[dict[str, Any]]
    ) -> BarReconciliationPlan:
        """Validate all changes and put resolved keys into the saved line copies.

        The caller must hold the writer transaction until apply/commit. Legacy bars
        can acquire a key only through an unambiguous, unchanged weight/purity match.
        No row-order guesses are made, including for bars that are back in stock.
        """
        desired = [self._normalize(item) for item in items]
        cursor.execute(
            """SELECT bars.*, EXISTS (
                   SELECT 1 FROM bar_transfers AS transfers
                   WHERE transfers.silver_bar_id = bars.bar_id
               ) AS has_transfers
               FROM silver_bars AS bars
               WHERE bars.estimate_voucher_no = ? ORDER BY bars.bar_id""",
            (voucher_no,),
        )
        existing = [dict(row) for row in cursor.fetchall()]
        by_key: dict[str, dict[str, Any]] = {}
        for bar in existing:
            key = str(bar["source_line_key"] or "").strip()
            if key and key in by_key:
                raise ValueError(
                    "Inventory has duplicate line keys; review its bar links before saving."
                )
            if key:
                by_key[key] = bar

        desired_keys = [bar["line_key"] for bar in desired if bar["line_key"]]
        if len(set(desired_keys)) != len(desired_keys):
            raise ValueError("Estimate contains duplicate silver-bar line keys.")
        # Reserve explicit identities first so a blank/legacy line cannot take one.
        claimed = {by_key[key]["bar_id"] for key in desired_keys if key in by_key}
        matches = {
            i: by_key[bar["line_key"]]
            for i, bar in enumerate(desired)
            if bar["line_key"] in by_key
        }
        for i, bar in enumerate(desired):
            if i in matches:
                continue
            candidates = [
                old
                for old in existing
                if old["bar_id"] not in claimed
                and (
                    not bar["line_key"] or not str(old["source_line_key"] or "").strip()
                )
                and self._values(old) == self._values(bar)
            ]
            if candidates:
                competing = [
                    entry
                    for j, entry in enumerate(desired)
                    if j not in matches
                    and self._values(entry) == self._values(bar)
                    and (
                        not entry["line_key"]
                        or not str(candidates[0]["source_line_key"] or "").strip()
                    )
                ]
                if len(candidates) != 1 or len(competing) != 1:
                    raise ValueError(
                        "Legacy silver-bar links are ambiguous; review them before saving."
                    )
                old = candidates[0]
                matches[i] = old
                claimed.add(old["bar_id"])
                if not bar["line_key"]:
                    bar["line_key"] = str(old["source_line_key"] or "").strip()
            if not bar["line_key"]:
                bar["line_key"] = uuid4().hex

        inserts = []
        updates = []
        removals = []
        links = []
        for i, bar in enumerate(desired):
            matched = matches.get(i)
            if matched is None:
                inserts.append(bar)
            elif self._values(matched) != self._values(bar):
                if not self._mutable(matched):
                    raise ValueError(
                        f"Silver bar {matched['bar_id']} is assigned, issued, or has transfer history. "
                        "Its weight and purity cannot be changed from the estimate."
                    )
                updates.append((matched["bar_id"], bar))
            elif matched["source_line_key"] != bar["line_key"]:
                links.append((matched["bar_id"], bar["line_key"]))
            items[i]["line_key"] = bar["line_key"]
        for old in existing:
            if old["bar_id"] in claimed:
                continue
            if not str(old["source_line_key"] or "").strip():
                raise ValueError(
                    f"Legacy silver bar {old['bar_id']} could not be linked safely. "
                    "Save its original weight and purity first, or review the inventory link."
                )
            if not self._mutable(old):
                raise ValueError(
                    f"Silver bar {old['bar_id']} is assigned, issued, or has transfer history. "
                    "Its estimate line cannot be removed or replaced."
                )
            removals.append(old["bar_id"])
        return BarReconciliationPlan(inserts, updates, removals, links)

    @staticmethod
    def apply(
        cursor: Cursor, voucher_no: str, plan: BarReconciliationPlan
    ) -> SilverBarSyncResult:
        """Apply a validated plan without starting or committing a transaction."""
        if plan.links:
            cursor.executemany(
                "UPDATE silver_bars SET source_line_key = ? WHERE bar_id = ?",
                [(key, bar_id) for bar_id, key in plan.links],
            )
        for bar_id, bar in plan.updates:
            cursor.execute(
                "UPDATE silver_bars SET weight = ?, purity = ?, fine_weight = ?, "
                "source_line_key = ? WHERE bar_id = ?",
                (
                    bar["weight"],
                    bar["purity"],
                    bar["fine_weight"],
                    bar["line_key"],
                    bar_id,
                ),
            )
        if plan.removals:
            cursor.executemany(
                "DELETE FROM silver_bars WHERE bar_id = ?",
                [(bar_id,) for bar_id in plan.removals],
            )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if plan.inserts:
            cursor.executemany(
                "INSERT INTO silver_bars (estimate_voucher_no, weight, purity, fine_weight, "
                "date_added, status, list_id, source_line_key) VALUES (?, ?, ?, ?, ?, 'In Stock', NULL, ?)",
                [
                    (
                        voucher_no,
                        bar["weight"],
                        bar["purity"],
                        bar["fine_weight"],
                        now,
                        bar["line_key"],
                    )
                    for bar in plan.inserts
                ],
            )
        return SilverBarSyncResult(
            len(plan.inserts),
            0,
            len(plan.updates) + len(plan.links),
            len(plan.removals),
        )

    def synchronize(
        self, voucher_no: str, bars: Iterable[Mapping[str, Any]]
    ) -> SilverBarSyncResult:
        """Compatibility inventory operation; estimate saves use prepare/apply instead."""
        conn, cursor = self._conn, self._cursor
        started = False
        items: list[dict[str, Any]] = []
        try:
            items = [dict(bar) for bar in bars]
            if conn is None or cursor is None or not voucher_no:
                raise ValueError(
                    "Cannot synchronize bars without a database connection and voucher."
                )
            conn.execute("BEGIN IMMEDIATE")
            started = True
            plan = self.prepare(cursor, voucher_no, items)
            result = self.apply(cursor, voucher_no, plan)
            conn.commit()
            started = False
            self._db.last_error = None
            return result
        except Exception as exc:
            self._db.last_error = str(exc)
            self._logger.error(
                "Bar synchronization failed for %s: %s", voucher_no, exc, exc_info=True
            )
            return SilverBarSyncResult(0, max(1, len(items)), error_detail=str(exc))
        finally:
            if started:
                conn.rollback()


__all__ = ["SilverBarSynchronizationRepository", "SilverBarSyncResult"]
