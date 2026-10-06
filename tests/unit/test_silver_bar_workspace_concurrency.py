"""Competing writers must never reserve the same bar in two saved lists."""

import sqlite3
import threading
from contextlib import closing
from types import SimpleNamespace

from silverestimate.persistence.silver_bar_command_repository import (
    SilverBarCommandRepository,
)


def test_competing_first_adds_create_exactly_one_list(tmp_path):
    path = tmp_path / "race.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript("""
            CREATE TABLE estimates(voucher_no TEXT PRIMARY KEY, note TEXT);
            CREATE TABLE silver_bar_lists(list_id INTEGER PRIMARY KEY, list_identifier TEXT UNIQUE, creation_date TEXT, list_note TEXT, issued_date TEXT);
            CREATE TABLE silver_bars(bar_id INTEGER PRIMARY KEY, estimate_voucher_no TEXT, weight REAL, purity REAL, fine_weight REAL, status TEXT, list_id INTEGER);
            CREATE TABLE bar_transfers(transfer_no TEXT, date TEXT, silver_bar_id INTEGER, list_id INTEGER, from_status TEXT, to_status TEXT, notes TEXT);
            INSERT INTO estimates VALUES ('1', '');
            INSERT INTO silver_bars VALUES (1, '1', 10, 125.5, 12.55, 'In Stock', NULL);
        """)
    gate = threading.Barrier(2)
    results = []

    def add():
        connection = sqlite3.connect(path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            repository = SilverBarCommandRepository(
                SimpleNamespace(conn=connection, cursor=connection.cursor())
            )
            gate.wait(timeout=5)
            results.append(repository.add_bars_to_list([1]))
        finally:
            connection.close()

    threads = [threading.Thread(target=add) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
        assert not thread.is_alive()
    assert sorted(result.succeeded for result in results) == [False, True]
    with closing(sqlite3.connect(path)) as conn:
        assert conn.execute("SELECT count(*) FROM silver_bar_lists").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM bar_transfers").fetchone()[0] == 1
