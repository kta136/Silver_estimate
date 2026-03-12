import sqlite3
from pathlib import Path

from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)


def _seed_snapshot_db(path: Path) -> None:
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
                ("V001", "Alpha"),
                ("V002", "Beta"),
                ("V003", "Gamma"),
                ("V004", "Delta"),
                ("V005", "Epsilon"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO silver_bar_lists
            (list_id, list_identifier, list_note, creation_date, issued_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "LIST-001", "Active", "2026-02-10 09:00:00", None),
                (2, "LIST-002", "Issued", "2026-02-11 09:00:00", "2026-02-12 09:00:00"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO silver_bars
            (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("V001", 10.0, 99.0, 9.90, "2026-02-10 10:00:00", "In Stock", None),
                ("V002", 11.0, 98.0, 10.78, "2026-02-10 11:00:00", "In Stock", None),
                ("V003", 12.0, 97.0, 11.64, "2026-02-10 12:00:00", "Assigned", 1),
                ("V004", 13.0, 96.0, 12.48, "2026-02-10 13:00:00", "Issued", 2),
                ("V005", 9.5, 95.0, 9.03, "2026-02-10 14:00:00", "Assigned", 1),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def test_snapshot_repository_available_page_returns_total_and_rows(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(db_path)

    repo = SilverBarsSnapshotRepository(str(db_path))
    rows, total_count = repo.get_available_bars_page(limit=1)

    assert total_count == 2
    assert len(rows) == 1
    assert rows[0]["estimate_voucher_no"] == "V002"
    assert rows[0]["status"] == "In Stock"
    assert rows[0]["list_id"] is None


def test_snapshot_repository_available_page_applies_date_range_filter(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(db_path)

    repo = SilverBarsSnapshotRepository(str(db_path))
    rows, total_count = repo.get_available_bars_page(
        date_range=("2026-02-10 10:30:00", "2026-02-10 11:30:00"),
        limit=100,
    )

    assert total_count == 1
    assert [row["estimate_voucher_no"] for row in rows] == ["V002"]


def test_snapshot_repository_list_page_returns_limited_rows_and_total(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(db_path)

    repo = SilverBarsSnapshotRepository(str(db_path))
    rows, total_count = repo.get_bars_in_list_page(1, limit=1, offset=0)

    assert total_count == 2
    assert len(rows) == 1
    assert rows[0]["estimate_voucher_no"] == "V003"
    assert rows[0]["list_id"] == 1


def test_snapshot_repository_history_search_filters_by_note_and_status(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(db_path)

    repo = SilverBarsSnapshotRepository(str(db_path))
    rows = repo.search_history_bars(
        voucher_term="Delta",
        weight_text="13.0",
        status_text="Issued",
        limit=2000,
    )

    assert [row["estimate_voucher_no"] for row in rows] == ["V004"]
    assert rows[0]["list_identifier"] == "LIST-002"


def test_snapshot_repository_closes_connections_after_queries():
    class _CursorStub:
        def execute(self, query, params):
            self.query = query
            self.params = params

        def fetchall(self):
            return [{"estimate_voucher_no": "V001"}]

    class _ConnectionStub:
        def __init__(self):
            self.closed = False
            self.cursor_obj = _CursorStub()

        def cursor(self):
            return self.cursor_obj

        def close(self):
            self.closed = True

    repo = SilverBarsSnapshotRepository("unused.sqlite")
    conn = _ConnectionStub()
    repo._connect = lambda: conn  # type: ignore[method-assign]

    rows = repo.search_history_bars(voucher_term="V001")

    assert rows == [{"estimate_voucher_no": "V001"}]
    assert conn.closed is True
