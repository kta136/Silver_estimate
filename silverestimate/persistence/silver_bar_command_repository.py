"""Transactional silver-bar command persistence component."""

from __future__ import annotations

from typing import Any, Iterable, Tuple

from silverestimate.persistence.database_driver import dbapi as sqlite3
from silverestimate.persistence.silver_bar_workspace_commands import (
    SilverBarWorkspaceCommands,
)


class SilverBarCommandRepository(SilverBarWorkspaceCommands):
    """Own list lifecycle and inventory mutation commands."""

    def reactivate_list(self, list_id: int) -> bool:
        return self.reactivate_issued_list(list_id).succeeded

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


__all__ = ["SilverBarCommandRepository"]
