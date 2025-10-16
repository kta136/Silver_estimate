from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QMessageBox,
    QFormLayout,
    QVBoxLayout,
)

from ..item_selection_dialog import ItemSelectionDialog

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from silverestimate.presenter import EstimateEntryPresenter


class _EstimateDialogsMixin:
    """Dialog helpers for the estimate entry workflow."""


    def prompt_item_selection(self, code: str):
        try:
            dialog = ItemSelectionDialog(self.db_manager, code, self)
            if dialog.exec_() == QDialog.Accepted:
                selected_item = dialog.get_selected_item()
                if selected_item:
                    return selected_item
        except Exception as exc:
            self.logger.error(
                "Error during item selection for code %s: %s", code, exc, exc_info=True
            )
            QMessageBox.critical(
                self, "Selection Error", f"Could not open selection dialog: {exc}"
            )
        return None


    def open_history_dialog(self) -> Optional[str]:
        try:
            from ..estimate_history import EstimateHistoryDialog

            history_dialog = EstimateHistoryDialog(
                self.db_manager,
                main_window_ref=self.main_window,
                parent=self,
            )
            if history_dialog.exec_() == QDialog.Accepted:
                return history_dialog.selected_voucher or None
            return None
        except Exception as exc:
            QMessageBox.critical(
                self,
                "History Error",
                f"Failed to open estimate history: {exc}",
            )
            self._status("History Error: Unable to open history dialog.", 5000)
            return None

    def show_silver_bar_management(self) -> None:
        try:
            if hasattr(self, "main_window") and hasattr(self.main_window, "show_silver_bars"):
                self.main_window.show_silver_bars()
                self._status("Opened Silver Bar Management.", 1500)
                return
        except Exception:
            pass
        from ..silver_bar_management import SilverBarDialog

        silver_dialog = SilverBarDialog(self.db_manager, self)
        silver_dialog.exec_()
        self._status("Closed Silver Bar Management.", 2000)


    def show_last_balance_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Enter Last Balance")
        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()

        self.lb_silver_spin = QDoubleSpinBox()
        self.lb_silver_spin.setRange(0, 1000000)
        self.lb_silver_spin.setDecimals(2)
        self.lb_silver_spin.setSuffix(" g")
        if hasattr(self, "last_balance_silver"):
            self.lb_silver_spin.setValue(self.last_balance_silver)
        form_layout.addRow("Silver Weight:", self.lb_silver_spin)

        self.lb_amount_spin = QDoubleSpinBox()
        self.lb_amount_spin.setRange(0, 10000000)
        self.lb_amount_spin.setDecimals(0)
        self.lb_amount_spin.setPrefix("₹ ")
        if hasattr(self, "last_balance_amount"):
            self.lb_amount_spin.setValue(self.last_balance_amount)
        form_layout.addRow("Amount:", self.lb_amount_spin)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        if dialog.exec_():
            self.last_balance_silver = self.lb_silver_spin.value()
            self.last_balance_amount = self.lb_amount_spin.value()
            self.logger.info(
                "Last balance set: %.2f g, ₹ %.0f",
                self.last_balance_silver,
                self.last_balance_amount,
            )
            self._status(
                f"Last balance set: {self.last_balance_silver:.2f} g, ₹ {self.last_balance_amount:.0f}",
                3000,
            )
            self.calculate_totals()
            self._mark_unsaved()
        else:
            self._status("Last balance not changed", 2000)


    def show_history(self):
        presenter = getattr(self, "presenter", None)
        if presenter is None:
            QMessageBox.critical(
                self,
                "History Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return
        try:
            presenter.open_history()
        except Exception as exc:
            self.logger.error("Error opening estimate history: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "History Error",
                f"Failed to open estimate history: {exc}",
            )
            self._status("History Error: Unable to open history dialog.", 5000)

    def show_silver_bars(self):
        presenter = getattr(self, "presenter", None)
        if presenter is None:
            QMessageBox.critical(
                self,
                "Error",
                "Estimate presenter is not available. Please restart the application.",
            )
            return
        try:
            presenter.open_silver_bar_management()
        except Exception as exc:
            self.logger.error("Error opening Silver Bar Management: %s", exc, exc_info=True)
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to open Silver Bar Management: {exc}",
            )
            self._status("Error: Unable to open Silver Bar Management.", 5000)

