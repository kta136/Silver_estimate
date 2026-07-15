import sqlite3
import threading
from pathlib import Path

import pytest

from silverestimate.ui.silver_bar_history import (
    _BarsHistoryRequest,
    _load_bars_history_page,
)


def _seed_history_worker_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript("""
            CREATE TABLE estimates (
                voucher_no TEXT PRIMARY KEY,
                note TEXT
            );
            CREATE TABLE silver_bar_lists (
                list_id INTEGER PRIMARY KEY,
                list_identifier TEXT,
                list_note TEXT,
                creation_date TEXT,
                issued_date TEXT
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
        conn.executemany(
            "INSERT INTO estimates (voucher_no, note) VALUES (?, ?)",
            [
                ("W001", "Worker A"),
                ("W002", "Worker B"),
            ],
        )
        conn.execute(
            """
            INSERT INTO silver_bar_lists
            (list_id, list_identifier, list_note, creation_date, issued_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                10,
                "LIST-010",
                "Issued batch",
                "2026-02-01 09:00:00",
                "2026-02-02 09:00:00",
            ),
        )
        conn.executemany(
            """
            INSERT INTO silver_bars
            (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("W001", 10.0, 99.0, 9.90, "2026-02-14 10:00:00", "In Stock", None),
                ("W002", 11.0, 98.0, 10.78, "2026-02-14 11:00:00", "Issued", 10),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_history_worker_filters_rows_from_snapshot_repository(qt_app, tmp_path):
    del qt_app
    db_path = tmp_path / "history-worker.sqlite"
    _seed_history_worker_db(db_path)

    request = _BarsHistoryRequest(
        str(db_path),
        "Worker B",
        "11.0",
        "Issued",
        None,
        False,
    )
    returned_request, page = _load_bars_history_page(request, threading.Event())

    assert returned_request is request
    assert [row["estimate_voucher_no"] for row in page.items] == ["W002"]
    assert page.items[0]["list_identifier"] == "LIST-010"


def test_history_worker_emits_error_for_missing_snapshot_db(qt_app):
    del qt_app
    request = _BarsHistoryRequest("", "", "", "All Statuses", None, False)
    with pytest.raises(RuntimeError, match="Temporary database path is unavailable"):
        _load_bars_history_page(request, threading.Event())
