from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QDate, QTimer, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem

from silverestimate.domain.estimate_models import (
    EstimateLine,
    EstimateLineCategory,
    TotalsResult,
)
from silverestimate.presenter import EstimateEntryViewState, LoadedEstimate
from silverestimate.services.estimate_calculator import compute_totals
from silverestimate.services.estimate_entry_persistence import (
    EstimateEntryPersistenceService,
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
from silverestimate.ui.view_models import EstimateEntryRowState

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from silverestimate.presenter import EstimateEntryPresenter


class _EstimatePersistenceMixin:
    """Presenter and persistence oriented helpers."""

    def _update_view_model_snapshot(self) -> None:
        """Refresh the view-model with current table state when available."""
        view_model = getattr(self, "view_model", None)
        if view_model is None or not hasattr(self, "item_table"):
            return

        rows: list[EstimateEntryRowState] = []
        table = self.item_table
        for row in range(table.rowCount()):
            try:
                type_item = table.item(row, COL_TYPE)
                category = EstimateLineCategory.from_label(
                    type_item.text() if type_item else None
                )
                name_item = table.item(row, COL_ITEM_NAME)
                row_state = EstimateEntryRowState(
                    code=self._get_row_code(row),
                    name=name_item.text() if name_item else "",
                    gross=self._get_cell_float(row, COL_GROSS),
                    poly=self._get_cell_float(row, COL_POLY),
                    net_weight=self._get_cell_float(row, COL_NET_WT),
                    purity=self._get_cell_float(row, COL_PURITY),
                    wage_rate=self._get_cell_float(row, COL_WAGE_RATE),
                    pieces=self._get_cell_int(row, COL_PIECES),
                    wage_amount=self._get_cell_float(row, COL_WAGE_AMT),
                    fine_weight=self._get_cell_float(row, COL_FINE_WT),
                    category=category,
                    row_index=row + 1,
                )
            except Exception as row_error:
                self.logger.debug(
                    "Skipping row %s for view-model snapshot: %s",
                    row + 1,
                    row_error,
                    exc_info=True,
                )
                continue
            rows.append(row_state)

        view_model.set_rows(rows)

        try:
            silver_rate = float(self.silver_rate_spin.value())
        except Exception:
            silver_rate = 0.0

        view_model.set_totals_inputs(
            silver_rate=silver_rate,
            last_balance_silver=getattr(self, "last_balance_silver", 0.0),
            last_balance_amount=getattr(self, "last_balance_amount", 0.0),
        )
        view_model.set_modes(
            return_mode=getattr(self, "return_mode", False),
            silver_bar_mode=getattr(self, "silver_bar_mode", False),
        )


    def apply_loaded_estimate(self, loaded: LoadedEstimate) -> bool:
        success = False
        self._push_unsaved_block()
        self.item_table.blockSignals(True)
        self.processing_cell = True
        try:
            while self.item_table.rowCount() > 0:
                self.item_table.removeRow(0)

            try:
                load_date = QDate.fromString(loaded.date, "yyyy-MM-dd")
                if load_date and load_date.isValid():
                    self.date_edit.setDate(load_date)
                else:
                    self.date_edit.setDate(QDate.currentDate())
            except Exception:
                self.date_edit.setDate(QDate.currentDate())

            self.silver_rate_spin.setValue(loaded.silver_rate)

            if hasattr(self, "note_edit"):
                try:
                    self.note_edit.setText(loaded.note or "")
                except Exception:
                    self.note_edit.setText("")

            view_model = getattr(self, "view_model", None)
            row_states = EstimateEntryPersistenceService.build_row_states_from_items(
                loaded.items
            )

            if view_model is not None:
                view_model.set_rows(row_states)
                view_model.set_totals_inputs(
                    silver_rate=loaded.silver_rate,
                    last_balance_silver=loaded.last_balance_silver,
                    last_balance_amount=loaded.last_balance_amount,
                )
                view_model.set_modes(return_mode=False, silver_bar_mode=False)

            self.last_balance_silver = loaded.last_balance_silver
            self.last_balance_amount = loaded.last_balance_amount

            for row_state in row_states:
                row = self.item_table.rowCount()
                self.item_table.insertRow(row)
                canonical_code = (row_state.code or "").strip()
                display_code = canonical_code.upper() if canonical_code else ""
                code_item = QTableWidgetItem(display_code)
                code_item.setData(Qt.UserRole, canonical_code or None)
                self.item_table.setItem(row, COL_CODE, code_item)
                self.item_table.setItem(
                    row, COL_ITEM_NAME, QTableWidgetItem(row_state.name)
                )
                self.item_table.setItem(
                    row, COL_GROSS, QTableWidgetItem(f"{row_state.gross:.2f}")
                )
                self.item_table.setItem(
                    row, COL_POLY, QTableWidgetItem(f"{row_state.poly:.2f}")
                )
                self.item_table.setItem(
                    row, COL_NET_WT, QTableWidgetItem(f"{row_state.net_weight:.2f}")
                )
                self.item_table.setItem(
                    row, COL_PURITY, QTableWidgetItem(f"{row_state.purity:.2f}")
                )
                self.item_table.setItem(
                    row, COL_WAGE_RATE, QTableWidgetItem(f"{row_state.wage_rate:.2f}")
                )
                self.item_table.setItem(
                    row, COL_PIECES, QTableWidgetItem(str(row_state.pieces))
                )
                self.item_table.setItem(
                    row, COL_WAGE_AMT, QTableWidgetItem(f"{row_state.wage_amount:.0f}")
                )
                self.item_table.setItem(
                    row, COL_FINE_WT, QTableWidgetItem(f"{row_state.fine_weight:.2f}")
                )

                if row_state.category.is_return():
                    type_text, bg_color = "Return", QColor(255, 200, 200)
                elif row_state.category.is_silver_bar():
                    type_text, bg_color = "Silver Bar", QColor(200, 255, 200)
                else:
                    type_text, bg_color = "No", QColor(255, 255, 255)
                type_item = QTableWidgetItem(type_text)
                type_item.setBackground(bg_color)
                type_item.setTextAlignment(Qt.AlignCenter)
                type_item.setFlags(type_item.flags() & ~Qt.ItemIsEditable)
                self.item_table.setItem(row, COL_TYPE, type_item)

                for col in [COL_NET_WT, COL_WAGE_AMT, COL_FINE_WT]:
                    cell = self.item_table.item(row, col)
                    if cell:
                        cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)

            self.add_empty_row()
            self.calculate_totals()
            self._update_view_model_snapshot()

            self._estimate_loaded = True
            success = True
            try:
                if hasattr(self, "delete_estimate_button"):
                    self.delete_estimate_button.setEnabled(True)
            except Exception:
                pass
        finally:
            self.processing_cell = False
            self.item_table.blockSignals(False)
            self._pop_unsaved_block()
            try:
                self.focus_on_code_column(0)
            except Exception:
                pass

        if success:
            self.set_voucher_number(loaded.voucher_no)
            self._set_unsaved(False, force=True)
        return success


    def capture_state(self) -> EstimateEntryViewState:
        view_model = getattr(self, "view_model", None)
        if view_model is not None:
            self._update_view_model_snapshot()
            return view_model.as_view_state()

        lines = []
        for row in range(self.item_table.rowCount()):
            code = self._get_row_code(row)
            if not code:
                continue
            try:
                type_item = self.item_table.item(row, COL_TYPE)
                category = EstimateLineCategory.from_label(
                    type_item.text() if type_item else None
                )
                line = EstimateLine(
                    code=code,
                    category=category,
                    gross=self._get_cell_float(row, COL_GROSS),
                    poly=self._get_cell_float(row, COL_POLY),
                    net_weight=self._get_cell_float(row, COL_NET_WT),
                    fine_weight=self._get_cell_float(row, COL_FINE_WT),
                    wage_amount=self._get_cell_float(row, COL_WAGE_AMT),
                )
                lines.append(line)
            except Exception as row_error:
                self.logger.warning(
                    "Skipping row %s in state capture due to error: %s",
                    row + 1,
                    row_error,
                )
                continue

        try:
            silver_rate = float(self.silver_rate_spin.value())
        except Exception:
            silver_rate = 0.0

        last_balance_silver = getattr(self, "last_balance_silver", 0.0)
        last_balance_amount = getattr(self, "last_balance_amount", 0.0)

        return EstimateEntryViewState(
            lines=lines,
            silver_rate=silver_rate,
            last_balance_silver=last_balance_silver,
            last_balance_amount=last_balance_amount,
        )

    def apply_totals(self, totals: TotalsResult) -> None:
        try:
            if hasattr(self, "overall_gross_label"):
                self.overall_gross_label.setText(f"{totals.overall_gross:.1f}")
            if hasattr(self, "overall_poly_label"):
                self.overall_poly_label.setText(f"{totals.overall_poly:.1f}")

            if hasattr(self, "total_gross_label"):
                self.total_gross_label.setText(f"{totals.regular.gross:.1f}")
            if hasattr(self, "total_net_label"):
                self.total_net_label.setText(f"{totals.regular.net:.1f}")
            if hasattr(self, "total_fine_label"):
                self.total_fine_label.setText(f"{totals.regular.fine:.1f}")

            if hasattr(self, "return_gross_label"):
                self.return_gross_label.setText(f"{totals.returns.gross:.1f}")
            if hasattr(self, "return_net_label"):
                self.return_net_label.setText(f"{totals.returns.net:.1f}")
            if hasattr(self, "return_fine_label"):
                self.return_fine_label.setText(f"{totals.returns.fine:.1f}")

            if hasattr(self, "bar_gross_label"):
                self.bar_gross_label.setText(f"{totals.silver_bars.gross:.1f}")
            if hasattr(self, "bar_net_label"):
                self.bar_net_label.setText(f"{totals.silver_bars.net:.1f}")
            if hasattr(self, "bar_fine_label"):
                self.bar_fine_label.setText(f"{totals.silver_bars.fine:.1f}")

            if hasattr(self, "net_fine_label"):
                if totals.last_balance_silver > 0:
                    self.net_fine_label.setText(
                        f"{totals.net_fine_core:.1f} + {totals.last_balance_silver:.1f} = {totals.net_fine:.1f}"
                    )
                else:
                    self.net_fine_label.setText(f"{totals.net_fine_core:.1f}")

            if hasattr(self, "net_wage_label"):
                base_wage = self._format_currency(totals.net_wage_core)
                if totals.last_balance_amount > 0:
                    lb_wage = self._format_currency(totals.last_balance_amount)
                    total_wage = self._format_currency(totals.net_wage)
                    self.net_wage_label.setText(f"{base_wage} + {lb_wage} = {total_wage}")
                else:
                    self.net_wage_label.setText(base_wage)

            if hasattr(self, "grand_total_label"):
                if totals.silver_rate > 0:
                    self.grand_total_label.setText(
                        self._format_currency(totals.grand_total)
                    )
                    if hasattr(self, "net_value_label"):
                        self.net_value_label.setText(
                            self._format_currency(totals.net_value)
                        )
                else:
                    wage_str = self._format_currency(totals.net_wage)
                    grand_total_text = f"{totals.net_fine:.1f} g | {wage_str}"
                    self.grand_total_label.setText(grand_total_text)
                    if hasattr(self, "net_value_label"):
                        self.net_value_label.setText("")
        except Exception as exc:
            self.logger.error(
                "Error updating UI labels in apply_totals: %s", exc, exc_info=True
            )
            self._status("Warning: Some UI elements could not be updated", 3000)

    def calculate_totals(self):
        presenter = getattr(self, "presenter", None)
        if presenter is not None:
            try:
                presenter.refresh_totals()
            except Exception as exc:
                self.logger.error(
                    "Presenter totals computation failed: %s", exc, exc_info=True
                )
                self._status("Warning: presenter totals failed, falling back.", 3500)

        state = self.capture_state()
        totals = compute_totals(
            state.lines,
            silver_rate=state.silver_rate,
            last_balance_silver=state.last_balance_silver,
            last_balance_amount=state.last_balance_amount,
        )
        self.apply_totals(totals)


    def generate_voucher(self):
        try:
            try:
                if hasattr(self, "safe_load_estimate"):
                    self.voucher_edit.editingFinished.disconnect(self.safe_load_estimate)
                else:
                    self.voucher_edit.editingFinished.disconnect(self.load_estimate)
            except TypeError:
                pass

            presenter = getattr(self, "presenter", None)
            if presenter is None:
                raise RuntimeError("Estimate presenter is not available.")

            voucher_no = presenter.generate_voucher()
            if not voucher_no:
                raise RuntimeError("No voucher number could be generated.")

            self.logger.info("Generated new voucher: %s", voucher_no)
            try:
                if hasattr(self, "delete_estimate_button"):
                    self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass
            self._estimate_loaded = False

        except Exception as exc:
            self.logger.error("Error generating voucher number: %s", exc, exc_info=True)
            self._status("Error generating voucher number", 3000)
            QMessageBox.critical(
                self, "Error", f"Failed to generate voucher number: {exc}"
            )
        finally:
            try:
                if hasattr(self, "safe_load_estimate"):
                    self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
                else:
                    self.voucher_edit.editingFinished.connect(self.load_estimate)
            except Exception as exc:
                self.logger.error("Error reconnecting signal: %s", exc, exc_info=True)


    def load_estimate(self):
        if hasattr(self, "initializing") and self.initializing:
            self.logger.debug("Skipping load_estimate during initialization")
            return

        presenter = getattr(self, "presenter", None)
        if presenter is None:
            self.logger.error("Cannot load estimate: presenter is not available")
            QMessageBox.critical(
                self,
                "Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return

        try:
            voucher_no = self.voucher_edit.text().strip()
        except Exception as exc:
            self.logger.error("Error getting voucher number: %s", exc, exc_info=True)
            QMessageBox.critical(self, "Error", f"Error accessing voucher field: {exc}")
            return

        if not voucher_no:
            return

        self.logger.info("Loading estimate %s...", voucher_no)
        self._status(f"Loading estimate {voucher_no}...", 2000)

        try:
            loaded_estimate = presenter.load_estimate(voucher_no)
        except Exception as exc:
            self.logger.error(
                "Error retrieving estimate %s: %s", voucher_no, exc, exc_info=True
            )
            QMessageBox.critical(
                self,
                "Load Error",
                f"Error retrieving estimate {voucher_no}: {exc}",
            )
            self._status(f"Error retrieving estimate {voucher_no}", 4000)
            return

        if loaded_estimate is None:
            self.logger.warning("Estimate voucher '%s' not found", voucher_no)
            QMessageBox.warning(
                self, "Load Error", f"Estimate voucher '{voucher_no}' not found."
            )
            self._status(f"Estimate {voucher_no} not found.", 4000)
            self._estimate_loaded = False
            try:
                if hasattr(self, "delete_estimate_button"):
                    self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass
            return

        if self.apply_loaded_estimate(loaded_estimate):
            self.logger.info(
                "Estimate %s loaded successfully", loaded_estimate.voucher_no
            )
            self._status(
                f"Estimate {loaded_estimate.voucher_no} loaded successfully.", 3000
            )
        else:
            self._status(f"Estimate {voucher_no} could not be loaded.", 4000)


    def save_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            self.logger.warning("Save Error: Voucher number missing")
            QMessageBox.warning(self, "Input Error", "Voucher number is required to save.")
            self._status("Save Error: Voucher number missing", 4000)
            return

        presenter = getattr(self, "presenter", None)
        if presenter is None:
            self.logger.error("Cannot save estimate: presenter is not available")
            QMessageBox.critical(
                self,
                "Save Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return

        view_model = getattr(self, "view_model", None)
        if view_model is None:
            self.logger.error("Cannot save estimate: view-model is not available")
            QMessageBox.critical(
                self,
                "Save Error",
                "Estimate view-model is unavailable. Please restart the application.",
            )
            return

        self.logger.info("Saving estimate %s...", voucher_no)
        self._status(f"Saving estimate {voucher_no}...", 2000)

        # Ensure the view-model reflects the latest UI state
        self._update_view_model_snapshot()

        note = self.note_edit.text().strip() if hasattr(self, "note_edit") else ""
        date = self.date_edit.date().toString("yyyy-MM-dd")

        service = EstimateEntryPersistenceService(view_model)
        try:
            outcome, preparation = service.execute_save(
                voucher_no=voucher_no,
                date=date,
                note=note,
                presenter=presenter,
            )
        except ValueError as exc:
            message = str(exc)
            self.logger.warning("Save Error: %s", message)
            QMessageBox.warning(self, "Input Error", message)
            self._status(f"Save Error: {message}", 4000)
            return
        except Exception as exc:
            self.logger.error(
                "Unexpected error saving estimate %s: %s", voucher_no, exc, exc_info=True
            )
            QMessageBox.critical(
                self,
                "Save Error",
                f"An unexpected error occurred while saving estimate '{voucher_no}': {exc}",
            )
            self._status("Save Error: Unexpected exception during save", 5000)
            return

        if preparation.skipped_rows:
            row_list = ", ".join(map(str, preparation.skipped_rows))
            error_msg = (
                "Could not process data in row(s): "
                f"{row_list}. These rows were skipped."
            )
            self.logger.warning(error_msg)
            for row_number, detail in preparation.row_errors.items():
                self.logger.error("Row %s skipped during save: %s", row_number, detail)
            QMessageBox.warning(self, "Data Error", error_msg)
            self._status(
                f"Save Error: Invalid data in row(s) {row_list}",
                5000,
            )

        if outcome.success:
            self._status(outcome.message, 5000)
            QMessageBox.information(self, "Success", outcome.message)
            self.print_estimate()
            self.clear_form(confirm=False)
        else:
            error_detail = outcome.error_detail
            if error_detail:
                dialog_message = (
                    f"Estimate '{voucher_no}' could not be saved.\n\n{error_detail}"
                )
                status_message = f"Save Error: {error_detail}"
            else:
                dialog_message = outcome.message
                status_message = outcome.message
            self.logger.error(
                "Save estimate %s failed: %s",
                voucher_no,
                error_detail or outcome.message,
            )
            QMessageBox.critical(self, "Save Error", dialog_message)
            self._status(status_message.replace('\n', ' ').strip(), 5000)

    def _get_row_code(self, row: int) -> str:
        code_item = self.item_table.item(row, COL_CODE)
        if not code_item:
            return ""
        data = code_item.data(Qt.UserRole)
        if isinstance(data, str) and data.strip():
            return data.strip()
        text = code_item.text()
        return text.strip() if text else ""


    def print_estimate(self):
        from ..print_manager import PrintManager

        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(
                self,
                "Print Error",
                "Please save the estimate or generate a voucher number before printing.",
            )
            self._status("Print Error: Voucher number missing", 4000)
            return

        self.logger.info("Generating print preview for %s...", voucher_no)
        self._status(f"Generating print preview for {voucher_no}...")
        try:
            if hasattr(self, "print_button"):
                self.print_button.setEnabled(False)
        except Exception:
            pass
        current_print_font = getattr(self.main_window, "print_font", None)
        print_manager = PrintManager(self.db_manager, print_font=current_print_font)
        success = print_manager.print_estimate(voucher_no, self)
        if success:
            self._status(f"Print preview for {voucher_no} generated.", 3000)
        else:
            self._status(f"Failed to generate print preview for {voucher_no}.", 4000)
        try:
            if hasattr(self, "print_button"):
                self.print_button.setEnabled(True)
        except Exception:
            pass


    def delete_current_estimate(self):
        voucher_no = self.voucher_edit.text().strip()
        if not voucher_no:
            QMessageBox.warning(
                self,
                "Delete Error",
                "No estimate voucher number entered/loaded.",
            )
            self._status("Delete Error: No voucher number", 3000)
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Delete Estimate",
            (
                f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
                "This action cannot be undone."
            ),
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )

        if reply == QMessageBox.Yes:
            try:
                presenter = getattr(self, "presenter", None)
                if presenter is None:
                    raise RuntimeError("Estimate presenter is not available.")
                success = presenter.delete_estimate(voucher_no)
                if success:
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Estimate '{voucher_no}' deleted successfully.",
                    )
                    self._status(f"Estimate {voucher_no} deleted.", 3000)
                    self.clear_form(confirm=False)
                else:
                    QMessageBox.warning(
                        self,
                        "Delete Error",
                        "Estimate '{voucher_no}' could not be deleted (might already be deleted).",
                    )
                    self._status(f"Delete Error: Failed for {voucher_no}", 4000)
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"An unexpected error occurred during deletion: {exc}",
                )
                self._status(f"Delete Error: Unexpected error for {voucher_no}", 5000)

