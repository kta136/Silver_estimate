from __future__ import annotations

import logging
import threading
import traceback
from typing import Optional, TYPE_CHECKING

from PyQt5.QtCore import QDate, QLocale, QTimer
from PyQt5.QtWidgets import QMessageBox

from .constants import COL_CODE

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from silverestimate.presenter import EstimateEntryPresenter


class _EstimateBaseMixin:
    """Core helpers for estimate entry logic."""

    presenter: Optional["EstimateEntryPresenter"]

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)
        self._estimate_loaded = False
        self._unsaved_changes = False
        self._unsaved_block = 0
        self._enforcing_code_nav = False
        self.presenter = None

        # Default state used by downstream mixins/tests.
        self.return_mode = False
        self.silver_bar_mode = False
        self.processing_cell = False
        self.current_row = -1
        self.current_column = COL_CODE
        self.last_balance_silver = 0.0
        self.last_balance_amount = 0.0

    # --- Status helpers -------------------------------------------------
    def _status(self, message, timeout=3000):
        if hasattr(self, "show_status") and callable(self.show_status):
            self.show_status(message, timeout)
        else:
            self.logger.info("Status: %s", message)

    def _push_unsaved_block(self) -> None:
        self._unsaved_block = getattr(self, "_unsaved_block", 0) + 1

    def _pop_unsaved_block(self) -> None:
        if getattr(self, "_unsaved_block", 0) > 0:
            self._unsaved_block -= 1

    def _set_unsaved(self, dirty: bool, *, force: bool = False) -> None:
        if not force and dirty and getattr(self, "_unsaved_block", 0) > 0:
            return
        previous = getattr(self, "_unsaved_changes", False)
        self._unsaved_changes = dirty
        if previous != dirty or force:
            callback = getattr(self, "_on_unsaved_state_changed", None)
            if callable(callback):
                try:
                    callback(dirty)
                except Exception:
                    pass

    def _mark_unsaved(self, *_, **__) -> None:
        self._set_unsaved(True)

    # --- Field helpers --------------------------------------------------
    def set_voucher_number(self, voucher_no: str) -> None:
        editor = getattr(self, "voucher_edit", None)
        if editor is None:
            return
        try:
            editor.blockSignals(True)
            editor.setText(voucher_no)
        finally:
            editor.blockSignals(False)

    # --- Signal wiring --------------------------------------------------
    def connect_signals(self, skip_load_estimate: bool = False) -> None:
        if not skip_load_estimate:
            if hasattr(self, "safe_load_estimate"):
                self.voucher_edit.editingFinished.connect(self.safe_load_estimate)
            else:
                self.voucher_edit.editingFinished.connect(self.load_estimate)

        self.silver_rate_spin.valueChanged.connect(self._handle_silver_rate_changed)

        if hasattr(self, "last_balance_button"):
            self.last_balance_button.clicked.connect(self.show_last_balance_dialog)
        if hasattr(self, "note_edit"):
            self.note_edit.textEdited.connect(self._mark_unsaved)
        if hasattr(self, "date_edit"):
            self.date_edit.dateChanged.connect(self._mark_unsaved)

        self.item_table.cellClicked.connect(self.cell_clicked)
        self.item_table.itemSelectionChanged.connect(self.selection_changed)
        self.item_table.currentCellChanged.connect(self.current_cell_changed)
        self.item_table.cellChanged.connect(self.handle_cell_changed)

        self.save_button.clicked.connect(self.save_estimate)
        self.clear_button.clicked.connect(self.clear_form)
        self.print_button.clicked.connect(self.print_estimate)
        self.return_toggle_button.clicked.connect(self.toggle_return_mode)
        self.silver_bar_toggle_button.clicked.connect(self.toggle_silver_bar_mode)

        if hasattr(self, "history_button"):
            self.history_button.clicked.connect(self.show_history)
        if hasattr(self, "silver_bars_button"):
            self.silver_bars_button.clicked.connect(self.show_silver_bars)
        if hasattr(self, "refresh_rate_button"):
            self.refresh_rate_button.clicked.connect(self.refresh_silver_rate)

        if hasattr(self, "delete_estimate_button"):
            self.delete_estimate_button.clicked.connect(self.delete_current_estimate)
            try:
                self.delete_estimate_button.setEnabled(False)
            except Exception:
                pass

    def _handle_silver_rate_changed(self, *_):
        try:
            self.calculate_totals()
        except Exception:
            pass
        self._mark_unsaved()
        self._mark_unsaved()

    def _format_currency(self, value):
        try:
            locale = QLocale.system()
            return locale.toCurrencyString(float(round(value)))
        except Exception:
            try:
                return f"₹ {int(round(value)):,}"
            except Exception:
                return str(value)

    # --- Live rate refresh ----------------------------------------------
    def refresh_silver_rate(self):
        btn = getattr(self, "refresh_rate_button", None)
        try:
            if btn:
                btn.setEnabled(False)
        except Exception:
            pass
        self._status("Refreshing live silver rate…", 2000)

        def worker():
            rate = None
            try:
                from silverestimate.services.dda_rate_fetcher import (
                    fetch_broadcast_rate_exact,
                    fetch_silver_agra_local_mohar_rate,
                )

                try:
                    rate, market_open, _ = fetch_broadcast_rate_exact(timeout=7)
                except Exception:
                    rate = None
                if rate is None:
                    try:
                        rate, _meta = fetch_silver_agra_local_mohar_rate(timeout=7)
                    except Exception:
                        rate = None
            except Exception:
                rate = None

            def apply():
                try:
                    if btn:
                        btn.setEnabled(True)
                except Exception:
                    pass
                if rate is None:
                    try:
                        QMessageBox.warning(
                            self,
                            "Rate Refresh",
                            "Could not fetch live silver rate. Please try again.",
                        )
                    except Exception:
                        pass
                    if hasattr(self, "live_rate_value_label"):
                        try:
                            self.live_rate_value_label.setText("N/A /g")
                        except Exception:
                            pass
                    self._status("Live rate refresh failed", 3000)
                    return

                gram_rate = None
                try:
                    gram_rate = float(rate) / 1000.0
                except Exception:
                    gram_rate = None

                if gram_rate is None:
                    if hasattr(self, "live_rate_value_label"):
                        try:
                            self.live_rate_value_label.setText("N/A /g")
                        except Exception:
                            pass
                    self._status("Live rate unavailable", 3000)
                    return

                if hasattr(self, "live_rate_value_label"):
                    try:
                        locale = QLocale.system()
                        display = locale.toCurrencyString(gram_rate)
                        display = f"{display} /g"
                    except Exception:
                        try:
                            display = f"₹ {round(gram_rate, 2)} /g"
                        except Exception:
                            display = str(gram_rate)
                    try:
                        self.live_rate_value_label.setText(display)
                    except Exception:
                        pass

                self._status("Live rate refreshed (per-gram display)", 2000)

            QTimer.singleShot(0, apply)

        threading.Thread(target=worker, daemon=True).start()

    # --- Form maintenance -----------------------------------------------
    def clear_form(self, confirm: bool = True):
        reply = QMessageBox.No
        if confirm:
            reply = QMessageBox.question(
                self,
                "Confirm New Estimate",
                "Start a new estimate? Unsaved changes will be lost.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

        if reply == QMessageBox.Yes or not confirm:
            self._push_unsaved_block()
            self.item_table.blockSignals(True)
            self.processing_cell = True
            cleared = False
            try:
                self.voucher_edit.clear()
                self.generate_voucher()
                self.date_edit.setDate(QDate.currentDate())
                self.silver_rate_spin.setValue(0)
                if hasattr(self, "note_edit"):
                    self.note_edit.clear()

                self.last_balance_silver = 0.0
                self.last_balance_amount = 0.0
                if getattr(self, "return_mode", False):
                    self.toggle_return_mode()
                if getattr(self, "silver_bar_mode", False):
                    self.toggle_silver_bar_mode()
                self.mode_indicator_label.setText("Mode: Regular")
                self.mode_indicator_label.setStyleSheet("font-weight: bold;")
                self._update_mode_tooltip()

                while self.item_table.rowCount() > 0:
                    self.item_table.removeRow(0)
                self.add_empty_row()
                self.calculate_totals()
                self._status("New estimate form cleared.", 3000)
                cleared = True
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Error clearing form: {exc}\n{traceback.format_exc()}",
                )
                self._status("Error clearing form.", 4000)
            finally:
                self.processing_cell = False
                self.item_table.blockSignals(False)
                QTimer.singleShot(50, lambda: self.focus_on_code_column(0))
                self._estimate_loaded = False
                try:
                    if hasattr(self, "delete_estimate_button"):
                        self.delete_estimate_button.setEnabled(False)
                except Exception:
                    pass
                self._pop_unsaved_block()
            if cleared:
                self._set_unsaved(False, force=True)

    def confirm_exit(self) -> bool:
        has_changes = getattr(self, "has_unsaved_changes", None)
        if callable(has_changes):
            if not has_changes():
                return True
        elif not getattr(self, "_unsaved_changes", False):
            return True

        reply = QMessageBox.question(
            self,
            "Discard Unsaved Changes?",
            "You have unsaved changes that will be lost. Exit anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            return True
        self._status("Close cancelled; current estimate still unsaved.", 2000)
        return False
