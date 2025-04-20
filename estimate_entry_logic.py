#!/usr/bin/env python
from PyQt5.QtWidgets import (QTableWidgetItem, QMessageBox, QDialog)
from PyQt5.QtCore import Qt, QDate, QTimer, QLocale # Added QLocale import
from PyQt5.QtGui import QColor

# Import necessary dialogs - ensure these files exist and are correct
from item_selection_dialog import ItemSelectionDialog
# from silver_bar_management import SilverBarDialog # Now handled by main window/estimate_entry
# from estimate_history import EstimateHistoryDialog # Now handled by estimate_entry

from datetime import datetime
import traceback # For detailed error reporting

# --- Column Constants ---
COL_CODE = 0
COL_ITEM_NAME = 1
COL_GROSS = 2
COL_POLY = 3
COL_NET_WT = 4
COL_PURITY = 5
COL_WAGE_RATE = 6
COL_PIECES = 7
COL_WAGE_AMT = 8
COL_FINE_WT = 9
COL_TYPE = 10
# --- End Constants ---

# Define editable columns centrally
EDITABLE_COLS = [COL_CODE, COL_GROSS, COL_POLY, COL_PURITY, COL_WAGE_RATE, COL_PIECES]

class EstimateLogic:
    """Business logic for the estimate entry widget."""

    # --- Helper to show status messages (assumes self has show_status method) ---
    def _status(self, message, timeout=3000):
        """ Safely shows status message if possible. """
        if hasattr(self, 'show_status') and callable(self.show_status):
            self.show_status(message, timeout)
        else: # Fallback if show_status isn't available (e.g. testing)
            print(f"Status: {message}")
    # --------------------------------------------------------------------------

    def connect_signals(self):
        """Connect UI signals to their handlers."""
        # Header signals
        self.voucher_edit.editingFinished.connect(self.load_estimate)
        self.generate_button.clicked.connect(self.generate_voucher)
        self.silver_rate_spin.valueChanged.connect(self.calculate_totals)

        # Table signals
        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
        self.item_table.cellChanged.connect(self.handle_cell_changed)

        # Button signals
        self.save_button.clicked.connect(self.save_estimate)
        self.clear_button.clicked.connect(self.clear_form)
        self.print_button.clicked.connect(self.print_estimate)
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

        # History/Silver Bars buttons are connected in EstimateEntryWidget __init__ now
        # if hasattr(self, 'history_button'): self.history_button.clicked.connect(self.show_history)
        # if hasattr(self, 'silver_bars_button'): self.silver_bars_button.clicked.connect(self.show_silver_bars)

    def print_estimate(self):
        """Print the current estimate."""
        from print_manager import PrintManager
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(self, "Print Error", "Please save the estimate or generate a voucher number first.")
            self._status("Print Error: Voucher missing", 4000)
            return

        self._status(f"Generating print preview for {voucher_no}...")
        pm = PrintManager(self.db_manager)
        success = pm.print_estimate(voucher_no, self)
        self._status(f"Print preview for {voucher_no} {'generated' if success else 'failed'}.", 3000)

    def add_empty_row(self):
        """Add an empty row to the item table, avoiding duplicates at the end."""
        if self.item_table.rowCount() > 0:
            last_row = self.item_table.rowCount() - 1
            code_item = self.item_table.item(last_row, COL_CODE)
            if not code_item or not code_item.text().strip(): # If last row's code is empty
                QTimer.singleShot(0, lambda: self.focus_on_code_column(last_row)); return # Focus existing empty

        self.processing_cell = True
        try:
            row = self.item_table.rowCount(); self.item_table.insertRow(row)
            for col in range(self.item_table.columnCount()):
                item = QTableWidgetItem("")
                # Set flags based on column type
                is_edit = col in EDITABLE_COLS
                calc_col = col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]
                if calc_col: item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled) # Not editable
                elif col == COL_TYPE: self._update_row_type_visuals_direct(item); item.setTextAlignment(Qt.AlignCenter); item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled) # Not editable
                else: item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable) # Default editable
                self.item_table.setItem(row, col, item)
        finally:
            self.processing_cell = False
            QTimer.singleShot(50, lambda: self.focus_on_code_column(row)) # Focus after UI update

    def _update_row_type_visuals_direct(self, type_item):
         """Sets text and background for a type cell based on current mode."""
         if self.return_mode: type_item.setText("Return"); type_item.setBackground(QColor(255, 200, 200))
         elif self.silver_bar_mode: type_item.setText("Silver Bar"); type_item.setBackground(QColor(200, 255, 200))
         else: type_item.setText("No"); type_item.setBackground(QColor(255, 255, 255))

    def cell_clicked(self, row, column):
        """Handle cell click: update position and start editing if editable."""
        self.current_row = row; self.current_column = column
        if column in EDITABLE_COLS:
            item = self.item_table.item(row, column)
            if item and (item.flags() & Qt.ItemIsEditable): self.item_table.editItem(item)

    def selection_changed(self):
        """Update current position based on selection."""
        sel = self.item_table.selectedItems()
        if sel: item = sel[0]; self.current_row = self.item_table.row(item); self.current_column = self.item_table.column(item)

    def handle_cell_changed(self, row, column):
        """Handle cell value changes and trigger necessary calculations. No auto-navigation."""
        if self.processing_cell: return
        if row < 0 or column < 0 or row >= self.item_table.rowCount() or column >= self.item_table.columnCount(): return
        self.current_row = row; self.current_column = column

        self.item_table.blockSignals(True)
        try:
            if column == COL_CODE: self.process_item_code()
            elif column == COL_GROSS or column == COL_POLY: self.calculate_net_weight()
            elif column == COL_PURITY: self.calculate_fine()
            elif column == COL_WAGE_RATE: self.calculate_wage()
            elif column == COL_PIECES:
                self.calculate_wage()
                if row == self.item_table.rowCount() - 1: # Auto-add row condition
                    code_item = self.item_table.item(row, COL_CODE)
                    if code_item and code_item.text().strip(): QTimer.singleShot(50, self.add_empty_row)
            else: self.calculate_totals() # Fallback

        except Exception as e:
            err_msg = f"Calc Error on change: {e}"; self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", f"{err_msg}\n{traceback.format_exc()}")
        finally:
            self.item_table.blockSignals(False)

    def move_to_next_cell(self):
        """Navigate to the next editable cell, called by keyPressEvent."""
        if self.processing_cell: return
        current_col = self.current_column; current_row = self.current_row
        next_col = -1; next_row = current_row
        try:
             idx = EDITABLE_COLS.index(current_col); next_idx = (idx + 1) % len(EDITABLE_COLS)
             next_col = EDITABLE_COLS[next_idx]
             if next_idx == 0: next_row = current_row + 1
        except ValueError: next_row = current_row + 1; next_col = COL_CODE

        if next_row >= self.item_table.rowCount():
             last_code = self.item_table.item(current_row, COL_CODE)
             if last_code and last_code.text().strip(): self.add_empty_row(); return
             else: next_row = current_row; next_col = COL_CODE # Wrap

        if 0 <= next_row < self.item_table.rowCount() and 0 <= next_col < self.item_table.columnCount():
            self.item_table.setCurrentCell(next_row, next_col)
            if next_col in EDITABLE_COLS:
                 item = self._ensure_cell_exists(next_row, next_col) # Ensure item exists
                 if item: QTimer.singleShot(0, lambda: self.item_table.editItem(item))

    def focus_on_code_column(self, row):
        """Focus code column and start editing."""
        if 0 <= row < self.item_table.rowCount():
            item = self._ensure_cell_exists(row, COL_CODE); self.item_table.setCurrentCell(row, COL_CODE)
            if item: QTimer.singleShot(0, lambda: self.item_table.editItem(item))

    def process_item_code(self):
        """Look up item code, populate row, or show selection dialog."""
        if self.processing_cell or self.current_row < 0: return
        item_cell = self.item_table.item(self.current_row, COL_CODE);
        if not item_cell: return
        code = item_cell.text().strip()
        if not code: QTimer.singleShot(0, self.move_to_next_cell); return

        item_data = self.db_manager.get_item_by_code(code)
        if item_data:
            self._status(f"Item '{code}' found.",2000); self.populate_item_row(dict(item_data))
            # Let populate trigger calculations, then move focus
            QTimer.singleShot(50, lambda: self.item_table.setCurrentCell(self.current_row, COL_GROSS))
            QTimer.singleShot(60, lambda: self.item_table.editItem(self.item_table.item(self.current_row, COL_GROSS)))
        else:
            self._status(f"Item '{code}' not found...",3000); dialog=ItemSelectionDialog(self.db_manager, code, self)
            if dialog.exec_()==QDialog.Accepted: sel=dialog.get_selected_item()
            if sel:
                self._status(f"Item '{sel['code']}' selected.",2000)
                self.item_table.blockSignals(True); item_cell.setText(sel['code']); self.item_table.blockSignals(False)
                self.populate_item_row(sel)
                QTimer.singleShot(50,lambda: self.item_table.setCurrentCell(self.current_row,COL_GROSS))
                QTimer.singleShot(60,lambda: self.item_table.editItem(self.item_table.item(self.current_row,COL_GROSS)))
            else: self._status("Selection cancelled.",2000)

    def populate_item_row(self, item_data):
        """Fill in item details in the current row."""
        if self.current_row < 0: return
        self.item_table.blockSignals(True)
        try:
            non_edit_cols=[COL_NET_WT,COL_WAGE_AMT,COL_FINE_WT,COL_TYPE];
            for c in range(1,self.item_table.columnCount()): self._ensure_cell_exists(self.current_row,c,editable=(c not in non_edit_cols))
            self.item_table.item(self.current_row,COL_ITEM_NAME).setText(item_data.get('name','')); self.item_table.item(self.current_row,COL_PURITY).setText(str(item_data.get('purity',0.0))); self.item_table.item(self.current_row,COL_WAGE_RATE).setText(str(item_data.get('wage_rate',0.0)))
            pcs=self.item_table.item(self.current_row,COL_PIECES);
            if not pcs.text().strip(): pcs.setText("1")
            type_i=self.item_table.item(self.current_row,COL_TYPE); self._update_row_type_visuals_direct(type_i); type_i.setTextAlignment(Qt.AlignCenter)
            # Trigger calculations after population using timer to ensure UI updated
            QTimer.singleShot(0, self.calculate_net_weight)
        except Exception as e: QMessageBox.critical(self,"Error",f"Populating row:{e}\n{traceback.format_exc()}"); self._status(f"Err pop row {self.current_row+1}",4000)
        finally: self.item_table.blockSignals(False)

    def _get_cell_float(self, row, col, default=0.0):
        """Safely get float value from a cell, treating empty as default."""
        item = self.item_table.item(row, col); text = item.text().strip() if item else ""
        if not text: return default
        try: locale = QLocale.system(); f_val, ok = locale.toDouble(text); return f_val if ok else default
        except Exception: return default

    def _get_cell_int(self, row, col, default=1):
        """Safely get integer value from a cell, treating empty as default=1."""
        item=self.item_table.item(row,col); text=item.text().strip() if item else "";
        if not text: return default
        try: return int(text)
        except ValueError: return default

    def _ensure_cell_exists(self, row, col, editable=True):
         """Ensure a QTableWidgetItem exists at row, col and has correct flags."""
         item = self.item_table.item(row, col)
         if not item: item = QTableWidgetItem(""); self.item_table.setItem(row, col, item)
         desired_flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
         if editable: desired_flags |= Qt.ItemIsEditable
         # Only set flags if they are different to avoid unnecessary signals/updates
         if item.flags() != desired_flags: item.setFlags(desired_flags)
         return item

    def calculate_net_weight(self):
        """Calculate net weight and trigger cascade."""
        if self.current_row < 0: return
        try:
            gross=self._get_cell_float(self.current_row,COL_GROSS); poly=self._get_cell_float(self.current_row,COL_POLY)
            net=max(0,gross-poly)
            item=self._ensure_cell_exists(self.current_row,COL_NET_WT,False); item.setText(f"{net:.3f}")
            # Use timers for cascade to allow UI to potentially update between calculations
            QTimer.singleShot(0, self.calculate_fine)
            QTimer.singleShot(0, self.calculate_wage)
        except Exception as e: err=f"Net Calc Error: {e}"; self._status(err,5000); QMessageBox.critical(self,"Error",f"{err}\n{traceback.format_exc()}")

    def calculate_fine(self):
        """Calculate fine weight and update totals."""
        # Check row index validity again in case called via timer after row deletion
        if self.current_row < 0 or self.current_row >= self.item_table.rowCount(): return
        try:
            net=self._get_cell_float(self.current_row,COL_NET_WT); purity=self._get_cell_float(self.current_row,COL_PURITY)
            fine=net*(purity/100.0) if purity>0 else 0.0
            item=self._ensure_cell_exists(self.current_row,COL_FINE_WT,False); item.setText(f"{fine:.3f}")
            self.calculate_totals() # Okay to call directly
        except Exception as e: err=f"Fine Calc Error: {e}"; self._status(err,5000); QMessageBox.critical(self,"Error",f"{err}\n{traceback.format_exc()}")

    def calculate_wage(self):
        """Calculate wage amount and update totals."""
        if self.current_row < 0 or self.current_row >= self.item_table.rowCount(): return
        try:
            net=self._get_cell_float(self.current_row,COL_NET_WT); wr=self._get_cell_float(self.current_row,COL_WAGE_RATE); pcs=self._get_cell_int(self.current_row,COL_PIECES)
            code_item=self.item_table.item(self.current_row,COL_CODE); code=code_item.text().strip() if code_item else ""
            wt="WT"; item_data=self.db_manager.get_item_by_code(code) if code else None
            if item_data and item_data['wage_type']: wt=item_data['wage_type'].strip().upper()
            wage=pcs*wr if wt=="PC" else net*wr
            item=self._ensure_cell_exists(self.current_row,COL_WAGE_AMT,False); item.setText(f"{wage:.2f}")
            self.calculate_totals() # Okay to call directly
        except Exception as e: err=f"Wage Calc Error: {e}"; self._status(err,5000); QMessageBox.critical(self,"Error",f"{err}\n{traceback.format_exc()}")

    def calculate_totals(self):
        """Calculate and update totals for all columns, separating categories."""
        try:
            rg,rn,rf,rw=0.0,0.0,0.0,0.0; retg,retn,retf,retw=0.0,0.0,0.0,0.0; barg,barn,barf,barw=0.0,0.0,0.0,0.0
            for r in range(self.item_table.rowCount()):
                code_i=self.item_table.item(r,COL_CODE);
                if not code_i or not code_i.text().strip(): continue # Skip empty rows
                try:
                    type_i=self.item_table.item(r,COL_TYPE); type_t=type_i.text() if type_i else "No"
                    g=self._get_cell_float(r,COL_GROSS); n=self._get_cell_float(r,COL_NET_WT); f=self._get_cell_float(r,COL_FINE_WT); w=self._get_cell_float(r,COL_WAGE_AMT)
                    if type_t=="Return": retg+=g; retn+=n; retf+=f; retw+=w
                    elif type_t=="Silver Bar": barg+=g; barn+=n; barf+=f; barw+=w
                    else: rg+=g; rn+=n; rf+=f; rw+=w
                except Exception as e: print(f"Warn: Skip row {r+1} totals: {e}") # Log error for specific row

            # Final Calculations
            sr=self.silver_rate_spin.value(); rfv=rf*sr; retv=retf*sr; barv=barf*sr
            netf_c=(rf+barf)-retf; netw_c=(rw+barw)-retw; netv_c=netf_c*sr

            # Update UI Labels
            self.total_gross_label.setText(f"{rg:.3f}"); self.total_net_label.setText(f"{rn:.3f}"); self.total_fine_label.setText(f"{rf:.3f}"); self.fine_value_label.setText(f"{rfv:.2f}"); self.total_wage_label.setText(f"{rw:.2f}")
            self.return_gross_label.setText(f"{retg:.3f}"); self.return_net_label.setText(f"{retn:.3f}"); self.return_fine_label.setText(f"{retf:.3f}"); self.return_value_label.setText(f"{retv:.2f}"); self.return_wage_label.setText(f"{retw:.2f}")
            self.bar_gross_label.setText(f"{barg:.3f}"); self.bar_net_label.setText(f"{barn:.3f}"); self.bar_fine_label.setText(f"{barf:.3f}"); self.bar_value_label.setText(f"{barv:.2f}")
            self.net_fine_label.setText(f"{netf_c:.3f}"); self.net_value_label.setText(f"{netv_c:.2f}"); self.net_wage_label.setText(f"{netw_c:.2f}")

        except Exception as e:
            err=f"Error updating totals: {e}"; print(f"ERROR:{err}\n{traceback.format_exc()}"); self._status(err,5000)
            try: # Attempt to reset labels on error
                labels=[self.total_gross_label,self.total_net_label,self.total_fine_label,self.fine_value_label,self.total_wage_label,self.return_gross_label,self.return_net_label,self.return_fine_label,self.return_value_label,self.return_wage_label,self.bar_gross_label,self.bar_net_label,self.bar_fine_label,self.bar_value_label,self.net_fine_label,self.net_value_label,self.net_wage_label]
                for lbl in labels: lbl.setText("Error")
            except Exception as ie: print(f"ERROR: Reset labels fail: {ie}")

    def generate_voucher(self):
        v=self.db_manager.generate_voucher_no(); self.voucher_edit.setText(v); self._status(f"Generated voucher: {v}",3000)

    def load_estimate(self):
        v=self.voucher_edit.text().strip();
        if not v: return
        self._status(f"Loading {v}...",2000); data=self.db_manager.get_estimate_by_voucher(v)
        if not data: QMessageBox.warning(self,"Load Error",f"Estimate '{v}' not found."); self._status(f"Estimate {v} not found.",4000); return

        self.item_table.blockSignals(True); self.processing_cell=True
        try:
            while self.item_table.rowCount()>0: self.item_table.removeRow(0)
            h=data['header'];
            try: self.date_edit.setDate(QDate.fromString(h.get('date', QDate.currentDate().toString("yyyy-MM-dd")),"yyyy-MM-dd"))
            except: self.date_edit.setDate(QDate.currentDate())
            self.silver_rate_spin.setValue(h.get('silver_rate',0.0))
            for i in data['items']:
                r=self.item_table.rowCount(); self.item_table.insertRow(r); is_r=i.get('is_return',0)==1; is_s=i.get('is_silver_bar',0)==1
                self.item_table.setItem(r,COL_CODE,QTableWidgetItem(i.get('item_code',''))); self.item_table.setItem(r,COL_ITEM_NAME,QTableWidgetItem(i.get('item_name','')))
                self.item_table.setItem(r,COL_GROSS,QTableWidgetItem(str(i.get('gross',0.0)))); self.item_table.setItem(r,COL_POLY,QTableWidgetItem(str(i.get('poly',0.0))))
                self.item_table.setItem(r,COL_NET_WT,QTableWidgetItem(str(i.get('net_wt',0.0)))); self.item_table.setItem(r,COL_PURITY,QTableWidgetItem(str(i.get('purity',0.0))))
                self.item_table.setItem(r,COL_WAGE_RATE,QTableWidgetItem(str(i.get('wage_rate',0.0)))); self.item_table.setItem(r,COL_PIECES,QTableWidgetItem(str(i.get('pieces',1))))
                self.item_table.setItem(r,COL_WAGE_AMT,QTableWidgetItem(str(i.get('wage',0.0)))); self.item_table.setItem(r,COL_FINE_WT,QTableWidgetItem(str(i.get('fine',0.0))))
                if is_r: tt,bg="Return",QColor(255,200,200)
                elif is_s: tt,bg="Silver Bar",QColor(200,255,200)
                else: tt,bg="No",QColor(255,255,255)
                ti=QTableWidgetItem(tt); ti.setBackground(bg); ti.setTextAlignment(Qt.AlignCenter); ti.setFlags(ti.flags()&~Qt.ItemIsEditable); self.item_table.setItem(r,COL_TYPE,ti)
                for c in [COL_NET_WT,COL_WAGE_AMT,COL_FINE_WT]: cell=self.item_table.item(r,c);
                if cell: cell.setFlags(cell.flags()&~Qt.ItemIsEditable)
            self.add_empty_row(); self.calculate_totals(); self._status(f"Estimate {v} loaded.",3000)
        except Exception as e: QMessageBox.critical(self,"Load Error",f"Loading estimate: {e}\n{traceback.format_exc()}"); self._status(f"Error loading {v}",5000)
        finally: self.processing_cell=False; self.item_table.blockSignals(False); QTimer.singleShot(50,lambda: self.focus_on_code_column(0) if self.item_table.rowCount()>0 else None)

    def save_estimate(self):
        v=self.voucher_edit.text().strip();
        if not v: QMessageBox.warning(self,"Input Error","Voucher number required."); self._status("Save Error: Voucher missing",4000); return
        self._status(f"Saving {v}...",2000); d=self.date_edit.date().toString("yyyy-MM-dd"); sr=self.silver_rate_spin.value()
        items_to_save, bars_inv, rows_err, invalid_codes = [], [], [], []

        # --- Collect and Validate Items ---
        for r in range(self.item_table.rowCount()):
            code_i=self.item_table.item(r,COL_CODE); code=code_i.text().strip() if code_i else "";
            if not code: continue # Skip truly empty rows
            type_i=self.item_table.item(r,COL_TYPE); type_t=type_i.text() if type_i else "No"; is_r=(type_t=="Return"); is_s=(type_t=="Silver Bar")
            try:
                item_d={'code':code,'name':self.item_table.item(r,COL_ITEM_NAME).text() if self.item_table.item(r,COL_ITEM_NAME) else '',
                        'gross':self._get_cell_float(r,COL_GROSS),'poly':self._get_cell_float(r,COL_POLY),'net_wt':self._get_cell_float(r,COL_NET_WT),
                        'purity':self._get_cell_float(r,COL_PURITY),'wage_rate':self._get_cell_float(r,COL_WAGE_RATE),'pieces':self._get_cell_int(r,COL_PIECES),
                        'wage':self._get_cell_float(r,COL_WAGE_AMT),'fine':self._get_cell_float(r,COL_FINE_WT),'is_return':is_r,'is_silver_bar':is_s}
                if item_d['net_wt']<0 or item_d['fine']<0 or item_d['wage']<0: raise ValueError("Negative calc value.")
                # Check Foreign Key constraint before adding
                if not self.db_manager.get_item_by_code(item_d['code']):
                    invalid_codes.append(item_d['code'])
                    if r+1 not in rows_err: rows_err.append(r+1) # Track row with invalid code
                    continue # Skip this item
                # If code valid, add item
                items_to_save.append(item_d)
                if is_s and not is_r: bars_inv.append(item_d)
            except Exception as e: rows_err.append(r+1); print(f"Err processing row {r+1}: {e}"); continue # Catch other processing errors

        # --- Handle Validation Results ---
        if invalid_codes:
            QMessageBox.critical(self,"Foreign Key Error",f"Cannot save: Invalid Item Code(s):\n- {', '.join(invalid_codes)}\n(Check Item Master or row(s): {', '.join(map(str,rows_err))})")
            self._status(f"Save Error: Invalid codes: {', '.join(invalid_codes)}",5000); return
        if rows_err: QMessageBox.warning(self,"Data Error",f"Skipped rows with other errors: {', '.join(map(str,rows_err))}."); self._status(f"Save Warn: Skipped rows",5000)
        if not items_to_save: QMessageBox.warning(self,"Input Error","No valid items found to save."); self._status("Save Error: No valid items",4000); return

        # --- Recalculate Totals from valid items_to_save ---
        tg,tn,nf,nw=0.0,0.0,0.0,0.0; rf,rw=0.0,0.0; bf,bw=0.0,0.0
        for item in items_to_save:
            tg+=item['gross']; tn+=item['net_wt']
            if item['is_return']: rf+=item['fine']; rw+=item['wage']
            elif item['is_silver_bar']: bf+=item['fine']; bw+=item['wage']
            else: nf+=item['fine']; nw+=item['wage']
        netf_c=(nf+bf)-rf; netw_c=(nw+bw)-rw; recalc_totals={'total_gross':tg,'total_net':tn,'net_fine':netf_c,'net_wage':netw_c}

        # --- Add bars to inventory ---
        bars_add_c, bars_fail_c = 0, 0
        if bars_inv:
            for bi in bars_inv:
                bn=bi['code']; w=bi['net_wt']; p=bi['purity']
                if not bn: print("Skip bar: no code"); bars_fail_c+=1; continue
                if self.db_manager.add_silver_bar(bn,w,p): bars_add_c+=1
                else: bars_fail_c+=1

        # --- Save estimate ---
        reg=[i for i in items_to_save if not i['is_return']]; ret=[i for i in items_to_save if i['is_return']]
        success = self.db_manager.save_estimate_with_returns(v,d,sr,reg,ret,recalc_totals)

        # --- Show result ---
        if success:
            msg_p=[f"Estimate '{v}' saved."];
            if bars_add_c>0: msg_p.append(f"{bars_add_c} bar(s) added.")
            if bars_fail_c>0: msg_p.append(f"{bars_fail_c} bar add(s) failed.")
            final_msg=" ".join(msg_p); self._status(final_msg,5000); QMessageBox.information(self,"Success",final_msg)
        else: err_msg=f"Failed save estimate '{v}'."; QMessageBox.critical(self,"Error",err_msg); self._status(err_msg,5000)

    def clear_form(self, confirm=True):
        reply=QMessageBox.No if not confirm else QMessageBox.question(self,"Confirm New","Clear form?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if reply==QMessageBox.Yes or not confirm:
            self.item_table.blockSignals(True); self.processing_cell=True
            try:
                self.voucher_edit.clear(); self.generate_voucher(); self.date_edit.setDate(QDate.currentDate()); self.silver_rate_spin.setValue(0)
                # Reset modes only if they are currently ON
                if self.return_mode: self.toggle_return_mode() # Will toggle OFF
                if self.silver_bar_mode: self.toggle_silver_bar_mode() # Will toggle OFF
                # Ensure label reflects the final (Regular) state
                self.mode_indicator_label.setText("Mode: Regular"); self.mode_indicator_label.setStyleSheet("font-weight:bold;color:green;margin:5px;")
                while self.item_table.rowCount()>0: self.item_table.removeRow(0)
                self.add_empty_row(); self.calculate_totals(); self._status("Form cleared.",3000)
            except Exception as e: QMessageBox.critical(self,"Error",f"Clearing form: {e}\n{traceback.format_exc()}"); self._status("Error clearing form.",4000)
            finally: self.processing_cell=False; self.item_table.blockSignals(False); QTimer.singleShot(50,lambda: self.focus_on_code_column(0))

    def show_history(self):
        from estimate_history import EstimateHistoryDialog; d=EstimateHistoryDialog(self.db_manager,self)
        if d.exec_()==QDialog.Accepted: v=d.selected_voucher;
        if v: self.voucher_edit.setText(v); self.load_estimate(); self._status(f"Loaded {v}.",3000)
        else: self._status("No estimate selected.",2000)

    def show_silver_bars(self): # To be called by EstimateEntryWidget's button/menu
        # Check if main_window reference exists and call its method
        if hasattr(self, 'main_window') and self.main_window and hasattr(self.main_window, 'show_silver_bars'):
            self.main_window.show_silver_bars()
        else:
            # Fallback or error if no access to main window method
            print("Error: Cannot call show_silver_bars. No main_window reference or method missing.")
            QMessageBox.warning(self, "Error", "Could not open Silver Bar Management.")

    def _update_row_type_visuals(self, row):
        if 0<=row<self.item_table.rowCount(): type_i=self._ensure_cell_exists(row,COL_TYPE,False); self.item_table.blockSignals(True);
        try: self._update_row_type_visuals_direct(type_i); type_i.setTextAlignment(Qt.AlignCenter)
        finally: self.item_table.blockSignals(False)

    def delete_current_row(self):
        cr = self.item_table.currentRow()
        if cr < 0: self._status("Delete: No row selected",3000); return
        if self.item_table.rowCount()<=1: self._status("Delete: Cannot delete last row",3000); QMessageBox.warning(self,"Delete","Cannot delete last row."); return
        reply=QMessageBox.question(self,"Confirm Delete",f"Delete row {cr+1}?",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if reply==QMessageBox.Yes:
            self.item_table.removeRow(cr); self.calculate_totals(); self._status(f"Row {cr+1} deleted.",2000)
            nc=self.item_table.rowCount()
            focus_row = min(cr, nc-1) if nc > 0 else 0
            if nc == 0: self.add_empty_row() # Add row if table became empty
            else: QTimer.singleShot(0,lambda: self.focus_on_code_column(focus_row))

    def confirm_exit(self): print("Confirm exit requested") # Placeholder

    def move_to_previous_cell(self):
        if self.processing_cell: return
        cc=self.current_column; cr=self.current_row; pc=-1; pr=cr
        try:
             idx=EDITABLE_COLS.index(cc); p_idx=(idx-1+len(EDITABLE_COLS))%len(EDITABLE_COLS); pc=EDITABLE_COLS[p_idx]
             if idx==0 and cr>0: pr=cr-1 # Wrapped around from Code, go previous row
        except ValueError: # Find previous editable
             tc=cc-1; found=False
             while tc>=0:
                 if tc in EDITABLE_COLS: pc=tc; found=True; break
                 tc-=1
             if not found:
                 if cr>0: pr=cr-1; pc=EDITABLE_COLS[-1] # Go to last editable of previous row
                 else: pc=COL_CODE; pr=0 # Stay at first cell
        if 0<=pr<self.item_table.rowCount() and 0<=pc<self.item_table.columnCount():
            self.item_table.setCurrentCell(pr,pc)
            if pc in EDITABLE_COLS:
                 itm=self._ensure_cell_exists(pr,pc) # Ensure item exists
                 if itm: QTimer.singleShot(0,lambda: self.item_table.editItem(itm)) # Edit immediately