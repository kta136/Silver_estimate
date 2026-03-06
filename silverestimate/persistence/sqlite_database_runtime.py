"""SQLite connection/bootstrap helpers for the persistence layer."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from silverestimate.infrastructure.db_session import ConnectionThreadGuard

_GET_ITEM_BY_CODE_SQL = "SELECT * FROM items WHERE code = ? COLLATE NOCASE"
_INSERT_ESTIMATE_ITEM_SQL = (
    "INSERT INTO estimate_items "
    "(voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, "
    "pieces, wage, fine, is_return, is_silver_bar) "
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


@dataclass
class SqliteConnectionState:
    conn: sqlite3.Connection
    cursor: sqlite3.Cursor
    get_item_by_code_cursor: sqlite3.Cursor | None
    get_item_by_code_sql: str | None
    insert_estimate_item_cursor: sqlite3.Cursor | None
    insert_estimate_item_sql: str | None


class SqliteDatabaseRuntime:
    """Manage SQLite connection setup and schema metadata helpers."""

    def __init__(
        self,
        *,
        logger: Optional[logging.Logger] = None,
        session: Optional[ConnectionThreadGuard] = None,
    ) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._session = session

    def connect(self, temp_db_path: str) -> SqliteConnectionState:
        """Connect to the temp DB and prepare cursors used by repositories."""
        if not temp_db_path:
            raise Exception("Temporary database path not set.")
        try:
            self._logger.debug("Connecting to temporary database")
            conn = sqlite3.connect(temp_db_path)
            if self._session is not None:
                self._session.attach_to_current_thread()
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row

            self._configure_connection_pragmas(conn)
            cursor = conn.cursor()
            prepared = self._prepare_hot_statements(conn)
            self._logger.debug("Connected to temporary database")
            return SqliteConnectionState(
                conn=conn,
                cursor=cursor,
                get_item_by_code_cursor=prepared[0],
                get_item_by_code_sql=prepared[1],
                insert_estimate_item_cursor=prepared[2],
                insert_estimate_item_sql=prepared[3],
            )
        except sqlite3.Error as exc:
            self._logger.error(
                "Failed to connect to temporary database: %s",
                exc,
                exc_info=True,
            )
            if self._session is not None:
                try:
                    self._session.clear()
                except Exception as clear_error:
                    self._logger.debug(
                        "Failed to clear connection thread guard after connect failure: %s",
                        clear_error,
                    )
            raise

    def table_exists(
        self,
        cursor: sqlite3.Cursor | None,
        table_name: str,
    ) -> bool:
        """Check if a table exists in the database."""
        if not cursor:
            return False
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def column_exists(
        self,
        cursor: sqlite3.Cursor | None,
        table_name: str,
        column_name: str,
    ) -> bool:
        """Check if a column exists in a table."""
        if not cursor or not self.table_exists(cursor, table_name):
            return False
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            return any(col["name"] == column_name for col in cursor.fetchall())
        except sqlite3.Error as exc:
            self._logger.error(
                "Error checking column %s.%s: %s",
                table_name,
                column_name,
                exc,
                exc_info=True,
            )
            return False

    def is_column_unique(
        self,
        cursor: sqlite3.Cursor | None,
        table_name: str,
        column_name: str,
    ) -> bool:
        """Check if a column has a UNIQUE constraint via PK or unique index."""
        if not cursor or not self.column_exists(cursor, table_name, column_name):
            return False
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            for col in cursor.fetchall():
                if col["name"] == column_name and int(col["pk"]) == 1:
                    return True

            cursor.execute(f"PRAGMA index_list({table_name})")
            for index in cursor.fetchall():
                if int(index["unique"]) != 1:
                    continue
                cursor.execute(f"PRAGMA index_info({index['name']})")
                idx_cols = cursor.fetchall()
                if len(idx_cols) == 1 and idx_cols[0]["name"] == column_name:
                    return True
            return False
        except sqlite3.Error as exc:
            self._logger.error(
                "Error checking unique constraint for %s.%s: %s",
                table_name,
                column_name,
                exc,
                exc_info=True,
            )
            return False

    def check_schema_version(
        self,
        conn: sqlite3.Connection | None,
        cursor: sqlite3.Cursor | None,
    ) -> int:
        """Ensure the schema_version table exists and return the current version."""
        if not conn or not cursor:
            return 0
        try:
            if not self.table_exists(cursor, "schema_version"):
                self._logger.info("Creating schema_version table...")
                cursor.execute("""
                    CREATE TABLE schema_version (
                        id INTEGER PRIMARY KEY,
                        version INTEGER NOT NULL,
                        applied_date TEXT NOT NULL
                    )
                """)
                cursor.execute(
                    """
                    INSERT INTO schema_version (version, applied_date)
                    VALUES (0, ?)
                """,
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
                )
                conn.commit()
                self._logger.info("Initialized schema version to 0.")
                return 0

            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0
        except sqlite3.Error as exc:
            self._logger.error(
                "Error checking schema version: %s",
                exc,
                exc_info=True,
            )
            return 0

    def update_schema_version(
        self,
        conn: sqlite3.Connection | None,
        cursor: sqlite3.Cursor | None,
        new_version: int,
    ) -> bool:
        """Append a schema version entry."""
        if not conn or not cursor:
            return False
        try:
            cursor.execute(
                """
                INSERT INTO schema_version (version, applied_date)
                VALUES (?, ?)
            """,
                (new_version, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            conn.commit()
            self._logger.info("Schema updated to version %s", new_version)
            return True
        except sqlite3.Error as exc:
            self._logger.error(
                "Error updating schema version: %s",
                exc,
                exc_info=True,
            )
            conn.rollback()
            return False

    def _configure_connection_pragmas(self, conn: sqlite3.Connection) -> None:
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.execute("PRAGMA cache_size=-20000")  # ~20 MB page cache
            try:
                conn.execute("PRAGMA mmap_size=268435456")  # 256 MB
            except Exception as exc:
                self._logger.debug("Could not set SQLite mmap_size pragma: %s", exc)
            self._log_pragma_values(conn)
        except Exception as exc:
            self._logger.warning("One or more PRAGMA settings failed: %s", exc)

    def _log_pragma_values(self, conn: sqlite3.Connection) -> None:
        try:
            for pragma in ("journal_mode", "synchronous", "temp_store", "cache_size"):
                cur = conn.execute(f"PRAGMA {pragma}")
                row = cur.fetchone()
                value = row[0] if row and len(row) > 0 else None
                self._logger.debug("PRAGMA %s = %s", pragma, value)
        except Exception as exc:
            self._logger.debug("Failed to read SQLite pragma values: %s", exc)

    def _prepare_hot_statements(
        self,
        conn: sqlite3.Connection,
    ) -> tuple[
        sqlite3.Cursor | None,
        str | None,
        sqlite3.Cursor | None,
        str | None,
    ]:
        get_item_cursor = None
        get_item_sql = None
        insert_estimate_cursor = None
        insert_estimate_sql = None

        try:
            get_item_cursor = conn.cursor()
            get_item_sql = _GET_ITEM_BY_CODE_SQL
        except Exception as exc:
            self._logger.debug("Failed to prepare get-item hot statement: %s", exc)
        try:
            insert_estimate_cursor = conn.cursor()
            insert_estimate_sql = _INSERT_ESTIMATE_ITEM_SQL
        except Exception as exc:
            self._logger.debug(
                "Failed to prepare insert-estimate-item hot statement: %s", exc
            )
        return (
            get_item_cursor,
            get_item_sql,
            insert_estimate_cursor,
            insert_estimate_sql,
        )


__all__ = ["SqliteConnectionState", "SqliteDatabaseRuntime"]
