from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.run_performance_gate import (
    BAR_COUNT,
    ESTIMATE_COUNT,
    ESTIMATE_LINE_COUNT,
    ITEM_COUNT,
    create_deterministic_dataset,
)


def test_deterministic_dataset_has_required_scale(tmp_path: Path) -> None:
    database_path = tmp_path / "performance.sqlite"
    create_deterministic_dataset(database_path)

    connection = sqlite3.connect(database_path)
    try:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("items", "silver_bars", "estimates", "estimate_items")
        }
    finally:
        connection.close()

    assert counts == {
        "items": ITEM_COUNT,
        "silver_bars": BAR_COUNT,
        "estimates": ESTIMATE_COUNT,
        "estimate_items": ESTIMATE_LINE_COUNT,
    }
