import sqlite3
from pathlib import Path

import pytest

from silverestimate.ui.silver_bar_management import _BarsLoadWorker


def _seed_worker_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE estimates (
                voucher_no TEXT PRIMARY KEY,
                note TEXT
            );
            CREATE TABLE silver_bars (
                bar_id INTEGER PRIMARY KEY AUTOINCREMENT,
                estimate_voucher_no TEXT,
                weight REAL,
                purity REAL,
                fine_weight REAL,
                date_added TEXT,
                status TEXT,
                list_id INTEGER
            );
            """
        )
        conn.execute(
            "INSERT INTO estimates (voucher_no, note) VALUES (?, ?)",
            ("V001", "Note 1"),
        )
        conn.execute(
            "INSERT INTO estimates (voucher_no, note) VALUES (?, ?)",
            ("V002", "Note 2"),
        )
        conn.executemany(
            """
            INSERT INTO silver_bars
            (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("V001", 10.0, 99.0, 9.9, "2026-02-14 10:00:00", "In Stock", None),
                ("V001", 11.0, 98.0, 10.78, "2026-02-14 11:00:00", "In Stock", 1),
                ("V002", 12.0, 97.0, 11.64, "2026-02-14 12:00:00", "Assigned", 1),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_available_worker_filters_unassigned_stock_only(qt_app, tmp_path):
    db_path = tmp_path / "bars.sqlite"
    _seed_worker_db(db_path)

    events = {"ready": None, "error": None}
    worker = _BarsLoadWorker(
        "available",
        7,
        str(db_path),
        {
            "weight_query": None,
            "weight_tolerance": 0.001,
            "min_purity": None,
            "max_purity": None,
            "date_range": None,
            "limit": 100,
        },
    )
    worker.data_ready.connect(
        lambda target, request_id, rows, total: events.__setitem__(
            "ready", (target, request_id, rows, total)
        )
    )
    worker.error.connect(
        lambda target, request_id, message: events.__setitem__(
            "error", (target, request_id, message)
        )
    )

    worker.run()

    assert events["error"] is None
    target, request_id, rows, total = events["ready"]
    assert target == "available"
    assert request_id == 7
    assert total == 1
    assert [row["list_id"] for row in rows] == [None]
    assert [row["status"] for row in rows] == ["In Stock"]


def test_list_worker_returns_limited_rows_and_total_count(qt_app, tmp_path):
    db_path = tmp_path / "bars.sqlite"
    _seed_worker_db(db_path)

    events = {"ready": None, "error": None}
    worker = _BarsLoadWorker(
        "list",
        9,
        str(db_path),
        {"list_id": 1, "limit": 1, "offset": 0},
    )
    worker.data_ready.connect(
        lambda target, request_id, rows, total: events.__setitem__(
            "ready", (target, request_id, rows, total)
        )
    )
    worker.error.connect(
        lambda target, request_id, message: events.__setitem__(
            "error", (target, request_id, message)
        )
    )

    worker.run()

    assert events["error"] is None
    target, request_id, rows, total = events["ready"]
    assert target == "list"
    assert request_id == 9
    assert total == 2
    assert len(rows) == 1
    assert rows[0]["list_id"] == 1
