#!/usr/bin/env python
import os
import sqlite3
from datetime import datetime

class DatabaseManager:
    """Manages SQLite database operations for the Silver Estimation App."""

    def __init__(self, db_path):
        """Initialize the database manager with the path to the database file."""
        self.db_path = db_path

        # Create the database directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Connect to the database
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Set up the database
        self.setup_database()

    def setup_database(self):
        """Create the necessary tables if they don't exist."""
        # Existing tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS items (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                purity REAL DEFAULT 0,
                wage_type TEXT DEFAULT 'P',
                wage_rate REAL DEFAULT 0
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS estimates (
                voucher_no TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                silver_rate REAL DEFAULT 0,
                total_gross REAL DEFAULT 0,
                total_net REAL DEFAULT 0,
                total_fine REAL DEFAULT 0, -- Note: This stores the NET fine after returns/bars
                total_wage REAL DEFAULT 0  -- Note: This stores the NET wage after returns/bars
            )
        ''')

        # Added is_silver_bar column
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
                is_silver_bar INTEGER DEFAULT 0, -- Added column
                FOREIGN KEY (voucher_no) REFERENCES estimates (voucher_no),
                FOREIGN KEY (item_code) REFERENCES items (code)
            )
        ''')

        # New tables for silver bars
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS silver_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bar_no TEXT UNIQUE,
                weight REAL DEFAULT 0,
                purity REAL DEFAULT 0,
                fine_weight REAL DEFAULT 0,
                date_added TEXT,
                status TEXT DEFAULT 'In Stock'
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS bar_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transfer_no TEXT,
                date TEXT,
                bar_id INTEGER,
                from_status TEXT,
                to_status TEXT,
                notes TEXT,
                FOREIGN KEY (bar_id) REFERENCES silver_bars (id)
            )
        ''')

        self.conn.commit()

    def get_item_by_code(self, code):
        """Get an item by its code (case-insensitive)."""
        self.cursor.execute('''
            SELECT * FROM items WHERE LOWER(code) = LOWER(?)
        ''', (code,))
        return self.cursor.fetchone()

    def search_items(self, search_term):
        """Search for items by code or name."""
        search_pattern = f"%{search_term}%"
        self.cursor.execute('''
            SELECT * FROM items
            WHERE LOWER(code) LIKE LOWER(?) OR LOWER(name) LIKE LOWER(?)
            ORDER BY code
        ''', (search_pattern, search_pattern))
        return self.cursor.fetchall()

    def get_all_items(self):
        """Get all items from the database."""
        self.cursor.execute('SELECT * FROM items ORDER BY code')
        return self.cursor.fetchall()

    def add_item(self, code, name, purity, wage_type, wage_rate):
        """Add a new item to the database."""
        try:
            self.cursor.execute('''
                INSERT INTO items (code, name, purity, wage_type, wage_rate)
                VALUES (?, ?, ?, ?, ?)
            ''', (code, name, purity, wage_type, wage_rate))
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def update_item(self, code, name, purity, wage_type, wage_rate):
        """Update an existing item in the database."""
        try:
            self.cursor.execute('''
                UPDATE items
                SET name = ?, purity = ?, wage_type = ?, wage_rate = ?
                WHERE code = ?
            ''', (name, purity, wage_type, wage_rate, code))
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def delete_item(self, code):
        """Delete an item from the database."""
        try:
            self.cursor.execute('DELETE FROM items WHERE code = ?', (code,))
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def get_estimate_by_voucher(self, voucher_no):
        """Get an estimate by its voucher number."""
        # Get the estimate header
        self.cursor.execute('SELECT * FROM estimates WHERE voucher_no = ?', (voucher_no,))
        estimate = self.cursor.fetchone()

        if not estimate:
            return None

        # Get the estimate items
        self.cursor.execute('''
            SELECT * FROM estimate_items
            WHERE voucher_no = ?
            ORDER BY is_return, is_silver_bar, id -- Order logically
        ''', (voucher_no,))
        items = self.cursor.fetchall()

        return {
            'header': dict(estimate),
            'items': [dict(item) for item in items]
        }

    def get_estimates(self, date_from=None, date_to=None, voucher_search=None):
        """Get estimates based on search criteria."""
        query = "SELECT * FROM estimates WHERE 1=1"
        params = []

        if date_from:
            query += " AND date >= ?"
            params.append(date_from)

        if date_to:
            query += " AND date <= ?"
            params.append(date_to)

        if voucher_search:
            query += " AND voucher_no LIKE ?"
            params.append(f"%{voucher_search}%")

        query += " ORDER BY date DESC, voucher_no DESC"

        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def generate_voucher_no(self):
        """Generate a new voucher number based on the current date."""
        today = datetime.now().strftime('%Y%m%d')

        # Get the highest voucher number for today
        self.cursor.execute('''
            SELECT voucher_no FROM estimates
            WHERE voucher_no LIKE ?
            ORDER BY voucher_no DESC LIMIT 1
        ''', (f"{today}%",))

        result = self.cursor.fetchone()

        if result:
            # Increment the last voucher number
            last_num = int(result['voucher_no'][8:])
            return f"{today}{last_num + 1}"  # No zfill to start from 1, 2, etc.
        else:
            # First voucher of the day
            return f"{today}1"  # Start from 1 instead of 001

    def save_estimate(self, voucher_no, date, silver_rate, items, totals):
        """Save an estimate and its items. (Deprecated, use save_estimate_with_returns)"""
        # This method is kept for potential backward compatibility but should not be used
        # for new saves that might involve returns or silver bars flags.
        # Redirecting to the more comprehensive method.
        regular_items = [item for item in items if not item.get('is_return') and not item.get('is_silver_bar')]
        return_items = [item for item in items if item.get('is_return')]
        # Note: This simple split doesn't handle silver bars correctly if they were passed in the 'items' list.
        # It's better to exclusively use save_estimate_with_returns.
        print("Warning: Using deprecated save_estimate method.")
        return self.save_estimate_with_returns(voucher_no, date, silver_rate, regular_items, return_items, totals)

    def assign_bars_to_list(self, bar_ids, note):
        """
        Assigns multiple silver bars to a 'list' by changing their status
        to 'Assigned' and recording a transfer event with the given note.
        Only assigns bars currently 'In Stock'.
        Returns True on success, False on failure.
        """
        if not bar_ids:
            print("No bar IDs provided for assignment.")
            return False

        date_assigned = datetime.now().strftime('%Y-%m-%d')
        transfer_base_no = f"L{datetime.now().strftime('%Y%m%d%H%M%S')}"  # List assignment prefix

        try:
            self.conn.execute('BEGIN TRANSACTION')
            assigned_count = 0
            for index, bar_id in enumerate(bar_ids):
                # Verify current status is 'In Stock' before assigning
                self.cursor.execute("SELECT status FROM silver_bars WHERE id = ?", (bar_id,))
                row = self.cursor.fetchone()
                if not row:
                    print(f"Warning: Bar ID {bar_id} not found. Skipping.")
                    continue  # Skip this bar
                current_status = row['status']

                if current_status != 'In Stock':
                    print(
                        f"Warning: Bar ID {bar_id} is not 'In Stock' (Status: {current_status}). Skipping assignment.")
                    continue  # Skip bars not in stock

                # Update bar status
                self.cursor.execute(
                    "UPDATE silver_bars SET status = ? WHERE id = ?",
                    ('Assigned', bar_id)
                )

                # Create transfer record
                transfer_no = f"{transfer_base_no}-{index + 1}"  # Unique transfer number per bar in list
                self.cursor.execute('''
                    INSERT INTO bar_transfers
                    (transfer_no, date, bar_id, from_status, to_status, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (transfer_no, date_assigned, bar_id, current_status, 'Assigned', note))
                assigned_count += 1

            self.conn.commit()
            print(f"Successfully assigned {assigned_count} bars.")
            return True

        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Database error assigning bars to list: {e}")
            return False

    def transfer_silver_bar(self, bar_id, to_status, notes=None):
        """Transfer a silver bar to a new status."""
        # (No changes needed here, but ensure 'Assigned' is handled if needed elsewhere)
        try:
            # Get current status
            self.cursor.execute("SELECT status FROM silver_bars WHERE id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row:
                return False

            from_status = row['status']

            # Begin transaction
            self.conn.execute('BEGIN TRANSACTION')

            # Update bar status
            self.cursor.execute(
                "UPDATE silver_bars SET status = ? WHERE id = ?",
                (to_status, bar_id)
            )

            # Create transfer record
            transfer_no = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
            date = datetime.now().strftime('%Y-%m-%d')

            self.cursor.execute('''
                   INSERT INTO bar_transfers
                   (transfer_no, date, bar_id, from_status, to_status, notes)
                   VALUES (?, ?, ?, ?, ?, ?)
               ''', (transfer_no, date, bar_id, from_status, to_status, notes))

            # Commit transaction
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def save_estimate_with_returns(self, voucher_no, date, silver_rate, regular_items, return_items, totals):
        """Save an estimate with regular and return items, including silver bar flag."""
        try:
            # Begin transaction
            self.conn.execute('BEGIN TRANSACTION')

            # Save estimate header - using the calculated net totals
            self.cursor.execute('''
                INSERT OR REPLACE INTO estimates
                (voucher_no, date, silver_rate, total_gross, total_net, total_fine, total_wage)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                voucher_no,
                date,
                silver_rate,
                totals.get('total_gross', 0.0), # Store overall gross
                totals.get('total_net', 0.0),   # Store overall net
                totals.get('net_fine', 0.0),    # Store NET fine
                totals.get('net_wage', 0.0)     # Store NET wage
            ))

            # Delete existing items if this is an update
            self.cursor.execute('DELETE FROM estimate_items WHERE voucher_no = ?', (voucher_no,))

            # Save regular items (includes regular items AND non-return silver bars)
            for item in regular_items:
                self._save_estimate_item(voucher_no, item) # Flags are now in item dict

            # Save return items (includes return items AND return silver bars)
            for item in return_items:
                self._save_estimate_item(voucher_no, item) # Flags are now in item dict

            # Commit the transaction
            self.conn.commit()
            return True

        except sqlite3.Error as e:
            # Rollback on error
            self.conn.rollback()
            print(f"Database error: {e}")
            return False

    # Modified _save_estimate_item to read flags from item dict
    def _save_estimate_item(self, voucher_no, item):
        """Save a single estimate item, reading flags from the item dictionary."""
        is_return = 1 if item.get('is_return', False) else 0
        is_silver_bar = 1 if item.get('is_silver_bar', False) else 0

        self.cursor.execute('''
            INSERT INTO estimate_items
            (voucher_no, item_code, item_name, gross, poly, net_wt,
             purity, wage_rate, pieces, wage, fine, is_return, is_silver_bar)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            voucher_no,
            item.get('code', ''),
            item.get('name', ''),
            item.get('gross', 0.0),
            item.get('poly', 0.0),
            item.get('net_wt', 0.0),
            item.get('purity', 0.0),
            item.get('wage_rate', 0.0),
            item.get('pieces', 1),
            item.get('wage', 0.0),
            item.get('fine', 0.0),
            is_return,
            is_silver_bar
        ))

    def add_silver_bar(self, bar_no, weight, purity):
        """Add a new silver bar to inventory."""
        date_added = datetime.now().strftime('%Y-%m-%d')
        fine_weight = weight * (purity / 100)

        try:
            self.cursor.execute('''
                INSERT INTO silver_bars
                (bar_no, weight, purity, fine_weight, date_added, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (bar_no, weight, purity, fine_weight, date_added, 'In Stock'))

            self.conn.commit()
            return True
        except sqlite3.IntegrityError: # Catch specific error for duplicate bar_no
            self.conn.rollback()
            print(f"Database integrity error: Could not add silver bar '{bar_no}'. It might already exist.")
            return False
        except sqlite3.Error as e:
            self.conn.rollback()
            print(f"Database error adding silver bar: {e}")
            return False

    def get_silver_bars(self, status=None):
        """Get silver bars, optionally filtered by status."""
        query = "SELECT * FROM silver_bars"
        params = []

        if status:
            query += " WHERE status = ?"
            params.append(status)

        query += " ORDER BY date_added DESC, bar_no"

        self.cursor.execute(query, params)
        return self.cursor.fetchall()

    def transfer_silver_bar(self, bar_id, to_status, notes=None):
        """Transfer a silver bar to a new status."""
        try:
            # Get current status
            self.cursor.execute("SELECT status FROM silver_bars WHERE id = ?", (bar_id,))
            row = self.cursor.fetchone()
            if not row:
                return False

            from_status = row['status']

            # Begin transaction
            self.conn.execute('BEGIN TRANSACTION')

            # Update bar status
            self.cursor.execute(
                "UPDATE silver_bars SET status = ? WHERE id = ?",
                (to_status, bar_id)
            )

            # Create transfer record
            transfer_no = f"T{datetime.now().strftime('%Y%m%d%H%M%S')}"
            date = datetime.now().strftime('%Y-%m-%d')

            self.cursor.execute('''
                INSERT INTO bar_transfers
                (transfer_no, date, bar_id, from_status, to_status, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (transfer_no, date, bar_id, from_status, to_status, notes))

            # Commit transaction
            self.conn.commit()
            return True
        except sqlite3.Error:
            self.conn.rollback()
            return False

    def drop_tables(self):
        """Drop all tables from the database."""
        try:
            # Begin transaction
            self.conn.execute('BEGIN TRANSACTION')

            # Drop all tables
            self.cursor.execute('DROP TABLE IF EXISTS estimate_items')
            self.cursor.execute('DROP TABLE IF EXISTS estimates')
            self.cursor.execute('DROP TABLE IF EXISTS items')
            self.cursor.execute('DROP TABLE IF EXISTS silver_bars')
            self.cursor.execute('DROP TABLE IF EXISTS bar_transfers')

            # Commit transaction
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            # Rollback on error
            self.conn.rollback()
            print(f"Database error dropping tables: {e}")
            return False

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()