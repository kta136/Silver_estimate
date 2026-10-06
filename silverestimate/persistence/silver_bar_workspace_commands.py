"""All-or-nothing list editing for rapid keyboard entry."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any, TypeVar
from uuid import uuid4

from silverestimate.domain.numeric_policy import decimal_value
from silverestimate.domain.silver_bar_workspace import BarListSnapshot

from .repository_results import RepositoryFailureKind, RepositoryResult
from .silver_bar_repository_base import _SilverBarRepositoryBase
from .silver_bar_workspace_queries import read_list_snapshot

T = TypeVar("T")


class SilverBarWorkspaceCommands(_SilverBarRepositoryBase):
    def _workspace_write(self, operation: Callable[[Any], T]) -> RepositoryResult[T]:
        conn = self._conn
        started = False
        try:
            if conn is None:
                raise RuntimeError("No database connection.")
            conn.execute("BEGIN IMMEDIATE")
            started = True
            value = operation(conn)
            conn.commit()
            return RepositoryResult.success(value)
        except ValueError as exc:
            return RepositoryResult.failed(RepositoryFailureKind.CONFLICT, str(exc))
        except Exception as exc:
            self._logger.exception("Silver-bar list update failed")
            return RepositoryResult.failed(RepositoryFailureKind.STORAGE, str(exc))
        finally:
            if started and conn.in_transaction:
                conn.rollback()

    @staticmethod
    def _active_snapshot(conn: Any, list_id: int) -> BarListSnapshot:
        snapshot = read_list_snapshot(conn, list_id)
        if snapshot.issued:
            raise ValueError(
                "This list has been issued. Reactivate it from history first."
            )
        if any(bar["status"] != "Assigned" for bar in snapshot.bars):
            raise ValueError("The list's bar statuses have changed. Refresh the list.")
        return snapshot

    @staticmethod
    def _record_transfer(  # noqa: PLR0913 - complete audit record
        conn: Any, bar_id: int, list_id: int, old: str, new: str, note: str
    ) -> None:
        conn.execute(
            """INSERT INTO bar_transfers
               (transfer_no,date,silver_bar_id,list_id,from_status,to_status,notes)
               VALUES (?,?,?,?,?,?,?)""",
            (
                uuid4().hex,
                datetime.now().isoformat(" "),
                bar_id,
                list_id,
                old,
                new,
                note,
            ),
        )

    def add_bars_to_list(
        self, bar_ids: Iterable[int], list_id: int | None = None, note: str = ""
    ) -> RepositoryResult[BarListSnapshot]:
        ids = self._normalize_bar_ids(bar_ids)

        def add(conn: Any) -> BarListSnapshot:
            target = list_id
            if not ids:
                raise ValueError("Choose at least one available bar.")
            if target is not None:
                self._active_snapshot(conn, target)
            for bar_id in ids:
                row = conn.execute(
                    "SELECT * FROM silver_bars WHERE bar_id = ?", (bar_id,)
                ).fetchone()
                if (
                    row is None
                    or row["status"] != "In Stock"
                    or row["list_id"] is not None
                ):
                    raise ValueError(
                        f"Bar {bar_id} is no longer available. Choose another match."
                    )
                for field in ("weight", "purity", "fine_weight"):
                    if decimal_value(row[field]) < 0:
                        raise ValueError(f"Bar {bar_id} has an invalid {field}.")
            if target is None:
                day = datetime.now().strftime("%Y%m%d")
                identifiers = conn.execute(
                    "SELECT list_identifier FROM silver_bar_lists WHERE list_identifier LIKE ?",
                    (f"L-{day}-%",),
                ).fetchall()
                sequences = [
                    int(row[0].rsplit("-", 1)[-1])
                    for row in identifiers
                    if row[0].rsplit("-", 1)[-1].isdigit()
                ]
                identifier = f"L-{day}-{max(sequences, default=0) + 1:03d}"
                result = conn.execute(
                    "INSERT INTO silver_bar_lists (list_identifier,creation_date,list_note) VALUES (?,?,?)",
                    (identifier, datetime.now().isoformat(" "), note),
                )
                target = int(result.lastrowid)
            for bar_id in ids:
                conn.execute(
                    "UPDATE silver_bars SET status = 'Assigned', list_id = ? WHERE bar_id = ?",
                    (target, bar_id),
                )
                self._record_transfer(
                    conn, bar_id, target, "In Stock", "Assigned", "Added to list"
                )
            return read_list_snapshot(conn, target)

        return self._workspace_write(add)

    def remove_list_bars(
        self, list_id: int, bar_ids: Iterable[int] | None = None
    ) -> RepositoryResult[BarListSnapshot]:
        ids = None if bar_ids is None else self._normalize_bar_ids(bar_ids)

        def remove(conn: Any) -> BarListSnapshot:
            snapshot = self._active_snapshot(conn, list_id)
            present = {int(bar["bar_id"]) for bar in snapshot.bars}
            selected = present if ids is None else set(ids)
            if not selected.issubset(present):
                raise ValueError(
                    "A selected bar no longer belongs to this list. Refresh it."
                )
            self._release(conn, list_id, selected)
            return read_list_snapshot(conn, list_id)

        return self._workspace_write(remove)

    def _release(self, conn: Any, list_id: int, ids: Iterable[int]) -> None:
        for bar_id in ids:
            conn.execute(
                "UPDATE silver_bars SET status = 'In Stock', list_id = NULL WHERE bar_id = ?",
                (bar_id,),
            )
            self._record_transfer(
                conn, bar_id, list_id, "Assigned", "In Stock", "Removed from list"
            )

    def delete_active_list(self, list_id: int) -> RepositoryResult[int]:
        def delete(conn: Any) -> int:
            snapshot = self._active_snapshot(conn, list_id)
            self._release(conn, list_id, (int(bar["bar_id"]) for bar in snapshot.bars))
            conn.execute("DELETE FROM silver_bar_lists WHERE list_id = ?", (list_id,))
            return list_id

        return self._workspace_write(delete)

    def save_active_list_note(
        self, list_id: int, note: str
    ) -> RepositoryResult[BarListSnapshot]:
        def save(conn: Any) -> BarListSnapshot:
            self._active_snapshot(conn, list_id)
            conn.execute(
                "UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?",
                (note, list_id),
            )
            return read_list_snapshot(conn, list_id)

        return self._workspace_write(save)

    def issue_printed_list(
        self, list_id: int, signature: str
    ) -> RepositoryResult[BarListSnapshot]:
        def issue(conn: Any) -> BarListSnapshot:
            snapshot = self._active_snapshot(conn, list_id)
            if not snapshot.bars:
                raise ValueError("An empty list cannot be issued.")
            if snapshot.signature != signature:
                raise ValueError(
                    "This list changed after printing. Print its current contents before issuing."
                )
            conn.execute(
                "UPDATE silver_bar_lists SET issued_date = ? WHERE list_id = ?",
                (datetime.now().isoformat(" "), list_id),
            )
            for bar in snapshot.bars:
                bar_id = int(bar["bar_id"])
                conn.execute(
                    "UPDATE silver_bars SET status = 'Issued' WHERE bar_id = ?",
                    (bar_id,),
                )
                self._record_transfer(
                    conn, bar_id, list_id, "Assigned", "Issued", "Issued after printing"
                )
            return read_list_snapshot(conn, list_id)

        return self._workspace_write(issue)

    def reactivate_issued_list(self, list_id: int) -> RepositoryResult[BarListSnapshot]:
        def reactivate(conn: Any) -> BarListSnapshot:
            snapshot = read_list_snapshot(conn, list_id)
            if not snapshot.issued or any(
                bar["status"] != "Issued" for bar in snapshot.bars
            ):
                raise ValueError(
                    "Only an issued list with unchanged bar statuses can be reactivated."
                )
            conn.execute(
                "UPDATE silver_bar_lists SET issued_date = NULL WHERE list_id = ?",
                (list_id,),
            )
            for bar in snapshot.bars:
                bar_id = int(bar["bar_id"])
                conn.execute(
                    "UPDATE silver_bars SET status = 'Assigned' WHERE bar_id = ?",
                    (bar_id,),
                )
                self._record_transfer(
                    conn, bar_id, list_id, "Issued", "Assigned", "List reactivated"
                )
            return read_list_snapshot(conn, list_id)

        return self._workspace_write(reactivate)
