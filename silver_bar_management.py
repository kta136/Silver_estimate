#!/usr/bin/env python
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                            QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
                            QLineEdit, QDoubleSpinBox, QComboBox, QMessageBox,
                            QAbstractItemView, QTextEdit, QFrame, QInputDialog) # Added QInputDialog
from PyQt5.QtCore import Qt, QDate
# Import the secondary dialog for viewing list contents (Defined below)
# from simple_list_view_dialog import ViewListBarsDialog # Placeholder

# --- Simple Dialog for Viewing List Bars (Defined inline for simplicity) ---
class ViewListBarsDialog(QDialog):
    """Simple dialog to display the bars within a selected list."""
    def __init__(self, list_identifier, list_note, bars_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Contents of List: {list_identifier}")
        self.setMinimumSize(600, 400) # Adjusted size
        layout = QVBoxLayout(self)

        # Display List Info
        info_layout = QGridLayout()
        info_layout.addWidget(QLabel("<b>List Identifier:</b>"), 0, 0)
        info_layout.addWidget(QLabel(list_identifier), 0, 1)
        info_layout.addWidget(QLabel("<b>Note:</b>"), 1, 0, alignment=Qt.AlignTop)
        note_display = QTextEdit(list_note if list_note else "N/A")
        note_display.setReadOnly(True)
        note_display.setMaximumHeight(60) # Limit height
        info_layout.addWidget(note_display, 1, 1)
        info_layout.setColumnStretch(1, 1)
        layout.addLayout(info_layout)

        layout.addWidget(QLabel("<b>Assigned Bars:</b>"))

        # Table for Bars
        table = QTableWidget()
        table.setColumnCount(5) # Bar No, Weight, Purity, Fine, Status
        table.setHorizontalHeaderLabels(["Bar Number", "Weight (g)", "Purity (%)", "Fine Wt (g)", "Status"])
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QAbstractItemView.NoSelection) # View only
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)

        table.setRowCount(len(bars_data))
        total_w = 0.0
        total_f = 0.0
        for row, bar in enumerate(bars_data):
            # Safely access data from sqlite3.Row
            bar_no = bar['bar_no'] if bar['bar_no'] is not None else 'N/A'
            weight = bar['weight'] if bar['weight'] is not None else 0.0
            purity = bar['purity'] if bar['purity'] is not None else 0.0
            fine_wt = bar['fine_weight'] if bar['fine_weight'] is not None else 0.0
            status = bar['status'] if bar['status'] is not None else 'N/A'

            table.setItem(row, 0, QTableWidgetItem(bar_no))
            table.setItem(row, 1, QTableWidgetItem(f"{weight:.3f}"))
            table.setItem(row, 2, QTableWidgetItem(f"{purity:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{fine_wt:.3f}"))
            table.setItem(row, 4, QTableWidgetItem(status))
            total_w += weight
            total_f += fine_wt
        layout.addWidget(table)

        # Summary Label
        summary = QLabel(f"<b>Total Bars:</b> {len(bars_data)} | <b>Total Weight:</b> {total_w:,.3f}g | <b>Total Fine:</b> {total_f:,.3f}g")
        summary.setAlignment(Qt.AlignRight)
        layout.addWidget(summary)

        # Close Button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)


