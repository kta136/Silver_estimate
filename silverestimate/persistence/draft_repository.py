"""One unfinished entry, kept inside the authenticated SQLCipher database."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

from silverestimate.persistence.database_driver import Connection

MAX_DRAFT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class DraftRecord:
    token: str
    voucher_no: str
    payload: str
    updated_utc: str


class DraftRepository:
    """Owner-thread writes with a short busy timeout and optimistic ownership."""

    def __init__(
        self,
        connection: Callable[[], Connection | None],
        maintenance: Callable[[], bool],
    ):
        self._connection = connection
        self._maintenance = maintenance

    def load(self) -> DraftRecord | None:
        conn = self._connection()
        if conn is None or self._maintenance():
            raise RuntimeError("Draft recovery storage is unavailable")
        row = conn.execute(
            "SELECT token,voucher_no,payload,updated_utc FROM estimate_draft WHERE slot=1"
        ).fetchone()
        return DraftRecord(*row) if row else None

    def write(
        self, token: str, voucher_no: str, payload: str, *, expected_token: str | None
    ) -> bool:
        if len(payload.encode("utf-8")) > MAX_DRAFT_BYTES:
            raise ValueError("Draft exceeds the 8 MiB recovery limit")
        return self._change(token, voucher_no, payload, expected_token)

    def delete(self, token: str) -> bool:
        return self._change(token, "", None, token)

    def _change(
        self,
        token: str,
        voucher_no: str,
        payload: str | None,
        expected_token: str | None,
    ) -> bool:
        conn = self._connection()
        if conn is None or self._maintenance() or conn.in_transaction:
            return False
        previous_timeout = int(conn.execute("PRAGMA busy_timeout").fetchone()[0])
        conn.execute("PRAGMA busy_timeout=50")
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute(
                "SELECT token FROM estimate_draft WHERE slot=1"
            ).fetchone()
            if current and current[0] != expected_token:
                conn.rollback()
                return False
            if payload is None:
                conn.execute(
                    "DELETE FROM estimate_draft WHERE slot=1 AND token=?", (token,)
                )
            else:
                conn.execute(
                    "INSERT INTO estimate_draft(slot,token,voucher_no,payload,updated_utc) VALUES(1,?,?,?,?) "
                    "ON CONFLICT(slot) DO UPDATE SET token=excluded.token,voucher_no=excluded.voucher_no,"
                    "payload=excluded.payload,updated_utc=excluded.updated_utc",
                    (
                        token,
                        voucher_no,
                        payload,
                        datetime.now(UTC).isoformat(timespec="seconds"),
                    ),
                )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.execute(f"PRAGMA busy_timeout={previous_timeout}")
