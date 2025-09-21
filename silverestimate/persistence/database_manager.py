#!/usr/bin/env python
import os
import threading  # For async debounced flush
import sqlite3
import tempfile # For temporary decrypted DB file
import traceback
import logging
import time
from datetime import datetime
from silverestimate.security import encryption as crypto_utils
from silverestimate.persistence import migrations as persistence_migrations
from silverestimate.persistence.items_repository import ItemsRepository
from silverestimate.persistence.estimates_repository import EstimatesRepository
from silverestimate.persistence.silver_bars_repository import SilverBarsRepository
from silverestimate.persistence.flush_scheduler import FlushScheduler
from silverestimate.infrastructure.db_session import ConnectionThreadGuard
from silverestimate.infrastructure.item_cache import ItemCacheController

from silverestimate.infrastructure.settings import get_app_settings

# Cryptography imports
from cryptography.exceptions import InvalidTag # To catch decryption errors

# Constants
SALT_KEY = crypto_utils.SALT_SETTINGS_KEY  # Legacy alias for settings key
KDF_ITERATIONS = crypto_utils.DEFAULT_KDF_ITERATIONS  # PBKDF2 iteration count

class DatabaseManager:
    """
    Manages SQLite database operations for the Silver Estimation App,
    including file-level encryption/decryption.
    """

    def __init__(self, db_path, password):
        """
        Initialize the database manager. Decrypts the database to a temporary
        file or creates a new encrypted database if it doesn't exist.
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing DatabaseManager for {db_path}")
        
        self.encrypted_db_path = db_path
        self.password = password
        self.salt = self._get_or_create_salt() # Get or create salt using QSettings
        self.key = self._derive_key(self.password, self.salt)
        self.temp_db_file = None # Will hold the temporary file object
        self.temp_db_path = None # Will hold the temporary file path
        self.conn = None
        self.cursor = None
        self._session = ConnectionThreadGuard(logger=self.logger)
        # Serialize encryption to avoid concurrent writers
        self._encrypt_lock = threading.Lock()
        # Optional UI callbacks (set by UI layer)
        self.on_flush_queued = None
        self.on_flush_done = None
        self._flush_scheduler = FlushScheduler(
            has_connection=lambda: self.conn is not None,
            commit=lambda: self._session.commit_if_owner(self.conn),
            checkpoint=self._checkpoint_wal,
            encrypt=self._encrypt_db,
            logger=self.logger,
            on_queued_getter=lambda: getattr(self, "on_flush_queued", None),
            on_done_getter=lambda: getattr(self, "on_flush_done", None),
        )
        self._item_cache_controller = ItemCacheController(logger=self.logger)

        self._items_repo = None
        self._estimates_repo = None
        self._silver_bars_repo = None

        # Ensure directory for encrypted DB exists
        os.makedirs(os.path.dirname(self.encrypted_db_path), exist_ok=True)

        try:
            # Create a temporary file for the decrypted database
            # delete=False is crucial as sqlite3 needs a path, not an open file handle initially
            self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
            self.temp_db_path = self.temp_db_file.name
            self.temp_db_file.close() # Close the handle, we just need the path

            # Store temp path in QSettings for crash recovery on next startup
            try:
                settings = get_app_settings()
                settings.setValue("security/last_temp_db_path", self.temp_db_path)
                settings.sync()
            except Exception as se:
                self.logger.warning(f"Could not store temp DB path for recovery: {se}")

            self.logger.debug(f"Using temporary database at: {self.temp_db_path}")

            # Attempt to decrypt the existing database
            decryption_result = self._decrypt_db()

            if decryption_result == 'success':
                self.logger.info("Database decrypted successfully")
                self._connect_temp_db()
                # Schema setup/migration should still run even on existing DB
                self.setup_database()
            elif decryption_result == 'first_run':
                self.logger.info("Encrypted database not found or empty. Initializing new database.")
                # Salt was created by _get_or_create_salt
                self._connect_temp_db()
                self.setup_database() # Setup schema on the new temp DB
                # No need to encrypt immediately, will happen on close()
            else: # Decryption failed
                self.logger.critical("Database decryption failed. Incorrect password or corrupted file.")
                raise Exception("Database decryption failed. Incorrect password or corrupted file.")

        except Exception as e:
            self.logger.critical(f"Failed to initialize DatabaseManager: {str(e)}", exc_info=True)
            # Cleanup temp file if created
            self._cleanup_temp_db()
            self.conn = None # Ensure connection is None on failure
            raise # Re-raise the exception to halt application startup

    @property
    def items_repo(self):
        """Lazy-load the ItemsRepository instance."""
        if self._items_repo is None:
            self._items_repo = ItemsRepository(self)
        return self._items_repo

    @property
    def estimates_repo(self):
        """Lazy-load the EstimatesRepository instance."""
        if self._estimates_repo is None:
            self._estimates_repo = EstimatesRepository(self)
        return self._estimates_repo

    @property
    def silver_bars_repo(self):
        """Lazy-load the SilverBarsRepository instance."""
        if self._silver_bars_repo is None:
            self._silver_bars_repo = SilverBarsRepository(self)
        return self._silver_bars_repo

    @property
    def item_cache_controller(self):
        return self._item_cache_controller

    def _connect_temp_db(self):
        """Connects sqlite3 to the temporary database file."""
        if not self.temp_db_path:
             raise Exception("Temporary database path not set.")
        try:
            self.logger.debug("Connecting to temporary database")
            self.conn = sqlite3.connect(self.temp_db_path)
            # Record the owning thread for this connection
            self._session.attach_to_current_thread()
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.row_factory = sqlite3.Row
            # Prepared cursors for hot statements
            self._c_get_item_by_code = None
            self._c_insert_estimate_item = None
            # Performance-oriented PRAGMAs (connection-scoped)
            try:
                self.conn.execute("PRAGMA journal_mode=WAL")
                self.conn.execute("PRAGMA synchronous=NORMAL")
                self.conn.execute("PRAGMA temp_store=MEMORY")
                self.conn.execute("PRAGMA cache_size=-20000")  # ~20MB page cache
                try:
                    # Best-effort: enable memory mapping for faster I/O if supported
                    self.conn.execute("PRAGMA mmap_size=268435456")  # 256 MB
                except Exception:
                    pass
                # Log critical PRAGMA values to confirm they are applied
                try:
                    for p in ("journal_mode", "synchronous", "temp_store", "cache_size"):
                        cur = self.conn.execute(f"PRAGMA {p}")
                        row = cur.fetchone()
                        val = row[0] if row and len(row) > 0 else None
                        self.logger.debug(f"PRAGMA {p} = {val}")
                except Exception:
                    pass
            except Exception as e:
                # Non-fatal; continue with defaults if any PRAGMA fails
                self.logger.warning(f"One or more PRAGMA settings failed: {e}")
            self.cursor = self.conn.cursor()
            # Initialize prepared cursors
            try:
                self._c_get_item_by_code = self.conn.cursor()
                self._sql_get_item_by_code = 'SELECT * FROM items WHERE code = ? COLLATE NOCASE'
            except Exception:
                self._c_get_item_by_code = None
                self._sql_get_item_by_code = None
            try:
                self._c_insert_estimate_item = self.conn.cursor()
                self._sql_insert_estimate_item = (
                    'INSERT INTO estimate_items '
                    '(voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
                )
            except Exception:
                self._c_insert_estimate_item = None
                self._sql_insert_estimate_item = None
            self.logger.debug("Connected to temporary database")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to temporary database: {str(e)}", exc_info=True)
            self.conn = None
            self.cursor = None
            try:
                self._session.clear()
            except Exception:
                pass
            raise

    def _get_or_create_salt(self):
        """Retrieves the salt from QSettings or creates and saves a new one."""
        settings = get_app_settings()
        return crypto_utils.get_or_create_salt(settings, logger=self.logger)

    def _derive_key(self, password, salt):
        """Derives a 32-byte AES key from the password and salt using PBKDF2."""
        return crypto_utils.derive_key(password, salt, iterations=KDF_ITERATIONS, logger=self.logger)

    def _encrypt_db(self):
        """Encrypt the temporary DB file and atomically save it to the encrypted path."""
        lock = getattr(self, '_encrypt_lock', None)
        if lock is None:
            self._encrypt_lock = threading.Lock()
            lock = self._encrypt_lock
        lock.acquire()
        try:
            if not self.conn or not self.temp_db_path or not os.path.exists(self.temp_db_path):
                self.logger.warning("Encryption skipped: No active connection or temporary DB file.")
                return False
            if not self.key:
                self.logger.warning("Encryption skipped: No encryption key available.")
                return False

            # Ensure any pending writes are flushed to the temp DB before reading
            if not self._session.commit_if_owner(self.conn):
                # If commit failed on owner thread, abort. If called from a non-owner thread,
                # commit_if_owner() returns True after skipping, so encryption can proceed.
                return False

            # If connection uses WAL, checkpoint it so the main DB file reflects latest state
            try:
                self._checkpoint_wal()
            except Exception:
                pass

            self.logger.info(f"Encrypting database to {self.encrypted_db_path}")
            start_time = time.time()
            tmp_out_path = f"{self.encrypted_db_path}.new"
            snapshot_path = None
            try:
                # Create a consistent snapshot copy using SQLite backup API
                snapshot_path = self._snapshot_temp_db_copy()
                source_path = snapshot_path if snapshot_path else self.temp_db_path

                with open(source_path, 'rb') as f_in:
                    plaintext = f_in.read()

                payload = crypto_utils.encrypt_payload(plaintext, self.key, logger=self.logger)

                # Write to a temp file first
                with open(tmp_out_path, 'wb') as f_out:
                    f_out.write(payload)
                    try:
                        f_out.flush()
                        os.fsync(f_out.fileno())
                    except Exception:
                        # fsync best-effort; ignore on platforms where not applicable
                        pass

                # Atomically replace the target
                os.replace(tmp_out_path, self.encrypted_db_path)

                duration = time.time() - start_time
                self.logger.info(f"Database encrypted successfully in {duration:.2f} seconds")
                return True
            except Exception as e:
                self.logger.error(f"Database encryption failed: {str(e)}", exc_info=True)
                # Clean up partial .new file but never delete the existing encrypted DB
                try:
                    if os.path.exists(tmp_out_path):
                        os.remove(tmp_out_path)
                except OSError as oe:
                    self.logger.warning(f"Could not remove temporary encrypted file '{tmp_out_path}': {str(oe)}")
                return False
            finally:
                # Remove snapshot file if created
                try:
                    if snapshot_path and os.path.exists(snapshot_path):
                        os.remove(snapshot_path)
                except Exception:
                    pass
        finally:
            try:
                lock.release()
            except Exception:
                pass

    def reencrypt_with_new_password(self, new_password: str) -> bool:
        """Re-encrypt the encrypted DB using a new password-derived key.

        Writes atomically to the encrypted store. On success, updates in-memory
        password/key so subsequent flushes use the new key. On failure, keeps
        the old key/password and returns False.
        """
        try:
            if not new_password:
                raise ValueError("New password cannot be empty.")
            # Derive new key using existing salt
            new_key = self._derive_key(new_password, self.salt)
            # Ensure latest state is committed and visible in main DB file
            try:
                self._session.commit_if_owner(self.conn)
            except Exception:
                pass
            try:
                self._checkpoint_wal()
            except Exception:
                pass
            # Swap key temporarily for encryption
            old_key, old_password = self.key, self.password
            self.key, self.password = new_key, new_password
            success = False
            try:
                success = self._encrypt_db()
            finally:
                if not success:
                    # Restore old credentials on failure
                    self.key, self.password = old_key, old_password
            if success:
                try:
                    self.logger.info("Database re-encrypted with new password.")
                except Exception:
                    pass
            return success
        except Exception as e:
            try:
                self.logger.error(f"Re-encryption failed: {e}", exc_info=True)
            except Exception:
                pass
            return False

    def _decrypt_db(self):
        """Decrypts the database file to the temporary path. Returns status."""
        if not os.path.exists(self.encrypted_db_path):
            self.logger.info("Encrypted database file not found")
            return 'first_run'
        if os.path.getsize(self.encrypted_db_path) <= 12: # Nonce size is 12
             self.logger.warning("Encrypted database file is empty or too small")
             # Treat as first run, existing empty/corrupt file will be overwritten on close.
             return 'first_run'
        if not self.key:
             self.logger.error("Decryption skipped: No encryption key available")
             return 'error'

        self.logger.info("Decrypting database to temporary location")
        start_time = time.time()
        try:
            with open(self.encrypted_db_path, 'rb') as f_in:
                payload = f_in.read()

            plaintext = crypto_utils.decrypt_payload(payload, self.key, logger=self.logger)

            with open(self.temp_db_path, 'wb') as f_out:
                f_out.write(plaintext)

            duration = time.time() - start_time
            self.logger.info(f"Database decrypted successfully in {duration:.2f} seconds")
            return 'success'
        except InvalidTag:
            self.logger.error("Decryption failed: Invalid password or corrupted data (InvalidTag)")
            self._cleanup_temp_db(keep_file=True)
            return 'error'
        except Exception as e:
            self.logger.error(f"Database decryption failed: {str(e)}", exc_info=True)
            self._cleanup_temp_db(keep_file=True)
            return 'error'

    def _cleanup_temp_db(self, keep_file=False):
         """Safely deletes the temporary database file."""
         path_to_delete = self.temp_db_path
         if path_to_delete and os.path.exists(path_to_delete):
              try:
                   self.logger.debug(f"Cleaning up temporary database: {path_to_delete}")
                   os.remove(path_to_delete)
                   if not keep_file:
                        self.temp_db_path = None
                        self.temp_db_file = None
                   self.logger.debug("Temporary database file deleted")
              except OSError as e:
                   self.logger.warning(f"Could not delete temporary database file '{path_to_delete}': {str(e)}")
         elif not keep_file:
              self.temp_db_path = None
              self.temp_db_file = None


    def _table_exists(self, table_name):
        """Check if a table exists in the database."""
        if not self.cursor: return False # Handle case where connection failed
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return self.cursor.fetchone() is not None

    def _column_exists(self, table_name, column_name):
        """Check if a column exists in a table."""
        if not self.cursor: return False
        if not self._table_exists(table_name):
            return False
        try:
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            return any(col['name'] == column_name for col in self.cursor.fetchall())
        except sqlite3.Error as e:
             self.logger.error(f"Error checking column {table_name}.{column_name}: {str(e)}", exc_info=True)
             return False

    def _is_column_unique(self, table_name, column_name):
        """Check if a column has a UNIQUE constraint via PK or unique index."""
        if not self.cursor:
            return False
        if not self._column_exists(table_name, column_name):
            return False
        try:
            # Primary key implies uniqueness
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            for col in self.cursor.fetchall():
                if col['name'] == column_name and int(col['pk']) == 1:
                    return True

            # Check separate UNIQUE indexes
            self.cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = self.cursor.fetchall()
            for index in indexes:
                if int(index['unique']) == 1:
                    self.cursor.execute(f"PRAGMA index_info({index['name']})")
                    idx_cols = self.cursor.fetchall()
                    if len(idx_cols) == 1 and idx_cols[0]['name'] == column_name:
                        return True
            return False
        except sqlite3.Error as e:
            self.logger.error(f"Error checking unique constraint for {table_name}.{column_name}: {str(e)}", exc_info=True)
            return False

    def _check_schema_version(self):
        """Check if the database has the schema version table and current version."""
        if not self.cursor: return 0 # Assume version 0 if no connection
        try:
            # Check if schema_version table exists
            if not self._table_exists('schema_version'):
                # Create schema_version table if it doesn't exist
                self.logger.info("Creating schema_version table...")
                self.cursor.execute('''
                    CREATE TABLE schema_version (
                        id INTEGER PRIMARY KEY,
                        version INTEGER NOT NULL,
                        applied_date TEXT NOT NULL
                    )
                ''')
                # Insert initial version 0
                self.cursor.execute('''
                    INSERT INTO schema_version (version, applied_date)
                    VALUES (0, ?)
                ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
                self.conn.commit()
                self.logger.info("Initialized schema version to 0.")
                return 0
            else:
                # Get current version if table exists
                self.cursor.execute("SELECT MAX(version) FROM schema_version")
                result = self.cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.Error as e:
            self.logger.error(f"Error checking schema version: {str(e)}", exc_info=True)
            return 0  # Assume version 0 on error

    def _update_schema_version(self, new_version):
        """Update the schema version in the database."""
        if not self.cursor: return False
        try:
            self.cursor.execute('''
                INSERT INTO schema_version (version, applied_date)
                VALUES (?, ?)
            ''', (new_version, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            self.conn.commit()
            self.logger.info(f"Schema updated to version {new_version}")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"Error updating schema version: {str(e)}", exc_info=True)
            self.conn.rollback()
            return False

    def setup_database(self):
        """Create/update the necessary tables in the temporary database."""
        persistence_migrations.run_schema_setup(self)

    # --- Item Methods ---
    # Add connection checks to all data access methods
    def get_item_by_code(self, code):
        return self.items_repo.get_item_by_code(code)

    def start_preload_item_cache(self):
        """Warm up the item cache off the UI thread using a separate connection."""
        controller = getattr(self, "_item_cache_controller", None)
        if not controller:
            return
        controller.start_preload(self.temp_db_path)

    def search_items(self, search_term):
        return self.items_repo.search_items(search_term)

    def get_all_items(self):
        return self.items_repo.get_all_items()

    def add_item(self, code, name, purity, wage_type, wage_rate):
        return self.items_repo.add_item(code, name, purity, wage_type, wage_rate)

    def update_item(self, code, name, purity, wage_type, wage_rate):
        return self.items_repo.update_item(code, name, purity, wage_type, wage_rate)

    def delete_item(self, code):
        return self.items_repo.delete_item(code)

    # --- Estimate Methods ---
    def get_estimate_by_voucher(self, voucher_no):
        return self.estimates_repo.get_estimate_by_voucher(voucher_no)

    def get_estimates(self, date_from=None, date_to=None, voucher_search=None):
        return self.estimates_repo.get_estimates(date_from=date_from, date_to=date_to, voucher_search=voucher_search)

    def get_estimate_headers(self, date_from=None, date_to=None, voucher_search=None):
        return self.estimates_repo.get_estimate_headers(date_from=date_from, date_to=date_to, voucher_search=voucher_search)

    def generate_voucher_no(self):
        return self.estimates_repo.generate_voucher_no()

    def save_estimate_with_returns(self, voucher_no, date, silver_rate, regular_items, return_items, totals):
        return self.estimates_repo.save_estimate_with_returns(voucher_no, date, silver_rate, regular_items, return_items, totals)

    def delete_all_estimates(self):
        return self.estimates_repo.delete_all_estimates()

    def delete_single_estimate(self, voucher_no):
        return self.estimates_repo.delete_single_estimate(voucher_no)

    # --- Silver Bar Methods (Overhauled) ---
    def _generate_list_identifier(self):
        return self.silver_bars_repo.generate_list_identifier()

    def create_silver_bar_list(self, note=None):
        return self.silver_bars_repo.create_list(note)

    def get_silver_bar_lists(self, include_issued=True):
        return self.silver_bars_repo.get_lists(include_issued)

    def get_silver_bar_list_details(self, list_id):
        return self.silver_bars_repo.get_list_details(list_id)

    def update_silver_bar_list_note(self, list_id, new_note):
        return self.silver_bars_repo.update_list_note(list_id, new_note)

    def delete_silver_bar_list(self, list_id):
        return self.silver_bars_repo.delete_list(list_id)

    def assign_bar_to_list(self, bar_id, list_id, note="Assigned to list", perform_commit=True):
        return self.silver_bars_repo.assign_bar_to_list(bar_id, list_id, note=note, perform_commit=perform_commit)

    def remove_bar_from_list(self, bar_id, note="Removed from list", perform_commit=True):
        return self.silver_bars_repo.remove_bar_from_list(bar_id, note=note, perform_commit=perform_commit)

    def get_bars_in_list(self, list_id):
        return self.silver_bars_repo.get_bars_in_list(list_id)

    def get_available_bars(self):
        return self.silver_bars_repo.get_available_bars()

    def add_silver_bar(self, estimate_voucher_no, weight, purity):
        return self.silver_bars_repo.add_silver_bar(estimate_voucher_no, weight, purity)

    def update_silver_bar_values(self, bar_id, weight, purity):
        return self.silver_bars_repo.update_silver_bar_values(bar_id, weight, purity)

    def get_silver_bars(self, status=None, weight_query=None, estimate_voucher_no=None, weight_tolerance=0.001, min_purity=None, max_purity=None, date_range=None):
        return self.silver_bars_repo.get_silver_bars(
            status=status,
            weight_query=weight_query,
            estimate_voucher_no=estimate_voucher_no,
            weight_tolerance=weight_tolerance,
            min_purity=min_purity,
            max_purity=max_purity,
            date_range=date_range,
        )

    def delete_silver_bars_for_estimate(self, voucher_no):
        return self.silver_bars_repo.delete_silver_bars_for_estimate(voucher_no)

    # --- Utility Methods ---
    def drop_tables(self):
        """Drops all known application tables from the temporary database."""
        if not self.conn or not self.cursor: return False
        # Added schema_version to the list
        tables = ['estimate_items', 'estimates', 'items', 'bar_transfers', 'silver_bars', 'silver_bar_lists', 'schema_version']
        try:
            self.logger.warning("Dropping all application tables from database")
            self.conn.execute('BEGIN TRANSACTION')
            for table in tables:
                self.logger.debug(f"Dropping table {table}")
                self.cursor.execute(f'DROP TABLE IF EXISTS {table}')
            self.conn.commit()
            self.logger.info("All application tables dropped successfully")
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"Database error dropping tables: {str(e)}", exc_info=True)
            return False

    def close(self):
        """Encrypts the temporary DB, closes the connection, and cleans up."""
        # Cancel pending flush work before encrypting on shutdown
        try:
            scheduler = getattr(self, "_flush_scheduler", None)
            if scheduler:
                scheduler.shutdown()
        except Exception:
            pass

        encrypt_success = False
        encryption_attempted = False
        if self.conn:
            self.logger.info("Closing database connection and encrypting data")
            encryption_attempted = True
            # Encrypt the current temporary DB back to the original file
            try:
                encrypt_success = self._encrypt_db()
            except Exception:
                encrypt_success = False
            if encrypt_success:
                self.logger.info("Temporary database encrypted successfully")
            else:
                # This is critical - data might be lost if encryption fails!
                # Keep the temp file for potential manual recovery
                self.logger.critical("Failed to encrypt database on close!")
                self.logger.critical(f"The unencrypted data might still be in: {self.temp_db_path}")

            # Close the connection to the temporary DB
            try:
                self.conn.close()
                self.conn = None
                self.cursor = None
                try:
                    self._session.clear()
                except Exception:
                    pass
                self.logger.debug("Database connection closed")
            except sqlite3.Error as e:
                self.logger.error(f"Error closing SQLite connection: {str(e)}", exc_info=True)
        else:
            self.logger.debug("No active database connection to close")

        # Only delete the temporary file when encryption succeeded; otherwise, keep for recovery
        try:
            if encrypt_success:
                self._cleanup_temp_db()
                # Clear stored temp path after successful encryption and cleanup
                try:
                    settings = get_app_settings()
                    settings.remove("security/last_temp_db_path")
                    settings.sync()
                except Exception as se:
                    self.logger.warning(f"Could not clear stored temp DB path: {se}")
            elif encryption_attempted:
                self.logger.critical("Preserving temporary database file due to encryption failure.")
            else:
                # No encryption attempt (already closed earlier); nothing to report.
                pass
        except Exception as e:
            self.logger.warning(f"Cleanup decision failed: {str(e)}")

    def flush_to_encrypted(self):
        """Flush current temp DB state to encrypted file safely (atomic replace)."""
        if not self.conn:
            self.logger.warning("flush_to_encrypted skipped: No active connection.")
            return False
        # Ensure all changes are committed before encryption (only on owner thread)
        if not self._session.commit_if_owner(self.conn):
            return False
        # Best-effort WAL checkpoint
        try:
            self._checkpoint_wal()
        except Exception:
            pass
        return self._encrypt_db()

    def request_flush(self, delay_seconds: float = 2.0):
        """Debounce and asynchronously flush the temp DB to the encrypted file."""
        scheduler = getattr(self, "_flush_scheduler", None)
        if not scheduler:
            return
        scheduler.schedule(delay_seconds=delay_seconds)

    # --- Startup Recovery Utilities ---
    def _snapshot_temp_db_copy(self):
        """Create a consistent snapshot of the temp DB using SQLite backup API.

        Returns path to the snapshot file, or None if backup failed.
        """
        if not self.temp_db_path:
            return None
        try:
            import sqlite3 as _sqlite3, tempfile as _tempfile
            # Prepare destination temporary file path
            tmp = _tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
            snapshot_path = tmp.name
            tmp.close()
            # Open a read-only connection to source DB (separate from main connection)
            try:
                src = _sqlite3.connect(f"file:{self.temp_db_path}?mode=ro", uri=True, timeout=5)
            except Exception:
                # Fallback to a normal connection if URI not supported
                src = _sqlite3.connect(self.temp_db_path, timeout=5)
            dest = _sqlite3.connect(snapshot_path, timeout=5)
            try:
                src.backup(dest)
            finally:
                try:
                    dest.close()
                except Exception:
                    pass
                try:
                    src.close()
                except Exception:
                    pass
            return snapshot_path
        except Exception as e:
            try:
                self.logger.debug(f"Snapshot backup failed or skipped: {e}")
            except Exception:
                pass
            # Best-effort: return None to fall back to direct file read
            return None
    def _checkpoint_wal(self):
        """Force a WAL checkpoint so the main DB file contains latest data.

        Uses a short-lived separate connection so it is safe from any thread.
        """
        if not self.temp_db_path:
            return False
        try:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(self.temp_db_path, timeout=5)
            try:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            finally:
                conn.close()
            return True
        except Exception as e:
            try:
                self.logger.debug(f"WAL checkpoint skipped/failed: {e}")
            except Exception:
                pass
            return False
    @staticmethod
    def _get_or_create_salt_static(logger=None):
        settings = get_app_settings()
        return crypto_utils.get_or_create_salt(settings, logger=logger)

    @staticmethod
    def check_recovery_candidate(encrypted_db_path):
        """Return path to prior temp DB if it exists and is newer than encrypted file."""
        settings = get_app_settings()
        temp_path = settings.value("security/last_temp_db_path")
        if not temp_path or not isinstance(temp_path, str):
            return None
        if not os.path.exists(temp_path):
            return None
        try:
            enc_exists = os.path.exists(encrypted_db_path)
            temp_mtime = os.path.getmtime(temp_path)
            enc_mtime = os.path.getmtime(encrypted_db_path) if enc_exists else 0
            if not enc_exists or temp_mtime > enc_mtime:
                return temp_path
        except Exception:
            return None
        return None

    @staticmethod
    def recover_encrypt_plain_to_encrypted(plain_temp_path, encrypted_db_path, password, logger=None):
        """Encrypt a plaintext SQLite DB file to the encrypted DB atomically using the app's KDF.

        Returns True on success, False otherwise.
        """
        try:
            if not os.path.exists(plain_temp_path):
                if logger: logger.error(f"Recovery failed: temp file not found: {plain_temp_path}")
                return False
            # Derive key with same KDF and salt
            salt = DatabaseManager._get_or_create_salt_static(logger=logger)
            key = crypto_utils.derive_key(password, salt, iterations=KDF_ITERATIONS, logger=logger)

            with open(plain_temp_path, 'rb') as f_in:
                plaintext = f_in.read()

            payload = crypto_utils.encrypt_payload(plaintext, key, logger=logger)

            tmp_out_path = f"{encrypted_db_path}.new"
            with open(tmp_out_path, 'wb') as f_out:
                f_out.write(payload)
                try:
                    f_out.flush(); os.fsync(f_out.fileno())
                except Exception:
                    pass
            os.replace(tmp_out_path, encrypted_db_path)
            if logger: logger.info("Recovered and encrypted temp DB into encrypted store.")
            # Best-effort: remove the plaintext temp file now that it's recovered
            try:
                os.remove(plain_temp_path)
            except Exception:
                pass
            # Clear stored temp path
            try:
                settings = get_app_settings()
                settings.remove("security/last_temp_db_path")
                settings.sync()
            except Exception:
                pass
            return True
        except Exception as e:
            if logger:
                logger.error(f"Recovery encryption failed: {str(e)}", exc_info=True)
            return False










