"""On-screen sales reports with period, item and voucher drill-down."""

from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from threading import Event
from typing import Any

from PySide6.QtCore import QDate, QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
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
from silverestimate.ui.models.sales_report_table_model import (
    SalesReportTableModel,
    format_period,
)
from silverestimate.ui.modern_components import polish_dense_table
from silverestimate.ui.screen_widgets import (
    SCREEN_QSS,
    EmptyStatePanel,
    KeyHintButton,
    OptionGroup,
    TableTotalsFooter,
    WeightBarDelegate,
    card,
    label,
)
from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.themed_controls import ThemedDateEdit

_UNLIMITED_HEIGHT = 16777215  # Qt's QWIDGETSIZE_MAX

# Below this width the filter bar uses two rows.
COMPACT_FILTER_WIDTH = 1150

_SALES_QSS = """
QLabel#SalesFieldLabel { color: __TEXT_MUTED__; font-weight: 600; font-size: 9pt; }
QLabel#MetricValue { font-size: 15pt; }
QLabel#MetricValue[accent="true"] { font-size: 15pt; }
QLabel#SalesBreadcrumb { font-size: 10pt; }
QPushButton#SalesPrimary, QPushButton#SalesSecondary { padding: 6px 14px; min-height: 24px; }
QPushButton#EmptyStateAction {
    background: __SURFACE_BG__; border: 1px solid __INPUT_BORDER__;
    border-radius: 6px; padding: 6px 14px; font-weight: 600;
}
"""


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
        self._item_name = ""
        self._crumbs: list[tuple[str, str]] = []
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
                card_names=[],
                title_label="SalesTitle",
                subtitle_label="SalesSubtitle",
                primary_button="SalesPrimary",
                secondary_button="SalesSecondary",
                include_table=True,
                extra_rules=SCREEN_QSS + _SALES_QSS,
            )
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_filters())
        body = QVBoxLayout()
        body.setContentsMargins(18, 10, 18, 12)
        body.setSpacing(10)
        body.addLayout(self._build_totals())
        body.addWidget(self._build_table_card(), 1)
        layout.addLayout(body, 1)
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence(Qt.Key.Key_F5))
        refresh.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        refresh.triggered.connect(self.refresh)
        self.addAction(refresh)
        self._update_actions()

    def _build_filters(self):
        header = QFrame()
        header.setObjectName("ScreenHeaderBar")
        layout = QVBoxLayout(header)
        layout.setContentsMargins(18, 10, 18, 10)
        layout.setSpacing(6)
        title_row = QHBoxLayout()
        title_row.setSpacing(14)
        title_row.addWidget(label("Sales reports", "ScreenTitle"))
        subtitle = label(
            "Every saved estimate · returns shown separately, not subtracted · "
            "weights in grams",
            "Muted",
        )
        subtitle.setWordWrap(True)
        title_row.addWidget(subtitle, 1)
        layout.addLayout(title_row)
        fields = QHBoxLayout()
        fields.setSpacing(18)
        second_row = QHBoxLayout()
        second_row.setSpacing(18)
        fields.addWidget(self._field("Dates", self._build_dates(), self.date_from))
        self.grouping = OptionGroup("segmented")
        self.grouping.addItem("Day", "day")
        self.grouping.addItem("Month", "month")
        self.grouping.setAccessibleName("Group by")
        self._grouping_field = self._field("Group by", self.grouping)
        fields.addWidget(self._grouping_field)
        self.item_search = QLineEdit()
        self.item_search.setPlaceholderText("All item codes")
        self.item_search.setClearButtonEnabled(True)
        self.item_search.setMinimumWidth(180)
        self.item_search.setMaximumWidth(280)
        self._item_field = self._field("Item code", self.item_search, self.item_search)
        fields.addWidget(self._item_field)
        fields.addStretch(1)
        self.refresh_button = KeyHintButton("View report", "F5")
        self.refresh_button.setObjectName("SalesPrimary")
        self.refresh_button.setAutoDefault(False)
        fields.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(fields)
        second_row.addStretch(1)
        layout.addLayout(second_row)
        self._filter_rows = (fields, second_row)
        self._connect_filters()
        return header

    def _connect_filters(self):
        self.today_button.clicked.connect(lambda: self._set_range(False))
        self.month_button.clicked.connect(lambda: self._set_range(True))
        self.refresh_button.clicked.connect(self.refresh)
        self.item_search.returnPressed.connect(self.refresh)
        self.date_from.dateChanged.connect(self._filters_changed)
        self.date_to.dateChanged.connect(self._filters_changed)
        self.grouping.currentIndexChanged.connect(self._filters_changed)
        self.item_search.textChanged.connect(self._filters_changed)

    def _build_dates(self):
        self.date_from = self._date_edit()
        self.date_to = self._date_edit()
        dates = QHBoxLayout()
        dates.setSpacing(8)
        dates.addWidget(self.date_from)
        dates.addWidget(label("to", "Muted"))
        dates.addWidget(self.date_to)
        self.today_button = self._chip("Today")
        self.month_button = self._chip("This month")
        dates.addWidget(self.today_button)
        dates.addWidget(self.month_button)
        return dates

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_filters()

    def _arrange_filters(self):
        """Below 1150 px the grouping, item code and button move to a second row."""
        first, second = self._filter_rows
        wide = self.width() >= COMPACT_FILTER_WIDTH
        target = first if wide else second
        if target.indexOf(self._grouping_field) >= 0:
            return
        moving = (self._grouping_field, self._item_field)
        source = second if wide else first
        for widget in (*moving, self.refresh_button):
            source.removeWidget(widget)
        start = 1 if wide else 0
        for offset, widget in enumerate(moving):
            target.insertWidget(start + offset, widget)
        target.addWidget(self.refresh_button, 0, Qt.AlignmentFlag.AlignBottom)

    @staticmethod
    def _field(caption, control, buddy=None):
        widget = QWidget()
        field = QVBoxLayout(widget)
        field.setContentsMargins(0, 0, 0, 0)
        field.setSpacing(5)
        caption_label = label(caption, "SalesFieldLabel")
        if buddy is not None:
            caption_label.setBuddy(buddy)
        field.addWidget(caption_label)
        if isinstance(control, QHBoxLayout):
            field.addLayout(control)
        else:
            field.addWidget(control, 0, Qt.AlignmentFlag.AlignLeft)
        return widget

    @staticmethod
    def _chip(text):
        button = QPushButton(text)
        button.setObjectName("ChipButton")
        button.setAutoDefault(False)
        return button

    def _date_edit(self):
        control = ThemedDateEdit()
        control.setCalendarPopup(True)
        control.setDisplayFormat("dd/MM/yyyy")
        control.setDate(QDate.currentDate())
        control.setMinimumWidth(140)
        return control

    def _build_totals(self):
        layout = QHBoxLayout()
        layout.setSpacing(14)
        self.total_labels: list[QLabel] = []
        self.scope_label = label("", "Muted")
        self.scope_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.scope_label.setWordWrap(True)
        for title, eyebrow, caption in (
            ("SALES", "EyebrowSale", self.scope_label),
            ("RETURNS", "EyebrowReturn", label("not subtracted from sales", "Muted")),
        ):
            frame = card(title.title())
            contents = QHBoxLayout(frame)
            contents.setContentsMargins(16, 8, 16, 8)
            contents.setSpacing(16)
            heading = QVBoxLayout()
            heading.setSpacing(2)
            heading.addWidget(label(title, eyebrow))
            heading.addWidget(caption)
            contents.addLayout(heading, 3)
            for name in ("Net", "Fine"):
                cell = QVBoxLayout()
                cell.setSpacing(0)
                cell.addWidget(label(name, "Muted"))
                value = label("—", "MetricValue")
                cell.addWidget(value)
                contents.addLayout(cell, 1)
                self.total_labels.append(value)
            layout.addWidget(frame, 1)
        self.total_labels[1].setProperty("accent", True)
        return layout

    def _build_table_card(self):
        frame = card("Report table")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addLayout(self._build_navigation())
        self.table = QTableView()
        self.table.setObjectName("ScreenTable")
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.model = SalesReportTableModel(self.table)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        polish_dense_table(
            self.table, row_height=32, show_grid=False, hide_vertical_header=True
        )
        self.table.horizontalHeader().setFixedHeight(
            self.table.horizontalHeader().fontMetrics().height() * 2 + 14
        )
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._bars = WeightBarDelegate(
            lambda row: self.model.weight_at(row, 1), self.table
        )
        self._weights = WeightBarDelegate(parent=self.table)
        self._empty_state = EmptyStatePanel(
            self.table, "", "No sales or returns in this selection."
        )
        self._clear_code_button = self._empty_state.add_action(
            "Clear item code", self._clear_item_code
        )
        self._month_action = self._empty_state.add_action(
            "This month", lambda: self._set_range(True)
        )
        self._empty_state.set_actions_visible(False)
        self.table.doubleClicked.connect(self._activate_selected)
        self.table.selectionModel().selectionChanged.connect(self._update_actions)
        self.table.installEventFilter(self)
        # The table takes nearly all spare height until it reaches its rows'
        # height; then the spacer under the totals takes the rest.
        layout.addWidget(self.table, 100)
        # The totals row follows the last row like a subtotal; the spacer
        # below it takes the spare height while the rows are few.
        self.totals_footer = TableTotalsFooter(self.table, frame)
        layout.addWidget(self.totals_footer)
        self._table_card_layout = layout
        layout.addStretch(0)
        self._table_spacer = layout.count() - 1
        hint = QHBoxLayout()
        hint.setContentsMargins(16, 5, 16, 6)
        self.status_label = label("Select a period to view its items.", "Muted")
        self.status_label.setWordWrap(True)
        hint.addWidget(self.status_label, 1)
        layout.addLayout(hint)
        return frame

    def _build_navigation(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(14)
        self.view_switch = QFrame()
        self.view_switch.setObjectName("SegmentGroup")
        switch = QHBoxLayout(self.view_switch)
        switch.setContentsMargins(3, 3, 3, 3)
        switch.setSpacing(2)
        self._view_buttons = QButtonGroup(self)
        self.by_period_button = QPushButton("By period")
        self.all_items_button = QPushButton("All items")
        for button in (self.by_period_button, self.all_items_button):
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setAutoDefault(False)
            self._view_buttons.addButton(button)
            switch.addWidget(button)
        self.by_period_button.setChecked(True)
        layout.addWidget(self.view_switch)
        self.breadcrumb = QLabel()
        self.breadcrumb.setObjectName("SalesBreadcrumb")
        self.breadcrumb.setTextFormat(Qt.TextFormat.RichText)
        self.breadcrumb.linkActivated.connect(self._crumb)
        self.breadcrumb.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        layout.addWidget(self.breadcrumb, 1)
        self.back_button = KeyHintButton("Back", "Backspace")
        self.open_button = KeyHintButton("View items", "Enter")
        self.open_button.setObjectName("SalesPrimary")
        for button in (self.back_button, self.open_button):
            button.setAutoDefault(False)
            layout.addWidget(button)
        self.back_button.clicked.connect(self._go_back)
        self.by_period_button.clicked.connect(self._by_period)
        self.all_items_button.clicked.connect(self._all_items)
        self.open_button.clicked.connect(self._activate_selected)
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
        self.breadcrumb.setText("")
        self.status_label.setText(
            "Filters changed. Select View report (F5) to update the results."
        )
        self._show_empty("Filters changed", "Select View report (F5) to apply them.")
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
            self._show_empty("", "Loading sales report…")
        except Exception as exc:
            self._loading = False
            self.status_label.setText(str(exc))
            self._show_empty("Check the dates", str(exc))
        self._update_actions()

    def _clear_result(self):
        self.model.set_report(self._level, ())
        self._set_totals(None)
        self.totals_footer.clear()
        self._fit_table()

    def _show_empty(self, title: str, body: str, *, actions: bool = False):
        self._empty_state.set_title(title)
        self._empty_state.setText(body)
        self._empty_state.set_actions_visible(actions)
        self._clear_code_button.setVisible(actions and bool(self.item_search.text()))

    def _update_scope(self, query):
        dates = (
            f"{format_display_date(query.date_from)} to "
            f"{format_display_date(query.date_to)}"
        )
        scope = (
            f"item code contains {query.item_search}"
            if query.item_search
            else "all items"
        )
        self.scope_label.setText(f"{dates} · {scope}")
        root = (
            f"{self.grouping.currentText()}-wise totals"
            if self._level == "period" or self._period
            else "All items"
        )
        crumbs = [("period" if self._period or self._level != "period" else "", root)]
        if self._period:
            crumbs.append(
                (
                    "item" if self._level == "voucher" else "",
                    format_period(self._period),
                )
            )
        if self._item_code is not None:
            name = f" · {self._item_name}" if self._item_name else ""
            crumbs.append(("", f"{self._item_code or '(No item code)'}{name}"))
        if self._level == "voucher" and not self._period:
            crumbs[0] = ("item", root)
        self._crumbs = crumbs

    def _render_breadcrumb(self, suffix: str = ""):
        parts = []
        for index, (target, text) in enumerate(self._crumbs):
            last = index == len(self._crumbs) - 1
            text = escape(text)
            if target and not last:
                parts.append(f'<a href="{target}">{text}</a>')
            else:
                parts.append(f"<b>{text}</b>")
        html = ' <span style="color:#94a3b8">›</span> '.join(parts)
        if suffix:
            html += f' <span style="color:#526176">· {escape(suffix)}</span>'
        self.breadcrumb.setText(html)

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
        self._show_table_totals(result.totals)
        self._fit_table()
        self._apply_weight_bars()
        self._show_no_results()
        instructions = {
            "period": "Enter or double-click a row to see its items. "
            "Click a column heading to sort.",
            "item": "Enter or double-click an item to see its vouchers.",
            "voucher": "Weights are for the selected item's lines only. "
            "Enter opens the estimate, asking first about unsaved changes.",
        }
        count = len(result.rows)
        nouns = {"period": "periods", "item": "items", "voucher": "vouchers"}
        if self._level == "period":
            noun = "days" if self.grouping.currentData() == "day" else "months"
        else:
            noun = nouns[self._level]
        self._render_breadcrumb(
            f"{count} {noun} with sales or returns" if count else "no matches"
        )
        self.status_label.setText(
            instructions[self._level]
            if count
            else "No sales or returns match the selected dates and item code."
        )
        if count:
            self.table.selectRow(0)
        self._update_actions()

    def _show_no_results(self):
        code = self.item_search.text().strip()
        dates = (
            f"{format_display_date(self.date_from.date().toString('yyyy-MM-dd'))} and "
            f"{format_display_date(self.date_to.date().toString('yyyy-MM-dd'))}"
        )
        if code:
            self._show_empty(
                f"No sales or returns for item code “{code}”",
                f"Nothing between {dates} has an item code containing {code}. "
                "Check the code or widen the dates.",
                actions=True,
            )
        else:
            self._show_empty(
                "No sales or returns",
                f"No saved estimates between {dates}. Try a wider date range.",
                actions=True,
            )

    def _fit_table(self):
        """Shrink the table to its rows so the totals sit right under them."""
        layout = self._table_card_layout
        spacer = self._table_spacer
        rows = self.model.rowCount()
        self.totals_footer.setVisible(rows > 0)
        if not rows:
            self.table.setMaximumHeight(_UNLIMITED_HEIGHT)
            layout.setStretch(spacer, 0)
            return
        height = (
            self.table.horizontalHeader().height()
            + rows * self.table.verticalHeader().defaultSectionSize()
            + 2 * self.table.frameWidth()
        )
        if self.table.horizontalScrollBar().isVisible():
            height += self.table.horizontalScrollBar().height()
        self.table.setMaximumHeight(height)
        layout.setStretch(spacer, 1)

    def _show_table_totals(self, totals: SalesWeights):
        if not self.model.rowCount():
            self.totals_footer.clear()
            self._fit_table()
            return
        offset = self.model.weight_offset
        self.totals_footer.set_values(
            {
                offset + index: format_indian_number(value, 2)
                for index, value in enumerate(totals.values())
            }
        )

    def _apply_weight_bars(self):
        offset = self.model.weight_offset
        for index in range(self.model.columnCount()):
            delegate = None
            if index >= offset:
                delegate = self._bars if index == offset + 1 else self._weights
            self.table.setItemDelegateForColumn(index, delegate)
        self._bars.set_maximum(
            max(
                (self.model.weight_at(row, 1) for row in range(self.model.rowCount())),
                default=0,
            )
        )

    def _failed(self, generation: int, error: object):
        if self._closed or generation != self._load_runner.generation:
            return
        self._loading = False
        self._clear_result()
        self.status_label.setText(
            f"Could not load sales report: {error}. Select View report to retry."
        )
        self._show_empty("Report unavailable", "Select View report (F5) to retry.")
        self._update_actions()

    def _set_totals(self, totals: SalesWeights | None):
        values = totals.values() if totals is not None else (None,) * 4
        for widget, value in zip(self.total_labels, values, strict=True):
            widget.setText(
                "—" if value is None else f"{format_indian_number(value, 2)} g"
            )

    def _update_actions(self, *_):
        self.back_button.setVisible(self._level != "period")
        self.back_button.setToolTip(
            "Back to items" if self._level == "voucher" else "Back to periods"
        )
        self.open_button.setText(
            {
                "period": "View items",
                "item": "View vouchers",
                "voucher": "Open estimate",
            }[self._level]
        )
        all_items = self._level != "period" and self._period is None
        (self.all_items_button if all_items else self.by_period_button).setChecked(True)
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
            self._item_name = row.detail
        self.refresh()

    def _all_items(self):
        self._level, self._period, self._item_code = "item", None, None
        self.refresh()

    def _by_period(self):
        self._level, self._period, self._item_code = "period", None, None
        self.refresh()

    def _crumb(self, target: str):
        if self._loading:
            return
        if target == "period":
            self._by_period()
        elif target == "item":
            self._level, self._item_code = "item", None
            self.refresh()

    def _clear_item_code(self):
        self.item_search.clear()
        self.refresh()
        self.item_search.setFocus()

    def eventFilter(self, watched, event):
        if (
            watched is self.table
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._activate_selected()
                return True
            if event.key() == Qt.Key.Key_Backspace and self._level != "period":
                self._go_back()
                return True
        return super().eventFilter(watched, event)

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
