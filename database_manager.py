#!/usr/bin/env python
import os
import sqlite3
from datetime import datetime
import traceback # For detailed error logging

class DatabaseManager:
    """Manages SQLite database operations for the Silver Estimation App."""

    def __init__(self, db_path):
        """Initialize the database manager with the path to the database file."""
        self.db_path = db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # Connect and enable Foreign Keys
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        # Setup or update the database schema
        self.setup_database()

    def _table_exists(self, table_name):
        """Check if a table exists in the database."""
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return self.cursor.fetchone() is not None

    def _column_exists(self, table_name, column_name):
        """Check if a column exists in a table."""
        if not self._table_exists(table_name):
            return False
        self.cursor.execute(f"PRAGMA table_info({table_name})")
        return any(col['name'] == column_name for col in self.cursor.fetchall())

    def _is_column_unique(self, table_name, column_name):
        """Check if a column has a UNIQUE constraint (via implicit index)."""
        if not self._column_exists(table_name, column_name):
            return False
        try:
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
            print(f"Error checking unique constraint for {table_name}.{column_name}: {e}")
            return False

    def _check_schema_version(self):
        """Check if the database has the schema version table and current version."""
        try:
            # Check if schema_version table exists
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
            if not self.cursor.fetchone():
                # Create schema_version table if it doesn't exist
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
                return 0
            else:
                # Get current version
                self.cursor.execute("SELECT MAX(version) FROM schema_version")
                result = self.cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except sqlite3.Error as e:
            print(f"Error checking schema version: {e}")
            return 0  # Assume version 0 on error

    def _update_schema_version(self, new_version):
        """Update the schema version in the database."""
        try:
            self.cursor.execute('''
                INSERT INTO schema_version (version, applied_date)
                VALUES (?, ?)
            ''', (new_version, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            self.conn.commit()
            print(f"Schema updated to version {new_version}")
            return True
        except sqlite3.Error as e:
            print(f"Error updating schema version: {e}")
            self.conn.rollback()
            return False

    def setup_database(self):
        """Create/update the necessary tables for the Silver Bar Management Overhaul."""
        print("Starting database setup check...")
        try:
            # Check current schema version
            current_version = self._check_schema_version()
            print(f"Current database schema version: {current_version}")
            
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
                print("Performing silver bar schema migration to version 1...")
                
                # 1. Drop dependent table first if it exists
                if self._table_exists('bar_transfers'):
                    print("Dropping existing 'bar_transfers' table...")
                    self.cursor.execute('DROP TABLE bar_transfers')

                # 2. Drop old silver_bars table if it exists
                if self._table_exists('silver_bars'):
                    print("Dropping existing 'silver_bars' table...")
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
                    print("Created 'silver_bar_lists' table.")

                # 4. Create the NEW silver_bars table
                print("Creating new 'silver_bars' table with updated schema...")
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
                print("Created 'silver_bars' table.")

                # 5. Create the NEW bar_transfers table
                print("Creating new 'bar_transfers' table with updated schema...")
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
                print("Created 'bar_transfers' table.")
                
                # Update schema version to 1
                self._update_schema_version(1)
            else:
                print("Silver bar schema is already at version 1 or higher. No migration needed.")
                
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
                print("Adding 'note' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN note TEXT')
                
            # Check if the last_balance columns exist in the estimates table
            if not self._column_exists('estimates', 'last_balance_silver'):
                print("Adding 'last_balance_silver' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN last_balance_silver REAL DEFAULT 0')
                
            if not self._column_exists('estimates', 'last_balance_amount'):
                print("Adding 'last_balance_amount' column to estimates table...")
                self.cursor.execute('ALTER TABLE estimates ADD COLUMN last_balance_amount REAL DEFAULT 0')
            
            self.conn.commit()
            print("Database schema setup/update complete.")

        except sqlite3.Error as e:
            print(f"FATAL Database setup error: {e}")
            print(traceback.format_exc())
            self.conn.rollback()  # Rollback transaction on error
            raise e  # Re-raise critical error

    # --- Item Methods ---
    def get_item_by_code(self, code):
        try: self.cursor.execute('SELECT * FROM items WHERE LOWER(code) = LOWER(?)', (code,)); return self.cursor.fetchone()
        except sqlite3.Error as e: print(f"DB Error get_item_by_code: {e}"); return None

    def search_items(self, search_term):
        try:
            search_pattern = f"%{search_term}%"
            self.cursor.execute('SELECT * FROM items WHERE LOWER(code) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?) ORDER BY code', (search_pattern, search_pattern)); return self.cursor.fetchall()
        except sqlite3.Error as e: print(f"DB Error search_items: {e}"); return []

    def get_all_items(self):
        try: self.cursor.execute('SELECT * FROM items ORDER BY code'); return self.cursor.fetchall()
        except sqlite3.Error as e: print(f"DB Error get_all_items: {e}"); return []

    def add_item(self, code, name, purity, wage_type, wage_rate):
        try: self.cursor.execute('INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)', (code, name, purity, wage_type, wage_rate)); self.conn.commit(); return True
        except sqlite3.Error as e: print(f"DB Error adding item: {e}"); self.conn.rollback(); return False

    def update_item(self, code, name, purity, wage_type, wage_rate):
        try: self.cursor.execute('UPDATE items SET name = ?, purity = ?, wage_type = ?, wage_rate = ? WHERE code = ?', (name, purity, wage_type, wage_rate, code)); self.conn.commit(); return self.cursor.rowcount > 0
        except sqlite3.Error as e: print(f"DB Error updating item: {e}"); self.conn.rollback(); return False

    def delete_item(self, code):
        try: self.cursor.execute('DELETE FROM items WHERE code = ?', (code,)); self.conn.commit(); return self.cursor.rowcount > 0
        except sqlite3.Error as e: print(f"DB Error deleting item: {e}"); self.conn.rollback(); return False

    # --- Estimate Methods ---
    def get_estimate_by_voucher(self, voucher_no):
        try:
            self.cursor.execute('SELECT * FROM estimates WHERE voucher_no = ?', (voucher_no,))
            estimate = self.cursor.fetchone()
            if estimate:
                self.cursor.execute('SELECT * FROM estimate_items WHERE voucher_no = ? ORDER BY is_return, is_silver_bar, id', (voucher_no,))
                items = self.cursor.fetchall()
                return {'header': dict(estimate), 'items': [dict(item) for item in items]}
            else: return None
        except sqlite3.Error as e: print(f"DB Error getting estimate {voucher_no}: {e}"); return None

    def get_estimates(self, date_from=None, date_to=None, voucher_search=None):
        """Fetches estimate headers and their associated items based on filters."""
        query = "SELECT * FROM estimates WHERE 1=1"; params = []
        if date_from: query += " AND date >= ?"; params.append(date_from)
        if date_to: query += " AND date <= ?"; params.append(date_to)
        if voucher_search: query += " AND voucher_no LIKE ?"; params.append(f"%{voucher_search}%")
        query += " ORDER BY date DESC, voucher_no DESC"
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
            print(f"DB Error getting estimates: {e}")
            return []

    def generate_voucher_no(self):
        today = datetime.now().strftime('%Y%m%d'); seq = 1
        try:
            self.cursor.execute("SELECT voucher_no FROM estimates WHERE voucher_no LIKE ? ORDER BY voucher_no DESC LIMIT 1", (f"{today}%",))
            result = self.cursor.fetchone()
            if result:
                try: seq = int(result['voucher_no'][8:]) + 1
                except (IndexError, ValueError): print(f"Warn: Non-numeric suffix on {result['voucher_no']}")
            return f"{today}{seq}"
        except sqlite3.Error as e: print(f"DB error gen voucher: {e}"); return f"ERR{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def save_estimate_with_returns(self, voucher_no, date, silver_rate, regular_items, return_items, totals):
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
                print(f"Updating existing estimate {voucher_no} (preserving silver bars)")
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
                print(f"Inserting new estimate {voucher_no}")
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
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error saving estimate {voucher_no}: {e}"); return False
        except Exception as e: # Catch other potential errors like data conversion
             self.conn.rollback(); print(f"Error during save estimate {voucher_no}: {e}"); print(traceback.format_exc()); return False

    def _save_estimate_item(self, voucher_no, item):
        is_return = 1 if item.get('is_return', False) else 0
        is_silver_bar = 1 if item.get('is_silver_bar', False) else 0
        try:
            self.cursor.execute('INSERT INTO estimate_items (voucher_no, item_code, item_name, gross, poly, net_wt, purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                                (voucher_no, item.get('code', ''), item.get('name', ''), float(item.get('gross', 0.0)), float(item.get('poly', 0.0)), float(item.get('net_wt', 0.0)), float(item.get('purity', 0.0)), float(item.get('wage_rate', 0.0)), int(item.get('pieces', 1)), float(item.get('wage', 0.0)), float(item.get('fine', 0.0)), is_return, is_silver_bar))
        except (ValueError, TypeError) as e: print(f"Data type error saving item for voucher {voucher_no}, code {item.get('code')}: {e}"); raise e # Re-raise to trigger transaction rollback

    # --- Methods for Silver Bar Lists (Overhauled) ---
    def _generate_list_identifier(self):
        """Generates a unique identifier for a new list."""
        today_str = datetime.now().strftime('%Y%m%d'); seq = 1
        try:
            # Use the new table name
            self.cursor.execute("SELECT list_identifier FROM silver_bar_lists WHERE list_identifier LIKE ? ORDER BY list_identifier DESC LIMIT 1", (f"L-{today_str}-%",))
            result = self.cursor.fetchone()
            if result:
                try: seq = int(result['list_identifier'].split('-')[-1]) + 1
                except (IndexError, ValueError): pass # Handle potential format issues
        except sqlite3.Error as e: print(f"Error generating list ID sequence: {e}")
        return f"L-{today_str}-{seq:03d}"

    def create_silver_bar_list(self, note=None):
        """Creates a new, empty silver bar list."""
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        list_identifier = self._generate_list_identifier()
        try:
            self.cursor.execute('INSERT INTO silver_bar_lists (list_identifier, creation_date, list_note) VALUES (?, ?, ?)',
                                (list_identifier, creation_date, note))
            self.conn.commit()
            list_id = self.cursor.lastrowid
            print(f"Created silver bar list {list_identifier} (ID: {list_id}).")
            return list_id
        except sqlite3.Error as e:
            print(f"DB error creating silver bar list: {e}")
            self.conn.rollback()
            return None

    def get_silver_bar_lists(self):
        """Fetches all silver bar lists (identifier and ID)."""
        try:
            self.cursor.execute('SELECT list_id, list_identifier, creation_date, list_note FROM silver_bar_lists ORDER BY creation_date DESC')
            return self.cursor.fetchall() # Return list of Row objects
        except sqlite3.Error as e:
            print(f"DB error fetching silver bar lists: {e}")
            return []

    def get_silver_bar_list_details(self, list_id):
        """Fetches details for a specific list ID."""
        try:
            self.cursor.execute('SELECT * FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            return self.cursor.fetchone() # Return single Row object or None
        except sqlite3.Error as e:
            print(f"DB error fetching list details for ID {list_id}: {e}")
            return None

    def update_silver_bar_list_note(self, list_id, new_note):
        """Updates the note for a specific list."""
        try:
            self.cursor.execute('UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?', (new_note, list_id))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"DB error updating list note for ID {list_id}: {e}")
            self.conn.rollback()
            return False

    def delete_silver_bar_list(self, list_id):
        """Deletes a list and unassigns/updates status of associated bars."""
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
                     print(f"Warning: Failed to properly unassign bar {bar_id} during list deletion.")
                     # Fallback: Just unlink if remove fails, though transfer record might be missed
                     self.cursor.execute("UPDATE silver_bars SET list_id = NULL, status = 'In Stock' WHERE bar_id = ?", (bar_id,))


            # Delete the list itself
            self.cursor.execute('DELETE FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            deleted = self.cursor.rowcount > 0

            self.conn.commit() # Commit transaction after all operations
            print(f"Deleted list {list_id}. Unassigned {unassigned_count} bars.")
            return deleted, "Deleted" if deleted else "List not found"
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"DB error deleting list {list_id}: {e}")
            return False, str(e)

    def assign_bar_to_list(self, bar_id, list_id, note="Assigned to list", perform_commit=True):
        """Assigns an 'In Stock' bar to a list and updates status."""
        date_assigned = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'In Stock', 'Assigned'
        transfer_no = f"ASSIGN-{bar_id}-{list_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            # Check bar status
            self.cursor.execute("SELECT status FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row or row['status'] != 'In Stock':
                print(f"Bar {bar_id} not found or not 'In Stock'. Cannot assign.")
                return False

            # Check if list exists
            self.cursor.execute("SELECT list_id FROM silver_bar_lists WHERE list_id = ?", (list_id,))
            if not self.cursor.fetchone():
                 print(f"List ID {list_id} not found. Cannot assign bar.")
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
            print(f"DB error assigning bar {bar_id} to list {list_id}: {e}")
            return False

    def remove_bar_from_list(self, bar_id, note="Removed from list", perform_commit=True):
        """Removes a bar from its list, sets status to 'In Stock'."""
        date_removed = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        from_status, to_status = 'Assigned', 'In Stock'
        transfer_no = f"REMOVE-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            # Get current list_id and status
            self.cursor.execute("SELECT status, list_id FROM silver_bars WHERE bar_id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row or row['status'] != 'Assigned' or row['list_id'] is None:
                print(f"Bar {bar_id} not found or not assigned to a list. Cannot remove.")
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
            print(f"DB error removing bar {bar_id} from list: {e}")
            return False

    def get_bars_in_list(self, list_id):
        """Fetches all bars assigned to a specific list."""
        try:
            self.cursor.execute("SELECT * FROM silver_bars WHERE list_id = ? ORDER BY bar_id", (list_id,))
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"DB error fetching bars for list {list_id}: {e}")
            return []

    def get_available_bars(self):
        """Fetches all bars with status 'In Stock' and not assigned to any list."""
        try:
            self.cursor.execute("SELECT * FROM silver_bars WHERE status = 'In Stock' AND list_id IS NULL ORDER BY date_added DESC, bar_id DESC")
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"DB error fetching available bars: {e}")
            return []

    # --- Silver Bar Methods (Overhauled) ---
    def add_silver_bar(self, estimate_voucher_no, weight, purity):
        """Adds a new silver bar record linked to an estimate."""
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
            print(f"DB Error adding silver bar for estimate {estimate_voucher_no}: {e}")
            self.conn.rollback()
            return None

    def get_silver_bars(self, status=None, weight_query=None, estimate_voucher_no=None):
        """Fetches silver bars based on optional filters."""
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
                print(f"Warning: Invalid weight query '{weight_query}'. Ignoring weight filter.")
        if estimate_voucher_no:
            query += " AND estimate_voucher_no LIKE ?"
            params.append(f"%{estimate_voucher_no}%")

        query += " ORDER BY date_added DESC, bar_id DESC" # Changed sort order
        try:
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except sqlite3.Error as e:
            print(f"DB error getting silver bars: {e}")
            return []

    def delete_silver_bars_for_estimate(self, voucher_no):
        """
        DEPRECATED: This method is kept for compatibility but no longer deletes any silver bars.
        Silver bars are now permanent and should only be managed through the Silver Bar Management interface.
        """
        if not voucher_no:
            print("Warning: delete_silver_bars_for_estimate called with empty voucher_no")
            return True
            
        print(f"Note: delete_silver_bars_for_estimate called for {voucher_no} but silver bars are now permanent.")
        print("Silver bars are preserved and should be managed through the Silver Bar Management interface.")
        
        # Count how many bars exist for this estimate (for informational purposes only)
        try:
            self.cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ?", (voucher_no,))
            total_bars = self.cursor.fetchone()[0]
            
            self.cursor.execute("SELECT COUNT(*) FROM silver_bars WHERE estimate_voucher_no = ? AND list_id IS NOT NULL", (voucher_no,))
            bars_in_lists = self.cursor.fetchone()[0]
            
            print(f"FYI: Estimate {voucher_no} has {total_bars} silver bars total, {bars_in_lists} in lists.")
            return True
        except sqlite3.Error as e:
            print(f"DB error checking silver bars for estimate {voucher_no}: {e}")
            return True  # Still return True to not block the save process

    # def transfer_silver_bar(...): # Removed - Replaced by list assignment logic

    def delete_all_estimates(self):
        """Deletes all records from estimates and estimate_items tables."""
        try:
            self.conn.execute('BEGIN TRANSACTION')
            # Delete items first due to foreign key constraint (if ON DELETE CASCADE isn't used/reliable)
            self.cursor.execute('DELETE FROM estimate_items')
            deleted_items_count = self.cursor.rowcount
            self.cursor.execute('DELETE FROM estimates')
            deleted_estimates_count = self.cursor.rowcount
            self.conn.commit()
            print(f"Deleted {deleted_estimates_count} estimates and {deleted_items_count} estimate items.")
            return True
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"DB error deleting all estimates: {e}")
            return False

    def delete_single_estimate(self, voucher_no):
        """Deletes a specific estimate, its items, and all associated silver bars."""
        if not voucher_no:
            print("Error: No voucher number provided for deletion.")
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
            print(f"Deleted {deleted_bars_count} silver bars for estimate {voucher_no}.")
            
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
                        print(f"Deleted empty list ID {list_id} after removing its bars.")
            
            self.conn.commit()
            
            if deleted_estimate_count > 0:
                print(f"Deleted estimate {voucher_no} with {deleted_items_count} items and {deleted_bars_count} silver bars.")
                return True
            else:
                print(f"Estimate {voucher_no} not found for deletion.")
                return False
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"DB error deleting estimate {voucher_no}: {e}")
            return False

    # --- Utility Methods ---
    def drop_tables(self):
        tables = ['estimate_items', 'estimates', 'items', 'bar_transfers', 'silver_bars', 'silver_bar_lists']
        try:
            self.conn.execute('BEGIN TRANSACTION')
            for table in tables: print(f"Dropping table {table}..."); self.cursor.execute(f'DROP TABLE IF EXISTS {table}')
            self.conn.commit(); print("All tables dropped successfully."); return True
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error dropping tables: {e}"); return False

    def close(self):
        if self.conn: self.conn.close(); print("Database connection closed.")