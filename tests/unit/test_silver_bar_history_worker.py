import sqlite3
from pathlib import Path

from silverestimate.ui.silver_bar_history import _BarsHistoryLoadWorker


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
            (10, "LIST-010", "Issued batch", "2026-02-01 09:00:00", "2026-02-02 09:00:00"),
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
    db_path = tmp_path / "history-worker.sqlite"
    _seed_history_worker_db(db_path)

    events = {"ready": None, "error": None}
    worker = _BarsHistoryLoadWorker(
        str(db_path),
        {
            "voucher_term": "Worker B",
            "weight_text": "11.0",
            "status_text": "Issued",
            "limit": 2000,
        },
    )
    worker.data_ready.connect(lambda rows: events.__setitem__("ready", rows))
    worker.error.connect(lambda message: events.__setitem__("error", message))

    worker.run()

    assert events["error"] is None
    assert [row["estimate_voucher_no"] for row in events["ready"]] == ["W002"]
    assert events["ready"][0]["list_identifier"] == "LIST-010"


def test_history_worker_emits_error_for_missing_snapshot_db(qt_app):
    events = {"ready": None, "error": None}
    worker = _BarsHistoryLoadWorker("", {"status_text": "All Statuses", "limit": 2000})
    worker.data_ready.connect(lambda rows: events.__setitem__("ready", rows))
    worker.error.connect(lambda message: events.__setitem__("error", message))

    worker.run()

    assert events["ready"] is None
    assert events["error"] == "Temporary database path is unavailable."
