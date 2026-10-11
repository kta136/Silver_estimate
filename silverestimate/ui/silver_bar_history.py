"""One keyboard-driven browser for saved lists, issued lists, and silver bars."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, cast

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QAction, QKeyEvent, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QSizePolicy,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.numeric_policy import fixed_decimal
from silverestimate.domain.pagination import Page, SilverBarHistoryCursor
from silverestimate.domain.silver_bar_workspace import BarListSnapshot
from silverestimate.infrastructure.latest_request_runner import LatestRequestRunner
from silverestimate.infrastructure.paged_load_state import PagedLoadState
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)

from .display_formatting import count_label, format_display_date
from .message_dialogs import ask
from .models.silver_bar_entry_model import SilverBarEntryModel
from .models.silver_bar_history_models import (
    SilverBarHistoryModel,
    SilverBarListsHistoryModel,
)
from .modern_components import install_table_empty_state, polish_dense_table
from .preview_build_worker import PreviewBuildController
from .print_manager import PrintManager
from .screen_widgets import (
    SCREEN_QSS,
    KeyHintButton,
    OptionGroup,
    StatusPill,
    StatusPillDelegate,
    TotalsStrip,
    card,
    label,
)
from .shared_screen_theme import build_management_screen_stylesheet
from .window_sizing import resize_to_available_screen

# Below this width the results and the selected list take turns on screen.
COMPACT_HISTORY_WIDTH = 1000
DETAIL_PANEL_WIDTH = 480

_PILL_STATES = {
    "Active": "active",
    "In active list": "active",
    "Issued": "issued",
    "Available": "available",
}

_HISTORY_QSS = """
QPushButton#HistoryButton, QPushButton#HistoryPrimary { padding: 5px 12px; min-height: 24px; }
QLineEdit { min-height: 24px; }
QLabel[error="true"] { color: __TEXT_STRONG__; background: __DANGER_BG__; }
"""


@dataclass(frozen=True)
class _BarsHistoryRequest:
    connection_factory: Callable[[threading.Event | None], Any]
    voucher_term: str
    weight_text: str
    status_text: str
    cursor: SilverBarHistoryCursor | None
    append: bool


def _load_bars_history_page(
    request: _BarsHistoryRequest, cancel_event: threading.Event
):
    repo = SilverBarsSnapshotRepository(
        request.connection_factory, cancel_event=cancel_event
    )
    return request, repo.search_history_bars_page(
        voucher_term=request.voucher_term,
        weight_text=request.weight_text,
        status_text=request.status_text,
        cursor=request.cursor,
        include_total=not request.append,
        limit=1000,
    )


@dataclass(frozen=True)
class _ListsHistoryRequest:
    factory: Callable
    search_term: str
    state: str
    cursor: int | None
    append: bool


def _load_lists_history_page(request: _ListsHistoryRequest, cancel: threading.Event):
    repo = SilverBarsSnapshotRepository(request.factory, cancel_event=cancel)
    return request, repo.get_list_history_page(
        search_term=request.search_term,
        state=request.state,
        cursor=request.cursor,
        include_total=not request.append,
    )


def _load_details(request: tuple[Callable, int], cancel: threading.Event):
    factory, list_id = request
    return SilverBarsSnapshotRepository(factory, cancel_event=cancel).get_list_snapshot(
        list_id
    )


class SilverBarHistoryDialog(QDialog):
    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.selected_list_id: int | None = None
        self.snapshot: BarListSnapshot | None = None
        self._closed = False
        self._busy = False
        self._loading = [False, False]
        self._detail_intent = "view"
        self._lists_page_state = PagedLoadState[dict[str, Any], int]()
        self._bars_page_state = PagedLoadState[dict[str, Any], SilverBarHistoryCursor]()
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self.refresh)
        self._lists_load_runner = LatestRequestRunner(
            _load_lists_history_page, self, name="bar-list-history"
        )
        self._bars_load_runner = LatestRequestRunner(
            _load_bars_history_page, self, name="silver-bar-history-loader"
        )
        self._detail_runner = LatestRequestRunner(
            _load_details, self, name="bar-history-details"
        )
        self._lists_load_runner.result.connect(self._lists_ready)
        self._bars_load_runner.result.connect(self._bars_ready)
        self._detail_runner.result.connect(self._details_ready)
        self._lists_load_runner.failed.connect(
            lambda _, error: self._load_error(0, error)
        )
        self._bars_load_runner.failed.connect(
            lambda _, error: self._load_error(1, error)
        )
        self._detail_runner.failed.connect(self._details_error)
        self._preview_builder = PreviewBuildController(
            self, message="Preparing list for printing…"
        )
        self.init_ui()
        self.refresh()
        QTimer.singleShot(0, self.focus_search)

    def init_ui(self):
        self.setWindowTitle("Silver Bar History")
        self.setObjectName("SilverBarHistoryDialog")
        self.setMinimumSize(760, 520)
        resize_to_available_screen(self, preferred_width=1120, preferred_height=760)
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#SilverBarHistoryDialog",
                card_names=[],
                title_label="HistoryTitle",
                subtitle_label="HistoryHint",
                primary_button="HistoryPrimary",
                secondary_button="HistoryButton",
                input_selectors=["QLineEdit"],
                include_table=True,
                extra_rules=SCREEN_QSS + _HISTORY_QSS,
            )
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_filter_bar())
        body = QHBoxLayout()
        body.setContentsMargins(16, 10, 16, 12)
        body.setSpacing(12)
        body.addWidget(self._build_results(), 1)
        self.detail_panel = card("Selected list")
        self.detail_panel.setMinimumWidth(360)
        self.detail_panel.setMaximumWidth(DETAIL_PANEL_WIDTH)
        panel_layout = QVBoxLayout(self.detail_panel)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget()
        panel_layout.addWidget(self.pages)
        body.addWidget(self.detail_panel, 1)
        root.addLayout(body, 1)
        self.pages.addWidget(self._build_placeholder())
        self._build_details()
        self.pages.currentChanged.connect(self._arrange_panels)
        self.view_combo.currentIndexChanged.connect(self._switch_view)
        for sequence, callback in (
            ("Ctrl+1", lambda: self._select_view(0)),
            ("Ctrl+2", lambda: self._select_view(1)),
            ("Ctrl+F", self.focus_search),
            ("F5", self.refresh),
            ("Ctrl+P", self.print_list),
            ("Ctrl+Shift+P", lambda: self.print_list(preview=True)),
            ("Ctrl+R", self.reactivate_list),
            ("Alt+Left", self.back_to_results),
            ("Ctrl+C", self.copy_rows),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(sequence))
            action.setAutoRepeat(False)
            action.triggered.connect(lambda _=False, cb=callback: self._shortcut(cb))
            self.addAction(action)
        self._arrange_panels()
        self._update_actions()

    def _build_header(self):
        header = QFrame(self)
        header.setObjectName("ScreenHeaderBar")
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(14)
        row.addWidget(label("History", "ScreenTitle"))
        self.view_combo = OptionGroup("segmented")
        self.view_combo.addItem("Lists", key_hint="Ctrl+1")
        self.view_combo.addItem("Bars", key_hint="Ctrl+2")
        self.view_combo.setAccessibleName("History view")
        self.view_combo.setToolTip("Lists: Ctrl+1 · Bars: Ctrl+2")
        row.addWidget(self.view_combo)
        row.addStretch(1)
        self.refresh_button = self._button("Refresh", self.refresh, "Refresh", "F5")
        row.addWidget(self.refresh_button)
        self.close_button = self._button(
            "Back to List", self._close_history, "Close history", "Esc"
        )
        row.addWidget(self.close_button)
        return header

    def _build_filter_bar(self):
        bar = QWidget(self)
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 12, 16, 0)
        row.setSpacing(10)
        self.filters = QStackedWidget()
        row.addWidget(self.filters, 1)
        self._build_filters()
        self.clear_button = self._button("Clear Filters", self.clear_filters)
        self.clear_button.setObjectName("LinkButton")
        row.addWidget(self.clear_button)
        return bar

    def _build_filters(self):
        lists = QWidget()
        row = self._filter_row(lists)
        self.list_search_edit = QLineEdit()
        self.list_search_edit.setPlaceholderText("Search list number or note · Ctrl+F")
        self.list_search_edit.setAccessibleName("Search saved lists")
        self.list_search_edit.setMinimumWidth(300)
        self.list_search_edit.setMaximumWidth(460)
        row.addWidget(self.list_search_edit, 2)
        self.list_state_combo = OptionGroup("chips")
        self.list_state_combo.addItems(["All", "Active", "Issued"])
        self.list_state_combo.setAccessibleName("List state")
        row.addWidget(self.list_state_combo)
        row.addStretch(1)
        self.filters.addWidget(lists)
        bars = QWidget()
        rows = QVBoxLayout(bars)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(8)
        row = QHBoxLayout()
        row.setSpacing(10)
        self._status_rows = (row, QHBoxLayout())
        rows.addLayout(row)
        rows.addLayout(self._status_rows[1])
        self._status_rows[1].addStretch(1)
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setPlaceholderText("Voucher or note · Ctrl+F")
        self.voucher_edit.setAccessibleName("Search bar voucher or note")
        self.voucher_edit.setMinimumWidth(200)
        self.voucher_edit.setMaximumWidth(360)
        row.addWidget(self.voucher_edit, 2)
        self.weight_edit = QLineEdit()
        self.weight_edit.setPlaceholderText("Weight (g)")
        self.weight_edit.setAccessibleName("Filter bar weight in grams")
        self.weight_edit.setMaximumWidth(110)
        row.addWidget(self.weight_edit)
        self.status_combo = OptionGroup("chips")
        for text, value in (
            ("All bars", "All Statuses"),
            ("Available", "In Stock"),
            ("In active list", "Assigned"),
            ("Issued", "Issued"),
            ("Sold", "Sold"),
        ):
            self.status_combo.addItem(text, value)
        self.status_combo.setAccessibleName("Bar status")
        row.addWidget(self.status_combo)
        row.addStretch(1)
        self.filters.addWidget(bars)
        for edit in (self.list_search_edit, self.voucher_edit, self.weight_edit):
            edit.textChanged.connect(self._schedule_search)
            edit.installEventFilter(self)
        self.list_state_combo.currentIndexChanged.connect(self._schedule_search)
        self.status_combo.currentIndexChanged.connect(self._schedule_search)

    @staticmethod
    def _filter_row(widget):
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        return row

    def _build_results(self):
        results = card("Results")
        self.results_card = results
        layout = self._layout(results)
        layout.setSpacing(0)
        self.tables = QStackedWidget()
        self.lists_model = SilverBarListsHistoryModel(self)
        self.bars_model = SilverBarHistoryModel(self)
        self.lists_table = self._table(
            self.lists_model,
            "No lists match your search.",
            {0: 132, 2: 96, 3: 48, 4: 82, 5: 82, 6: 92, 7: 92},
            stretch=1,
        )
        header = self.lists_table.horizontalHeader()
        header.setResizeContentsPrecision(50)
        for column in (0, 6, 7):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.lists_table.setItemDelegateForColumn(
            2, StatusPillDelegate(_PILL_STATES, self.lists_table)
        )
        self.bars_table = self._table(
            self.bars_model,
            "No bars match your search.",
            {0: 60, 2: 92, 3: 92, 4: 88, 5: 130, 6: 132, 7: 96},
            stretch=1,
        )
        self.bars_table.setItemDelegateForColumn(
            5, StatusPillDelegate(_PILL_STATES, self.bars_table)
        )
        for table in (self.lists_table, self.bars_table):
            self.tables.addWidget(table)
            table.selectionModel().selectionChanged.connect(self._update_actions)
            table.doubleClicked.connect(self.open_selected_list)
        layout.addWidget(self.tables, 1)
        footer = QHBoxLayout()
        footer.setContentsMargins(14, 6, 10, 8)
        footer.setSpacing(8)
        self.status_label = label("", "Muted")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.load_more_button = self._button(
            "Load More", self.load_more, "Down on the last row also loads more"
        )
        footer.addWidget(self.load_more_button)
        self.open_button = self._button(
            "Open", self.open_selected_list, "Open selected list", "Enter"
        )
        footer.addWidget(self.open_button)
        layout.addLayout(footer)
        return results

    def _build_placeholder(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.addStretch(1)
        title = label("Pick a list to see it here", "EmptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        body = label(
            "Press Enter on an issued list to see its bars, reprint it, or "
            "reopen it. Active lists open in the workspace for editing.",
            "EmptyStateBody",
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _build_details(self):
        detail = QWidget()
        layout = self._layout(detail)
        layout.setSpacing(0)
        head = QVBoxLayout()
        head.setContentsMargins(16, 12, 12, 12)
        head.setSpacing(4)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.detail_title = label("", "CardTitle")
        title_row.addWidget(self.detail_title)
        self.detail_pill = StatusPill(detail)
        title_row.addWidget(self.detail_pill)
        title_row.addStretch(1)
        self.back_button = self._button(
            "Close", self.back_to_results, "Back to results · Esc / Alt+Left", "Esc"
        )
        self.back_button.setObjectName("LinkButton")
        title_row.addWidget(self.back_button)
        head.addLayout(title_row)
        self.detail_note = label()
        self.detail_note.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        head.addWidget(self.detail_note)
        self.detail_dates = label("", "Muted")
        head.addWidget(self.detail_dates)
        layout.addLayout(head)
        self.list_totals_label = TotalsStrip(
            ("Bars", "Weight", "Fine"), accent_last=False
        )
        self.list_totals_label.setProperty("flat", True)
        layout.addWidget(self.list_totals_label)
        self.list_bars_model = SilverBarEntryModel(self)
        self.list_bars_table = self._table(
            self.list_bars_model,
            "Loading list…",
            {0: 88, 1: 76, 2: 80, 4: 52},
            stretch=3,
        )
        layout.addWidget(self.list_bars_table, 1)
        status_row = QHBoxLayout()
        status_row.setContentsMargins(16, 6, 12, 0)
        self.detail_status = label("", "Muted")
        self.detail_status.setWordWrap(True)
        status_row.addWidget(self.detail_status, 1)
        self.detail_more_button = self._button("Load More", self.load_more_details)
        status_row.addWidget(self.detail_more_button)
        layout.addLayout(status_row)
        actions = QHBoxLayout()
        actions.setContentsMargins(16, 8, 12, 12)
        actions.setSpacing(8)
        self.reprint_button = self._button(
            "Reprint", self.print_list, "Reprint", "Ctrl+P"
        )
        self.reprint_button.setObjectName("HistoryPrimary")
        self.preview_button = self._button(
            "Preview",
            lambda: self.print_list(preview=True),
            "Preview / PDF / printer settings · Ctrl+Shift+P",
        )
        self.reactivate_button = self._button(
            "Reopen for Editing", self.reactivate_list, "Reopen list", "Ctrl+R"
        )
        actions.addWidget(self.reprint_button)
        actions.addWidget(self.preview_button)
        actions.addStretch(1)
        actions.addWidget(self.reactivate_button)
        layout.addLayout(actions)
        self.pages.addWidget(detail)

    def _arrange_panels(self, *_):
        wide = self.width() >= COMPACT_HISTORY_WIDTH
        # Narrow windows give the bar status chips a row of their own.
        target, source = self._status_rows if wide else self._status_rows[::-1]
        if target.indexOf(self.status_combo) < 0:
            source.removeWidget(self.status_combo)
            target.insertWidget(2 if wide else 0, self.status_combo)
        for page in range(self.filters.count()):
            shown = page == self.filters.currentIndex()
            policy = (
                QSizePolicy.Policy.Preferred if shown else QSizePolicy.Policy.Ignored
            )
            self.filters.widget(page).setSizePolicy(policy, policy)
        self.filters.updateGeometry()
        showing_detail = self.pages.currentIndex() == 1
        self.detail_panel.setVisible(
            showing_detail or (wide and self.view_combo.currentIndex() == 0)
        )
        self.results_card.setVisible(wide or not showing_detail)
        # Beside the panel, weight and created date give way to the note.
        crowded = self.detail_panel.isVisibleTo(self) and self.width() < 1400
        for column in (4, 6):
            self.lists_table.setColumnHidden(column, crowded)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._arrange_panels()

    def _close_history(self):
        if not self._busy:
            self.done(QDialog.DialogCode.Rejected)

    @staticmethod
    def _layout(widget):
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        return layout

    def _button(self, text, callback, tooltip="", key_hint=""):
        button = KeyHintButton(text, key_hint, self)
        button.setObjectName("HistoryButton")
        button.setAutoDefault(False)
        button.setToolTip(tooltip)
        button.clicked.connect(lambda _=False: callback())
        return button

    def _table(self, model, empty, widths, *, stretch):
        table = QTableView(self)
        table.setObjectName("ScreenTable")
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        table.setSortingEnabled(True)
        table.horizontalHeader().setToolTip(
            "Sort loaded rows; filters search all records."
        )
        for column, width in widths.items():
            table.setColumnWidth(column, width)
        table.horizontalHeader().setSectionResizeMode(
            stretch, QHeaderView.ResizeMode.Stretch
        )
        table.installEventFilter(self)
        polish_dense_table(
            table,
            row_height=32,
            header_height=32,
            show_grid=False,
            hide_vertical_header=True,
        )
        install_table_empty_state(table, empty)
        return table

    def _shortcut(self, callback):
        if QApplication.activeModalWidget() in (None, self):
            callback()

    def _message(self, text: str, *, error=False):
        label = self.detail_status if self.pages.currentIndex() else self.status_label
        label.setText(text)
        label.setToolTip(text)
        label.setProperty("error", error)
        label.style().unpolish(label)
        label.style().polish(label)

    def _select_view(self, index):
        if not self._busy:
            self.view_combo.setCurrentIndex(index)

    def _switch_view(self, index):
        if self._busy:
            return
        self.back_to_results()
        self.filters.setCurrentIndex(index)
        self.tables.setCurrentIndex(index)
        self._arrange_panels()
        self.refresh()
        self.focus_search()

    def focus_search(self):
        if self._busy:
            return
        self.back_to_results()
        edit = (
            self.list_search_edit
            if self.view_combo.currentIndex() == 0
            else self.voucher_edit
        )
        edit.setFocus()
        edit.selectAll()

    def _schedule_search(self, *_):
        self._lists_load_runner.cancel()
        self._bars_load_runner.cancel()
        index = self.view_combo.currentIndex()
        self._loading[index] = True
        self._search_timer.start()
        self._update_actions()

    def refresh(self):
        if self._busy:
            return
        self._search_timer.stop()
        if self.pages.currentIndex() and self.snapshot:
            self._read_details(self.snapshot.list_id, "view")
        elif self.view_combo.currentIndex() == 0:
            self.load_lists()
        else:
            self.load_all_bars()

    def load_lists(self, *, append=False):
        if not append:
            self._lists_page_state.reset()
            self.lists_model.clear_rows()
        self._loading[0] = True
        self._message("Loading lists…")
        self._lists_load_runner.submit(
            _ListsHistoryRequest(
                self.db_manager.open_read_connection,
                self.list_search_edit.text().strip(),
                self.list_state_combo.currentText(),
                self._lists_page_state.cursor,
                append,
            )
        )
        self._update_actions()

    def load_all_bars(self, *, append=False):
        if not append:
            self._bars_page_state.reset()
            self.bars_model.clear_rows()
        self._loading[1] = True
        self._message("Loading bars…")
        self._bars_load_runner.submit(
            _BarsHistoryRequest(
                self.db_manager.open_read_connection,
                self.voucher_edit.text().strip(),
                self.weight_edit.text().strip(),
                self.status_combo.currentData(),
                self._bars_page_state.cursor,
                append,
            )
        )
        self._update_actions()

    def _apply_page(self, index, request, page):
        state = self._lists_page_state if index == 0 else self._bars_page_state
        model = self.lists_model if index == 0 else self.bars_model
        table = self.lists_table if index == 0 else self.bars_table
        normalized = Page(
            page.items,
            page.total if page.total is not None else state.total,
            page.next_cursor,
        )
        state.apply(normalized, append=request.append)
        if request.append:
            model.append_rows(state.last_page_rows, total_count=state.total)
        else:
            model.set_rows(state.last_page_rows, total_count=state.total)
            if model.rowCount():
                table.selectRow(0)
        self._loading[index] = False
        if index == self.view_combo.currentIndex():
            noun = "lists" if index == 0 else "bars"
            self._message(
                f"{state.loaded} of {state.total} {noun} · Enter open · Ctrl+P reprint"
                + (" · Narrow filters to see more" if state.limit_reached else "")
            )
        self._update_actions()

    def _lists_ready(self, _, value):
        request, page = value
        self._apply_page(0, request, page)

    def _bars_ready(self, _, value):
        request, page = value
        self._apply_page(1, request, page)

    def _load_error(self, index, error):
        self._loading[index] = False
        self._message(f"Could not load records: {error}. F5 retries.", error=True)
        self._update_actions()

    def load_more(self):
        index = self.view_combo.currentIndex()
        state = self._lists_page_state if index == 0 else self._bars_page_state
        if not self._loading[index] and state.has_more:
            (self.load_lists if index == 0 else self.load_all_bars)(append=True)

    def clear_filters(self):
        controls = (
            (self.list_search_edit, self.list_state_combo)
            if self.view_combo.currentIndex() == 0
            else (self.voucher_edit, self.weight_edit, self.status_combo)
        )
        for control in controls:
            control.blockSignals(True)
            if isinstance(control, QLineEdit):
                control.clear()
            else:
                control.setCurrentIndex(0)
            control.blockSignals(False)
        self._update_actions()
        self.refresh()
        self.focus_search()

    def _filters_active(self) -> bool:
        if self.view_combo.currentIndex() == 0:
            return bool(
                self.list_search_edit.text().strip()
                or self.list_state_combo.currentIndex()
            )
        return bool(
            self.voucher_edit.text().strip()
            or self.weight_edit.text().strip()
            or self.status_combo.currentIndex()
        )

    def _selected_list_id(self):
        table = self.tables.currentWidget()
        rows = table.selectionModel().selectedRows()
        payload = table.model().row_payload(rows[0].row()) if rows else None
        return int(payload["list_id"]) if payload and payload.get("list_id") else None

    def _update_actions(self, *_):
        self.view_combo.setEnabled(not self._busy)
        self.clear_button.setVisible(self._filters_active())
        index = self.view_combo.currentIndex()
        state = self._lists_page_state if index == 0 else self._bars_page_state
        self.open_button.setEnabled(
            not self._loading[index] and self._selected_list_id() is not None
        )
        self.load_more_button.setVisible(state.has_more)
        self.load_more_button.setEnabled(not self._loading[index])
        loaded = self.snapshot is not None and not self._busy
        self.reactivate_button.setEnabled(loaded)
        issued = bool(self.snapshot and self.snapshot.issued)
        self.reactivate_button.setText("Reopen for Editing" if issued else "Edit List")
        self.reprint_button.setEnabled(
            loaded and issued and bool(self.snapshot.bars if self.snapshot else ())
        )
        self.preview_button.setEnabled(loaded and issued)
        self.detail_more_button.setVisible(
            bool(
                self.snapshot
                and self.list_bars_model.rowCount() < len(self.snapshot.bars)
            )
        )

    def open_selected_list(self, *_):
        if self._busy or self._loading[self.view_combo.currentIndex()]:
            return
        list_id = self._selected_list_id()
        if list_id is not None:
            self._read_details(list_id, "open")

    def _read_details(self, list_id: int, intent: str):
        self._detail_intent = intent
        self.snapshot = None
        self.list_bars_model.clear_rows()
        self.detail_title.setText("Opening list…")
        self.detail_pill.hide()
        self.detail_note.clear()
        self.detail_dates.clear()
        self.list_totals_label.set_values(("", "", ""), empty=True)
        self.pages.setCurrentIndex(1)
        self._message("Loading all list contents…")
        self._update_actions()
        self._detail_runner.submit((self.db_manager.open_read_connection, list_id))

    def _details_ready(self, _, value):
        snapshot = cast(BarListSnapshot, value)
        if not snapshot.issued and self._detail_intent == "open":
            self._choose_for_editing(snapshot.list_id)
            return
        self.snapshot = snapshot
        self._show_snapshot_header(snapshot)
        self.list_bars_model.set_rows(
            list(snapshot.bars[:1500]), total_count=len(snapshot.bars)
        )
        weight = f"{fixed_decimal(snapshot.weight, 2)} g"
        fine = f"{fixed_decimal(snapshot.fine_weight, 2)} g"
        self.list_totals_label.set_values(
            (str(len(snapshot.bars)), weight, fine),
            summary=(
                f"{count_label(len(snapshot.bars), 'bar')} · Weight {weight} · "
                f"Fine {fine}"
            ),
        )
        self._message(
            "Read only · Ctrl+P Reprint · Ctrl+R Reopen"
            if snapshot.issued
            else "Active list · Ctrl+R Edit"
        )
        self._update_actions()
        self._restore_detail_focus()
        if snapshot.bars:
            self.list_bars_table.selectRow(0)
        if self._detail_intent in ("print", "preview"):
            self.print_list(preview=self._detail_intent == "preview")

    def _show_snapshot_header(self, snapshot: BarListSnapshot):
        details = snapshot.details
        self.detail_title.setText(str(details["list_identifier"]))
        self.detail_pill.set_state(
            "issued" if snapshot.issued else "active",
            "Issued" if snapshot.issued else "Active",
        )
        self.detail_pill.show()
        note = str(details.get("list_note") or "No note")
        self.detail_note.setText(note)
        self.detail_note.setToolTip(note)
        dates = []
        if created := format_display_date(details.get("creation_date")):
            dates.append(f"Created {created}")
        if issued := format_display_date(details.get("issued_date")):
            dates.append(f"Issued {issued}")
        self.detail_dates.setText(" · ".join(dates))

    def _details_error(self, _, error):
        self._message(
            f"Could not open list: {error}. Return to results and retry.", error=True
        )

    def load_more_details(self):
        if self.snapshot:
            shown = self.list_bars_model.rowCount()
            self.list_bars_model.append_rows(
                list(self.snapshot.bars[shown : shown + 1500]),
                total_count=len(self.snapshot.bars),
            )
            self._update_actions()

    def back_to_results(self):
        if self._busy:
            return
        self._detail_runner.cancel()
        self.pages.setCurrentIndex(0)
        self.snapshot = None
        self.tables.currentWidget().setFocus()

    def _choose_for_editing(self, list_id):
        self.selected_list_id = list_id
        self.done(QDialog.DialogCode.Accepted)

    def reactivate_list(self):
        if self._busy or self.snapshot is None:
            return
        snapshot = self.snapshot
        if snapshot.issued:
            if not ask(
                self,
                title="Reopen Issued List",
                heading=(f"Reopen {snapshot.details['list_identifier']} for editing?"),
                detail=(
                    "The bars stay in this list, and the list becomes active again."
                ),
                action_label="Reopen List",
                default_to_cancel=True,
            ):
                return
            if not self.db_manager.reactivate_silver_bar_list(snapshot.list_id):
                self._message(
                    "Could not reopen this list. Refresh and try again.", error=True
                )
                return
        self._choose_for_editing(snapshot.list_id)

    def print_list(self, *, preview=False):
        if self._busy:
            return
        if not self.pages.currentIndex():
            list_id = self._selected_list_id()
            if (
                list_id is not None
                and not self._loading[self.view_combo.currentIndex()]
            ):
                self._read_details(list_id, "preview" if preview else "print")
            return
        if not self.snapshot or not self.snapshot.issued:
            self._message("Open the active list for editing to print and issue it.")
            return
        snapshot = self.snapshot
        manager = PrintManager(self.db_manager)
        self._busy = True
        self._update_actions()
        self._preview_builder.start(
            lambda: manager.build_silver_bar_list_preview_payload(
                snapshot.details, snapshot.bars
            ),
            on_ready=lambda payload: self._print_ready(manager, payload, preview),
            on_error=self._print_error,
            empty_message="The list is empty.",
        )

    def _print_ready(self, manager, payload, preview):
        try:
            outcome = (
                manager.show_preview(payload, parent_widget=self)
                if preview
                else manager.quick_print(payload)
            )
            self._busy = False
            self._message(
                "List reprinted."
                if outcome.succeeded
                else outcome.message or "No print submitted.",
                error=not outcome.succeeded and not outcome.cancelled,
            )
        except Exception as exc:
            self._print_error(str(exc))
        self._update_actions()
        self._restore_detail_focus()
        QTimer.singleShot(0, self._restore_detail_focus)

    def _restore_detail_focus(self):
        if (
            not self._closed
            and self.isVisible()
            and not self._busy
            and QApplication.activeModalWidget() in (None, self)
        ):
            self.activateWindow()
            self.list_bars_table.setFocus()

    def _print_error(self, message):
        self._busy = False
        self._message(f"Printing failed: {message}", error=True)
        self._update_actions()
        self._restore_detail_focus()
        QTimer.singleShot(0, self._restore_detail_focus)

    def copy_rows(self):
        focus = QApplication.focusWidget()
        if isinstance(focus, QLineEdit):
            focus.copy()
            return
        table = (
            self.list_bars_table
            if self.pages.currentIndex()
            else self.tables.currentWidget()
        )
        self.copy_selected_rows(table)

    @staticmethod
    def _table_cell_text(table, row, column):
        return str(table.model().data(table.model().index(row, column)) or "")

    def copy_selected_rows(self, table):
        rows = [
            "\t".join(
                self._table_cell_text(table, index.row(), column)
                for column in range(table.model().columnCount())
            )
            for index in table.selectionModel().selectedRows()
        ]
        QApplication.clipboard().setText("\n".join(rows))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if (
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not event.isAutoRepeat()
            ):
                if watched is not self.list_bars_table:
                    self.open_selected_list()
                return True
            if event.key() == Qt.Key.Key_Down:
                if isinstance(watched, QLineEdit):
                    self.tables.currentWidget().setFocus()
                    return True
                if (
                    isinstance(watched, QTableView)
                    and watched.currentIndex().row() == watched.model().rowCount() - 1
                ):
                    self.load_more_details() if watched is self.list_bars_table else self.load_more()
        return super().eventFilter(watched, event)

    def accept(self):
        self.open_selected_list()

    def reject(self):
        if self.pages.currentIndex() and not self._busy:
            self.back_to_results()
        else:
            self.done(QDialog.DialogCode.Rejected)

    def _cancel_active_loads(self):
        self._search_timer.stop()
        self._lists_load_runner.shutdown()
        self._bars_load_runner.shutdown()
        self._detail_runner.shutdown()
        self._preview_builder.shutdown()

    def done(self, result):
        if not self._closed:
            self._closed = True
            self._cancel_active_loads()
        super().done(result)

    def closeEvent(self, event):
        self.done(QDialog.DialogCode.Rejected)
        event.accept()
