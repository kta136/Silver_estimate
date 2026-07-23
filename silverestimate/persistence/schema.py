"""Current database schema creation and validation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from silverestimate.persistence.database_driver import dbapi as sqlite3

CURRENT_SCHEMA_VERSION = 8

if TYPE_CHECKING:  # pragma: no cover
    from silverestimate.persistence.database_manager import DatabaseManager


def run_schema_setup(db: "DatabaseManager") -> None:
    """Create a new current schema or validate an existing current schema."""
    conn = getattr(db, "conn", None)
    cursor = getattr(db, "cursor", None)
    logger = getattr(db, "logger", logging.getLogger(__name__))

    if not conn or not cursor:
        logger.warning("Database setup skipped: No active connection.")
        return

    logger.info("Starting database schema check...")
    try:
        current_version = db._check_schema_version()
        logger.info("Current database schema version: %s", current_version)
        if current_version not in (0, CURRENT_SCHEMA_VERSION):
            raise RuntimeError(
                f"Unsupported database schema version {current_version}; "
                f"this release accepts only version {CURRENT_SCHEMA_VERSION}."
            )

        conn.execute("BEGIN IMMEDIATE")
        if current_version == 0:
            existing_domain_tables = {
                table
                for table in (
                    "items",
                    "estimates",
                    "estimate_items",
                    "silver_bars",
                    "silver_bar_lists",
                    "bar_transfers",
                )
                if db._table_exists(table)
            }
            if existing_domain_tables:
                raise RuntimeError(
                    "Unversioned database schema is unsupported; "
                    "open it with an older release before using this version."
                )
            _create_current_schema(db)
            _stage_schema_version(db, CURRENT_SCHEMA_VERSION)
        _ensure_indexes(db)
        _validate_schema(db)

        conn.commit()
        logger.info("Database schema is current at version %s.", CURRENT_SCHEMA_VERSION)
    except (sqlite3.Error, RuntimeError) as exc:  # pragma: no cover - bubbled up
        logger.critical("FATAL Database setup error: %s", exc, exc_info=True)
        conn.rollback()
        raise


def _create_current_schema(db: "DatabaseManager") -> None:
    cursor = db.cursor
    assert cursor is not None
    cursor.execute("""
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY,
            version INTEGER NOT NULL,
            applied_date TEXT NOT NULL
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            purity REAL DEFAULT 0,
            wage_type TEXT DEFAULT 'P',
            wage_rate REAL DEFAULT 0,
            tunch TEXT
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estimates (
            voucher_no TEXT PRIMARY KEY,
            voucher_no_int INTEGER,
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
        """)
    cursor.execute("""
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
            wage_type TEXT,
            wage REAL DEFAULT 0,
            fine REAL DEFAULT 0,
            is_return INTEGER DEFAULT 0,
            is_silver_bar INTEGER DEFAULT 0,
            line_key TEXT,
            FOREIGN KEY (voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
            FOREIGN KEY (item_code) REFERENCES items (code) ON DELETE SET NULL
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS silver_bar_lists (
            list_id INTEGER PRIMARY KEY AUTOINCREMENT,
            list_identifier TEXT UNIQUE NOT NULL,
            creation_date TEXT NOT NULL,
            list_note TEXT,
            issued_date TEXT
        )
        """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS silver_bars (
            bar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            estimate_voucher_no TEXT NOT NULL,
            weight REAL DEFAULT 0,
            purity REAL DEFAULT 0,
            fine_weight REAL DEFAULT 0,
            date_added TEXT,
            status TEXT DEFAULT 'In Stock',
            list_id INTEGER,
            source_line_key TEXT,
            FOREIGN KEY (estimate_voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
            FOREIGN KEY (list_id) REFERENCES silver_bar_lists (list_id) ON DELETE SET NULL
        )
        """)
    cursor.execute("""
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
        """)


def _stage_schema_version(db: "DatabaseManager", version: int) -> None:
    if db._update_schema_version(version) is not True:
        raise sqlite3.OperationalError(f"Failed to stage schema version {version}.")


def _ensure_indexes(db: "DatabaseManager") -> None:
    cursor = db.cursor
    logger = db.logger
    assert cursor is not None
    assert logger is not None

    mandatory_indexes = {
        "idx_items_code": "CREATE INDEX IF NOT EXISTS idx_items_code ON items(code)",
        "idx_items_code_nocase": (
            "CREATE INDEX IF NOT EXISTS idx_items_code_nocase "
            "ON items(code COLLATE NOCASE)"
        ),
        "idx_items_name_nocase": (
            "CREATE INDEX IF NOT EXISTS idx_items_name_nocase "
            "ON items(name COLLATE NOCASE)"
        ),
        "idx_estimates_voucher": (
            "CREATE INDEX IF NOT EXISTS idx_estimates_voucher ON estimates(voucher_no)"
        ),
        "idx_estimates_date": (
            "CREATE INDEX IF NOT EXISTS idx_estimates_date ON estimates(date)"
        ),
        "idx_estimates_voucher_no_int": (
            "CREATE INDEX IF NOT EXISTS idx_estimates_voucher_no_int "
            "ON estimates(voucher_no_int DESC)"
        ),
        "idx_estimates_history_keyset": (
            "CREATE INDEX IF NOT EXISTS idx_estimates_history_keyset "
            "ON estimates(voucher_no_int DESC, voucher_no DESC)"
        ),
        "idx_estimate_items_voucher": (
            "CREATE INDEX IF NOT EXISTS idx_estimate_items_voucher "
            "ON estimate_items(voucher_no)"
        ),
        "idx_estimate_items_code": (
            "CREATE INDEX IF NOT EXISTS idx_estimate_items_code "
            "ON estimate_items(item_code)"
        ),
        "idx_estimate_items_voucher_line_key": (
            "CREATE INDEX IF NOT EXISTS idx_estimate_items_voucher_line_key "
            "ON estimate_items(voucher_no, line_key)"
        ),
        "idx_sbars_voucher": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_voucher "
            "ON silver_bars(estimate_voucher_no)"
        ),
        "idx_sbars_list": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_list ON silver_bars(list_id)"
        ),
        "idx_sbars_status": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_status ON silver_bars(status)"
        ),
        "idx_sbars_status_list_date_id": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_status_list_date_id "
            "ON silver_bars(status, list_id, date_added DESC, bar_id DESC)"
        ),
        "idx_sbars_status_list_weight_date_id": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_status_list_weight_date_id "
            "ON silver_bars(status, list_id, weight, date_added DESC, bar_id DESC)"
        ),
        "idx_sbars_date_added": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_date_added ON silver_bars(date_added)"
        ),
        "idx_sbars_voucher_line_key": (
            "CREATE INDEX IF NOT EXISTS idx_sbars_voucher_line_key "
            "ON silver_bars(estimate_voucher_no, source_line_key)"
        ),
        "idx_sbar_lists_identifier": (
            "CREATE INDEX IF NOT EXISTS idx_sbar_lists_identifier "
            "ON silver_bar_lists(list_identifier)"
        ),
    }
    failures: list[str] = []
    for position, (name, statement) in enumerate(mandatory_indexes.items()):
        savepoint = f"schema_index_{position}"
        cursor.execute(f"SAVEPOINT {savepoint}")
        try:
            cursor.execute(statement)
        except sqlite3.Error as exc:
            cursor.execute(f"ROLLBACK TO {savepoint}")
            failures.append(f"{name}: {exc}")
        finally:
            cursor.execute(f"RELEASE {savepoint}")

    try:
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_items_code_upper "
            "ON items(UPPER(code))"
        )
    except sqlite3.Error as exc:
        logger.warning(
            "Optional case-insensitive item-code uniqueness index was skipped: %s",
            exc,
        )

    if failures:
        raise sqlite3.OperationalError(
            "Mandatory index creation failed: " + "; ".join(failures)
        )
    logger.info("Database indexes staged.")


