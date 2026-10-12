"""The sqlite3 behaviours repositories rely on, reproduced over APSW."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from silverestimate.persistence import apsw_dbapi as dbapi


@pytest.fixture
def conn():
    connection = dbapi.connect(":memory:")
    connection.row_factory = dbapi.Row
    connection.execute(
        "CREATE TABLE items(id INTEGER PRIMARY KEY, code TEXT UNIQUE, purity REAL)"
    )
    yield connection
    connection.close()


def _codes(conn):
    return [row["code"] for row in conn.execute("SELECT code FROM items ORDER BY id")]


def test_data_changes_open_a_transaction_that_rollback_undoes(conn):
    assert not conn.in_transaction
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    conn.execute("  update items SET purity = 125.5")
    assert conn.in_transaction
    conn.rollback()
    assert not conn.in_transaction
    assert _codes(conn) == []


def test_commit_keeps_changes_and_a_later_rollback_leaves_them(conn):
    conn.executemany("INSERT INTO items(code) VALUES (?)", [("A",), ("B",)])
    conn.commit()
    conn.rollback()
    conn.commit()
    assert _codes(conn) == ["A", "B"]


def test_a_failed_statement_leaves_earlier_changes_for_rollback(conn):
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    with pytest.raises(dbapi.IntegrityError, match="UNIQUE constraint failed"):
        conn.execute("INSERT INTO items(code) VALUES ('A')")
    assert conn.in_transaction
    conn.rollback()
    assert _codes(conn) == []


def test_reads_and_schema_changes_do_not_open_a_transaction(conn):
    conn.execute("SELECT * FROM items").fetchall()
    conn.execute("CREATE INDEX idx_items_purity ON items(purity)")
    assert not conn.in_transaction


def test_explicit_transactions_pass_through(conn):
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    assert conn.in_transaction
    conn.commit()
    assert _codes(conn) == ["A"]


def test_with_block_commits_on_success_and_rolls_back_on_error(conn):
    with conn:
        conn.execute("INSERT INTO items(code) VALUES ('A')")
    with pytest.raises(RuntimeError), conn:
        conn.execute("INSERT INTO items(code) VALUES ('B')")
        raise RuntimeError("abandon")
    assert _codes(conn) == ["A"]
    assert not conn.in_transaction


def test_rowcount_and_lastrowid_follow_each_statement(conn):
    inserted = conn.execute("INSERT INTO items(code) VALUES ('A')")
    assert (inserted.rowcount, inserted.lastrowid) == (1, 1)
    many = conn.executemany("INSERT INTO items(code) VALUES (?)", [("B",), ("C",)])
    assert many.rowcount == 2
    cursor = conn.cursor()
    assert cursor.execute("UPDATE items SET purity = 92.5").rowcount == 3
    assert cursor.execute("DELETE FROM items WHERE code = 'missing'").rowcount == 0
    assert cursor.execute("SELECT * FROM items").rowcount == -1
    assert conn.total_changes == 6


def test_rows_read_by_position_and_by_name(conn):
    conn.execute("INSERT INTO items(code, purity) VALUES ('A', 125.5)")
    cursor = conn.execute("SELECT id, code, purity AS Purity FROM items")
    assert [column[0] for column in cursor.description] == ["id", "code", "Purity"]
    row = cursor.fetchone()
    assert isinstance(row, dbapi.Row)
    assert (row[0], row["code"], row["purity"], row[-1]) == (1, "A", 125.5, 125.5)
    assert row.keys() == ["id", "code", "Purity"]
    assert dict(row) == {"id": 1, "code": "A", "Purity": 125.5}
    assert tuple(row) == (1, "A", 125.5) and len(row) == 3
    with pytest.raises(IndexError):
        row["missing"]
    assert conn.execute("UPDATE items SET purity = 1").description is None


def test_rows_are_plain_tuples_without_a_row_factory(conn):
    conn.row_factory = None
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    assert conn.execute("SELECT id, code FROM items").fetchall() == [(1, "A")]


def test_fetch_methods_share_one_position(conn):
    conn.executemany("INSERT INTO items(code) VALUES (?)", [(c,) for c in "ABCDE"])
    cursor = conn.execute("SELECT code FROM items ORDER BY id")
    assert cursor.fetchone()["code"] == "A"
    assert [row["code"] for row in cursor.fetchmany(2)] == ["B", "C"]
    assert [row["code"] for row in cursor] == ["D", "E"]
    assert cursor.fetchone() is None and cursor.fetchall() == []


def test_a_statement_is_finished_once_its_last_row_is_fetched(conn):
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    conn.commit()
    cursor = conn.cursor()
    assert cursor.execute("SELECT count(*) FROM items").fetchone()[0] == 1
    # VACUUM refuses to run while any statement on the connection is unfinished.
    conn.execute("VACUUM")


def test_errors_use_the_sqlite3_hierarchy(conn):
    with pytest.raises(dbapi.OperationalError, match="no such table: missing"):
        conn.execute("SELECT * FROM missing")
    with pytest.raises(dbapi.ProgrammingError):
        conn.execute("SELECT ?, ?", (1,))
    assert issubclass(dbapi.IntegrityError, dbapi.DatabaseError)
    assert issubclass(dbapi.OperationalError, dbapi.DatabaseError)
    assert issubclass(dbapi.DatabaseError, dbapi.Error)


def test_a_closed_connection_reports_misuse():
    connection = dbapi.connect(":memory:")
    connection.close()
    connection.close()
    with pytest.raises(dbapi.ProgrammingError):
        connection.execute("SELECT 1")


def test_another_thread_cannot_use_the_connection(conn):
    cursor = conn.execute("SELECT 1")
    with ThreadPoolExecutor(max_workers=1) as pool:
        for call in (
            lambda: conn.execute("SELECT 1"),
            conn.cursor,
            conn.commit,
            cursor.fetchone,
            conn.close,
        ):
            with pytest.raises(dbapi.ProgrammingError, match="same thread"):
                pool.submit(call).result(timeout=10)


def test_trace_callback_reports_statements_with_their_values(conn):
    statements = []
    conn.set_trace_callback(statements.append)
    conn.execute("INSERT INTO items(code, purity) VALUES (?, ?)", ("A", 125.5))
    conn.commit()
    conn.set_trace_callback(None)
    conn.execute("SELECT 1")
    assert statements == [
        "BEGIN",
        "INSERT INTO items(code, purity) VALUES ('A', 125.5)",
        "COMMIT",
    ]


def test_progress_handler_can_cancel_a_running_query(conn):
    conn.set_progress_handler(lambda: 1, 10)
    with pytest.raises(dbapi.OperationalError, match="interrupted"):
        conn.execute(
            "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) "
            "SELECT count(*) FROM n"
        )
    conn.set_progress_handler(None, 10)
    assert conn.execute("SELECT 1").fetchone()[0] == 1


def test_functions_and_backup(conn, tmp_path):
    conn.create_function("twice", 1, lambda value: value * 2)
    assert conn.execute("SELECT twice(21)").fetchone()[0] == 42
    conn.execute("INSERT INTO items(code) VALUES ('A')")
    conn.commit()
    target = dbapi.connect(tmp_path / "copy.db")
    try:
        conn.backup(target)
        assert target.execute("SELECT code FROM items").fetchall() == [("A",)]
    finally:
        target.close()
