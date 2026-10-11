import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from silverestimate.persistence.silver_bar_query_repository import (
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


def _connection_factory(path: Path):
    def open_connection(_cancel_event=None):
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection

    return open_connection


def test_snapshot_repository_history_search_filters_by_note_and_status(tmp_path):
    db_path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(db_path)

    repo = SilverBarsSnapshotRepository(_connection_factory(db_path))
    page = repo.search_history_bars_page(
        voucher_term="Delta",
        weight_text="13.0",
        status_text="Issued",
    )

    assert [row["estimate_voucher_no"] for row in page.items] == ["V004"]
    assert page.items[0]["list_identifier"] == "LIST-002"
    assert page.total == 1


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

        def execute(self, query):
            self.begun = query

        def cursor(self):
            return self.cursor_obj

        def close(self):
            self.closed = True

    repo = SilverBarsSnapshotRepository("unused.sqlite")
    conn = _ConnectionStub()
    repo._connect = lambda: conn  # type: ignore[method-assign]

    page = repo.search_history_bars_page(voucher_term="V001", include_total=False)

    assert page.items == ({"estimate_voucher_no": "V001"},)
    assert conn.closed is True


def test_list_history_pages_include_empty_lists_and_complete_totals(tmp_path):
    path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(path)
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute(
            "INSERT INTO silver_bar_lists (list_id, list_identifier, list_note) "
            "VALUES (3, 'LIST-003', 'Empty')"
        )
        conn.execute(
            "INSERT INTO silver_bars (weight, purity, fine_weight, list_id) "
            "VALUES (10, 125.5, 12.55, 1)"
        )
    repo = SilverBarsSnapshotRepository(_connection_factory(path))
    first = repo.get_list_history_page(limit=1)
    assert first.total == 3
    assert first.items[0]["list_id"] == 3
    assert first.items[0]["bar_count"] == 0
    assert first.items[0]["weight"] == first.items[0]["fine_weight"] == 0
    assert first.next_cursor == 3

    second = repo.get_list_history_page(
        cursor=first.next_cursor, limit=1, include_total=False
    )
    assert second.total is None
    assert second.items[0]["list_id"] == 2
    last = repo.get_list_history_page(cursor=second.next_cursor, limit=1)
    assert last.total == 3
    assert last.next_cursor is None
    assert last.items[0]["list_id"] == 1
    assert last.items[0]["bar_count"] == 3
    assert last.items[0]["weight"] == 31.5
    assert last.items[0]["fine_weight"] == pytest.approx(33.22)


@pytest.mark.parametrize(
    "state, search, ids",
    [
        ("All", "", [2, 1]),
        ("Active", "", [1]),
        ("Issued", "", [2]),
        ("All", "LIST-001", [1]),
        ("All", "Issued", [2]),
        ("Active", "Issued", []),
    ],
)
def test_list_history_search_and_state_filter_counts(tmp_path, state, search, ids):
    path = tmp_path / "snapshot.sqlite"
    _seed_snapshot_db(path)
    repo = SilverBarsSnapshotRepository(_connection_factory(path))
    page = repo.get_list_history_page(state=state, search_term=search)
    assert [row["list_id"] for row in page.items] == ids
    assert page.total == len(ids)
    assert page.next_cursor is None