def _validate_schema(db: "DatabaseManager") -> None:
    cursor = db.cursor
    assert cursor is not None

    required_columns = {
        "items": {"code", "name", "purity", "wage_type", "wage_rate", "tunch"},
        "estimates": {
            "voucher_no",
            "voucher_no_int",
            "date",
            "total_gross",
            "total_net",
        },
        "estimate_items": {"voucher_no", "wage_type", "line_key"},
        "silver_bars": {
            "bar_id",
            "weight",
            "status",
            "list_id",
            "source_line_key",
        },
        "silver_bar_lists": {"list_id", "list_identifier", "issued_date"},
        "bar_transfers": {"id", "silver_bar_id"},
    }
    for table_name, expected in required_columns.items():
        cursor.execute(f"PRAGMA table_info({table_name})")
        actual = {str(row["name"]) for row in cursor.fetchall()}
        missing = expected - actual
        if missing:
            raise sqlite3.OperationalError(
                f"Schema validation failed for {table_name}; missing {sorted(missing)}"
            )

    cursor.execute("SELECT MAX(version) FROM schema_version")
    version_row = cursor.fetchone()
    version = int(version_row[0]) if version_row and version_row[0] is not None else 0
    if version != CURRENT_SCHEMA_VERSION:
        raise sqlite3.OperationalError(
            f"Expected schema version {CURRENT_SCHEMA_VERSION}, found {version}."
        )

    cursor.execute("PRAGMA foreign_key_check")
    violations = cursor.fetchall()
    if violations:
        raise sqlite3.IntegrityError(
            f"Foreign-key validation failed with {len(violations)} violation(s)."
        )
