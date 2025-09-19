"""Database schema setup and migration helpers."""
from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from database_manager import DatabaseManager


def run_schema_setup(db: "DatabaseManager") -> None:
    """Ensure database schema and indexes exist, applying migrations as needed."""
    conn = getattr(db, "conn", None)
    cursor = getattr(db, "cursor", None)
    logger = getattr(db, "logger", logging.getLogger(__name__))

    if not conn or not cursor:
        logger.warning("Database setup skipped: No active connection.")
        return

    logger.info("Starting database setup check...")
    try:
        current_version = db._check_schema_version()
        logger.info("Current database schema version: %s", current_version)

        conn.execute("BEGIN TRANSACTION")

        _ensure_core_tables(db, current_version)
        _apply_versioned_migrations(db, current_version)

        conn.commit()
        logger.info("Database schema setup/update complete.")

        _ensure_indexes(db)
    except sqlite3.Error as exc:  # pragma: no cover - bubbled up to caller
        logger.critical("FATAL Database setup error: %s", exc, exc_info=True)
        conn.rollback()
        raise


def _ensure_core_tables(db: "DatabaseManager", current_version: int) -> None:
    cursor = db.cursor
    # Core domain tables (items, estimates, estimate_items)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            purity REAL DEFAULT 0,
            wage_type TEXT DEFAULT 'P',
            wage_rate REAL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS estimates (
            voucher_no TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            silver_rate REAL DEFAULT 0,
            total_gross REAL DEFAULT 0,
            total_net REAL DEFAULT 0,
            total_fine REAL DEFAULT 0,
            total_wage REAL DEFAULT 0,
            note TEXT,
            last_balance_silver REAL DEFAULT 0,
            last_balance_amount REAL DEFAULT 0
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS estimate_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            voucher_no TEXT,
            item_code TEXT,
            item_name TEXT,
            gross REAL DEFAULT 0,
            poly REAL DEFAULT 0,
            net_wt REAL DEFAULT 0,
            purity REAL DEFAULT 0,
            wage_rate REAL DEFAULT 0,
            pieces INTEGER DEFAULT 1,
            wage REAL DEFAULT 0,
            fine REAL DEFAULT 0,
            is_return INTEGER DEFAULT 0,
            is_silver_bar INTEGER DEFAULT 0,
            FOREIGN KEY (voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
            FOREIGN KEY (item_code) REFERENCES items (code) ON DELETE SET NULL
        )
        """
    )

    # Ensure note/last balance columns exist for legacy installs
    if not db._column_exists("estimates", "note"):
        cursor.execute("ALTER TABLE estimates ADD COLUMN note TEXT")
    if not db._column_exists("estimates", "last_balance_silver"):
        cursor.execute("ALTER TABLE estimates ADD COLUMN last_balance_silver REAL DEFAULT 0")
    if not db._column_exists("estimates", "last_balance_amount"):
        cursor.execute("ALTER TABLE estimates ADD COLUMN last_balance_amount REAL DEFAULT 0")

    # Silver bar tables (baseline creation ensures availability even on latest version)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS silver_bar_lists (
            list_id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_identifier TEXT UNIQUE NOT NULL,
            creation_date TEXT NOT NULL,
            list_note TEXT,
            issued_date TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS silver_bars (
            bar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            estimate_voucher_no TEXT NOT NULL,
            weight REAL DEFAULT 0,
            purity REAL DEFAULT 0,
            fine_weight REAL DEFAULT 0,
            date_added TEXT,
            status TEXT DEFAULT 'In Stock',
            list_id INTEGER,
            FOREIGN KEY (estimate_voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
            FOREIGN KEY (list_id) REFERENCES silver_bar_lists (list_id) ON DELETE SET NULL
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bar_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_no TEXT,
            date TEXT,
            silver_bar_id INTEGER NOT NULL,
            list_id INTEGER,
            from_status TEXT,
            to_status TEXT,
            notes TEXT,
            FOREIGN KEY (silver_bar_id) REFERENCES silver_bars (bar_id) ON DELETE CASCADE,
            FOREIGN KEY (list_id) REFERENCES silver_bar_lists (list_id) ON DELETE SET NULL
        )
        """
    )


def _apply_versioned_migrations(db: "DatabaseManager", current_version: int) -> None:
    cursor = db.cursor
    logger = db.logger

    if current_version < 1:
        logger.info("Applying silver bar schema migration to version 1 (non-destructive)...")

        if db._table_exists("silver_bars"):
            for column, definition in (
                ("weight", "REAL DEFAULT 0"),
                ("purity", "REAL DEFAULT 0"),
                ("fine_weight", "REAL DEFAULT 0"),
                ("date_added", "TEXT"),
                ("status", "TEXT DEFAULT 'In Stock'"),
                ("list_id", "INTEGER"),
            ):
                if not db._column_exists("silver_bars", column):
                    cursor.execute(f"ALTER TABLE silver_bars ADD COLUMN {column} {definition}")

        if db._table_exists("bar_transfers"):
            for column, definition in (
                ("transfer_no", "TEXT"),
                ("date", "TEXT"),
                ("silver_bar_id", "INTEGER"),
                ("list_id", "INTEGER"),
                ("from_status", "TEXT"),
                ("to_status", "TEXT"),
                ("notes", "TEXT"),
            ):
                if not db._column_exists("bar_transfers", column):
                    cursor.execute(f"ALTER TABLE bar_transfers ADD COLUMN {column} {definition}")

        db._update_schema_version(1)

    if current_version < 2:
        logger.info("Performing schema migration to version 2: Adding issued_date column...")
        if not db._column_exists("silver_bar_lists", "issued_date"):
            cursor.execute("ALTER TABLE silver_bar_lists ADD COLUMN issued_date TEXT")
        db._update_schema_version(2)
    else:
        logger.info("Silver bar schema is already at version 2 or higher. No migration needed.")


def _ensure_indexes(db: "DatabaseManager") -> None:
    cursor = db.cursor
    logger = db.logger

    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_code ON items(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_items_code_nocase ON items(code COLLATE NOCASE)")
        try:
            cursor.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_items_code_upper ON items(UPPER(code))"
            )
        except sqlite3.Error:
            pass

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_estimates_voucher ON estimates(voucher_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_estimates_date ON estimates(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_estimate_items_voucher ON estimate_items(voucher_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_estimate_items_code ON estimate_items(item_code)")

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sbars_voucher ON silver_bars(estimate_voucher_no)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sbars_list ON silver_bars(list_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sbars_status ON silver_bars(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sbars_date_added ON silver_bars(date_added)")

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sbar_lists_identifier ON silver_bar_lists(list_identifier)"
        )

        db.conn.commit()
        logger.info("Database indexes ensured.")
    except sqlite3.Error as exc:
        logger.warning("Failed creating one or more indexes: %s", exc)
