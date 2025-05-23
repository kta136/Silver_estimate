#!/usr/bin/env python
import os
import sqlite3
import tempfile # For temporary decrypted DB file
import traceback
import base64 # For encoding/decoding salt
import hashlib # For KDF
import logging
import time
from datetime import datetime
from PyQt5.QtCore import QSettings # To store/retrieve salt

# Cryptography imports
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidTag # To catch decryption errors

# Constants
SALT_KEY = "security/db_salt" # QSettings key for the salt
KDF_ITERATIONS = 100000 # Number of iterations for PBKDF2

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

        # Ensure directory for encrypted DB exists
        os.makedirs(os.path.dirname(self.encrypted_db_path), exist_ok=True)

        try:
            # Create a temporary file for the decrypted database
            # delete=False is crucial as sqlite3 needs a path, not an open file handle initially
            self.temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
            self.temp_db_path = self.temp_db_file.name
            self.temp_db_file.close() # Close the handle, we just need the path

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

    def _connect_temp_db(self):
        """Connects sqlite3 to the temporary database file."""
        if not self.temp_db_path:
             raise Exception("Temporary database path not set.")
        try:
            self.logger.debug("Connecting to temporary database")
            self.conn = sqlite3.connect(self.temp_db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.logger.debug("Connected to temporary database")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to connect to temporary database: {str(e)}", exc_info=True)
            self.conn = None
            self.cursor = None
            raise

    def _get_or_create_salt(self):
        """Retrieves the salt from QSettings or creates and saves a new one."""
        settings = QSettings("YourCompany", "SilverEstimateApp")
        salt_b64 = settings.value(SALT_KEY)
        if salt_b64:
            try:
                self.logger.debug("Retrieved existing salt from settings")
                return base64.b64decode(salt_b64)
            except Exception as e:
                 self.logger.warning(f"Failed to decode stored salt: {str(e)}. Generating new salt.")
                 # Fall through to generate new salt if decoding fails

        # Generate, save, and return a new salt
        self.logger.info("Generating new salt and saving to settings")
        new_salt = os.urandom(16) # 16 bytes salt
        settings.setValue(SALT_KEY, base64.b64encode(new_salt).decode('utf-8'))
        settings.sync()
        return new_salt

    def _derive_key(self, password, salt):
        """Derives a 32-byte AES key from the password and salt using PBKDF2HMAC."""
        if not password:
            self.logger.critical("Password cannot be empty for key derivation")
            raise ValueError("Password cannot be empty for key derivation.")
        if not salt:
            self.logger.critical("Salt cannot be empty for key derivation")
            raise ValueError("Salt cannot be empty for key derivation.")
            
        self.logger.debug("Deriving encryption key")
        start_time = time.time()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32, # AES-256 key length
            salt=salt,
            iterations=KDF_ITERATIONS,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))
        duration = time.time() - start_time
        self.logger.debug(f"Encryption key derived in {duration:.2f} seconds")
        return key

    def _encrypt_db(self):
        """Encrypts the temporary DB file and saves it to the original path."""
        if not self.conn or not self.temp_db_path or not os.path.exists(self.temp_db_path):
            self.logger.warning("Encryption skipped: No active connection or temporary DB file.")
            return False
        if not self.key:
             self.logger.warning("Encryption skipped: No encryption key available.")
             return False

        self.logger.info(f"Encrypting database to {self.encrypted_db_path}")
        start_time = time.time()
        try:
            aesgcm = AESGCM(self.key)
            nonce = os.urandom(12) # AES-GCM recommended nonce size

            with open(self.temp_db_path, 'rb') as f_in, open(self.encrypted_db_path, 'wb') as f_out:
                plaintext = f_in.read()
                if not plaintext:
                    self.logger.warning("Temporary database file is empty. Writing empty encrypted file.")
                    # Write nonce even for empty file to maintain structure
                    f_out.write(nonce)
                    # No ciphertext or tag needed
                    return True

                ciphertext = aesgcm.encrypt(nonce, plaintext, None) # No associated data

                # Write nonce first, then ciphertext (which includes the tag)
                f_out.write(nonce)
                f_out.write(ciphertext)
                
            duration = time.time() - start_time
            self.logger.info(f"Database encrypted successfully in {duration:.2f} seconds")
            return True
        except Exception as e:
            self.logger.error(f"Database encryption failed: {str(e)}", exc_info=True)
            # Attempt to delete potentially corrupted encrypted file
            try:
                if os.path.exists(self.encrypted_db_path):
                    os.remove(self.encrypted_db_path)
                    self.logger.info(f"Deleted potentially corrupted encrypted file: {self.encrypted_db_path}")
            except OSError as oe:
                 self.logger.warning(f"Could not delete potentially corrupted encrypted file '{self.encrypted_db_path}': {str(oe)}")
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

        self.logger.info(f"Decrypting database to temporary location")
        start_time = time.time()
        try:
            aesgcm = AESGCM(self.key)
            with open(self.encrypted_db_path, 'rb') as f_in, open(self.temp_db_path, 'wb') as f_out:
                nonce = f_in.read(12) # Read the 12-byte nonce
                ciphertext = f_in.read() # Read the rest (ciphertext + tag)

                if not nonce or len(nonce) != 12:
                     self.logger.error("Invalid encrypted file format: Nonce missing or incorrect size")
                     raise ValueError("Invalid encrypted file format: Nonce missing or incorrect size.")
                if not ciphertext:
                     self.logger.error("Invalid encrypted file format: Ciphertext missing")
                     raise ValueError("Invalid encrypted file format: Ciphertext missing.")

                plaintext = aesgcm.decrypt(nonce, ciphertext, None)
                f_out.write(plaintext)
                
            duration = time.time() - start_time
            self.logger.info(f"Database decrypted successfully in {duration:.2f} seconds")
            return 'success'
        except InvalidTag:
            self.logger.error("Decryption failed: Invalid password or corrupted data (InvalidTag)")
            # Clean up potentially partially written temp file
            self._cleanup_temp_db(keep_file=True) # Keep the empty file handle, just clear content
            return 'error'
        except Exception as e:
            self.logger.error(f"Database decryption failed: {str(e)}", exc_info=True)
            # Clean up potentially partially written temp file
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
        """Check if a column has a UNIQUE constraint (via implicit index)."""
        if not self.cursor: return False
        if not self._column_exists(table_name, column_name):
            return False
        try:
            # Check UNIQUE constraints defined directly on the column
            self.cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = self.cursor.fetchall()
            for col in columns_info:
                if col['name'] == column_name and col['unique'] == 1: # Check the 'unique' flag from table_info
                    return True

            # Check separate UNIQUE indexes
            self.cursor.execute(f"PRAGMA index_list({table_name})")
            indexes = self.cursor.fetchall()
            for index in indexes:
                if index['unique'] == 1:
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
        if not self.conn or not self.cursor:
            self.logger.warning("Database setup skipped: No active connection.")
            return

        self.logger.info("Starting database setup check...")
        try:
            # Check current schema version
            current_version = self._check_schema_version()
            self.logger.info(f"Current database schema version: {current_version}")
            
            self.conn.execute('BEGIN TRANSACTION')  # Use transaction for schema changes

            # --- Core Tables (Items, Estimates, Estimate Items) ---
            # These are always created if they don't exist
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    code TEXT PRIMARY KEY, name TEXT NOT NULL, purity REAL DEFAULT 0,
                    wage_type TEXT DEFAULT 'P', wage_rate REAL DEFAULT 0
                )''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS estimates (
                    voucher_no TEXT PRIMARY KEY, date TEXT NOT NULL, silver_rate REAL DEFAULT 0,
                    total_gross REAL DEFAULT 0, total_net REAL DEFAULT 0,
                    total_fine REAL DEFAULT 0, total_wage REAL DEFAULT 0,
                    note TEXT,
                    last_balance_silver REAL DEFAULT 0,
                    last_balance_amount REAL DEFAULT 0
                )''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS estimate_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, voucher_no TEXT, item_code TEXT,
                    item_name TEXT, gross REAL DEFAULT 0, poly REAL DEFAULT 0, net_wt REAL DEFAULT 0,
                    purity REAL DEFAULT 0, wage_rate REAL DEFAULT 0, pieces INTEGER DEFAULT 1,
                    wage REAL DEFAULT 0, fine REAL DEFAULT 0, is_return INTEGER DEFAULT 0,
                    is_silver_bar INTEGER DEFAULT 0,
                    FOREIGN KEY (voucher_no) REFERENCES estimates (voucher_no) ON DELETE CASCADE,
                    FOREIGN KEY (item_code) REFERENCES items (code) ON DELETE SET NULL
                )''')

            # --- Silver Bar Related Tables ---
            # Only perform the schema migration if we're at version 0
            if current_version < 1:
                self.logger.info("Performing silver bar schema migration to version 1...")
                
                # 1. Drop dependent table first if it exists
                if self._table_exists('bar_transfers'):
                    self.logger.info("Dropping existing 'bar_transfers' table...")
                    self.cursor.execute('DROP TABLE bar_transfers')

                # 2. Drop old silver_bars table if it exists
                if self._table_exists('silver_bars'):
                    self.logger.info("Dropping existing 'silver_bars' table...")
                    self.cursor.execute('DROP TABLE silver_bars')

                # 3. Create/Ensure silver_bar_lists table exists (dependency for silver_bars)
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS silver_bar_lists (
                        list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        list_identifier TEXT UNIQUE NOT NULL,
                        creation_date TEXT NOT NULL,
                        list_note TEXT
                    )''')
                if not self._table_exists('silver_bar_lists'):
                    self.logger.info("Created 'silver_bar_lists' table.")

                # 4. Create the NEW silver_bars table
                self.logger.info("Creating new 'silver_bars' table with updated schema...")
                self.cursor.execute('''
                    CREATE TABLE silver_bars (
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
                    )''')
                self.logger.info("Created 'silver_bars' table.")

                # 5. Create the NEW bar_transfers table
                self.logger.info("Creating new 'bar_transfers' table with updated schema...")
                self.cursor.execute('''
                     CREATE TABLE bar_transfers (
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
                     )''')
                self.logger.info("Created 'bar_transfers' table.")
                
                # Update schema version to 1
                self._update_schema_version(1)
            else:
                self.logger.info("Silver bar schema is already at version 1 or higher. No migration needed.")
                
                # Ensure tables exist (without dropping)
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS silver_bar_lists (
                        list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        list_identifier TEXT UNIQUE NOT NULL,
                        creation_date TEXT NOT NULL,
                        list_note TEXT
                    )''')
                    
                self.cursor.execute('''
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
                    )''')
                    
                self.cursor.execute('''
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
                     )''')

            # Check if the note column exists in the estimates table
            if not self._column_exists('estimates', 'note'):
                self.logger.info("Adding 'note' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN note TEXT')
                
            # Check if the last_balance columns exist in the estimates table
            if not self._column_exists('estimates', 'last_balance_silver'):
                self.logger.info("Adding 'last_balance_silver' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN last_balance_silver REAL DEFAULT 0')
                
            if not self._column_exists('estimates', 'last_balance_amount'):
                self.logger.info("Adding 'last_balance_amount' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN last_balance_amount REAL DEFAULT 0')
            
            self.conn.commit()
            self.logger.info("Database schema setup/update complete.")

        except sqlite3.Error as e:
            self.logger.critical(f"FATAL Database setup error: {str(e)}", exc_info=True)
            self.conn.rollback()  # Rollback transaction on error
            raise e  # Re-raise critical error

    # --- Item Methods ---
    # Add connection checks to all data access methods
    def get_item_by_code(self, code):
        if not self.cursor: return None
        try: self.cursor.execute('SELECT * FROM items WHERE LOWER(code) = LOWER(?)', (code,)); return self.cursor.fetchone()
        except sqlite3.Error as e:
            self.logger.error(f"DB Error get_item_by_code: {str(e)}", exc_info=True)
            return None

    def search_items(self, search_term):
        if not self.cursor: return []
        try:
            search_pattern = f"%{search_term}%"
            self.cursor.execute('SELECT * FROM items WHERE LOWER(code) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?) ORDER BY code', (search_pattern, search_pattern)); return self.cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"DB Error search_items: {str(e)}", exc_info=True)
            return []

    def get_all_items(self):
        if not self.cursor: return []
        try: self.cursor.execute('SELECT * FROM items ORDER BY code'); return self.cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"DB Error get_all_items: {str(e)}", exc_info=True)
            return []

    def add_item(self, code, name, purity, wage_type, wage_rate):
        if not self.conn or not self.cursor: return False
        try: self.cursor.execute('INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)', (code, name, purity, wage_type, wage_rate)); self.conn.commit(); return True
        except sqlite3.Error as e:
            self.logger.error(f"DB Error adding item: {str(e)}", exc_info=True)
            self.conn.rollback()
            return False

    def update_item(self, code, name, purity, wage_type, wage_rate):
        if not self.conn or not self.cursor: return False
        try: self.cursor.execute('UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ?', (name, purity, wage_type, wage_rate, code)); self.conn.commit(); return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"DB Error updating item: {str(e)}", exc_info=True)
            self.conn.rollback()
            return False

    def delete_item(self, code):
        if not self.conn or not self.cursor: return False
        try: self.cursor.execute('DELETE FROM items WHERE code = ?', (code,)); self.conn.commit(); return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"DB Error deleting item: {str(e)}", exc_info=True)
            self.conn.rollback()
            return False

    # --- Estimate Methods ---
    def get_estimate_by_voucher(self, voucher_no):
        """
        Get an estimate by its voucher number with improved error handling.
        Returns a dictionary with 'header' and 'items' keys, or None if not found.
        """
        if not self.cursor or not self.conn:
            self.logger.error(f"Cannot get estimate {voucher_no}: No active database connection")
            return None
            
        # Use a transaction to ensure consistency
        try:
            # Start a transaction
            self.conn.execute('BEGIN TRANSACTION')
            
            # Get the estimate header
            self.cursor.execute('SELECT * FROM estimates WHERE voucher_no = ?', (voucher_no,))
            estimate = self.cursor.fetchone()
            
            if not estimate:
                self.conn.rollback()
                return None
                
            # Get the estimate items
            self.cursor.execute('SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY is_return, is_silver_bar, id', (voucher_no,))
            items = self.cursor.fetchall()
            
            # Convert to dictionaries
            result = {
                'header': dict(estimate),
                'items': [dict(item) for item in items]
            }
            
            # Commit the transaction
            self.conn.commit()
            return result
            
        except sqlite3.Error as e:
            # Roll back the transaction on error
            if self.conn:
                self.conn.rollback()
            self.logger.error(f"DB Error getting estimate {voucher_no}: {str(e)}", exc_info=True)
            return None
        except Exception as e:
            # Roll back the transaction on any other error
            if self.conn:
                self.conn.rollback()
            self.logger.error(f"Unexpected error getting estimate {voucher_no}: {str(e)}", exc_info=True)
            return None

    def get_estimates(self, date_from=None, date_to=None, voucher_search=None):
        """Fetches estimate headers and their associated items based on filters."""
        if not self.cursor: return []
        query = "SELECT * FROM estimates WHERE 1=1"; params = []
        if date_from: query += " AND date >= ?"; params.append(date_from)
        if date_to: query += " AND date <= ?"; params.append(date_to)
        if voucher_search: query += " AND voucher_no LIKE ?"; params.append(f"%{voucher_search}%")
        # Changed to sort by voucher_no as integer in descending order
        # For numeric voucher numbers, cast to integer for proper sorting
        query += " ORDER BY CAST(voucher_no AS INTEGER) DESC"
        results = []
        try:
            self.cursor.execute(query, params)
            estimate_headers = self.cursor.fetchall()
            for header in estimate_headers:
                voucher_no = header['voucher_no']
                self.cursor.execute('SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY id', (voucher_no,))
                items = self.cursor.fetchall()
                results.append({'header': dict(header), 'items': [dict(item) for item in items]})
            return results
        except sqlite3.Error as e:
            self.logger.error(f"DB Error getting estimates: {str(e)}", exc_info=True)
            return []

    def generate_voucher_no(self):
        """Generates the next sequential voucher number (simple integer increment)."""
        if not self.cursor: return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}" # Error if no cursor
        next_voucher_no = 1
        try:
            # Find the highest existing numeric voucher number
            self.cursor.execute("SELECT MAX(CAST(voucher_no AS INTEGER)) FROM estimates WHERE voucher_no GLOB '[0-9]*'")
            result = self.cursor.fetchone()
            if result and result[0] is not None:
                try:
                    next_voucher_no = int(result[0]) + 1
                except (ValueError, TypeError):
                    self.logger.warning(f"Could not parse max voucher number '{result[0]}' as integer. Starting from 1.")
                    # Fallback to 1 if parsing fails, though the query should prevent this
                    next_voucher_no = 1
            # If no numeric voucher exists or table is empty, next_voucher_no remains 1
            return str(next_voucher_no)
        except sqlite3.Error as e:
            self.logger.error(f"DB error generating voucher number: {str(e)}", exc_info=True)
            # Fallback to a timestamp-based error string if DB query fails
            return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def save_estimate_with_returns(self, voucher_no, date, silver_rate, regular_items, return_items, totals):
        if not self.conn or not self.cursor: return False
        try:
            self.conn.execute('BEGIN TRANSACTION')

            # Check if estimate exists
            self.cursor.execute('SELECT 1 FROM estimates WHERE voucher_no = ?', (voucher_no,))
            estimate_exists = self.cursor.fetchone() is not None
            
            # Get note and last balance from totals dictionary
            note = totals.get('note', '')
            last_balance_silver = totals.get('last_balance_silver', 0.0)
            last_balance_amount = totals.get('last_balance_amount', 0.0)
            
            # Use UPDATE instead of INSERT OR REPLACE to avoid triggering ON DELETE CASCADE
            if estimate_exists:
                self.logger.info(f"Updating existing estimate {voucher_no} (preserving silver bars)")
                self.cursor.execute('''
                    UPDATE estimates
                    SET date = ?, silver_rate = ?, total_gross = ?, total_net = ?,
                        total_fine = ?, total_wage = ?, note = ?,
                        last_balance_silver = ?, last_balance_amount = ?
                    WHERE voucher_no = ?
                ''', (date, silver_rate,
                     totals.get('total_gross', 0.0),
                     totals.get('total_net', 0.0),
                     totals.get('net_fine', 0.0),
                     totals.get('net_wage', 0.0),
                     note,
                     last_balance_silver,
                     last_balance_amount,
                     voucher_no))
            else:
                self.logger.info(f"Inserting new estimate {voucher_no}")
                self.cursor.execute('''
                    INSERT INTO estimates
                    (voucher_no, date, silver_rate, total_gross, total_net, total_fine, total_wage, note,
                     last_balance_silver, last_balance_amount)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (voucher_no, date, silver_rate,
                     totals.get('total_gross', 0.0),
                     totals.get('total_net', 0.0),
                     totals.get('net_fine', 0.0),
                     totals.get('net_wage', 0.0),
                     note,
                     last_balance_silver,
                     last_balance_amount))
            
            # Delete and recreate estimate items (these don't have ON DELETE CASCADE issues)
            self.cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            for item in regular_items: self._save_estimate_item(voucher_no, item)
            for item in return_items: self._save_estimate_item(voucher_no, item)
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"DB error saving estimate {voucher_no}: {str(e)}", exc_info=True)
            return False
        except Exception as e: # Catch other potential errors like data conversion
            self.conn.rollback()
            self.logger.error(f"Error during save estimate {voucher_no}: {str(e)}", exc_info=True)
            return False

    def _save_estimate_item(self, voucher_no, item):
        is_return = 1 if item.get('is_return', False) else 0
        is_silver_bar = 1 if item.get('is_silver_bar', False) else 0
        if not self.cursor: raise sqlite3.Error("No database cursor available.")
        try:
            self.cursor.execute('INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                (voucher_no, item.get('code', ''), item.get('name', ''), float(item.get('gross', 0.0)), float(item.get('poly', 0.0)), float(item.get('net_wt', 0.0)), float(item.get('purity', 0.0)), float(item.get('wage_rate', 0.0)), int(item.get('pieces', 1)), float(item.get('wage', 0.0)), float(item.get('fine', 0.0)), is_return, is_silver_bar))
        except (ValueError, TypeError) as e:
            self.logger.error(f"Data type error saving item for voucher {voucher_no}, code {item.get('code')}: {str(e)}", exc_info=True)
            raise e # Re-raise to trigger transaction rollback
        except sqlite3.Error as e:
            self.logger.error(f"DB error saving item for voucher {voucher_no}, code {item.get('code')}: {str(e)}", exc_info=True)
            raise e # Re-raise

    # --- Methods for Silver Bar Lists (Overhauled) ---
    def _generate_list_identifier(self):
        """Generates a unique identifier for a new list."""
        if not self.cursor: return f"ERR-L-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        today_str = datetime.now().strftime('%Y%m%d'); seq = 1
        try:
            # Use the new table name
            self.cursor.execute("SELECT list_identifier FROM silver_bar_lists WHERE list_identifier LIKE ? ORDER BY list_identifier DESC LIMIT 1", (f"L-{today_str}-%",))
            result = self.cursor.fetchone()
            if result:
                try: seq = int(result['list_identifier'].split('-')[-1]) + 1
                except (IndexError, ValueError):
                    self.logger.warning("Format issue when parsing list identifier")
                    pass # Handle potential format issues
        except sqlite3.Error as e:
            self.logger.error(f"Error generating list ID sequence: {str(e)}", exc_info=True)
        return f"L-{today_str}-{seq:03d}"

    def create_silver_bar_list(self, note=None):
        """Creates a new, empty silver bar list."""
        if not self.conn or not self.cursor: return None
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        list_identifier = self._generate_list_identifier()
        try:
            self.cursor.execute('INSERT INTO silver_bar_lists (list_identifier, creation_date, list_note) VALUES (?, ?, ?)',
                                (list_identifier, creation_date, note))
            self.conn.commit()
            list_id = self.cursor.lastrowid
            self.logger.info(f"Created silver bar list {list_identifier} (ID: {list_id}).")
            return list_id
        except sqlite3.Error as e:
            self.logger.error(f"DB error creating silver bar list: {str(e)}", exc_info=True)
            self.conn.rollback()
            return None

    def get_silver_bar_lists(self):
        """Fetches all silver bar lists (identifier and ID)."""
        if not self.cursor: return []
        try:
            self.cursor.execute('SELECT list_id, list_identifier, creation_date, list_note FROM silver_bar_lists ORDER BY creation_date DESC')
            return self.cursor.fetchall() # Return list of Row objects
        except sqlite3.Error as e:
            self.logger.error(f"DB error fetching silver bar lists: {str(e)}", exc_info=True)
            return []

    def get_silver_bar_list_details(self, list_id):
        """Fetches details for a specific list ID."""
        if not self.cursor: return None
        try:
            self.cursor.execute('SELECT * FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            return self.cursor.fetchone() # Return single Row object or None
        except sqlite3.Error as e:
            self.logger.error(f"DB error fetching list details for ID {list_id}: {str(e)}", exc_info=True)
            return None

    def update_silver_bar_list_note(self, list_id, new_note):
        """Updates the note for a specific list."""
        if not self.conn or not self.cursor: return False
        try:
            self.cursor.execute('UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?', (new_note, list_id))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            self.logger.error(f"DB error updating list note for ID {list_id}: {str(e)}", exc_info=True)
            self.conn.rollback()
            return False

    def delete_silver_bar_list(self, list_id):
        """Deletes a list and unassigns/updates status of associated bars."""
        if not self.conn or not self.cursor: return False, "No database connection"
        try:
            self.conn.execute('BEGIN TRANSACTION')
            # Find bars currently assigned to this list
            self.cursor.execute("SELECT bar_id FROM silver_bars WHERE list_id = ?", (list_id,))
            bars_to_unassign = [row['bar_id'] for row in self.cursor.fetchall()]

            unassign_note = f"Unassigned due to list {list_id} deletion"
            unassigned_count = 0
            for bar_id in bars_to_unassign:
                # Use the remove_bar_from_list logic (which includes transfer record)
                if self.remove_bar_from_list(bar_id, note=unassign_note, perform_commit=False): # Don't commit inside loop
                     unassigned_count += 1
                else:
                     self.logger.warning(f"Failed to properly unassign bar {bar_id} during list deletion.")
                     # Fallback: Just unlink if remove fails, though transfer record might be missed
                     self.cursor.execute("UPDATE silver_bars SET list_id = NULL, status = 'In Stock' WHERE bar_id = ?", (bar_id,))


            # Delete the list itself
            self.cursor.execute('DELETE FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            deleted = self.cursor.rowcount > 0

            self.conn.commit() # Commit transaction after all operations
            self.logger.info(f"Deleted list {list_id}. Unassigned {unassigned_count} bars.")
            return deleted, "Deleted" if deleted else "List not found"
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"DB error deleting list {list_id}: {str(e)}", exc_info=True)
            return False, str(e)

    def assign_bar_to_list(self, bar_id, list_id, note="Assigned to list", perform_commit=True):
        """Assigns an 'In Stock' bar to a list and updates status."""
        if not self.conn or not self.cursor: return False
        date_assigned = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'In Stock', 'Assigned'
        transfer_no = f"ASSIGN-{bar_id}-{list_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            # Check bar status
            self.cursor.execute("SELECT status FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row or row['status'] != 'In Stock':
                self.logger.warning(f"Bar {bar_id} not found or not 'In Stock'. Cannot assign.")
                return False

            # Check if list exists
            self.cursor.execute("SELECT list_id FROM silver_bar_lists WHERE list_id = ?", (list_id,))
            if not self.cursor.fetchone():
                 self.logger.warning(f"List ID {list_id} not found. Cannot assign bar.")
                 return False

            if perform_commit: self.conn.execute('BEGIN TRANSACTION')
            # Update bar status and list_id
            self.cursor.execute("UPDATE silver_bars SET status = ?, list_id = ? WHERE bar_id = ?", (to_status, list_id, bar_id))
            # Add transfer record using the correct silver_bar_id column name
            self.cursor.execute('''
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (transfer_no, date_assigned, bar_id, list_id, from_status, to_status, note))

            if perform_commit: self.conn.commit()
            return True
        except sqlite3.Error as e:
            if perform_commit: self.conn.rollback()
            self.logger.error(f"DB error assigning bar {bar_id} to list {list_id}: {str(e)}", exc_info=True)
            return False

    def remove_bar_from_list(self, bar_id, note="Removed from list", perform_commit=True):
        """Removes a bar from its list, sets status to 'In Stock'."""
        if not self.conn or not self.cursor: return False
        date_removed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'Assigned', 'In Stock'
        transfer_no = f"REMOVE-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            # Get current list_id and status
            self.cursor.execute("SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row or row['status'] != 'Assigned' or row['list_id'] is None:
                self.logger.warning(f"Bar {bar_id} not found or not assigned to a list. Cannot remove.")
                return False
            current_list_id = row['list_id']

            if perform_commit: self.conn.execute('BEGIN TRANSACTION')
            # Update bar status and clear list_id
            self.cursor.execute("UPDATE silver_bars SET status = ?, list_id = NULL WHERE bar_id = ?", (to_status, bar_id))
            # Add transfer record using the correct silver_bar_id column name
            self.cursor.execute('''
                INSERT INTO bar_transfers
                (transfer_no, date, silver_bar_id, list_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (transfer_no, date_removed, bar_id, current_list_id, from_status, to_status, note))

            if perform_commit: self.conn.commit()
            return True
        except sqlite3.Error as e:
            if perform_commit: self.conn.rollback()
            self.logger.error(f"DB error removing bar {bar_id} from list: {str(e)}", exc_info=True)
            return False

    def get_bars_in_list(self, list_id):
        """Fetches all bars assigned to a specific list."""
        if not self.cursor: return []
        try:
            self.cursor.execute("SELECT * FROM silver_bars WHERE list_id = ? ORDER BY bar_id", (list_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"DB error fetching bars for list {list_id}: {str(e)}", exc_info=True)
            return []

    def get_available_bars(self):
        """Fetches all bars with status 'In Stock' and not assigned to any list."""
        if not self.cursor: return []
        try:
            self.cursor.execute("SELECT * FROM silver_bars WHERE status = 'In Stock' AND list_id IS NULL ORDER BY date_added DESC, bar_id DESC")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"DB error fetching available bars: {str(e)}", exc_info=True)
            return []

    # --- Silver Bar Methods (Overhauled) ---
    def add_silver_bar(self, estimate_voucher_no, weight, purity):
        """Adds a new silver bar record linked to an estimate."""
        if not self.conn or not self.cursor: return None
        date_added = datetime.now().strftime('%Y-%m-%d %H:%M:%S') # Use timestamp for potential sorting
        fine_weight = weight * (purity / 100)
        try:
            self.cursor.execute('''
                INSERT INTO silver_bars
                (estimate_voucher_no, weight, purity, fine_weight, date_added, status, list_id)
                VALUES (?, ?, ?, ?, ?, ?, NULL)
            ''', (estimate_voucher_no, weight, purity, fine_weight, date_added, 'In Stock'))
            self.conn.commit()
            return self.cursor.lastrowid # Return the new bar_id
        except sqlite3.Error as e:
            self.logger.error(f"DB Error adding silver bar for estimate {estimate_voucher_no}: {str(e)}", exc_info=True)
            self.conn.rollback()
            return None

    def get_silver_bars(self, status=None, weight_query=None, estimate_voucher_no=None):
        """Fetches silver bars based on optional filters."""
        if not self.cursor: return []
        query = "SELECT * FROM silver_bars WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if weight_query is not None:
            # Allow searching for weights within a small tolerance (e.g., +/- 0.001)
            try:
                target_weight = float(weight_query)
                query += " AND weight BETWEEN ? AND ?"
                params.extend([target_weight - 0.001, target_weight + 0.001])
            except ValueError:
                self.logger.warning(f"Invalid weight query '{weight_query}'. Ignoring weight filter.")
        if estimate_voucher_no:
            query += " AND estimate_voucher_no LIKE ?"
            params.append(f"%{estimate_voucher_no}%")

        query += " ORDER BY date_added DESC, bar_id DESC" # Changed sort order
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            self.logger.error(f"DB error getting silver bars: {str(e)}", exc_info=True)
            return []

    def delete_silver_bars_for_estimate(self, voucher_no):
        """
        DEPRECATED: This method is kept for compatibility but no longer deletes any silver bars.
        Silver bars are now permanent and should only be managed through the Silver Bar Management interface.
        """
        if not voucher_no:
            self.logger.warning("delete_silver_bars_for_estimate called with empty voucher_no")
            return True
            
        self.logger.info(f"delete_silver_bars_for_estimate called for {voucher_no} but silver bars are now permanent.")
        self.logger.info("Silver bars are preserved and should be managed through the Silver Bar Management interface.")
        
        # Count how many bars exist for this estimate (for informational purposes only)
        try:
            self.cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
            total_bars = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ? AND list_id IS NOT NULL", (voucher_no,))
            bars_in_lists = self.cursor.fetchone()[0]
            
            self.logger.info(f"Estimate {voucher_no} has {total_bars} silver bars total, {bars_in_lists} in lists.")
            return True
        except sqlite3.Error as e:
            self.logger.error(f"DB error checking silver bars for estimate {voucher_no}: {str(e)}", exc_info=True)
            return True  # Still return True to not block the save process

    # def transfer_silver_bar(...): # Removed - Replaced by list assignment logic

    def delete_all_estimates(self):
        """Deletes all records from estimates and estimate_items tables."""
        if not self.conn or not self.cursor: return False
        try:
            self.conn.execute('BEGIN TRANSACTION')
            # Delete items first due to foreign key constraint (if ON DELETE CASCADE isn't used/reliable)
            self.cursor.execute('DELETE FROM estimate_items')
            deleted_items_count = self.cursor.rowcount
            self.cursor.execute('DELETE FROM estimates')
            deleted_estimates_count = self.cursor.rowcount
            self.conn.commit()
            self.logger.info(f"Deleted {deleted_estimates_count} estimates and {deleted_items_count} estimate items.")
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"DB error deleting all estimates: {str(e)}", exc_info=True)
            return False

    def delete_single_estimate(self, voucher_no):
        """Deletes a specific estimate, its items, and all associated silver bars."""
        if not self.conn or not self.cursor: return False
        if not voucher_no:
            self.logger.error("No voucher number provided for deletion.")
            return False
        try:
            self.conn.execute('BEGIN TRANSACTION')

            # First, find all silver bars associated with this estimate
            self.cursor.execute("SELECT bar_id, list_id FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
            bars = self.cursor.fetchall()
            
            # Track lists that contain bars from this estimate
            affected_lists = set()
            for bar in bars:
                if bar['list_id'] is not None:
                    affected_lists.add(bar['list_id'])
            
            # Delete all silver bars associated with this estimate
            # This will also delete related bar_transfers due to ON DELETE CASCADE
            self.cursor.execute("DELETE FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
            deleted_bars_count = self.cursor.rowcount
            self.logger.info(f"Deleted {deleted_bars_count} silver bars for estimate {voucher_no}.")
            
            # Delete estimate items
            self.cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            deleted_items_count = self.cursor.rowcount
            
            # Delete the estimate header
            self.cursor.execute('DELETE FROM estimates WHERE voucher_no = ?', (voucher_no,))
            deleted_estimate_count = self.cursor.rowcount
            
            # Delete any lists that are now empty due to bar deletions
            for list_id in affected_lists:
                # Check if the list is now empty
                self.cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE list_id = ?", (list_id,))
                remaining_bars = self.cursor.fetchone()[0]
                
                if remaining_bars == 0:
                    # List is empty, delete it
                    self.cursor.execute("DELETE FROM silver_bar_lists WHERE list_id = ?", (list_id,))
                    if self.cursor.rowcount > 0:
                        self.logger.info(f"Deleted empty list ID {list_id} after removing its bars.")
            
            self.conn.commit()
            
            if deleted_estimate_count > 0:
                self.logger.info(f"Deleted estimate {voucher_no} with {deleted_items_count} items and {deleted_bars_count} silver bars.")
                return True
            else:
                self.logger.warning(f"Estimate {voucher_no} not found for deletion.")
                return False
        except sqlite3.Error as e:
            self.conn.rollback()
            self.logger.error(f"DB error deleting estimate {voucher_no}: {str(e)}", exc_info=True)
            return False

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
        if self.conn:
            self.logger.info("Closing database connection and encrypting data")
            # Encrypt the current temporary DB back to the original file
            encrypt_success = self._encrypt_db()
            if encrypt_success:
                 self.logger.info("Temporary database encrypted successfully")
            else:
                 # This is critical - data might be lost if encryption fails!
                 # Keep the temp file for potential manual recovery?
                 self.logger.critical("Failed to encrypt database on close!")
                 self.logger.critical(f"The unencrypted data might still be in: {self.temp_db_path}")
                 # Decide on recovery strategy - maybe don't delete temp file on failure?
                 # For now, we proceed to close and cleanup, but log the error prominently.

            # Close the connection to the temporary DB
            try:
                self.conn.close()
                self.conn = None
                self.cursor = None
                self.logger.debug("Database connection closed")
            except sqlite3.Error as e:
                 self.logger.error(f"Error closing SQLite connection: {str(e)}", exc_info=True)
        else:
             self.logger.debug("No active database connection to close")

        # Clean up the temporary file regardless of encryption success (unless we change strategy above)
        self._cleanup_temp_db()