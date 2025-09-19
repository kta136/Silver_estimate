#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QLineEdit, QDateEdit, QMessageBox)
from PyQt5.QtCore import Qt, QDate, QThread, QObject, pyqtSignal
from .print_manager import PrintManager # Added import

class EstimateHistoryDialog(QDialog):
    """Dialog for browsing and selecting past estimates."""

    # Accept db_manager, an explicit main_window_ref, and the standard parent
    def __init__(self, db_manager, main_window_ref, parent=None):
        super().__init__(parent) # Use standard parent for QDialog
        self.db_manager = db_manager
        self.main_window = main_window_ref # Store the explicit reference to MainWindow
        self.selected_voucher = None
        self.init_ui()
        self.load_estimates()

    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Estimate History")
        self.setMinimumWidth(1000)
        self.setMinimumHeight(600)

        # Main layout
        layout = QVBoxLayout(self)

        # Header
        header_label = QLabel("Estimate History")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)

        # Search filters
        filter_layout = QHBoxLayout()

        # Date range filter
        filter_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate().addMonths(-1))  # Default to 1 month ago
        filter_layout.addWidget(self.date_from)

        filter_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        filter_layout.addWidget(self.date_to)

        # Voucher search
        filter_layout.addWidget(QLabel("Voucher No:"))
        self.voucher_search = QLineEdit()
        self.voucher_search.setMaximumWidth(150)
        filter_layout.addWidget(self.voucher_search)

        # Search button
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.load_estimates)
        filter_layout.addWidget(self.search_button)

        # Add filters to main layout
        layout.addLayout(filter_layout)

        # Estimates table
        self.estimates_table = QTableWidget()
        self.estimates_table.setColumnCount(9) # Increased column count to include Note
        self.estimates_table.setHorizontalHeaderLabels([
            "Voucher No", "Date", "Note", "Silver Rate", "Total Gross",
            "Total Net", "Net Fine", "Net Wage", "Grand Total" # Moved Note column after Date
        ])

        # Set column widths (adjusting for new columns)
        self.estimates_table.setColumnWidth(0, 110)  # Voucher No
        self.estimates_table.setColumnWidth(1, 90)   # Date
        self.estimates_table.setColumnWidth(2, 200)  # Note (Moved here)
        self.estimates_table.setColumnWidth(3, 90)   # Silver Rate
        self.estimates_table.setColumnWidth(4, 90)   # Total Gross
        self.estimates_table.setColumnWidth(5, 90)   # Total Net
        self.estimates_table.setColumnWidth(6, 90)   # Net Fine
        self.estimates_table.setColumnWidth(7, 90)   # Net Wage
        self.estimates_table.setColumnWidth(8, 110)  # Grand Total

        # Table properties
        self.estimates_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.estimates_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.estimates_table.setSelectionMode(QTableWidget.SingleSelection)
        self.estimates_table.itemDoubleClicked.connect(self.accept)

        layout.addWidget(self.estimates_table)

        # Buttons
        button_layout = QHBoxLayout()

        self.open_button = QPushButton("Open Selected")
        self.open_button.clicked.connect(self.accept)
        button_layout.addWidget(self.open_button)

        self.print_button = QPushButton("Print Selected")
        self.print_button.clicked.connect(self.print_estimate)
        button_layout.addWidget(self.print_button)

        self.delete_button = QPushButton("Delete Selected") # New button
        self.delete_button.setToolTip("Permanently delete the selected estimate")
        self.delete_button.clicked.connect(self.delete_selected_estimate) # Connect to new handler
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch(1) # Add stretch before close

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def load_estimates(self):
        """Load estimates based on search criteria (runs queries in a background thread)."""
        # Start threaded load and return early to keep UI responsive
        try:
            self.search_button.setEnabled(False)
            if hasattr(self, 'open_button'): self.open_button.setEnabled(False)
            if hasattr(self, 'print_button'): self.print_button.setEnabled(False)
            if hasattr(self, 'delete_button'): self.delete_button.setEnabled(False)
        except Exception:
            pass

        worker = _HistoryLoadWorker(self.db_manager.temp_db_path,
                                    self.date_from.date().toString("yyyy-MM-dd"),
                                    self.date_to.date().toString("yyyy-MM-dd"),
                                    self.voucher_search.text().strip())
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(lambda headers, agg: self._populate_table(headers, agg))
        worker.error.connect(lambda msg: QMessageBox.warning(self, "Load Error", msg))
        worker.finished.connect(lambda: self._loading_done(thread, worker))
        thread.start()
        return

        table = self.estimates_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setSortingEnabled(False)
            # Get search criteria
            date_from = self.date_from.date().toString("yyyy-MM-dd")
            date_to = self.date_to.date().toString("yyyy-MM-dd")
            voucher_search = self.voucher_search.text().strip()

            # Fetch only estimate headers for performance (no item lists)
            headers = self.db_manager.get_estimate_headers(date_from, date_to, voucher_search)

            # Clear and populate table
            table.setRowCount(0)
            table.setRowCount(len(headers))  # Set row count based on results

            # Pre-compute Regular-only aggregates for all vouchers in one query
            voucher_nos = [str(h['voucher_no']) for h in headers]
            agg_map = {}
            try:
                if voucher_nos and hasattr(self.db_manager, 'cursor') and self.db_manager.cursor:
                    placeholders = ",".join(["?"] * len(voucher_nos))
                    sql = (
                        f"SELECT voucher_no, "
                        f"SUM(CASE WHEN is_return=0 AND is_silver_bar=0 THEN gross ELSE 0 END) AS rg, "
                        f"SUM(CASE WHEN is_return=0 AND is_silver_bar=0 THEN net_wt ELSE 0 END) AS rn "
                        f"FROM estimate_items WHERE voucher_no IN ({placeholders}) GROUP BY voucher_no"
                    )
                    self.db_manager.cursor.execute(sql, voucher_nos)
                    for row in self.db_manager.cursor.fetchall():
                        # sqlite3.Row supports index or key; use keys for clarity
                        vno = row["voucher_no"] if "voucher_no" in row.keys() else row[0]
                        rg = row["rg"] if "rg" in row.keys() else row[1]
                        rn = row["rn"] if "rn" in row.keys() else row[2]
                        agg_map[str(vno)] = (float(rg or 0.0), float(rn or 0.0))
            except Exception:
                agg_map = {}

            for row_idx, header in enumerate(headers):
                vno = str(header['voucher_no'])
                regular_gross_sum, regular_net_sum = agg_map.get(vno, (0.0, 0.0))

                # Populate table cells
                table.setItem(row_idx, 0, QTableWidgetItem(header['voucher_no']))
                table.setItem(row_idx, 1, QTableWidgetItem(header['date']))
                # Column 2: Note (Moved here)
                note = header.get('note', '')
                table.setItem(row_idx, 2, QTableWidgetItem(note))
                table.setItem(row_idx, 3, QTableWidgetItem(f"{header.get('silver_rate', 0.0):.2f}"))
                # Column 4: Regular Gross
                table.setItem(row_idx, 4, QTableWidgetItem(f"{regular_gross_sum:.3f}"))
                # Column 5: Regular Net
                table.setItem(row_idx, 5, QTableWidgetItem(f"{regular_net_sum:.3f}"))
                # Column 6: Net Fine (Directly from header as it's already calculated net)
                net_fine = header.get('total_fine', 0.0)
                table.setItem(row_idx, 6, QTableWidgetItem(f"{net_fine:.3f}"))
                # Column 7: Net Wage (Directly from header)
                net_wage = header.get('total_wage', 0.0)
                table.setItem(row_idx, 7, QTableWidgetItem(f"{net_wage:.2f}"))

                # Column 8: Grand Total (Net Value + Net Wage + Last Balance Amount)
                silver_rate = header.get('silver_rate', 0.0)
                net_value = net_fine * silver_rate
                last_balance_amount = header.get('last_balance_amount', 0.0)
                grand_total = net_value + net_wage + last_balance_amount
                table.setItem(row_idx, 8, QTableWidgetItem(f"{grand_total:.2f}"))
        finally:
            table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

    def _populate_table(self, headers, agg_map):
        table = self.estimates_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.setSortingEnabled(False)
            table.setRowCount(0)
            table.setRowCount(len(headers))
            for row_idx, header in enumerate(headers):
                vno = str(header['voucher_no'])
                rg, rn = agg_map.get(vno, (0.0, 0.0))
                table.setItem(row_idx, 0, QTableWidgetItem(header['voucher_no']))
                table.setItem(row_idx, 1, QTableWidgetItem(header['date']))
                note = header.get('note', '')
                table.setItem(row_idx, 2, QTableWidgetItem(note))
                table.setItem(row_idx, 3, QTableWidgetItem(f"{header.get('silver_rate', 0.0):.2f}"))
                table.setItem(row_idx, 4, QTableWidgetItem(f"{rg:.3f}"))
                table.setItem(row_idx, 5, QTableWidgetItem(f"{rn:.3f}"))
                net_fine = header.get('total_fine', 0.0)
                table.setItem(row_idx, 6, QTableWidgetItem(f"{net_fine:.3f}"))
                net_wage = header.get('total_wage', 0.0)
                table.setItem(row_idx, 7, QTableWidgetItem(f"{net_wage:.2f}"))
                silver_rate = header.get('silver_rate', 0.0)
                net_value = net_fine * silver_rate
                last_balance_amount = header.get('last_balance_amount', 0.0)
                grand_total = net_value + net_wage + last_balance_amount
                table.setItem(row_idx, 8, QTableWidgetItem(f"{grand_total:.2f}"))
        finally:
            table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

    def _loading_done(self, thread, worker):
        try:
            thread.quit(); thread.wait(1000)
        except Exception:
            pass
        try:
            worker.deleteLater()
        except Exception:
            pass
        try:
            self.search_button.setEnabled(True)
            if hasattr(self, 'open_button'): self.open_button.setEnabled(True)
            if hasattr(self, 'print_button'): self.print_button.setEnabled(True)
            if hasattr(self, 'delete_button'): self.delete_button.setEnabled(True)
        except Exception:
            pass


    def get_selected_voucher(self):
        """Get the selected voucher number."""
        selected_items = self.estimates_table.selectedItems()
        if not selected_items:
            return None

        row = selected_items[0].row()
        return self.estimates_table.item(row, 0).text()

    def accept(self):
        """Handle dialog acceptance and return the selected voucher."""
        self.selected_voucher = self.get_selected_voucher()
        if not self.selected_voucher:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return

        super().accept()

    def print_estimate(self):
        """Print the selected estimate."""
        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate first.")
            return

        # --- Get the print font from the explicitly stored main window reference ---
        print_font_setting = None
        if self.main_window and hasattr(self.main_window, 'print_font'):
            print_font_setting = self.main_window.print_font
        # ---------------------------------------------------------

        # Create print manager instance, passing the font, and print the selected estimate
        print_manager = PrintManager(self.db_manager, print_font=print_font_setting)
        success = print_manager.print_estimate(voucher_no, self)  # 'self' used as parent for dialogs

        if not success:
            QMessageBox.warning(self, "Print Error", f"Failed to print estimate {voucher_no}.")

    def delete_selected_estimate(self):
        """Handle deletion of the selected estimate."""
        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(self, "Selection Error", "Please select an estimate to delete.")
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Delete Estimate",
            f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            try:
                success = self.db_manager.delete_single_estimate(voucher_no)
                if success:
                    QMessageBox.information(self, "Success", f"Estimate '{voucher_no}' deleted successfully.")
                    self.load_estimates()  # Refresh the list
                else:
                    QMessageBox.warning(self, "Delete Error", f"Estimate '{voucher_no}' could not be deleted (might already be deleted).")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An unexpected error occurred during deletion: {str(e)}")


