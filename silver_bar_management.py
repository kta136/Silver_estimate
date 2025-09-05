#!/usr/bin/env python
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit, QComboBox,
    QMessageBox, QAbstractItemView, QFrame, QInputDialog, QSplitter,
    QWidget # Added QSplitter, QWidget
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor
import traceback # Added for error handling in actions

class SilverBarDialog(QDialog):
    """Dialog for managing silver bars and grouping them into lists (v2.0)."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_list_id = None # Track the currently selected list
        self.init_ui()
        self.load_lists()
        self.load_available_bars()

    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Silver Bar Management (v2.0)")
        self.setMinimumSize(950, 750) # Adjusted size

        main_layout = QVBoxLayout(self)

        # --- Top Section: Search and Available Bars ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0,0,0,0)

        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search Available Bars by Weight (approx):"))
        self.weight_search_edit = QLineEdit()
        self.weight_search_edit.setPlaceholderText("Enter weight (e.g., 1000.123)")
        self.weight_search_edit.textChanged.connect(self.load_available_bars) # Use textChanged for live search
        search_layout.addWidget(self.weight_search_edit)
        self.refresh_available_button = QPushButton("Refresh Available")
        self.refresh_available_button.clicked.connect(self.load_available_bars)
        search_layout.addWidget(self.refresh_available_button)
        top_layout.addLayout(search_layout)

        self.available_bars_table = QTableWidget()
        self.available_bars_table.setColumnCount(7) # bar_id, estimate_voucher_no, weight, purity, fine_weight, date_added, status
        self.available_bars_table.setHorizontalHeaderLabels(["ID", "Estimate Vch/Note", "Weight (g)", "Purity (%)", "Fine Wt (g)", "Date Added", "Status"])
        self.available_bars_table.setColumnHidden(0, True) # Hide bar_id
        self.available_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.available_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.available_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.available_bars_table.setAlternatingRowColors(True)
        self.available_bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.available_bars_table.horizontalHeader().setStretchLastSection(True)
        top_layout.addWidget(self.available_bars_table)
        
        # Add totals label for available bars
        self.available_totals_label = QLabel("Available Bars: 0 | Total Weight: 0.000 g | Total Fine Wt: 0.000 g")
        self.available_totals_label.setStyleSheet("font-weight: bold;")
        self.available_totals_label.setAlignment(Qt.AlignRight)
        top_layout.addWidget(self.available_totals_label)

        # --- Middle Section: List Selection and Actions ---
        list_action_layout = QHBoxLayout()
        list_action_layout.addWidget(QLabel("Select List:"))
        self.list_combo = QComboBox()
        self.list_combo.setMinimumWidth(200)
        self.list_combo.currentIndexChanged.connect(self.list_selection_changed)
        list_action_layout.addWidget(self.list_combo)

        self.create_list_button = QPushButton("Create New List...")
        self.create_list_button.clicked.connect(self.create_new_list)
        list_action_layout.addWidget(self.create_list_button)

        self.add_to_list_button = QPushButton("Add Selected Bars to List ↑")
        self.add_to_list_button.setToolTip("Add selected 'Available' bars to the list selected above.")
        self.add_to_list_button.clicked.connect(self.add_selected_to_list)
        list_action_layout.addWidget(self.add_to_list_button)
        list_action_layout.addStretch()


        # --- Bottom Section: Bars in Selected List ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0,0,0,0)

        list_details_layout = QHBoxLayout()
        self.list_details_label = QLabel("Selected List: None")
        self.list_details_label.setStyleSheet("font-weight: bold;")
        list_details_layout.addWidget(self.list_details_label)
        list_details_layout.addStretch()
        self.edit_note_button = QPushButton("Edit List Note...")
        self.edit_note_button.clicked.connect(self.edit_list_note)
        self.edit_note_button.setEnabled(False) # Disabled initially
        list_details_layout.addWidget(self.edit_note_button)
        self.print_list_button = QPushButton("Print List")
        self.print_list_button.clicked.connect(self.print_selected_list)
        self.print_list_button.setEnabled(False) # Disabled initially
        list_details_layout.addWidget(self.print_list_button)
        self.delete_list_button = QPushButton("Delete List")
        self.delete_list_button.setStyleSheet("color: red;")
        self.delete_list_button.clicked.connect(self.delete_selected_list)
        self.delete_list_button.setEnabled(False) # Disabled initially
        list_details_layout.addWidget(self.delete_list_button)
        bottom_layout.addLayout(list_details_layout)


        self.list_bars_table = QTableWidget()
        # Same columns as available bars table for consistency
        self.list_bars_table.setColumnCount(7)
        self.list_bars_table.setHorizontalHeaderLabels(["ID", "Estimate Vch/Note", "Weight (g)", "Purity (%)", "Fine Wt (g)", "Date Added", "Status"])
        self.list_bars_table.setColumnHidden(0, True)
        self.list_bars_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.list_bars_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.list_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_bars_table.setAlternatingRowColors(True)
        self.list_bars_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.list_bars_table.horizontalHeader().setStretchLastSection(True)
        bottom_layout.addWidget(self.list_bars_table)
        
        # Add totals label for list bars
        self.list_totals_label = QLabel("List Bars: 0 | Total Weight: 0.000 g | Total Fine Wt: 0.000 g")
        self.list_totals_label.setStyleSheet("font-weight: bold;")
        self.list_totals_label.setAlignment(Qt.AlignRight)
        bottom_layout.addWidget(self.list_totals_label)

        list_bar_actions_layout = QHBoxLayout()
        list_bar_actions_layout.addStretch()
        self.remove_from_list_button = QPushButton("Remove Selected Bars from List ↓")
        self.remove_from_list_button.setToolTip("Remove selected bars from the list above (status becomes 'In Stock').")
        self.remove_from_list_button.clicked.connect(self.remove_selected_from_list)
        self.remove_from_list_button.setEnabled(False) # Disabled initially
        list_bar_actions_layout.addWidget(self.remove_from_list_button)
        bottom_layout.addLayout(list_bar_actions_layout)

        # --- Splitter to separate Available and List views ---
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(bottom_widget)
        splitter.setSizes([350, 400]) # Initial size distribution

        main_layout.addLayout(list_action_layout) # List selection above splitter
        main_layout.addWidget(splitter)

        # --- Bottom Close Button ---
        close_button_layout = QHBoxLayout()
        close_button_layout.addStretch()
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        close_button_layout.addWidget(self.close_button)
        main_layout.addLayout(close_button_layout)

    # --- Data Loading Methods ---

    def load_available_bars(self):
        """Loads bars with status 'In Stock' and no list_id, applying weight filter."""
        # print("Loading available bars...") # Optional: Keep for debugging
        weight_query = self.weight_search_edit.text().strip()
        try:
            # Use get_silver_bars with specific filters
            available_bars = self.db_manager.get_silver_bars(
                status='In Stock',
                weight_query=weight_query if weight_query else None
            )
            # Filter further to ensure list_id is NULL (get_silver_bars doesn't have this filter yet)
            available_bars = [bar for bar in available_bars if bar['list_id'] is None]
            self._populate_table(self.available_bars_table, available_bars)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load available bars: {e}")
            self.available_bars_table.setRowCount(0)

    def load_lists(self):
        """Populates the list selection combo box."""
        import logging
        logging.getLogger(__name__).debug("Loading lists...")
        self.list_combo.blockSignals(True)
        self.list_combo.clear()
        self.list_combo.addItem("--- Select a List ---", None)
        try:
            lists = self.db_manager.get_silver_bar_lists()
            for list_row in lists:
                # Store list_id as item data, show list note but remove timestamp
                list_note = list_row['list_note'] or ""
                list_date = list_row['creation_date'].split()[0] if 'creation_date' in list_row.keys() and list_row['creation_date'] else ""
                display_text = f"{list_row['list_identifier']} ({list_date})"
                if list_note:
                    display_text += f" - {list_note}"
                self.list_combo.addItem(display_text, list_row['list_id'])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load lists: {e}")
        finally:
            self.list_combo.blockSignals(False)
            self.list_selection_changed() # Update UI based on initial selection

    def list_selection_changed(self):
        """Handles changes in the selected list."""
        selected_index = self.list_combo.currentIndex()
        self.current_list_id = self.list_combo.itemData(selected_index)

        is_list_selected = self.current_list_id is not None
        self.edit_note_button.setEnabled(is_list_selected)
        self.print_list_button.setEnabled(is_list_selected)
        self.delete_list_button.setEnabled(is_list_selected)
        self.remove_from_list_button.setEnabled(is_list_selected)

        if is_list_selected:
            details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
            if details:
                self.list_details_label.setText(f"Selected List: {details['list_identifier']} (Note: {details['list_note'] or 'N/A'})")
            else:
                self.list_details_label.setText("Selected List: Error loading details")
            self.load_bars_in_selected_list()
        else:
            self.list_details_label.setText("Selected List: None")
            self.list_bars_table.setRowCount(0) # Clear list bars table

    def load_bars_in_selected_list(self):
        """Loads bars assigned to the currently selected list."""
        if self.current_list_id is None:
            self.list_bars_table.setRowCount(0)
            return

        # print(f"Loading bars for list ID: {self.current_list_id}") # Optional: Keep for debugging
        try:
            bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)
            self._populate_table(self.list_bars_table, bars_in_list)
        except Exception as e:
             QMessageBox.critical(self, "Error", f"Failed to load bars for list {self.current_list_id}: {e}")
             self.list_bars_table.setRowCount(0)

    # --- Action Methods ---

    def create_new_list(self):
        """Prompts for a note and creates a new list."""
        import logging
        logging.getLogger(__name__).info("Creating new list...")
        note, ok = QInputDialog.getText(self, "Create New List", "Enter a note for the new list:", QLineEdit.Normal)
        if ok:
            new_list_id = self.db_manager.create_silver_bar_list(note if note else None)
            if new_list_id:
                QMessageBox.information(self, "Success", "New list created.")
                self.load_lists()
                # Optionally select the newly created list
                index = self.list_combo.findData(new_list_id)
                if index >= 0:
                    self.list_combo.setCurrentIndex(index)
            else:
                QMessageBox.critical(self, "Error", "Failed to create new list.")

    def add_selected_to_list(self):
        """Adds selected available bars to the currently selected list."""
        if self.current_list_id is None:
            QMessageBox.warning(self, "Selection Error", "Please select a list first.")
            return

        selected_rows = self.available_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select one or more available bars to add.")
            return

        bar_ids_to_add = []
        for index in selected_rows:
            bar_id_item = self.available_bars_table.item(index.row(), 0) # Hidden ID column
            if bar_id_item:
                bar_ids_to_add.append(bar_id_item.data(Qt.UserRole)) # Get ID from item data

        if not bar_ids_to_add:
            QMessageBox.warning(self, "Error", "Could not get IDs for selected bars.")
            return

        reply = QMessageBox.question(self, "Confirm Add",
                                     f"Add {len(bar_ids_to_add)} selected bar(s) to list '{self.list_combo.currentText()}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            added_count = 0
            failed_ids = []
            for bar_id in bar_ids_to_add:
                if self.db_manager.assign_bar_to_list(bar_id, self.current_list_id):
                    added_count += 1
                else:
                    failed_ids.append(str(bar_id))

            if added_count > 0:
                QMessageBox.information(self, "Success", f"{added_count} bar(s) added to the list.")
            if failed_ids:
                QMessageBox.warning(self, "Error", f"Failed to add bars with IDs: {', '.join(failed_ids)}")

            self.load_available_bars()
            self.load_bars_in_selected_list()

    def remove_selected_from_list(self):
        """Removes selected bars from the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return

        selected_rows = self.list_bars_table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Selection Error", "Please select one or more bars from the list to remove.")
            return

        bar_ids_to_remove = []
        for index in selected_rows:
            bar_id_item = self.list_bars_table.item(index.row(), 0) # Hidden ID column
            if bar_id_item:
                bar_ids_to_remove.append(bar_id_item.data(Qt.UserRole))

        if not bar_ids_to_remove:
            QMessageBox.warning(self, "Error", "Could not get IDs for selected bars.")
            return

        reply = QMessageBox.question(self, "Confirm Remove",
                                     f"Remove {len(bar_ids_to_remove)} selected bar(s) from list '{self.list_combo.currentText()}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            removed_count = 0
            failed_ids = []
            for bar_id in bar_ids_to_remove:
                if self.db_manager.remove_bar_from_list(bar_id):
                    removed_count += 1
                else:
                    failed_ids.append(str(bar_id))

            if removed_count > 0:
                QMessageBox.information(self, "Success", f"{removed_count} bar(s) removed from the list.")
            if failed_ids:
                QMessageBox.warning(self, "Error", f"Failed to remove bars with IDs: {', '.join(failed_ids)}")

            self.load_available_bars()
            self.load_bars_in_selected_list()

    def edit_list_note(self):
        """Edits the note for the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(self, "Error", "Could not retrieve current list details.")
            return

        current_note = details['list_note'] or ""
        new_note, ok = QInputDialog.getText(self, "Edit List Note",
                                            f"Enter new note for list '{details['list_identifier']}':",
                                            QLineEdit.Normal, current_note)

        if ok and new_note != current_note:
            if self.db_manager.update_silver_bar_list_note(self.current_list_id, new_note):
                QMessageBox.information(self, "Success", "List note updated.")
                # Refresh label and potentially combo box text
                self.list_details_label.setText(f"Selected List: {details['list_identifier']} (Note: {new_note or 'N/A'})")
                # Find and update combo box item text with the new note
                index = self.list_combo.findData(self.current_list_id)
                if index >= 0:
                    list_date = details['creation_date'].split()[0] if 'creation_date' in details.keys() and details['creation_date'] else ""
                    display_text = f"{details['list_identifier']} ({list_date})"
                    if new_note:
                        display_text += f" - {new_note}"
                    self.list_combo.setItemText(index, display_text)
            else:
                QMessageBox.critical(self, "Error", "Failed to update list note.")

    def delete_selected_list(self):
        """Deletes the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        list_name = details['list_identifier'] if details else f"ID {self.current_list_id}"

        reply = QMessageBox.warning(self, "Confirm Delete",
                                    f"Are you sure you want to delete list '{list_name}'?\n"
                                    f"All bars currently assigned to this list will be unassigned (status set to 'In Stock').\n"
                                    f"This action cannot be undone.",
                                    QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)

        if reply == QMessageBox.Yes:
            success, msg = self.db_manager.delete_silver_bar_list(self.current_list_id)
            if success:
                QMessageBox.information(self, "Success", f"List '{list_name}' deleted successfully.")
                self.load_lists() # Reload lists, which triggers selection change and table refresh
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete list: {msg}")

    def print_selected_list(self):
        """Prints the details and bars of the currently selected list."""
        if self.current_list_id is None:
             QMessageBox.warning(self, "Error", "No list selected.")
             return
        details = self.db_manager.get_silver_bar_list_details(self.current_list_id)
        if not details:
            QMessageBox.warning(self, "Error", "Could not retrieve list details for printing.")
            return

        bars_in_list = self.db_manager.get_bars_in_list(self.current_list_id)

        import logging
        logging.getLogger(__name__).info(f"Printing list {details['list_identifier']} (ID: {self.current_list_id}) with {len(bars_in_list)} bars.")

        try:
            from print_manager import PrintManager # Import locally
            # Assuming parent() gives access to main window or similar context for font
            parent_context = self.parent()
            current_print_font = getattr(parent_context, 'print_font', None) if parent_context else None

            print_manager = PrintManager(self.db_manager, print_font=current_print_font)

            # Call the existing method, assuming it's suitable or will be adapted
            # This method is defined in print_manager.py and might need adjustment (Step 5)
            success = print_manager.print_silver_bar_list_details(details, bars_in_list, self)

            if not success:
                 QMessageBox.warning(self, "Print Error", "Failed to generate print preview for the list.")

        except ImportError:
             QMessageBox.critical(self, "Error", "Could not import PrintManager.")
        except AttributeError as ae:
             QMessageBox.critical(self, "Error", f"Print function not found or incorrect in PrintManager: {ae}")
        except Exception as e:
             QMessageBox.critical(self, "Print Error", f"An unexpected error occurred during printing: {e}\n{traceback.format_exc()}")

    # --- Helper Methods ---
    def _populate_table(self, table, bars_data):
        """Helper function to populate a table widget with bar data and update totals."""
        table.blockSignals(True)
        table.setRowCount(0) # Clear existing rows
        
        # Initialize totals
        total_weight = 0.0
        total_fine_weight = 0.0
        bar_count = 0
        try:
            if bars_data:
                table.setRowCount(len(bars_data))
                for row_idx, bar_row in enumerate(bars_data):
                    bar_id = bar_row['bar_id']
                    id_item = QTableWidgetItem(str(bar_id))
                    id_item.setData(Qt.UserRole, bar_id) # Store ID in item data

                    # Access items using dictionary-style keys for sqlite3.Row
                    voucher_no = bar_row['estimate_voucher_no'] if 'estimate_voucher_no' in bar_row.keys() else 'N/A'
                    
                    # Get the note for this estimate
                    note = ""
                    try:
                        self.db_manager.cursor.execute("SELECT note FROM estimates WHERE voucher_no = ?", (voucher_no,))
                        result = self.db_manager.cursor.fetchone()
                        if result and result['note']:
                            note = result['note']
                    except Exception:
                        pass
                    
                    # Create display text with voucher and note
                    display_text = voucher_no
                    if note:
                        display_text += f" ({note})"
                    
                    est_vch_item = QTableWidgetItem(display_text)
                    weight_item = QTableWidgetItem(f"{bar_row['weight'] if 'weight' in bar_row.keys() else 0.0:.3f}")
                    purity_item = QTableWidgetItem(f"{bar_row['purity'] if 'purity' in bar_row.keys() else 0.0:.2f}")
                    fine_wt_item = QTableWidgetItem(f"{bar_row['fine_weight'] if 'fine_weight' in bar_row.keys() else 0.0:.3f}")
                    date_item = QTableWidgetItem(bar_row['date_added'] if 'date_added' in bar_row.keys() else '')
                    status_item = QTableWidgetItem(bar_row['status'] if 'status' in bar_row.keys() else '')

                    # Set alignment for numeric columns
                    weight_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    purity_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    fine_wt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                    # Set items in table
                    table.setItem(row_idx, 0, id_item) # Hidden ID
                    table.setItem(row_idx, 1, est_vch_item)
                    table.setItem(row_idx, 2, weight_item)
                    table.setItem(row_idx, 3, purity_item)
                    table.setItem(row_idx, 4, fine_wt_item)
                    table.setItem(row_idx, 5, date_item)
                    table.setItem(row_idx, 6, status_item)
                    # Update totals
                    weight = bar_row['weight'] if 'weight' in bar_row.keys() and bar_row['weight'] is not None else 0.0
                    fine_weight = bar_row['fine_weight'] if 'fine_weight' in bar_row.keys() and bar_row['fine_weight'] is not None else 0.0
                    total_weight += weight
                    total_fine_weight += fine_weight
                    bar_count += 1
                
                # Update the appropriate totals label
                totals_text = f"Bars: {bar_count} | Total Weight: {total_weight:.3f} g | Total Fine Wt: {total_fine_weight:.3f} g"
                if table == self.available_bars_table:
                    self.available_totals_label.setText(f"Available {totals_text}")
                elif table == self.list_bars_table:
                    self.list_totals_label.setText(f"List {totals_text}")
        except Exception as e:
             QMessageBox.critical(self, "Table Error", f"Error populating table: {e}\n{traceback.format_exc()}")
        finally:
            table.blockSignals(False)
            # Optional: Resize columns after populating if not using fixed modes
            # table.resizeColumnsToContents()

# Example usage (if run directly)
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    # Mock DB Manager for testing
    class MockDBManager:
        def get_silver_bar_lists(self): return [{'list_id': 1, 'list_identifier': 'L-20250424-001', 'creation_date': '2025-04-24 10:00:00', 'list_note': 'Test List 1'}, {'list_id': 2, 'list_identifier': 'L-20250424-002', 'creation_date': '2025-04-24 11:00:00', 'list_note': None}]
        def get_silver_bars(self, status=None, weight_query=None, estimate_voucher_no=None): # Updated mock signature
             print(f"Mock DB: get_silver_bars(status={status}, weight_query={weight_query})")
             # Simulate filtering
             bars = [{'bar_id': 101, 'estimate_voucher_no': '202504231', 'weight': 1000.0, 'purity': 99.9, 'fine_weight': 999.0, 'date_added': '2025-04-23', 'status': 'In Stock', 'list_id': None},
                     {'bar_id': 103, 'estimate_voucher_no': '202504232', 'weight': 1000.123, 'purity': 99.0, 'fine_weight': 990.12177, 'date_added': '2025-04-23', 'status': 'In Stock', 'list_id': None}]
             filtered_bars = bars
             if status:
                 filtered_bars = [b for b in filtered_bars if b['status'] == status]
             if weight_query:
                 try:
                     target = float(weight_query)
                     filtered_bars = [b for b in filtered_bars if abs(b['weight'] - target) < 0.001]
                 except ValueError: pass # Ignore invalid weight query
             return filtered_bars
        def get_bars_in_list(self, list_id): return [{'bar_id': 102, 'estimate_voucher_no': '202504241', 'weight': 500.0, 'purity': 99.5, 'fine_weight': 497.5, 'date_added': '2025-04-24', 'status': 'Assigned', 'list_id': list_id}] if list_id == 1 else []
        def get_silver_bar_list_details(self, list_id): return {'list_id': list_id, 'list_identifier': f'L-20250424-{list_id:03d}', 'creation_date': '...', 'list_note': 'Mock Note'} if list_id else None
        def create_silver_bar_list(self, note): print(f"Mock: Create list with note: {note}"); return 3 # Simulate new ID
        # Add mock methods for assign, remove, update_note, delete_list as needed for testing UI flow

    app = QApplication(sys.argv)
    db_manager = MockDBManager() # Use mock for direct run
    dialog = SilverBarDialog(db_manager)
    dialog.show()
    sys.exit(app.exec_())
