from __future__ import annotations

from datetime import datetime
from typing import Any

from silverestimate.domain.numeric_policy import fine_weight


def insert_silver_bar(
    db: Any,
    estimate_voucher_no: str,
    weight: float,
    purity: float,
    *,
    status: str = "In Stock",
    list_id: int | None = None,
    date_added: str | None = None,
) -> int:
    """Insert one inventory row directly, the way legacy imports left them."""
    cursor = db.conn.execute(
        """
        INSERT INTO silver_bars
        (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            estimate_voucher_no,
            weight,
            purity,
            fine_weight(weight, purity),
            date_added or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status,
            list_id,
        ),
    )
    db.conn.commit()
    return int(cursor.lastrowid)
