import logging
import sqlite3

from silverestimate.infrastructure.db_session import ConnectionThreadGuard
from silverestimate.persistence.sqlite_database_runtime import SqliteDatabaseRuntime


def test_connect_initializes_connection_state(tmp_path):
    temp_db_path = tmp_path / "runtime.sqlite"
    session = ConnectionThreadGuard()
    runtime = SqliteDatabaseRuntime(
        logger=logging.getLogger("test.sqlite_runtime"),
        session=session,
    )

    state = runtime.connect(str(temp_db_path))
    try:
        assert state.conn.row_factory is sqlite3.Row
        assert state.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert state.cursor is not None
        assert state.get_item_by_code_cursor is not None
        assert state.get_item_by_code_sql == (
            "SELECT * FROM items WHERE code = ? COLLATE NOCASE"
        )
        assert state.insert_estimate_item_cursor is not None
        assert "INSERT INTO estimate_items" in state.insert_estimate_item_sql
        assert session.is_owner() is True
    finally:
        state.conn.close()


def test_schema_helpers_create_and_advance_schema_version():
    runtime = SqliteDatabaseRuntime(logger=logging.getLogger("test.sqlite_runtime"))
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        assert runtime.check_schema_version(conn, cursor) == 0
        assert runtime.table_exists(cursor, "schema_version") is True
        assert runtime.update_schema_version(conn, cursor, 3) is True
        assert runtime.check_schema_version(conn, cursor) == 3
    finally:
        conn.close()


def test_column_and_uniqueness_helpers_detect_metadata():
    runtime = SqliteDatabaseRuntime(logger=logging.getLogger("test.sqlite_runtime"))
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "CREATE TABLE items (code TEXT PRIMARY KEY, name TEXT, category TEXT)"
        )
        cursor.execute("CREATE UNIQUE INDEX idx_items_name ON items(name)")

        assert runtime.column_exists(cursor, "items", "code") is True
        assert runtime.column_exists(cursor, "items", "missing") is False
        assert runtime.is_column_unique(cursor, "items", "code") is True
        assert runtime.is_column_unique(cursor, "items", "name") is True
        assert runtime.is_column_unique(cursor, "items", "category") is False
    finally:
        conn.close()