# --- Main Dialog ---
class SilverBarDialog(QDialog):
    """Dialog for adding, managing, and listing silver bars (v1.1 Refined)."""

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.list_identifiers_cache = [] # Cache for list selection dialogs
        self.init_ui()
        self.load_bars() # Load initial view ('All' or 'In Stock')

    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Silver Bar Management & Lists") # Updated title
        self.setMinimumWidth(850) # Slightly wider
        self.setMinimumHeight(700) # Increased height slightly for new buttons

        layout = QVBoxLayout(self)
        header_label = QLabel("Silver Bar Management")
        header_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header_label)

        # --- Add bar section ---
        add_bar_layout = QGridLayout()
        add_bar_layout.addWidget(QLabel("Bar Number:"), 0, 0); self.bar_no_edit = QLineEdit(); self.bar_no_edit.setMaximumWidth(150); add_bar_layout.addWidget(self.bar_no_edit, 0, 1)
        add_bar_layout.addWidget(QLabel("Weight (g):"), 0, 2); self.weight_spin = QDoubleSpinBox(); self.weight_spin.setRange(0, 100000); self.weight_spin.setDecimals(3); self.weight_spin.setSingleStep(10); add_bar_layout.addWidget(self.weight_spin, 0, 3)
        add_bar_layout.addWidget(QLabel("Purity (%):"), 0, 4); self.purity_spin = QDoubleSpinBox(); self.purity_spin.setRange(0, 100); self.purity_spin.setDecimals(2); self.purity_spin.setValue(100); self.purity_spin.setSingleStep(0.5); add_bar_layout.addWidget(self.purity_spin, 0, 5)
        self.add_bar_button = QPushButton("Add Bar"); self.add_bar_button.clicked.connect(self.add_bar); add_bar_layout.addWidget(self.add_bar_button, 0, 6)
        layout.addLayout(add_bar_layout)

        # --- Filter section ---
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter by Status:"))
        self.status_filter = QComboBox(); self.status_filter.addItems(["All", "In Stock", "Assigned", "Transferred", "Sold", "Melted"]); self.status_filter.currentTextChanged.connect(self.load_bars); filter_layout.addWidget(self.status_filter)
        filter_layout.addStretch()
        self.refresh_button = QPushButton("Refresh List"); self.refresh_button.clicked.connect(self.load_bars); filter_layout.addWidget(self.refresh_button)
        layout.addLayout(filter_layout)

        # --- Silver bars table ---
        self.bars_table = QTableWidget()
        self.bars_table.setColumnCount(7); self.bars_table.setHorizontalHeaderLabels(["ID", "Bar Number", "Weight (g)", "Purity (%)", "Fine Weight (g)", "Date Added", "Status"])
        self.bars_table.setColumnHidden(0, True); self.bars_table.setColumnWidth(1, 120); self.bars_table.setColumnWidth(2, 100); self.bars_table.setColumnWidth(3, 100); self.bars_table.setColumnWidth(4, 120); self.bars_table.setColumnWidth(5, 120); self.bars_table.setColumnWidth(6, 120)
        self.bars_table.setEditTriggers(QTableWidget.NoEditTriggers); self.bars_table.setSelectionBehavior(QAbstractItemView.SelectRows); self.bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection); self.bars_table.setAlternatingRowColors(True)
        layout.addWidget(self.bars_table)

        # --- Transfer section ---
        transfer_layout = QGridLayout()
        transfer_layout.addWidget(QLabel("Transfer Selected Bar(s) to:"), 0, 0); self.transfer_status = QComboBox(); self.transfer_status.addItems(["In Stock", "Assigned", "Transferred", "Sold", "Melted"]); transfer_layout.addWidget(self.transfer_status, 0, 1)
        transfer_layout.addWidget(QLabel("Transfer Notes:"), 0, 2); self.transfer_notes = QLineEdit(); self.transfer_notes.setPlaceholderText("Optional notes for transfer"); transfer_layout.addWidget(self.transfer_notes, 0, 3)
        self.transfer_button = QPushButton("Transfer Selected"); self.transfer_button.setToolTip("Transfer selected bar(s) individually (uses above Notes)"); self.transfer_button.clicked.connect(self.transfer_selected_bars); transfer_layout.addWidget(self.transfer_button, 0, 4)
        layout.addLayout(transfer_layout)

        # --- Separator 1 ---
        line1 = QFrame(); line1.setFrameShape(QFrame.HLine); line1.setFrameShadow(QFrame.Sunken); layout.addWidget(line1)

        # --- List Creation Section ---
        list_layout = QGridLayout()
        list_layout.addWidget(QLabel("<b>Create New List & Assign Selected:</b>"), 0, 0, 1, 4)
        list_layout.addWidget(QLabel("List Note:"), 1, 0); self.list_note_edit = QTextEdit(); self.list_note_edit.setPlaceholderText("Enter note for the new list..."); self.list_note_edit.setMaximumHeight(60); list_layout.addWidget(self.list_note_edit, 1, 1, 1, 2)
        self.create_list_button = QPushButton("Create List & Assign"); self.create_list_button.setToolTip("Create a new list and assign selected 'In Stock' bars."); self.create_list_button.clicked.connect(self.create_list_and_assign); list_layout.addWidget(self.create_list_button, 1, 3)
        list_layout.setColumnStretch(1, 1)
        layout.addLayout(list_layout)

        # --- Separator 2 ---
        line2 = QFrame(); line2.setFrameShape(QFrame.HLine); line2.setFrameShadow(QFrame.Sunken); layout.addWidget(line2)

        # --- List Management / Actions Section ---
        list_manage_layout = QHBoxLayout()
        list_manage_layout.addWidget(QLabel("<b>List Actions:</b>"))
        self.view_list_button = QPushButton("View List Contents...")
        self.view_list_button.setToolTip("Select a list to view its assigned bars.")
        self.view_list_button.clicked.connect(self.view_list_contents)
        self.edit_list_note_button = QPushButton("Edit List Note...")
        self.edit_list_note_button.setToolTip("Select a list to edit its note.")
        self.edit_list_note_button.clicked.connect(self.edit_selected_list_note)
        self.unassign_button = QPushButton("Unassign Selected Bar(s)")
        self.unassign_button.setToolTip("Remove selected 'Assigned' bar(s) from their list (status becomes 'In Stock').")
        self.unassign_button.clicked.connect(self.unassign_selected_bars)
        self.delete_list_button = QPushButton("Delete List...")
        self.delete_list_button.setToolTip("Select a list to delete it (bars become unassigned).")
        self.delete_list_button.clicked.connect(self.delete_selected_list)

        list_manage_layout.addWidget(self.view_list_button)
        list_manage_layout.addWidget(self.edit_list_note_button)
        list_manage_layout.addWidget(self.unassign_button)
        list_manage_layout.addWidget(self.delete_list_button)
        list_manage_layout.addStretch()
        layout.addLayout(list_manage_layout)

        # --- Summary section ---
        summary_layout = QHBoxLayout(); summary_layout.addWidget(QLabel("Total Displayed Bars:")); self.total_bars_label = QLabel("0"); summary_layout.addWidget(self.total_bars_label); summary_layout.addWidget(QLabel("Total Displayed Weight:")); self.total_weight_label = QLabel("0.000 g"); summary_layout.addWidget(self.total_weight_label); summary_layout.addWidget(QLabel("Total Displayed Fine Wt:")); self.total_fine_label = QLabel("0.000 g"); summary_layout.addWidget(self.total_fine_label); layout.addLayout(summary_layout)

        # --- Bottom Buttons ---
        button_layout = QHBoxLayout(); self.print_button = QPushButton("Print Displayed Bars"); self.print_button.clicked.connect(self.print_bar_list); button_layout.addWidget(self.print_button); self.close_button = QPushButton("Close"); self.close_button.clicked.connect(self.accept); button_layout.addWidget(self.close_button); layout.addLayout(button_layout)

    # --- Helper to get list choices for dialogs ---
    def _get_list_choices(self):
        """Fetches and caches list identifiers for use in QInputDialog."""
        self.list_identifiers_cache = self.db_manager.get_all_list_identifiers()
        # Return just the identifiers for display
        return [identifier for identifier, list_id in self.list_identifiers_cache]

    def _get_list_id_from_identifier(self, identifier_string):
        """Finds the list_id corresponding to an identifier string from the cache."""
        for identifier, list_id in self.list_identifiers_cache:
            if identifier == identifier_string:
                return list_id
        return None # Not found

    # --- Data Loading and Basic Actions ---
    def load_bars(self):
        """Load silver bars based on the status filter."""
        status_filter = self.status_filter.currentText()
        status = None if status_filter == "All" else status_filter
        bars = self.db_manager.get_silver_bars(status)
        self.bars_table.setRowCount(0); total_weight = 0.0; total_fine = 0.0
        self.bars_table.blockSignals(True)
        self.bars_table.setRowCount(len(bars))
        for row, bar in enumerate(bars):
            id_item = QTableWidgetItem(str(bar['id'])); id_item.setData(Qt.UserRole, bar['id'])
            self.bars_table.setItem(row, 0, id_item)
            self.bars_table.setItem(row, 1, QTableWidgetItem(bar['bar_no']))
            self.bars_table.setItem(row, 2, QTableWidgetItem(f"{bar['weight']:.3f}"))
            self.bars_table.setItem(row, 3, QTableWidgetItem(f"{bar['purity']:.2f}"))
            self.bars_table.setItem(row, 4, QTableWidgetItem(f"{bar['fine_weight']:.3f}"))
            self.bars_table.setItem(row, 5, QTableWidgetItem(bar['date_added']))
            self.bars_table.setItem(row, 6, QTableWidgetItem(bar['status']))
            if isinstance(bar['weight'], (int, float)): total_weight += bar['weight']
            if isinstance(bar['fine_weight'], (int, float)): total_fine += bar['fine_weight']
        self.bars_table.blockSignals(False)
        self.total_bars_label.setText(str(len(bars))); self.total_weight_label.setText(f"{total_weight:.3f} g"); self.total_fine_label.setText(f"{total_fine:.3f} g")

    def add_bar(self):
        """Add a new silver bar to inventory."""
        bar_no = self.bar_no_edit.text().strip(); weight = self.weight_spin.value(); purity = self.purity_spin.value()
        if not bar_no: QMessageBox.warning(self, "Input Error", "Bar number required."); return
        if weight <= 0: QMessageBox.warning(self, "Input Error", "Weight must be > 0."); return
        if self.db_manager.add_silver_bar(bar_no, weight, purity):
            QMessageBox.information(self, "Success", f"Bar '{bar_no}' added."); self.bar_no_edit.clear(); self.weight_spin.setValue(0); self.purity_spin.setValue(100); self.load_bars()
        else: QMessageBox.critical(self, "Error", "Failed to add bar (duplicate bar_no?).")

    def transfer_selected_bars(self):
        """Transfer one or more selected bars to a new status."""
        selected_rows = self.bars_table.selectionModel().selectedRows()
        if not selected_rows: QMessageBox.warning(self, "Selection Error", "Select bar(s) to transfer."); return
        new_status = self.transfer_status.currentText(); notes = self.transfer_notes.text().strip()
        transfer_count, skipped_count = 0, 0; bar_nos_skipped = []
        confirm_text = f"Transfer {len(selected_rows)} selected bar(s) to status '{new_status}'?"; reply = QMessageBox.question(self, "Confirm Transfer", confirm_text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for index in selected_rows:
                row = index.row(); bar_id = self.bars_table.item(row, 0).data(Qt.UserRole); bar_no = self.bars_table.item(row, 1).text(); current_status = self.bars_table.item(row, 6).text()
                if current_status == new_status: skipped_count += 1; bar_nos_skipped.append(bar_no); continue
                if self.db_manager.transfer_silver_bar(bar_id, new_status, notes): transfer_count += 1
                else: skipped_count += 1; bar_nos_skipped.append(bar_no)
            msg = f"{transfer_count} bar(s) transferred to '{new_status}'.";
            if skipped_count > 0: msg += f"\n{skipped_count} skipped: {', '.join(bar_nos_skipped)}"
            QMessageBox.information(self, "Transfer Complete", msg); self.transfer_notes.clear(); self.load_bars()

    # --- List Creation and Assignment ---
    def create_list_and_assign(self):
        """Creates a new list and assigns selected 'In Stock' bars."""
        selected_rows = self.bars_table.selectionModel().selectedRows(); note = self.list_note_edit.toPlainText().strip()
        if not selected_rows: QMessageBox.warning(self, "Selection Error", "Select 'In Stock' bars to assign."); return
        if not note: QMessageBox.warning(self, "Input Error", "List note required."); self.list_note_edit.setFocus(); return
        bar_ids_to_assign = []; can_assign = True
        for index in selected_rows:
            row = index.row(); bar_id = self.bars_table.item(row, 0).data(Qt.UserRole); current_status = self.bars_table.item(row, 6).text()
            if current_status != 'In Stock': bar_no = self.bars_table.item(row, 1).text(); QMessageBox.warning(self, "Selection Error", f"Bar '{bar_no}' not 'In Stock'. Select only 'In Stock' bars."); can_assign = False; break
            bar_ids_to_assign.append(bar_id)
        if not can_assign or not bar_ids_to_assign: return
        reply = QMessageBox.question(self, "Confirm", f"Create list with note:\n'{note}'\nAnd assign {len(bar_ids_to_assign)} bar(s)?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            list_id = self.db_manager.create_list_and_assign_bars(note, bar_ids_to_assign)
            if list_id is not None: QMessageBox.information(self, "Success", f"List created, {len(bar_ids_to_assign)} bar(s) assigned."); self.list_note_edit.clear(); self.status_filter.setCurrentText("Assigned")
            else: QMessageBox.critical(self, "Error", "Failed to create list/assign bars.")

    # --- List Management Actions ---
    def view_list_contents(self):
        """Show bars for a selected list in a separate dialog."""
        list_choices = self._get_list_choices()
        if not list_choices: QMessageBox.information(self, "No Lists", "No lists have been created yet."); return
        choice, ok = QInputDialog.getItem(self, "View List Contents", "Select a list to view:", list_choices, 0, False)
        if ok and choice:
            selected_list_id = self._get_list_id_from_identifier(choice)
            if selected_list_id is not None:
                list_details = self.db_manager.get_list_details(selected_list_id)
                bars = self.db_manager.get_bars_by_list_id(selected_list_id)
                if list_details:
                    view_dialog = ViewListBarsDialog(choice, list_details['list_note'], bars, self)
                    view_dialog.exec_()
                else: QMessageBox.warning(self, "Error", "Could not retrieve details for list.")
            else: QMessageBox.warning(self, "Error", "Could not identify selected list.")

    def edit_selected_list_note(self):
        """Allow editing the note of a selected list."""
        list_choices = self._get_list_choices()
        if not list_choices: QMessageBox.information(self, "No Lists", "No lists available to edit."); return
        choice, ok = QInputDialog.getItem(self, "Edit List Note", "Select list to edit note:", list_choices, 0, False)
        if ok and choice:
            selected_list_id = self._get_list_id_from_identifier(choice)
            if selected_list_id:
                list_details = self.db_manager.get_list_details(selected_list_id)
                if list_details:
                    current_note = list_details['list_note'] if list_details['list_note'] else ""
                    new_note, ok_edit = QInputDialog.getText(self, "Edit Note", f"Editing note for list {choice}:", QLineEdit.Normal, current_note)
                    if ok_edit and new_note != current_note:
                        if self.db_manager.update_list_note(selected_list_id, new_note): QMessageBox.information(self, "Success", "List note updated.")
                        else: QMessageBox.critical(self, "Error", "Failed to update list note.")
                else: QMessageBox.warning(self, "Error", "Could not retrieve details for list.")
            else: QMessageBox.warning(self, "Error", "Could not identify selected list.")

    def delete_selected_list(self):
        """Allow deleting a selected list."""
        list_choices = self._get_list_choices()
        if not list_choices: QMessageBox.information(self, "No Lists", "No lists available to delete."); return
        choice, ok = QInputDialog.getItem(self, "Delete List", "Select list to DELETE:", list_choices, 0, False)
        if ok and choice:
            selected_list_id = self._get_list_id_from_identifier(choice)
            if selected_list_id:
                reply = QMessageBox.warning(self, "Confirm Delete List", f"DELETE list '{choice}'?\nBars assigned will become unassigned.\nThis cannot be undone!", QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
                if reply == QMessageBox.Yes:
                    success, msg = self.db_manager.delete_silver_bar_list(selected_list_id)
                    if success: QMessageBox.information(self, "Success", f"List '{choice}' deleted.")
                    else: QMessageBox.critical(self, "Error", f"Failed to delete list: {msg}")
                    self.load_bars() # Refresh main view
            else: QMessageBox.warning(self, "Error", "Could not identify selected list.")

    def unassign_selected_bars(self):
        """Unassign selected 'Assigned' bars from their list."""
        selected_rows = self.bars_table.selectionModel().selectedRows()
        if not selected_rows: QMessageBox.warning(self, "Selection Error", "Select 'Assigned' bar(s) to unassign."); return
        bar_ids_to_unassign = []; can_unassign = True
        for index in selected_rows:
            row = index.row(); bar_id = self.bars_table.item(row, 0).data(Qt.UserRole); current_status = self.bars_table.item(row, 6).text()
            if current_status != 'Assigned': bar_no = self.bars_table.item(row, 1).text(); QMessageBox.warning(self, "Selection Error", f"Bar '{bar_no}' is not 'Assigned'. Select only 'Assigned' bars."); can_unassign = False; break
            bar_ids_to_unassign.append(bar_id)
        if not can_unassign or not bar_ids_to_unassign: return
        reply = QMessageBox.question(self, "Confirm Unassign", f"Unassign {len(bar_ids_to_unassign)} selected bar(s)?\n(Status becomes 'In Stock')", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            unassign_count = 0
            for bar_id in bar_ids_to_unassign:
                if self.db_manager.unassign_bar_from_list(bar_id): unassign_count += 1
            QMessageBox.information(self, "Success", f"{unassign_count} bar(s) unassigned."); self.load_bars() # Refresh

    # --- Printing ---
    def print_bar_list(self):
        """Print the currently displayed list of silver bars."""
        from print_manager import PrintManager
        status_filter = None
        if self.status_filter.currentText() != "All": status_filter = self.status_filter.currentText()
        print_manager = PrintManager(self.db_manager)
        print_manager.print_silver_bars(status_filter, self) # Prints inventory report