class _HistoryLoadWorker(QObject):
    data_ready = pyqtSignal(list, dict)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, db_path, date_from, date_to, voucher_search):
        super().__init__()
        self.db_path = db_path
        self.date_from = date_from
        self.date_to = date_to
        self.voucher_search = voucher_search

    def run(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            # Headers only
            query = "SELECT * FROM estimates WHERE 1=1"; params = []
            if self.date_from: query += " AND date >= ?"; params.append(self.date_from)
            if self.date_to: query += " AND date <= ?"; params.append(self.date_to)
            if self.voucher_search: query += " AND voucher_no LIKE ?"; params.append(f"%{self.voucher_search}%")
            query += " ORDER BY CAST(voucher_no AS INTEGER) DESC"
            cur.execute(query, params)
            headers = [dict(r) for r in cur.fetchall()]

            agg_map = {}
            if headers:
                voucher_nos = [str(h['voucher_no']) for h in headers]
                placeholders = ",".join(["?"] * len(voucher_nos))
                sql = (
                    f"SELECT voucher_no, "
                    f"SUM(CASE WHEN is_return=0 AND is_silver_bar=0 THEN gross ELSE 0 END) AS rg, "
                    f"SUM(CASE WHEN is_return=0 AND is_silver_bar=0 THEN net_wt ELSE 0 END) AS rn "
                    f"FROM estimate_items WHERE voucher_no IN ({placeholders}) GROUP BY voucher_no"
                )
                cur.execute(sql, voucher_nos)
                for row in cur.fetchall():
                    vno, rg, rn = row[0], row[1], row[2]
                    agg_map[str(vno)] = (float(rg or 0.0), float(rn or 0.0))
            try:
                conn.close()
            except Exception:
                pass
            self.data_ready.emit(headers, agg_map)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()
