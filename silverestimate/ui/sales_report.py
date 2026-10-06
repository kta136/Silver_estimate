"""On-screen sales reports with period, item and voucher drill-down."""

from collections.abc import Callable
from dataclasses import dataclass
from threading import Event
from typing import Any

from PySide6.QtCore import QDate, QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.sales_report import (
    ReportLevel,
    SalesReportQuery,
    SalesReportResult,
    SalesWeights,
)
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.infrastructure.sqlite_worker import cancellable_sqlite_connection
from silverestimate.persistence.sales_report_repository import fetch_sales_report
from silverestimate.ui.display_formatting import format_display_date
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.models.sales_report_table_model import SalesReportTableModel
from silverestimate.ui.modern_components import (
    install_table_empty_state,
    polish_dense_table,
)
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedComboBox, ThemedDateEdit


@dataclass(frozen=True)
class _ReportRequest:
    connection_factory: Callable[[Event | None], Any]
    query: SalesReportQuery


def _load_report(request: _ReportRequest, cancel_event: Event) -> SalesReportResult:
    with cancellable_sqlite_connection(
        request.connection_factory, cancel_event
    ) as connection:
        connection.execute("BEGIN")
        return fetch_sales_report(connection.cursor(), request.query, cancel_event)


class SalesReportWidget(QWidget):
    voucher_requested = Signal(str)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self._level: ReportLevel = "period"
        self._period: str | None = None
        self._item_code: str | None = None
        self._closed = False
        self._loading = False
        self._load_runner = LatestRequestRunner(
            _load_report, self, name="sales-report-loader"
        )
        self._load_runner.result.connect(self._loaded)
        self._load_runner.failed.connect(self._failed)
        self._build_ui()

    def _build_ui(self):
        self.setObjectName("SalesReportScreen")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QWidget#SalesReportScreen",
                card_names=["SalesHeader", "SalesFilters", "SalesSummary"],
                title_label="SalesTitle",
                subtitle_label="SalesSubtitle",
                primary_button="SalesPrimary",
                secondary_button="SalesSecondary",
                include_table=True,
                extra_rules="""
                    QComboBox#SalesPeriodSelector {
                        padding-right: 42px;
                    }
                    QComboBox#SalesPeriodSelector::drop-down {
                        subcontrol-origin: padding;
                        subcontrol-position: top right;
                        width: 36px;
                        background-color: __SELECTION_BG__;
                        border: none;
                        border-left: 1px solid __FOCUS_RING__;
                        border-top-right-radius: 5px;
                        border-bottom-right-radius: 5px;
                    }
                    QComboBox#SalesPeriodSelector::drop-down:hover {
                        background-color: __INFO_BORDER__;
                    }
                """,
            )
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)
        header = QFrame()
        header.setObjectName("SalesHeader")
        header_layout = QVBoxLayout(header)
        title = QLabel("Sales Reports")
        title.setObjectName("SalesTitle")
        subtitle = QLabel(
            "Every saved estimate · Sales and returns shown separately · Weights in grams"
        )
        subtitle.setObjectName("SalesSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header)
        layout.addWidget(self._build_filters())
        layout.addLayout(self._build_totals())
        layout.addLayout(self._build_navigation())
        self.scope_label = QLabel()
        self.scope_label.setTextFormat(Qt.TextFormat.PlainText)
        self.scope_label.setWordWrap(True)
        layout.addWidget(self.scope_label)
        self.table = QTableView()
        self.model = SalesReportTableModel(self.table)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        polish_dense_table(self.table, hide_vertical_header=True)
        self.table.horizontalHeader().setFixedHeight(
            self.table.horizontalHeader().fontMetrics().height() * 2 + 12
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._empty_state = install_table_empty_state(
            self.table, "No sales or returns in this selection."
        )
        self.table.doubleClicked.connect(self._activate_selected)
        self.table.selectionModel().selectionChanged.connect(self._update_actions)
        layout.addWidget(self.table, 1)
        self.status_label = QLabel("Select a period to view its items.")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status_label)
        self._update_actions()

    def _build_filters(self):
        card = QFrame()
        card.setObjectName("SalesFilters")
        layout = QVBoxLayout(card)
        fields = QHBoxLayout()
        self.date_from = self._date_edit()
        self.date_to = self._date_edit()
        self.grouping = ThemedComboBox()
        self.grouping.setObjectName("SalesPeriodSelector")
        self.grouping.addItem("Day-wise", "day")
        self.grouping.addItem("Month-wise", "month")
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("All item codes")
        self.item_search.setClearButtonEnabled(True)
        for label, control in (
            ("From", self.date_from),
            ("To", self.date_to),
            ("Group by", self.grouping),
            ("Item code", self.item_search),
        ):
            field = QVBoxLayout()
            caption = QLabel(label)
            caption.setBuddy(control)
            field.addWidget(caption)
            field.addWidget(control)
            fields.addLayout(field, 1)
        layout.addLayout(fields)
        buttons = QHBoxLayout()
        self.today_button = QPushButton("Today")
        self.month_button = QPushButton("This month")
        self.refresh_button = QPushButton("View report")
        self.refresh_button.setObjectName("SalesPrimary")
        buttons.addWidget(self.today_button)
        buttons.addWidget(self.month_button)
        buttons.addStretch()
        buttons.addWidget(self.refresh_button)
        layout.addLayout(buttons)
        self.today_button.clicked.connect(lambda: self._set_range(False))
        self.month_button.clicked.connect(lambda: self._set_range(True))
        self.refresh_button.clicked.connect(self.refresh)
        self.item_search.returnPressed.connect(self.refresh)
        self.date_from.dateChanged.connect(self._filters_changed)
        self.date_to.dateChanged.connect(self._filters_changed)
        self.grouping.currentIndexChanged.connect(self._filters_changed)
        self.item_search.textChanged.connect(self._filters_changed)
        return card

    def _date_edit(self):
        control = ThemedDateEdit()
        control.setCalendarPopup(True)
        control.setDisplayFormat("dd/MM/yyyy")
        control.setDate(QDate.currentDate())
        return control

    def _build_totals(self):
        layout = QHBoxLayout()
        self.total_labels: list[QLabel] = []
        for caption in (
            "Sale net weight",
            "Sale fine weight",
            "Return net weight",
            "Return fine weight",
        ):
            card = QFrame()
            card.setObjectName("SalesSummary")
            contents = QVBoxLayout(card)
            contents.addWidget(QLabel(caption))
            value = QLabel("—")
            font = value.font()
            font.setPointSize(14)
            font.setBold(True)
            value.setFont(font)
            contents.addWidget(value)
            self.total_labels.append(value)
            layout.addWidget(card, 1)
        return layout

    def _build_navigation(self):
        layout = QHBoxLayout()
        self.back_button = QPushButton("Back to periods")
        self.all_items_button = QPushButton("All items in date range")
        self.open_button = QPushButton("View items")
        self.open_button.setObjectName("SalesPrimary")
        self.back_button.clicked.connect(self._go_back)
        self.all_items_button.clicked.connect(self._all_items)
        self.open_button.clicked.connect(self._activate_selected)
        layout.addWidget(self.back_button)
        layout.addWidget(self.all_items_button)
        layout.addStretch()
        layout.addWidget(self.open_button)
        return layout

    def _set_range(self, whole_month: bool):
        today = QDate.currentDate()
        with QSignalBlocker(self.date_from), QSignalBlocker(self.date_to):
            self.date_from.setDate(
                QDate(today.year(), today.month(), 1) if whole_month else today
            )
            self.date_to.setDate(
                QDate(today.year(), today.month(), today.daysInMonth())
                if whole_month
                else today
            )
        self._filters_changed()
        self.refresh()

    def _filters_changed(self, *_):
        self._load_runner.cancel()
        self._loading = False
        self._level, self._period, self._item_code = "period", None, None
        self._clear_result()
        self.scope_label.setText("")
        self.status_label.setText(
            "Filters changed. Select View report to update the results."
        )
        self._empty_state.setText("Select View report to apply your filters.")
        self._update_actions()

    def _query(self):
        return SalesReportQuery(
            date_from=self.date_from.date().toString("yyyy-MM-dd"),
            date_to=self.date_to.date().toString("yyyy-MM-dd"),
            grouping=self.grouping.currentData(),
            item_search=self.item_search.text().strip(),
            level=self._level,
            period=self._period,
            item_code=self._item_code,
        )

    def refresh(self):
        if self._closed:
            return
        self._load_runner.cancel()
        self._clear_result()
        self._loading = False
        query = self._query()
        self._update_scope(query)
        try:
            query.validate()
            self._loading = True
            self._load_runner.submit(
                _ReportRequest(self.db_manager.open_read_connection, query)
            )
            self.status_label.setText("Loading sales report…")
            self._empty_state.setText("Loading sales report…")
        except Exception as exc:
            self._loading = False
            self.status_label.setText(str(exc))
            self._empty_state.setText(str(exc))
        self._update_actions()

    def _clear_result(self):
        self.model.set_report(self._level, ())
        self._set_totals(None)

    def _update_scope(self, query):
        view = {
            "period": self.grouping.currentText() + " totals",
            "item": "Item totals",
            "voucher": "Contributing vouchers",
        }[self._level]
        scope = f"{view} · {format_display_date(query.date_from)} – {format_display_date(query.date_to)}"
        if self._period:
            scope += f" · Period: {self._period}"
        if self._item_code is not None:
            scope += f" · Item: {self._item_code}"
        elif query.item_search:
            scope += f" · Item code contains: {query.item_search}"
        self.scope_label.setText(scope)

    def _loaded(self, generation: int, result: SalesReportResult):
        if self._closed or generation != self._load_runner.generation:
            return
        self._loading = False
        self.model.set_report(self._level, result.rows)
        column = 1 if self._level == "voucher" else 0
        order = (
            Qt.SortOrder.AscendingOrder
            if self._level == "item"
            else Qt.SortOrder.DescendingOrder
        )
        self.table.sortByColumn(column, order)
        self._set_totals(result.totals)
        self._empty_state.setText(
            "No sales or returns match the selected dates and item code."
        )
        instructions = {
            "period": "Select a period to view its items.",
            "item": "Select an item to view its contributing vouchers.",
            "voucher": "Weights are for the selected item. Select a voucher to open the estimate.",
        }
        count = len(result.rows)
        self.status_label.setText(
            f"{count} rows · {instructions[self._level]}"
            if count
            else "No sales or returns match the selected dates and item code."
        )
        self._update_actions()

    def _failed(self, generation: int, error: object):
        if self._closed or generation != self._load_runner.generation:
            return
        self._loading = False
        self._clear_result()
        self.status_label.setText(
            f"Could not load sales report: {error}. Select View report to retry."
        )
        self._empty_state.setText("Report unavailable. Select View report to retry.")
        self._update_actions()

    def _set_totals(self, totals: SalesWeights | None):
        values = totals.values() if totals is not None else (None,) * 4
        for label, value in zip(self.total_labels, values, strict=True):
            label.setText(
                "—" if value is None else f"{format_indian_number(value, 2)} g"
            )

    def _update_actions(self, *_):
        self.back_button.setVisible(self._level != "period")
        self.back_button.setText(
            "Back to items" if self._level == "voucher" else "Back to periods"
        )
        self.open_button.setText(
            {
                "period": "View items",
                "item": "View vouchers",
                "voucher": "Open estimate",
            }[self._level]
        )
        selected = bool(self.table.selectionModel().selectedRows())
        self.open_button.setEnabled(not self._loading and selected)

    def _activate_selected(self, *_):
        selected = self.table.selectionModel().selectedRows()
        if self._loading or not selected:
            return
        row = self.model.rows[selected[0].row()]
        if self._level == "voucher":
            self.voucher_requested.emit(row.key)
            return
        if self._level == "period":
            self._period, self._level = row.key, "item"
        else:
            self._item_code, self._level = row.key, "voucher"
        self.refresh()

    def _all_items(self):
        self._level, self._period, self._item_code = "item", None, None
        self.refresh()

    def _go_back(self):
        if self._level == "voucher":
            self._level, self._item_code = "item", None
        else:
            self._level, self._period = "period", None
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def hideEvent(self, event):
        self._load_runner.cancel()
        super().hideEvent(event)

    def shutdown_workers(self):
        self._closed = True
        self._load_runner.shutdown()

    def closeEvent(self, event):
        self.shutdown_workers()
        super().closeEvent(event)
