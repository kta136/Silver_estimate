#!/usr/bin/env python
import logging
import os
import time
from functools import partial

from PyQt6.QtCore import QDate, QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
)

from silverestimate.persistence.estimates_repository import fetch_estimate_history_rows
from silverestimate.ui.models import EstimateHistoryRow, EstimateHistoryTableModel
from silverestimate.ui.modern_components import (
    BottomStatusStrip,
    DetailsStrip,
    polish_dense_table,
)

from .icons import get_icon
from .print_manager import PrintManager, PrintPreviewBuildWorker
from .shared_screen_theme import build_management_screen_stylesheet
from .themed_controls import ThemedDateEdit
from .window_sizing import resize_to_available_screen


class EstimateHistoryDialog(QDialog):
    """Dialog for browsing and selecting past estimates."""

    # Accept db_manager, an explicit main_window_ref, and the standard parent
    def __init__(self, db_manager, main_window_ref, parent=None):
        super().__init__(parent)  # Use standard parent for QDialog
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.main_window = main_window_ref  # Store the explicit reference to MainWindow
        self.selected_voucher = None
        self._load_request_id = 0
        self._active_load_workers: dict[QThread, QObject] = {}
        self._print_preview_request_id = 0
        self._active_print_preview_workers: dict[QThread, QObject] = {}
        self.init_ui()
        self.load_estimates()

    def init_ui(self):
        """Set up the user interface."""
        self.setWindowTitle("Estimate History")
        self.setMinimumSize(820, 500)
        resize_to_available_screen(
            self,
            preferred_width=1120,
            preferred_height=640,
        )
        self.setObjectName("EstimateHistoryDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#EstimateHistoryDialog",
                card_names=[
                    "HistoryHeaderCard",
                    "HistoryFilterCard",
                    "HistoryActionCard",
                    "HistoryDetailsStrip",
                ],
                title_label="HistoryTitleLabel",
                subtitle_label="HistorySubtitleLabel",
                field_label="HistoryFieldLabel",
                primary_button="HistoryPrimaryButton",
                secondary_button="HistorySecondaryButton",
                danger_button="HistoryDangerButton",
                input_selectors=["QLineEdit", "QDateEdit"],
                include_table=True,
                extra_rules="""
                QLabel#HistorySubtitleLabel {
                    font-size: 8.7pt;
                }
                QLabel#HistorySummaryLabel {
                    background-color: __HEADER_BG__;
                    border: 1px solid __CARD_BORDER__;
                    border-radius: 6px;
                    color: __FIELD_TEXT__;
                    font-weight: 600;
                    padding: 5px 10px;
                }
                QLabel#HistoryTitleLabel {
                    font-size: 13pt;
                    color: __HEADER_TEXT__;
                }
                QTableView {
                    color: __TEXT_STRONG__;
                    font-size: 8.8pt;
                    alternate-background-color: __SURFACE_BG__;
                }
                QTableView::item {
                    padding: 1px 6px;
                }
                QDateEdit {
                    min-width: 120px;
                    max-width: 138px;
                }
                QHeaderView::section {
                    background-color: __HEADER_BG__;
                    color: __FIELD_TEXT__;
                    padding: 5px 7px;
                }
                """,
            )
        )

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        header_card = QFrame(self)
        header_card.setObjectName("HistoryHeaderCard")
        header_layout = QHBoxLayout(header_card)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.setSpacing(8)

        header_label = QLabel("Estimate History")
        header_label.setObjectName("HistoryTitleLabel")
        header_layout.addWidget(header_label, 0, Qt.AlignmentFlag.AlignLeft)
        subtitle_label = QLabel("Find, open, print, or delete saved estimates.")
        subtitle_label.setObjectName("HistorySubtitleLabel")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        header_layout.addWidget(subtitle_label, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)
        layout.addWidget(header_card)

        filter_card = QFrame(self)
        filter_card.setObjectName("HistoryFilterCard")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(12, 7, 12, 7)
        filter_layout.setSpacing(6)

        from_label = QLabel("From")
        from_label.setObjectName("HistoryFieldLabel")
        filter_layout.addWidget(from_label)
        self.date_from = ThemedDateEdit()
        self.date_from.setCalendarPopup(True)
        first_estimate_date = self._resolve_first_estimate_date()
        self.date_from.setDate(first_estimate_date)
        self.date_from.setMinimumWidth(124)
        self.date_from.setMaximumWidth(138)
        filter_layout.addWidget(self.date_from)

        to_label = QLabel("To")
        to_label.setObjectName("HistoryFieldLabel")
        filter_layout.addWidget(to_label)
        self.date_to = ThemedDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setMinimumWidth(124)
        self.date_to.setMaximumWidth(138)
        filter_layout.addWidget(self.date_to)

        voucher_label = QLabel("Voucher No")
        voucher_label.setObjectName("HistoryFieldLabel")
        filter_layout.addWidget(voucher_label)
        self.voucher_search = QLineEdit()
        self.voucher_search.setPlaceholderText("Search voucher...")
        self.voucher_search.setClearButtonEnabled(True)
        self.voucher_search.setMinimumWidth(160)
        self.voucher_search.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.voucher_search.returnPressed.connect(self.load_estimates)
        filter_layout.addWidget(self.voucher_search, 1)

        self.search_button = QPushButton("Search")
        self.search_button.setObjectName("HistoryPrimaryButton")
        self.search_button.setIcon(get_icon("search", widget=self, color="#ffffff"))
        self.search_button.setMinimumWidth(88)
        self.search_button.clicked.connect(self.load_estimates)
        filter_layout.addWidget(self.search_button)

        self.results_summary_label = QLabel("Loading estimates...")
        self.results_summary_label.setObjectName("HistorySummaryLabel")
        self.results_summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_summary_label.setMinimumWidth(150)
        filter_layout.addWidget(self.results_summary_label)

        layout.addWidget(filter_card)

        # Estimates table
        self.estimates_table = QTableView(self)
        self.estimates_table.setObjectName("HistoryTable")
        self.estimates_model = EstimateHistoryTableModel(self.estimates_table)
        self.estimates_table.setModel(self.estimates_model)
        header = self.estimates_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.estimates_table.setColumnWidth(0, 92)
        self.estimates_table.setColumnWidth(1, 96)
        self.estimates_table.setColumnWidth(3, 98)
        self.estimates_table.setColumnWidth(4, 94)
        self.estimates_table.setColumnWidth(5, 94)
        self.estimates_table.setColumnWidth(6, 94)
        self.estimates_table.setColumnWidth(7, 104)
        self.estimates_table.setColumnWidth(8, 128)

        # Table properties
        self.estimates_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.estimates_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.estimates_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.estimates_table.setSortingEnabled(True)
        self.estimates_table.setAlternatingRowColors(True)
        self.estimates_table.setShowGrid(False)
        self.estimates_table.setWordWrap(False)
        self.estimates_table.verticalHeader().setVisible(False)
        polish_dense_table(
            self.estimates_table,
            row_height=28,
            header_height=30,
            show_grid=False,
            hide_vertical_header=True,
        )
        self.estimates_table.doubleClicked.connect(lambda *_: self.accept())
        selection_model = self.estimates_table.selectionModel()
        if selection_model is not None:
            selection_model.selectionChanged.connect(
                lambda *_: self._update_selected_details()
            )

        layout.addWidget(self.estimates_table, 1)

        self.selected_details_strip = DetailsStrip("Selected Estimate", self)
        self.selected_details_strip.setObjectName("HistoryDetailsStrip")
        layout.addWidget(self.selected_details_strip)

        self.bottom_status_strip = BottomStatusStrip(self)
        self.bottom_status_strip.set_left_items(["Rows: 0"])
        layout.addWidget(self.bottom_status_strip)

        actions_card = QFrame(self)
        actions_card.setObjectName("HistoryActionCard")
        button_layout = QHBoxLayout(actions_card)
        button_layout.setContentsMargins(12, 8, 12, 8)
        button_layout.setSpacing(8)

        self.open_button = QPushButton("Open")
        self.open_button.setObjectName("HistoryPrimaryButton")
        self.open_button.setIcon(get_icon("open", widget=self, color="#ffffff"))
        self.open_button.setToolTip("Open the selected estimate")
        self.open_button.clicked.connect(self.accept)
        button_layout.addWidget(self.open_button)

        self.print_button = QPushButton("Print")
        self.print_button.setObjectName("HistorySecondaryButton")
        self.print_button.setIcon(get_icon("print", widget=self))
        self.print_button.setToolTip("Open print preview for the selected estimate")
        self.print_button.clicked.connect(self.print_estimate)
        button_layout.addWidget(self.print_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("HistoryDangerButton")
        self.delete_button.setToolTip("Permanently delete the selected estimate")
        self.delete_button.setIcon(get_icon("delete", widget=self, color="#dc2626"))
        self.delete_button.clicked.connect(self.delete_selected_estimate)
        button_layout.addWidget(self.delete_button)

        button_layout.addStretch(1)

        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("HistorySecondaryButton")
        self.close_button.setIcon(get_icon("close", widget=self))
        self.close_button.clicked.connect(self.reject)
        button_layout.addWidget(self.close_button)

        layout.addWidget(actions_card)

        self._update_results_summary()
        self._update_selected_details()

    def _resolve_first_estimate_date(self):
        """Resolve the earliest estimate date, falling back to today."""
        today = QDate.currentDate()
        getter = getattr(self.db_manager, "get_first_estimate_date", None)
        if not callable(getter):
            return today
        try:
            first_date_str = getter()
            if not first_date_str:
                return today
            parsed = QDate.fromString(str(first_date_str), "yyyy-MM-dd")
            return parsed if parsed.isValid() else today
        except Exception:
            return today

    def load_estimates(self):
        """Load estimates based on search criteria (runs queries in a background thread)."""
        self._load_request_id += 1
        request_id = self._load_request_id
        self.results_summary_label.setText("Loading estimates...")
        started_at = time.perf_counter()

        # Start threaded load and return early to keep UI responsive
        try:
            self.search_button.setEnabled(False)
            if hasattr(self, "open_button"):
                self.open_button.setEnabled(False)
            if hasattr(self, "print_button"):
                self.print_button.setEnabled(False)
            if hasattr(self, "delete_button"):
                self.delete_button.setEnabled(False)
        except Exception as exc:
            self.logger.debug("Failed to disable history action buttons: %s", exc)

        temp_db_path = getattr(self.db_manager, "temp_db_path", None)
        if (
            not isinstance(temp_db_path, str)
            or not temp_db_path
            or temp_db_path == ":memory:"
        ):
            try:
                rows = self._load_estimates_sync()
                self._populate_table(rows, request_id=request_id, started_at=started_at)
            except Exception as exc:
                self._handle_load_error(str(exc), request_id)
                self._loading_done(None, None, request_id)
            return

        worker = _HistoryLoadWorker(
            temp_db_path,
            self.date_from.date().toString("yyyy-MM-dd"),
            self.date_to.date().toString("yyyy-MM-dd"),
            self.voucher_search.text().strip(),
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.data_ready.connect(
            partial(self._populate_table, request_id=request_id, started_at=started_at)
        )
        worker.error.connect(partial(self._handle_load_error, request_id=request_id))
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(partial(self._loading_done, thread, None, request_id))
        self._active_load_workers[thread] = worker
        thread.start()
        return

    def _load_estimates_sync(self) -> list[dict]:
        getter = getattr(self.db_manager, "get_estimate_history_rows", None)
        if callable(getter):
            return list(
                getter(
                    date_from=self.date_from.date().toString("yyyy-MM-dd"),
                    date_to=self.date_to.date().toString("yyyy-MM-dd"),
                    voucher_search=self.voucher_search.text().strip(),
                )
                or []
            )
        raise RuntimeError("Estimate history rows are unavailable.")

    def _handle_load_error(self, message, request_id, *_) -> None:
        if request_id != self._load_request_id:
            return
        QMessageBox.warning(self, "Load Error", message)

    def _populate_table(
        self, history_rows, request_id=None, started_at=None, *_
    ) -> None:
        if request_id is not None and request_id != self._load_request_id:
            return
        table = self.estimates_table
        sorting_enabled = table.isSortingEnabled()
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            rows = []
            for history_row in history_rows or []:
                vno = str(history_row.get("voucher_no", "") or "")
                total_gross = float(history_row.get("total_gross", 0.0) or 0.0)
                total_net = float(history_row.get("total_net", 0.0) or 0.0)
                net_fine = float(history_row.get("total_fine", 0.0) or 0.0)
                net_wage = float(history_row.get("total_wage", 0.0) or 0.0)
                silver_rate = float(history_row.get("silver_rate", 0.0) or 0.0)
                last_balance_amount = float(
                    history_row.get("last_balance_amount", 0.0) or 0.0
                )
                rows.append(
                    EstimateHistoryRow(
                        voucher_no=vno,
                        date=str(history_row.get("date", "") or ""),
                        note=str(history_row.get("note", "") or ""),
                        silver_rate=silver_rate,
                        total_gross=total_gross,
                        total_net=total_net,
                        net_fine=net_fine,
                        net_wage=net_wage,
                        grand_total=(net_fine * silver_rate)
                        + net_wage
                        + last_balance_amount,
                    )
                )
            if sorting_enabled:
                table.setSortingEnabled(False)
            self.estimates_model.set_rows(rows)
            self._update_results_summary(len(rows))
            if rows:
                table.selectRow(0)
            else:
                table.clearSelection()
            self._update_selected_details()
        finally:
            if sorting_enabled:
                table.setSortingEnabled(True)
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()
        if started_at is not None:
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            if elapsed_ms >= 20.0:
                self.logger.debug(
                    "[perf] estimate_history.load_estimates=%.2fms rows=%s",
                    elapsed_ms,
                    len(rows),
                )

    def _loading_done(self, thread, worker, request_id=None, *_) -> None:
        if thread is not None:
            self._active_load_workers.pop(thread, None)
        if worker is not None:
            try:
                worker.deleteLater()
            except Exception as exc:
                self.logger.debug("Failed to schedule history worker deletion: %s", exc)
        if request_id is not None and request_id != self._load_request_id:
            return
        try:
            self.search_button.setEnabled(True)
            if hasattr(self, "open_button"):
                self.open_button.setEnabled(True)
            if hasattr(self, "print_button"):
                self.print_button.setEnabled(True)
            if hasattr(self, "delete_button"):
                self.delete_button.setEnabled(True)
        except Exception as exc:
            self.logger.debug("Failed to re-enable history action buttons: %s", exc)

    def _update_results_summary(self, row_count: int | None = None) -> None:
        total = self.estimates_model.rowCount() if row_count is None else int(row_count)
        if total <= 0:
            text = "No estimates found"
        elif total == 1:
            text = "1 estimate"
        else:
            text = f"{total} estimates"

        if self.voucher_search.text().strip():
            text += " match current filters"
        else:
            text += " in current date range"
        self.results_summary_label.setText(text)
        self._update_bottom_status(total)

    def _update_selected_details(self) -> None:
        strip = getattr(self, "selected_details_strip", None)
        if strip is None:
            return
        selection_model = self.estimates_table.selectionModel()
        selected_rows = selection_model.selectedRows() if selection_model else []
        if not selected_rows:
            strip.setVisible(False)
            strip.set_items([("Voucher No", "-"), ("Date", "-"), ("Grand Total", "-")])
            self._update_bottom_status()
            return
        payload = self.estimates_model.row_payload(selected_rows[0].row())
        if payload is None:
            strip.setVisible(False)
            strip.set_items([("Voucher No", "-"), ("Date", "-"), ("Grand Total", "-")])
            self._update_bottom_status()
            return
        strip.setVisible(True)
        strip.set_items(
            [
                ("Voucher No", payload.voucher_no),
                ("Date", payload.date),
                ("Note", payload.note or "-"),
                ("Silver Rate", f"{payload.silver_rate:,.2f}"),
                ("Total Gross", f"{payload.total_gross:.3f}"),
                ("Total Net", f"{payload.total_net:.3f}"),
                ("Net Fine", f"{payload.net_fine:.3f}"),
                ("Net Wage", f"{payload.net_wage:,.2f}"),
                ("Grand Total", f"{payload.grand_total:,.2f}"),
            ]
        )
        self._update_bottom_status()

    def _update_bottom_status(self, row_count: int | None = None) -> None:
        strip = getattr(self, "bottom_status_strip", None)
        if strip is None:
            return
        total = self.estimates_model.rowCount() if row_count is None else int(row_count)
        selection_model = self.estimates_table.selectionModel()
        selected = len(selection_model.selectedRows()) if selection_model else 0
        try:
            user = os.environ.get("USERNAME") or os.environ.get("USER") or "-"
        except Exception:
            user = "-"
        strip.set_left_items([f"Rows: {total}"])
        strip.set_right_items([f"{selected} row selected", "Last Saved: -", f"User: {user}"])

    def _cancel_active_loads(self, timeout_ms: int = 4000) -> None:
        # Invalidate any pending UI updates from old workers.
        self._load_request_id += 1
        active = list(self._active_load_workers.items())
        self._active_load_workers.clear()

        for thread, worker in active:
            try:
                worker.deleteLater()
            except Exception as exc:
                self.logger.debug(
                    "Failed to schedule history worker deletion during cancel: %s", exc
                )
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        thread.terminate()
                        thread.wait(1000)
            except Exception as exc:
                self.logger.debug(
                    "Failed to stop estimate history worker thread during cancel: %s",
                    exc,
                )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def reject(self):
        self._cancel_active_loads()
        self._cancel_active_print_previews()
        super().reject()

    def closeEvent(self, event):
        self._cancel_active_loads()
        self._cancel_active_print_previews()
        super().closeEvent(event)

    def get_selected_voucher(self):
        """Get the selected voucher number."""
        selection_model = self.estimates_table.selectionModel()
        assert selection_model is not None
        selected_rows = selection_model.selectedRows()
        if not selected_rows:
            return None
        payload = self.estimates_model.row_payload(selected_rows[0].row())
        return payload.voucher_no if payload is not None else None

    def accept(self):
        """Handle dialog acceptance and return the selected voucher."""
        self.selected_voucher = self.get_selected_voucher()
        if not self.selected_voucher:
            QMessageBox.warning(
                self, "Selection Error", "Please select an estimate first."
            )
            return

        super().accept()

    def print_estimate(self):
        """Print the selected estimate."""
        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(
                self, "Selection Error", "Please select an estimate first."
            )
            return

        # --- Get the print font from the explicitly stored main window reference ---
        print_font_setting = None
        if self.main_window and hasattr(self.main_window, "print_font"):
            print_font_setting = self.main_window.print_font
        # ---------------------------------------------------------

        estimate_data = self.db_manager.get_estimate_by_voucher(voucher_no)
        if not estimate_data:
            QMessageBox.warning(
                self, "Print Error", f"Estimate {voucher_no} could not be loaded."
            )
            return

        print_manager = PrintManager(self.db_manager, print_font=print_font_setting)
        self._start_print_preview_build(
            print_manager=print_manager,
            build_preview=lambda: print_manager.build_estimate_preview_payload(
                voucher_no,
                estimate_data=estimate_data,
            ),
        )

    def _next_print_preview_request_id(self) -> int:
        self._print_preview_request_id += 1
        return self._print_preview_request_id

    def _start_print_preview_build(self, *, print_manager, build_preview) -> None:
        request_id = self._next_print_preview_request_id()
        progress = QProgressDialog("Preparing print preview...", "", 0, 0, self)
        progress.setCancelButton(None)
        progress.setWindowTitle("Print Preview")
        progress.setMinimumDuration(0)
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.show()

        worker = PrintPreviewBuildWorker(request_id, build_preview)
        thread = QThread(self)
        worker.moveToThread(thread)
        self._active_print_preview_workers[thread] = worker

        thread.started.connect(worker.run)
        worker.preview_ready.connect(
            partial(
                self._on_print_preview_ready,
                thread=thread,
                worker=worker,
                print_manager=print_manager,
                progress=progress,
            )
        )
        worker.preview_error.connect(
            partial(
                self._on_print_preview_error,
                thread=thread,
                worker=worker,
                progress=progress,
            )
        )
        worker.finished.connect(
            partial(
                self._finish_print_preview_build,
                thread=thread,
                worker=worker,
                progress=progress,
            )
        )
        thread.start()

    def _on_print_preview_ready(
        self,
        request_id,
        payload,
        *,
        thread,
        worker,
        print_manager,
        progress,
    ) -> None:
        del thread, worker
        if request_id != self._print_preview_request_id:
            return
        try:
            progress.close()
        except Exception as exc:
            self.logger.debug("Failed to close history print preview progress: %s", exc)
        if payload is None:
            QMessageBox.warning(
                self,
                "Print Error",
                "Failed to prepare the selected estimate for preview.",
            )
            return
        print_manager.show_preview(payload, parent_widget=self)

    def _on_print_preview_error(
        self,
        request_id,
        message,
        *,
        thread,
        worker,
        progress,
    ) -> None:
        del thread, worker
        if request_id != self._print_preview_request_id:
            return
        try:
            progress.close()
        except Exception as exc:
            self.logger.debug(
                "Failed to close history print preview progress after error: %s",
                exc,
            )
        QMessageBox.warning(self, "Print Error", message)

    def _finish_print_preview_build(
        self,
        request_id,
        *,
        thread,
        worker,
        progress,
    ) -> None:
        self._active_print_preview_workers.pop(thread, None)
        try:
            progress.close()
            progress.deleteLater()
        except Exception as exc:
            self.logger.debug(
                "Failed to dispose history print preview progress dialog: %s",
                exc,
            )
        try:
            thread.quit()
            thread.wait(1000)
        except Exception as exc:
            self.logger.debug(
                "Failed to stop estimate history preview worker thread: %s", exc
            )
        try:
            worker.deleteLater()
            thread.deleteLater()
        except Exception as exc:
            self.logger.debug(
                "Failed to schedule history preview worker deletion: %s", exc
            )
        if request_id != self._print_preview_request_id:
            return

    def _cancel_active_print_previews(self, timeout_ms: int = 4000) -> None:
        self._print_preview_request_id += 1
        active = list(self._active_print_preview_workers.items())
        self._active_print_preview_workers.clear()

        for thread, worker in active:
            try:
                worker.deleteLater()
            except Exception as exc:
                self.logger.debug(
                    "Failed to schedule history preview worker deletion during cancel: %s",
                    exc,
                )
            try:
                if thread.isRunning():
                    thread.quit()
                    if not thread.wait(timeout_ms):
                        thread.terminate()
                        thread.wait(1000)
            except Exception as exc:
                self.logger.debug(
                    "Failed to stop estimate history preview worker during cancel: %s",
                    exc,
                )

    def delete_selected_estimate(self):
        """Handle deletion of the selected estimate."""
        voucher_no = self.get_selected_voucher()
        if not voucher_no:
            QMessageBox.warning(
                self, "Selection Error", "Please select an estimate to delete."
            )
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Delete Estimate",
            f"Are you sure you want to permanently delete estimate '{voucher_no}'?\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                success = self.db_manager.delete_single_estimate(voucher_no)
                if success:
                    QMessageBox.information(
                        self,
                        "Success",
                        f"Estimate '{voucher_no}' deleted successfully.",
                    )
                    self.load_estimates()  # Refresh the list
                else:
                    QMessageBox.warning(
                        self,
                        "Delete Error",
                        f"Estimate '{voucher_no}' could not be deleted (might already be deleted).",
                    )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"An unexpected error occurred during deletion: {str(e)}",
                )


class _HistoryLoadWorker(QObject):
    data_ready = pyqtSignal(list)
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

        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            rows = fetch_estimate_history_rows(
                cur,
                date_from=self.date_from,
                date_to=self.date_to,
                voucher_search=self.voucher_search,
            )
            self.data_ready.emit(rows)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception as exc:
                    logging.getLogger(__name__).debug(
                        "Failed to close estimate history worker connection: %s", exc
                    )
            self.finished.emit()
