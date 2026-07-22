import sqlite3
import threading
import time
from pathlib import Path

from silverestimate.ui.silver_bar_load_controller import (
    _BarsLoadRequest,
    _load_bars_page,
)


def _seed_worker_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
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
            """)
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


def _factory(path: Path):
    def connect(_cancel_event=None):
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    return connect


def test_available_worker_filters_unassigned_stock_only(qt_app, tmp_path):
    del qt_app
    db_path = tmp_path / "bars.sqlite"
    _seed_worker_db(db_path)

    request = _BarsLoadRequest(
        "available",
        _factory(db_path),
        {
            "weight_query": None,
            "weight_tolerance": 0.001,
            "min_purity": None,
            "max_purity": None,
            "date_range": None,
            "limit": 100,
        },
        None,
        False,
        time.perf_counter(),
    )
    returned_request, page = _load_bars_page(request, threading.Event())

    assert returned_request is request
    assert page.total == 1
    assert [row["list_id"] for row in page.items] == [None]
    assert [row["status"] for row in page.items] == ["In Stock"]


def test_list_worker_returns_keyset_page_and_total_count(qt_app, tmp_path):
    del qt_app
    db_path = tmp_path / "bars.sqlite"
    _seed_worker_db(db_path)

    request = _BarsLoadRequest(
        "list",
        _factory(db_path),
        {"list_id": 1, "limit": 1, "offset": 0},
        None,
        False,
        time.perf_counter(),
    )
    returned_request, page = _load_bars_page(request, threading.Event())

    assert returned_request is request
    assert page.total == 2
    assert len(page.items) == 2
    assert all(row["list_id"] == 1 for row in page.items)
