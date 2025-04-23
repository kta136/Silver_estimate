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

    def setup_database(self):
        """Create/update the necessary tables."""
        print("Starting database setup...")
        try:
            # --- Items Table ---
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    purity REAL DEFAULT 0,
                    wage_type TEXT DEFAULT 'P',
                    wage_rate REAL DEFAULT 0
                )''')
            if not self._table_exists('items'): print("Created 'items' table.")

            # --- Estimates Table ---
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS estimates (
                    voucher_no TEXT PRIMARY KEY,
                    date TEXT NOT NULL,
                    silver_rate REAL DEFAULT 0,
                    total_gross REAL DEFAULT 0,
                    total_net REAL DEFAULT 0,
                    total_fine REAL DEFAULT 0, -- Note: Stores NET fine
                    total_wage REAL DEFAULT 0  -- Note: Stores NET wage
                )''')
            if not self._table_exists('estimates'): print("Created 'estimates' table.")

            # --- Estimate Items Table ---
            self.cursor.execute('''
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
                )''')
            if not self._table_exists('estimate_items'): print("Created 'estimate_items' table.")

            # --- New Silver Bar Lists Table ---
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS silver_bar_lists (
                    list_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    list_identifier TEXT UNIQUE NOT NULL,
                    creation_date TEXT NOT NULL,
                    list_note TEXT
                )''')
            if not self._table_exists('silver_bar_lists'): print("Created 'silver_bar_lists' table.")


            # --- Silver Bars Table: Ensure bar_no is NOT unique ---
            if self._table_exists('silver_bars') and self._is_column_unique('silver_bars', 'bar_no'):
                print("Found UNIQUE constraint on silver_bars.bar_no. Recreating table...")
                # Add migration logic here if needed for production data
                # For development, dropping and recreating is often simpler
                try:
                    self.conn.execute('BEGIN TRANSACTION')
                    self.cursor.execute("ALTER TABLE silver_bars RENAME TO silver_bars_old")
                    self.cursor.execute('''
                        CREATE TABLE silver_bars (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            bar_no TEXT NOT NULL, -- Removed UNIQUE
                            weight REAL DEFAULT 0, purity REAL DEFAULT 0, fine_weight REAL DEFAULT 0,
                            date_added TEXT, status TEXT DEFAULT 'In Stock', list_id INTEGER,
                            FOREIGN KEY (list_id) REFERENCES silver_bar_lists(list_id) ON DELETE SET NULL
                        )''')
                    print("Created new silver_bars table without UNIQUE on bar_no.")
                    self.cursor.execute('''
                        INSERT INTO silver_bars (id, bar_no, weight, purity, fine_weight, date_added, status, list_id)
                        SELECT id, bar_no, weight, purity, fine_weight, date_added, status, list_id
                        FROM silver_bars_old
                    ''')
                    print(f"Copied {self.cursor.rowcount} rows to new silver_bars table.")
                    self.cursor.execute("DROP TABLE silver_bars_old")
                    self.conn.commit()
                    print("Table silver_bars recreated successfully.")
                except sqlite3.Error as e:
                    print(f"ERROR recreating silver_bars table: {e}\n{traceback.format_exc()}")
                    self.conn.rollback()
                    print("WARNING: Failed to remove UNIQUE constraint. Recreating base table.")
                    self.cursor.execute('DROP TABLE IF EXISTS silver_bars') # Drop potential partial table
                    self.cursor.execute('''
                         CREATE TABLE silver_bars (
                             id INTEGER PRIMARY KEY AUTOINCREMENT, bar_no TEXT NOT NULL, weight REAL DEFAULT 0,
                             purity REAL DEFAULT 0, fine_weight REAL DEFAULT 0, date_added TEXT,
                             status TEXT DEFAULT 'In Stock', list_id INTEGER,
                             FOREIGN KEY (list_id) REFERENCES silver_bar_lists(list_id) ON DELETE SET NULL
                         )''') # Create without unique
                    if not self._table_exists('silver_bars'): print("Created 'silver_bars' table.")

            else:
                 # Create if not exists (without UNIQUE constraint)
                self.cursor.execute('''
                     CREATE TABLE IF NOT EXISTS silver_bars (
                         id INTEGER PRIMARY KEY AUTOINCREMENT, bar_no TEXT NOT NULL, weight REAL DEFAULT 0,
                         purity REAL DEFAULT 0, fine_weight REAL DEFAULT 0, date_added TEXT,
                         status TEXT DEFAULT 'In Stock', list_id INTEGER,
                         FOREIGN KEY (list_id) REFERENCES silver_bar_lists(list_id) ON DELETE SET NULL
                     )''')
                if not self._table_exists('silver_bars'): print("Created 'silver_bars' table.")


            # --- Bar Transfers Table Modifications ---
            if self._table_exists('bar_transfers') and not self._column_exists('bar_transfers', 'list_id'):
                 print("Attempting to add 'list_id' to 'bar_transfers'.")
                 try:
                    self.cursor.execute('ALTER TABLE bar_transfers ADD COLUMN list_id INTEGER REFERENCES silver_bar_lists(list_id) ON DELETE SET NULL')
                    print("Added 'list_id' column to 'bar_transfers' with constraint.")
                 except sqlite3.OperationalError as e:
                    print(f"Could not add column 'list_id' with constraint via ALTER ({e}). Trying without constraint.")
                    try:
                        self.cursor.execute('ALTER TABLE bar_transfers ADD COLUMN list_id INTEGER')
                        print("Added 'list_id' column placeholder to 'bar_transfers'. FK NOT enforced by this ALTER.")
                    except sqlite3.OperationalError as e2:
                         print(f"Failed to add 'list_id' column even without constraint: {e2}.")
            # Ensure base table exists
            self.cursor.execute('''
                 CREATE TABLE IF NOT EXISTS bar_transfers (
                     id INTEGER PRIMARY KEY AUTOINCREMENT, transfer_no TEXT, date TEXT,
                     bar_id INTEGER, list_id INTEGER, from_status TEXT, to_status TEXT, notes TEXT,
                     FOREIGN KEY (bar_id) REFERENCES silver_bars (id) ON DELETE CASCADE,
                     FOREIGN KEY (list_id) REFERENCES silver_bar_lists(list_id) ON DELETE SET NULL
                 )''')
            if not self._table_exists('bar_transfers'): print("Created 'bar_transfers' table.")

            self.conn.commit()
            print("Database schema check/update complete.")

        except sqlite3.Error as e:
            print(f"FATAL Database setup error: {e}")
            print(traceback.format_exc())
            self.conn.rollback()
            raise e # Re-raise critical error

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
            self.cursor.execute('INSERT OR REPLACE INTO estimates (voucher_no, date, silver_rate, total_gross, total_net, total_fine, total_wage) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                (voucher_no, date, silver_rate, totals.get('total_gross', 0.0), totals.get('total_net', 0.0), totals.get('net_fine', 0.0), totals.get('net_wage', 0.0)))
            self.cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            for item in regular_items: self._save_estimate_item(voucher_no, item)
            for item in return_items: self._save_estimate_item(voucher_no, item)
            self.conn.commit(); return True
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

    # --- Methods for Silver Bar Lists (v1.1) ---
    def _generate_list_identifier(self):
        today_str = datetime.now().strftime('%Y%m%d'); seq = 1
        try:
            self.cursor.execute("SELECT list_identifier FROM silver_bar_lists WHERE list_identifier LIKE ? ORDER BY list_identifier DESC LIMIT 1", (f"L-{today_str}-%",))
            result = self.cursor.fetchone()
            if result:
                try: seq = int(result['list_identifier'].split('-')[-1]) + 1
                except (IndexError, ValueError): pass
        except sqlite3.Error as e: print(f"Error generating list ID sequence: {e}")
        return f"L-{today_str}-{seq:03d}"

    def create_list_and_assign_bars(self, note, bar_ids):
        if not bar_ids: print("No bar IDs provided for list creation."); return None
        creation_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); list_identifier = self._generate_list_identifier()
        transfer_base_no = f"ASSIGN-{list_identifier}"; assigned_count = 0; list_id = None
        from_status, to_status = 'In Stock', 'Assigned'
        try:
            self.conn.execute('BEGIN TRANSACTION')
            self.cursor.execute('INSERT INTO silver_bar_lists (list_identifier, creation_date, list_note) VALUES (?, ?, ?)', (list_identifier, creation_date, note))
            list_id = self.cursor.lastrowid
            if not list_id: raise sqlite3.Error("Failed list insertion.")
            for index, bar_id in enumerate(bar_ids):
                self.cursor.execute("SELECT status FROM silver_bars WHERE id = ?", (bar_id,))
                row = self.cursor.fetchone()
                if not row or row['status'] != 'In Stock': print(f"Skipping bar ID {bar_id}: Not found or not 'In Stock'."); continue
                self.cursor.execute("UPDATE silver_bars SET status = ?, list_id = ? WHERE id = ?", (to_status, list_id, bar_id))
                transfer_no = f"{transfer_base_no}-{index+1}"
                self.cursor.execute('INSERT INTO bar_transfers (transfer_no, date, bar_id, list_id, from_status, to_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                    (transfer_no, creation_date, bar_id, list_id, from_status, to_status, f"Assigned to list: {list_identifier}"))
                assigned_count += 1
            self.conn.commit(); print(f"Created list {list_identifier} (ID: {list_id}) and assigned {assigned_count} bars."); return list_id
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error creating list/assigning bars: {e}\n{traceback.format_exc()}"); return None

    def get_all_list_identifiers(self):
        try:
            self.cursor.execute('SELECT list_identifier, list_id FROM silver_bar_lists ORDER BY creation_date DESC')
            return [(row['list_identifier'], row['list_id']) for row in self.cursor.fetchall()]
        except sqlite3.Error as e: print(f"DB error fetching list identifiers: {e}"); return []

    def get_list_details(self, list_id):
         try: self.cursor.execute('SELECT * FROM silver_bar_lists WHERE list_id = ?', (list_id,)); return self.cursor.fetchone()
         except sqlite3.Error as e: print(f"DB error fetching list details ID {list_id}: {e}"); return None

    def update_list_note(self, list_id, new_note):
        try: self.cursor.execute('UPDATE silver_bar_lists SET list_note = ? WHERE list_id = ?', (new_note, list_id)); self.conn.commit(); return self.cursor.rowcount > 0
        except sqlite3.Error as e: print(f"DB error updating list note: {e}"); self.conn.rollback(); return False

    def delete_silver_bar_list(self, list_id):
        try:
            self.conn.execute('BEGIN TRANSACTION')
            self.cursor.execute("UPDATE silver_bars SET list_id = NULL WHERE list_id = ?", (list_id,))
            print(f"Unlinked {self.cursor.rowcount} bars from list {list_id}.")
            # Optionally update transfers: self.cursor.execute("UPDATE bar_transfers SET list_id = NULL WHERE list_id = ?", (list_id,))
            self.cursor.execute('DELETE FROM silver_bar_lists WHERE list_id = ?', (list_id,))
            deleted = self.cursor.rowcount > 0
            self.conn.commit(); return deleted, "Deleted" if deleted else "List not found"
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error deleting list: {e}"); return False, str(e)

    def unassign_bar_from_list(self, bar_id, note="Unassigned from list"):
        date_unassigned = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); from_status, to_status = 'Assigned', 'In Stock'
        transfer_no = f"UNASSIGN-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            self.cursor.execute("SELECT status, list_id FROM silver_bars WHERE id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row or row['status'] != 'Assigned': return False
            current_list_id = row['list_id']
            self.conn.execute('BEGIN TRANSACTION')
            self.cursor.execute("UPDATE silver_bars SET status = ?, list_id = NULL WHERE id = ?", (to_status, bar_id))
            self.cursor.execute('INSERT INTO bar_transfers (transfer_no, date, bar_id, list_id, from_status, to_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                (transfer_no, date_unassigned, bar_id, current_list_id, from_status, to_status, note))
            self.conn.commit(); return True
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error unassigning bar {bar_id}: {e}"); return False

    # --- Silver Bar Methods ---
    def add_silver_bar(self, bar_no, weight, purity):
        date_added = datetime.now().strftime('%Y-%m-%d'); fine_weight = weight * (purity / 100)
        try:
            self.cursor.execute('INSERT INTO silver_bars (bar_no, weight, purity, fine_weight, date_added, status, list_id) VALUES (?, ?, ?, ?, ?, ?, NULL)',
                                (bar_no, weight, purity, fine_weight, date_added, 'In Stock'))
            self.conn.commit(); return True
        except sqlite3.IntegrityError: print(f"DB Integrity error adding bar '{bar_no}'."); self.conn.rollback(); return False
        except sqlite3.Error as e: print(f"DB Error adding silver bar: {e}"); self.conn.rollback(); return False

    def get_silver_bars(self, status=None):
        query = "SELECT * FROM silver_bars"; params = []
        if status: query += " WHERE status = ?"; params.append(status)
        query += " ORDER BY date_added DESC, bar_no"
        try: self.cursor.execute(query, params); return self.cursor.fetchall()
        except sqlite3.Error as e: print(f"DB error getting silver bars: {e}"); return []

    def transfer_silver_bar(self, bar_id, to_status, notes=None):
        date_transfer = datetime.now().strftime('%Y-%m-%d %H:%M:%S'); transfer_no = f"TRANSFER-{bar_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            self.cursor.execute("SELECT status, list_id FROM silver_bars WHERE id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row: return False
            from_status = row['status']; current_list_id = row['list_id']
            if from_status == to_status: return False
            self.conn.execute('BEGIN TRANSACTION')
            new_list_id = None if from_status == 'Assigned' and to_status != 'Assigned' else current_list_id
            self.cursor.execute("UPDATE silver_bars SET status = ?, list_id = ? WHERE id = ?", (to_status, new_list_id, bar_id))
            self.cursor.execute('INSERT INTO bar_transfers (transfer_no, date, bar_id, list_id, from_status, to_status, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
                                (transfer_no, date_transfer, bar_id, current_list_id, from_status, to_status, notes))
            self.conn.commit(); return True
        except sqlite3.Error as e: self.conn.rollback(); print(f"DB error transferring bar {bar_id}: {e}"); return False

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
        """Deletes a specific estimate and its items by voucher number."""
        if not voucher_no:
            print("Error: No voucher number provided for deletion.")
            return False
        try:
            self.conn.execute('BEGIN TRANSACTION')
            # Delete items first (optional if ON DELETE CASCADE works reliably, but safer)
            self.cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))
            # Delete the estimate header
            self.cursor.execute('DELETE FROM estimates WHERE voucher_no = ?', (voucher_no,))
            deleted_count = self.cursor.rowcount # Check if the estimate header was found and deleted
            self.conn.commit()
            if deleted_count > 0:
                print(f"Deleted estimate {voucher_no} successfully.")
                return True
            else:
                print(f"Estimate {voucher_no} not found for deletion.")
                return False # Indicate estimate wasn't found
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