from __future__ import annotations

from PyQt5.QtCore import QLocale, QTimer, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QMessageBox, QTableWidgetItem

from silverestimate.services.estimate_calculator import (
    compute_fine_weight,
    compute_net_weight,
    compute_wage_amount,
)

from .constants import (
    COL_CODE,
    COL_ITEM_NAME,
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)


class _EstimateTableMixin:
    """Row and table editing helpers."""


    def populate_row(self, row_index: int, item_data):
        if row_index < 0 or row_index >= self.item_table.rowCount():
            return
        self.item_table.blockSignals(True)
        previous_row = getattr(self, "current_row", -1)
        try:
            non_editable_calc_cols = [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT, COL_TYPE]
            for col in range(self.item_table.columnCount()):
                self._ensure_cell_exists(
                    row_index, col, editable=(col not in non_editable_calc_cols)
                )

            code_text = (item_data.get("code", "") or "").strip()
            if code_text:
                code_text = code_text.upper()
            code_item = self.item_table.item(row_index, COL_CODE)
            if code_item is not None:
                code_item.setText(code_text)

            self.item_table.item(row_index, COL_ITEM_NAME).setText(
                item_data.get("name", "")
            )
            self.item_table.item(row_index, COL_PURITY).setText(
                str(item_data.get("purity", 0.0))
            )
            self.item_table.item(row_index, COL_WAGE_RATE).setText(
                str(item_data.get("wage_rate", 0.0))
            )

            pcs_item = self.item_table.item(row_index, COL_PIECES)
            if not pcs_item.text().strip():
                pcs_item.setText("1")

            type_item = self.item_table.item(row_index, COL_TYPE)
            self._update_row_type_visuals_direct(type_item)
            type_item.setTextAlignment(Qt.AlignCenter)

            self.current_row = row_index
            self.calculate_net_weight()
        except Exception as exc:
            self.logger.error(
                "Error populating row %s: %s", row_index + 1, exc, exc_info=True
            )
            QMessageBox.critical(self, "Error", f"Error populating row: {exc}")
            self._status(f"Error populating row {row_index + 1}", 4000)
        finally:
            self.item_table.blockSignals(False)
            self.current_row = previous_row

    def populate_item_row(self, item_data):
        if getattr(self, "current_row", -1) < 0:
            return
        self.populate_row(self.current_row, item_data)


    def focus_after_item_lookup(self, row_index: int) -> None:
        if row_index < 0 or row_index >= self.item_table.rowCount():
            return
        try:
            self.item_table.setCurrentCell(row_index, COL_GROSS)
            QTimer.singleShot(
                0, lambda: self.item_table.setCurrentCell(row_index, COL_GROSS)
            )
            QTimer.singleShot(
                10,
                lambda: self.item_table.editItem(
                    self.item_table.item(row_index, COL_GROSS)
                ),
            )
        except Exception:
            pass

    def add_empty_row(self):
        try:
            if self.item_table.rowCount() > 0:
                last_row = self.item_table.rowCount() - 1
                last_code_item = self.item_table.item(last_row, COL_CODE)
                if not last_code_item or not last_code_item.text().strip():
                    QTimer.singleShot(0, lambda: self.focus_on_code_column(last_row))
                    return

            self.processing_cell = True
            row = self.item_table.rowCount()
            self.item_table.insertRow(row)

            for col in range(self.item_table.columnCount()):
                item = QTableWidgetItem("")
                if col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif col == COL_TYPE:
                    self._update_row_type_visuals_direct(item)
                    item.setTextAlignment(Qt.AlignCenter)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.item_table.setItem(row, col, item)

            self.processing_cell = False
            QTimer.singleShot(50, lambda: self.focus_on_code_column(row))

        except Exception as exc:
            self.logger.error("Error adding empty row: %s", exc, exc_info=True)
            self._status("Warning: Could not add empty row", 3000)
            self.processing_cell = False

    def _update_row_type_visuals_direct(self, type_item):
        try:
            if not type_item:
                self.logger.warning(
                    "Null type_item passed to _update_row_type_visuals_direct"
                )
                return

            if getattr(self, "return_mode", False):
                type_item.setText("Return")
                type_item.setBackground(QColor(255, 200, 200))
            elif getattr(self, "silver_bar_mode", False):
                type_item.setText("Silver Bar")
                type_item.setBackground(QColor(200, 255, 200))
            else:
                type_item.setText("No")
                type_item.setBackground(QColor(255, 255, 255))
        except Exception as exc:
            self.logger.error(
                "Error updating row type visuals: %s", exc, exc_info=True
            )

    def _is_code_empty(self, row):
        try:
            item = self.item_table.item(row, COL_CODE)
            return (not item) or (not item.text().strip())
        except Exception:
            return True

    def _enforce_code_required(self, target_row, target_col, show_hint=True):
        if self._enforcing_code_nav:
            return True
        try:
            if 0 <= getattr(self, "current_row", -1) < self.item_table.rowCount():
                if self._is_code_empty(self.current_row):
                    if target_row != self.current_row or target_col != COL_CODE:
                        if show_hint:
                            self._status("Enter item code first", 1500)
                        self._enforcing_code_nav = True
                        try:
                            self.focus_on_code_column(self.current_row)
                        finally:
                            self._enforcing_code_nav = False
                        return False
        except Exception:
            return True
        return True


    def cell_clicked(self, row, column):
        prev_row = getattr(self, "current_row", -1)
        prev_empty_code = (
            self._is_code_empty(prev_row)
            if 0 <= prev_row < self.item_table.rowCount()
            else False
        )
        self.current_row = row
        self.current_column = column
        editable_cols = [
            COL_CODE,
            COL_GROSS,
            COL_POLY,
            COL_PURITY,
            COL_WAGE_RATE,
            COL_PIECES,
        ]
        if column in editable_cols:
            item = self.item_table.item(row, column)
            if item and (item.flags() & Qt.ItemIsEditable):
                if not (prev_empty_code and row != prev_row):
                    self.item_table.editItem(item)

    def selection_changed(self):
        selected_items = self.item_table.selectedItems()
        if not selected_items:
            return
        item = selected_items[0]
        row = self.item_table.row(item)
        col = self.item_table.column(item)
        prev_row = getattr(self, "current_row", -1)
        prev_empty_code = (
            self._is_code_empty(prev_row)
            if 0 <= prev_row < self.item_table.rowCount()
            else False
        )
        self.current_row = row
        self.current_column = col
        editable_cols = [
            COL_CODE,
            COL_GROSS,
            COL_POLY,
            COL_PURITY,
            COL_WAGE_RATE,
            COL_PIECES,
        ]
        if col in editable_cols:
            cell = self._ensure_cell_exists(row, col)
            if cell and (cell.flags() & Qt.ItemIsEditable):
                if not (prev_empty_code and row != prev_row):
                    QTimer.singleShot(
                        0, lambda c=cell: self.item_table.editItem(c)
                    )

    def current_cell_changed(self, currentRow, currentCol, previousRow, previousCol):
        try:
            mouse_pressed = QApplication.mouseButtons() != Qt.NoButton
        except Exception:
            mouse_pressed = False
        if not mouse_pressed:
            if not self._enforce_code_required(currentRow, currentCol):
                return
        self.current_row = currentRow
        self.current_column = currentCol
        editable_cols = [
            COL_CODE,
            COL_GROSS,
            COL_POLY,
            COL_PURITY,
            COL_WAGE_RATE,
            COL_PIECES,
        ]
        if currentCol in editable_cols and 0 <= currentRow < self.item_table.rowCount():
            cell = self._ensure_cell_exists(currentRow, currentCol)
            if cell and (cell.flags() & Qt.ItemIsEditable):
                QTimer.singleShot(
                    0, lambda c=cell: self.item_table.editItem(c)
                )

    def handle_cell_changed(self, row, column):
        if self.processing_cell:
            return

        self.current_row = row
        self.current_column = column

        self.item_table.blockSignals(True)
        try:
            if column == COL_CODE:
                self.process_item_code()
            elif column in [COL_GROSS, COL_POLY]:
                self.calculate_net_weight()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_PURITY:
                self.calculate_fine()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_WAGE_RATE:
                self.calculate_wage()
                QTimer.singleShot(0, self.move_to_next_cell)
            elif column == COL_PIECES:
                self.calculate_wage()
                if row == self.item_table.rowCount() - 1:
                    code_item = self.item_table.item(row, COL_CODE)
                    if code_item and code_item.text().strip():
                        QTimer.singleShot(10, self.add_empty_row)
                else:
                    QTimer.singleShot(
                        10, lambda: self.focus_on_code_column(row + 1)
                    )
            else:
                if hasattr(self, "request_totals_recalc"):
                    self.request_totals_recalc()
                else:
                    self.calculate_totals()

        except (ValueError, TypeError) as exc:
            err_msg = f"Value Error in calculation: {exc}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", err_msg)
        except Exception as exc:
            err_msg = f"Unexpected Error in calculation: {exc}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", err_msg)
        finally:
            self.item_table.blockSignals(False)
        self._mark_unsaved()


    def move_to_next_cell(self):
        if self.processing_cell:
            return

        current_col = self.current_column
        current_row = self.current_row
        next_col = -1
        next_row = current_row

        if current_col == COL_CODE and self._is_code_empty(current_row):
            self._status("Enter item code first", 1500)
            self.focus_on_code_column(current_row)
            return

        if current_col == COL_CODE:
            next_col = COL_GROSS
        elif current_col == COL_GROSS:
            next_col = COL_POLY
        elif current_col == COL_POLY:
            next_col = COL_PURITY
        elif current_col == COL_PURITY:
            next_col = COL_WAGE_RATE
        elif current_col == COL_WAGE_RATE:
            next_col = COL_PIECES
        elif current_col == COL_PIECES:
            next_row = current_row + 1
            next_col = COL_CODE
        else:
            next_col = COL_CODE
            next_row = current_row

        if next_row >= self.item_table.rowCount():
            last_code_item = self.item_table.item(current_row, COL_CODE)
            if last_code_item and last_code_item.text().strip():
                self.add_empty_row()
                return
            next_row = current_row
            next_col = current_col

        editable_cols = [
            COL_CODE,
            COL_GROSS,
            COL_POLY,
            COL_PURITY,
            COL_WAGE_RATE,
            COL_PIECES,
        ]
        if (
            0 <= next_row < self.item_table.rowCount()
            and 0 <= next_col < self.item_table.columnCount()
        ):
            self.item_table.setCurrentCell(next_row, next_col)
            if next_col in editable_cols:
                item_to_edit = self.item_table.item(next_row, next_col)
                if item_to_edit:
                    QTimer.singleShot(
                        10, lambda: self.item_table.editItem(item_to_edit)
                    )

    def focus_on_code_column(self, row):
        try:
            if 0 <= row < self.item_table.rowCount():
                self._ensure_cell_exists(row, COL_CODE)
                self.item_table.setCurrentCell(row, COL_CODE)
                target_row, target_col = row, COL_CODE
                QTimer.singleShot(
                    10, lambda: self._safe_edit_item(target_row, target_col)
                )
            else:
                self.logger.warning(
                    "Invalid row %s in focus_on_code_column (rowCount: %s)",
                    row,
                    self.item_table.rowCount(),
                )
        except Exception as exc:
            self.logger.error(
                "Error focusing on code column for row %s: %s", row, exc, exc_info=True
            )

    def _safe_edit_item(self, row, col):
        try:
            if (
                row < 0
                or row >= self.item_table.rowCount()
                or col < 0
                or col >= self.item_table.columnCount()
            ):
                self.logger.warning(
                    "Invalid row/col in _safe_edit_item: %s/%s", row, col
                )
                return

            item = self.item_table.item(row, col)
            if item:
                self.item_table.editItem(item)
        except Exception as exc:
            self.logger.error(
                "Error in _safe_edit_item(%s, %s): %s", row, col, exc, exc_info=True
            )

    def process_item_code(self):
        if self.processing_cell:
            return
        if self.current_row < 0 or not self.item_table.item(self.current_row, COL_CODE):
            return

        code_item = self.item_table.item(self.current_row, COL_CODE)
        code = code_item.text().strip().upper()
        code_item.setText(code)

        if not code:
            self._status("Enter item code first", 1500)
            QTimer.singleShot(0, lambda: self.focus_on_code_column(self.current_row))
            return

        presenter = getattr(self, "presenter", None)
        if presenter is None:
            self.logger.error("Presenter unavailable for item code processing.")
            self._status("Item lookup unavailable; presenter not initialised.", 4000)
            return

        try:
            if presenter.handle_item_code(self.current_row, code):
                self._mark_unsaved()
        except Exception as exc:
            self.logger.error(
                "Presenter handle_item_code failed for %s: %s", code, exc, exc_info=True
            )
            self._status("Warning: Item lookup failed via presenter.", 4000)


    def _get_cell_float(self, row, col, default=0.0):
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        value = default
        ok = False
        try:
            locale = QLocale.system()
            f_val, ok = locale.toDouble(text)
            if ok:
                value = f_val
        except Exception:
            ok = False

        if not ok and text:
            try:
                text_for_float = text.replace(",", ".")
                value = float(text_for_float)
                ok = True
            except (ValueError, Exception):
                ok = False

        return value if ok else default

    def _get_cell_int(self, row, col, default=1):
        item = self.item_table.item(row, col)
        text = item.text().strip() if item else ""
        try:
            return int(text) if text else default
        except ValueError:
            return default

    def _ensure_cell_exists(self, row, col, editable=True):
        try:
            if (
                row < 0
                or row >= self.item_table.rowCount()
                or col < 0
                or col >= self.item_table.columnCount()
            ):
                self.logger.warning(
                    "Invalid row/col in _ensure_cell_exists: %s/%s", row, col
                )
                return None

            item = self.item_table.item(row, col)
            if not item:
                item = QTableWidgetItem("")
                self.item_table.setItem(row, col, item)
                if not editable:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            return item
        except Exception as exc:
            self.logger.error(
                "Error ensuring cell exists at %s/%s: %s", row, col, exc, exc_info=True
            )
            return None

    def calculate_net_weight(self):
        if self.current_row < 0:
            return
        try:
            gross = self._get_cell_float(self.current_row, COL_GROSS)
            poly = self._get_cell_float(self.current_row, COL_POLY)
            net = compute_net_weight(gross, poly)
            net_item = self._ensure_cell_exists(
                self.current_row, COL_NET_WT, editable=False
            )
            net_item.setText(f"{net:.2f}")
            self.calculate_fine()
            self.calculate_wage()
        except Exception as exc:
            err_msg = f"Error calculating Net Weight: {exc}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", err_msg)

    def calculate_fine(self):
        if self.current_row < 0:
            return
        try:
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            purity = self._get_cell_float(self.current_row, COL_PURITY)
            fine = compute_fine_weight(net, purity)
            fine_item = self._ensure_cell_exists(
                self.current_row, COL_FINE_WT, editable=False
            )
            fine_item.setText(f"{fine:.2f}")
            if hasattr(self, "request_totals_recalc"):
                self.request_totals_recalc()
            else:
                self.calculate_totals()
        except Exception as exc:
            err_msg = f"Error calculating Fine Weight: {exc}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", err_msg)

    def calculate_wage(self):
        if self.current_row < 0:
            return
        try:
            net = self._get_cell_float(self.current_row, COL_NET_WT)
            wage_rate = self._get_cell_float(self.current_row, COL_WAGE_RATE)
            pieces = self._get_cell_int(self.current_row, COL_PIECES)
            code_item = self.item_table.item(self.current_row, COL_CODE)
            code = code_item.text().strip() if code_item else ""
            wage_basis = "WT"
            if code:
                repo = getattr(self.presenter, "repository", None)
                item_data = repo.fetch_item(code) if repo else None
                if item_data and item_data.get("wage_type") is not None:
                    wage_basis = item_data["wage_type"]
            wage = compute_wage_amount(
                wage_basis,
                net_weight=net,
                wage_rate=wage_rate,
                pieces=pieces,
            )
            wage_item = self._ensure_cell_exists(
                self.current_row, COL_WAGE_AMT, editable=False
            )
            wage_item.setText(f"{wage:.0f}")
            if hasattr(self, "request_totals_recalc"):
                self.request_totals_recalc()
            else:
                self.calculate_totals()
        except Exception as exc:
            err_msg = f"Error calculating Wage: {exc}"
            self.logger.error(err_msg, exc_info=True)
            self._status(err_msg, 5000)
            QMessageBox.critical(self, "Calculation Error", err_msg)


    def _update_row_type_visuals(self, row):
        if 0 <= row < self.item_table.rowCount():
            type_item = self._ensure_cell_exists(row, COL_TYPE, editable=False)
            self.item_table.blockSignals(True)
            try:
                self._update_row_type_visuals_direct(type_item)
                type_item.setTextAlignment(Qt.AlignCenter)
            finally:
                self.item_table.blockSignals(False)

    def toggle_return_mode(self):
        if not getattr(self, "return_mode", False) and getattr(self, "silver_bar_mode", False):
            self.silver_bar_mode = False
            self.silver_bar_toggle_button.setChecked(False)
            self.silver_bar_toggle_button.setText("🥈 Silver Bars")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )

        self.return_mode = not getattr(self, "return_mode", False)
        self.return_toggle_button.setChecked(self.return_mode)

        if self.return_mode:
            self.return_toggle_button.setText("↩ Return Items Mode ACTIVE")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #e8f4fd;
                    border: 2px solid #0066cc;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #003d7a;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #d6eafc;
                }
            """
            )
            self.mode_indicator_label.setText("Mode: Return Items")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #0066cc;")
            self._status("Return Items mode activated", 2000)
        else:
            self.return_toggle_button.setText("↩ Return Items")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )
            if not getattr(self, "silver_bar_mode", False):
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet(
                    """
                    font-weight: bold;
                    color: palette(windowText);
                    background-color: palette(window);
                    border: 1px solid palette(mid);
                    border-radius: 3px;
                    padding: 2px 6px;
                """
                )
            self._status("Return Items mode deactivated", 2000)

        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_mode_tooltip()
        self._mark_unsaved()

    def toggle_silver_bar_mode(self):
        if not getattr(self, "silver_bar_mode", False) and getattr(self, "return_mode", False):
            self.return_mode = False
            self.return_toggle_button.setChecked(False)
            self.return_toggle_button.setText("↩ Return Items")
            self.return_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )

        self.silver_bar_mode = not getattr(self, "silver_bar_mode", False)
        self.silver_bar_toggle_button.setChecked(self.silver_bar_mode)

        if self.silver_bar_mode:
            self.silver_bar_toggle_button.setText("🥈 Silver Bar Mode ACTIVE")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: #fff4e6;
                    border: 2px solid #cc6600;
                    border-radius: 4px;
                    font-weight: bold;
                    color: #994d00;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #ffe6cc;
                }
            """
            )
            self.mode_indicator_label.setText("Mode: Silver Bars")
            self.mode_indicator_label.setStyleSheet("font-weight: bold; color: #cc6600;")
            self._status("Silver Bars mode activated", 2000)
        else:
            self.silver_bar_toggle_button.setText("🥈 Silver Bars")
            self.silver_bar_toggle_button.setStyleSheet(
                """
                QPushButton {
                    background-color: palette(button);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    font-weight: normal;
                    color: palette(buttonText);
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: palette(light);
                }
            """
            )
            if not getattr(self, "return_mode", False):
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet(
                    """
                    font-weight: bold;
                    color: palette(windowText);
                    background-color: palette(window);
                    border: 1px solid palette(mid);
                    border-radius: 3px;
                    padding: 2px 6px;
                """
                )
            self._status("Silver Bars mode deactivated", 2000)

        self._refresh_empty_row_type()
        self.focus_on_empty_row(update_visuals=True)
        self._update_mode_tooltip()
        self._mark_unsaved()

    def _refresh_empty_row_type(self):
        try:
            table = self.item_table
            for row in range(table.rowCount()):
                code_item = table.item(row, COL_CODE)
                if code_item and code_item.text().strip():
                    continue
                type_item = table.item(row, COL_TYPE)
                if type_item is None:
                    type_item = QTableWidgetItem("")
                    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    table.setItem(row, COL_TYPE, type_item)
                table.blockSignals(True)
                try:
                    self._update_row_type_visuals_direct(type_item)
                    type_item.setTextAlignment(Qt.AlignCenter)
                finally:
                    table.blockSignals(False)
        except Exception:
            self.logger.debug("Failed to refresh empty row type", exc_info=True)

    def focus_on_empty_row(self, update_visuals=False):
        empty_row_index = -1
        for row in range(self.item_table.rowCount()):
            code_item = self.item_table.item(row, COL_CODE)
            if not code_item or not code_item.text().strip():
                empty_row_index = row
                break

        if empty_row_index != -1:
            if update_visuals:
                self._update_row_type_visuals(empty_row_index)
                self.calculate_totals()
            self.focus_on_code_column(empty_row_index)
        else:
            self.add_empty_row()

    def delete_current_row(self):
        current_row = self.item_table.currentRow()
        if current_row < 0:
            self._status("Delete Row: No row selected", 3000)
            return

        if self.item_table.rowCount() <= 1:
            self._status("Delete Row: Cannot delete the only row", 3000)
            QMessageBox.warning(self, "Delete Row", "Cannot delete the only row.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete row {current_row + 1}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.item_table.removeRow(current_row)
            self.calculate_totals()
            self._status(f"Row {current_row + 1} deleted.", 2000)
            self._mark_unsaved()

            new_row_count = self.item_table.rowCount()
            if new_row_count == 0:
                self.add_empty_row()
            else:
                focus_row = min(current_row, new_row_count - 1)
                QTimer.singleShot(0, lambda: self.focus_on_code_column(focus_row))

    def move_to_previous_cell(self):
        if self.processing_cell:
            return

        current_col = self.current_column
        current_row = self.current_row
        prev_col = -1
        prev_row = current_row

        editable_cols = [
            COL_CODE,
            COL_GROSS,
            COL_POLY,
            COL_PURITY,
            COL_WAGE_RATE,
            COL_PIECES,
        ]

        if current_col == COL_PIECES:
            prev_col = COL_WAGE_RATE
        elif current_col == COL_WAGE_RATE:
            prev_col = COL_PURITY
        elif current_col == COL_PURITY:
            prev_col = COL_POLY
        elif current_col == COL_POLY:
            prev_col = COL_GROSS
        elif current_col == COL_GROSS:
            prev_col = COL_CODE
        elif current_col == COL_CODE:
            if current_row > 0:
                prev_row = current_row - 1
                prev_col = COL_PIECES
            else:
                prev_col = COL_CODE
                prev_row = 0
        else:
            temp_col = current_col - 1
            while temp_col >= 0:
                if temp_col in editable_cols:
                    prev_col = temp_col
                    break
                temp_col -= 1
            if prev_col == -1:
                if current_row > 0:
                    prev_row = current_row - 1
                    prev_col = COL_PIECES
                else:
                    prev_col = COL_CODE
                    prev_row = 0

        if (
            0 <= prev_row < self.item_table.rowCount()
            and 0 <= prev_col < self.item_table.columnCount()
        ):
            self.item_table.setCurrentCell(prev_row, prev_col)
            if prev_col in editable_cols:
                item_to_edit = self.item_table.item(prev_row, prev_col)
                if item_to_edit:
                    QTimer.singleShot(
                        10, lambda: self.item_table.editItem(item_to_edit)
                    )

