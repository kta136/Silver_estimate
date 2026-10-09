"""Two-pane workspace UI for keyboard-driven silver-bar entry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .models.silver_bar_entry_model import SilverBarEntryModel
from .modern_components import install_table_empty_state, polish_dense_table
from .screen_widgets import (
    SCREEN_QSS,
    KeyHintButton,
    StatusPill,
    TotalsStrip,
    card,
    label,
)
from .shared_screen_theme import build_management_screen_stylesheet
from .window_sizing import resize_to_available_screen

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog

# Below this width the action buttons move under the list title.
COMPACT_HEADER_WIDTH = 1040
# Below this width both bar tables hide the bar number column.
COMPACT_TABLE_WIDTH = 900


class SilverBarManagementUiBuilder:
    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host

    def init_ui(self) -> None:
        h = self.host
        h.setWindowTitle("Silver Bar Management")
        h.setObjectName("SilverBarManagementDialog")
        h.setMinimumSize(760, 520)
        resize_to_available_screen(h, preferred_width=1180, preferred_height=760)
        h.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#SilverBarManagementDialog",
                card_names=[],
                title_label="SilverBarTitle",
                subtitle_label="SilverBarSubtitle",
                primary_button="SilverBarPrimaryButton",
                secondary_button="SilverBarSecondaryButton",
                input_selectors=["QLineEdit"],
                include_table=True,
                extra_rules=SCREEN_QSS
                + """
                QLineEdit#SilverBarWeightInput { font-size: 12pt; padding: 5px 9px; min-height: 26px; }
                QPushButton#SilverBarSecondaryButton, QPushButton#SilverBarPrimaryButton { padding: 5px 12px; min-height: 24px; }
                QPushButton#SilverBarPrimaryButton:disabled { background-color: #9cc9cc; border-color: #9cc9cc; color: #ffffff; }
                QToolButton#SilverBarMoreButton {
                    background-color: __HEADER_BG__; border: 1px solid __INPUT_BORDER__;
                    border-radius: 6px; padding: 5px 12px; font-weight: 600; min-height: 24px;
                }
                QLabel#SilverBarStatus[error="true"] { color: __TEXT_STRONG__; background-color: __DANGER_BG__; }
                QFrame#SilverBarSuggestions { background: transparent; border: none; }
                QTableView#SilverBarSuggestionsTable, QTableView#SilverBarListTable {
                    border: none; border-top: 1px solid __CARD_BORDER_SOFT__; border-radius: 0;
                }
            """,
            )
        )
        layout = QVBoxLayout(h)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._header())
        body = QWidget(h)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(14, 12, 14, 12)
        body_layout.setSpacing(12)
        body_layout.addWidget(self._issued_banner())
        panes = QHBoxLayout()
        panes.setSpacing(12)
        panes.addWidget(self._available_card(), 1)
        panes.addWidget(self._list_card(), 1)
        body_layout.addLayout(panes, 1)
        layout.addWidget(body, 1)
        layout.addWidget(self._footer())
        QWidget.setTabOrder(h.weight_search_edit, h.list_bars_table)
        QWidget.setTabOrder(h.list_bars_table, h.print_list_button)
        for keys, callback in (
            ("Ctrl+N", h.create_new_list),
            ("Ctrl+O", h.open_saved_list),
            ("Ctrl+F", lambda: h.focus_weight(announce=True)),
            ("F2", h.edit_list_note),
            ("Ctrl+P", h.print_selected_list),
            ("Ctrl+Shift+P", h.preview_selected_list),
            ("Ctrl+G", h.generate_optimal_list),
            ("Ctrl+H", h.open_history),
            ("Ctrl+R", h.reopen_issued_list),
            ("F1", h.show_keyboard_help),
            ("Alt+I", h.retry_issue),
        ):
            action = QAction(h)
            action.setShortcut(QKeySequence(keys))
            action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)
            action.setAutoRepeat(False)
            action.triggered.connect(
                lambda _checked=False, cb=callback: h.run_shortcut(cb)
            )
            h.addAction(action)
        h.weight_search_edit.textChanged.connect(h._load_controller.schedule_search)
        h.suggestions_table.doubleClicked.connect(h.add_current_match)

    def _header(self) -> QFrame:
        h = self.host
        bar = QFrame(h)
        bar.setObjectName("ScreenHeaderBar")
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(16, 10, 16, 10)
        outer.setSpacing(8)
        h.header_top_row = QHBoxLayout()
        h.header_top_row.setSpacing(10)
        h.list_info_label = label("New list", "ScreenTitle", bar)
        h.header_top_row.addWidget(h.list_info_label)
        h.list_state_pill = StatusPill(bar)
        h.header_top_row.addWidget(h.list_state_pill)
        h.edit_note_button = KeyHintButton("Add note", "F2", bar)
        h.edit_note_button.setObjectName("LinkButton")
        h.edit_note_button.setCursor(Qt.CursorShape.PointingHandCursor)
        h.edit_note_button.clicked.connect(lambda _=False: h.edit_list_note())
        h.header_top_row.addWidget(h.edit_note_button)
        h.header_top_row.addStretch(1)
        h.header_actions = QWidget(bar)
        actions = QHBoxLayout(h.header_actions)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        h.new_list_button = self.button(
            "New list", h.create_new_list, "Start a new list", "Ctrl+N"
        )
        h.generate_optimal_button = self.button(
            "Optimal list",
            h.generate_optimal_list,
            "Build a list that fits a target fine weight",
            "Ctrl+G",
        )
        h.open_list_button = self.button(
            "History", h.open_saved_list, "Lists and bar history · Ctrl+O", "Ctrl+H"
        )
        h.retry_issue_button = self.button(
            "Issue", h.retry_issue, "Retry issuing without printing again", "Alt+I"
        )
        h.retry_issue_button.hide()
        for button in (
            h.new_list_button,
            h.generate_optimal_button,
            h.open_list_button,
            h.retry_issue_button,
        ):
            actions.addWidget(button)
        h.more_button = QToolButton(h.header_actions)
        h.more_button.setObjectName("SilverBarMoreButton")
        h.more_button.setText("&More")
        h.more_button.setToolTip("More actions · Alt+M · Keyboard help: F1")
        h.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(h.more_button)
        menu.addAction("Print &preview  Ctrl+Shift+P", h.preview_selected_list)
        h.export_action = menu.addAction("&Export CSV", h.export_current_list_to_csv)
        h.clear_action = menu.addAction("&Clear list", h.clear_current_list)
        h.delete_action = menu.addAction("&Delete list", h.delete_selected_list)
        menu.addSeparator()
        menu.addAction("Keyboard &help  F1", h.show_keyboard_help)
        h.more_button.setMenu(menu)
        actions.addWidget(h.more_button)
        divider = QFrame(h.header_actions)
        divider.setObjectName("MetricDivider")
        divider.setFixedSize(1, 26)
        actions.addWidget(divider)
        h.print_list_button = self.button(
            "Print && issue",
            h.print_selected_list,
            "Print, issue, and start a new list",
            "Ctrl+P",
        )
        h.print_list_button.setObjectName("SilverBarPrimaryButton")
        actions.addWidget(h.print_list_button)
        h.header_top_row.addWidget(h.header_actions)
        outer.addLayout(h.header_top_row)
        h.header_bottom = QWidget(bar)
        h.header_bottom_row = QHBoxLayout(h.header_bottom)
        h.header_bottom_row.setContentsMargins(0, 0, 0, 0)
        h.header_bottom_row.addStretch(1)
        h.header_bottom.hide()
        outer.addWidget(h.header_bottom)
        return bar

    def _issued_banner(self) -> QFrame:
        h = self.host
        h.issued_banner = QFrame(h)
        h.issued_banner.setObjectName("IssuedBanner")
        row = QHBoxLayout(h.issued_banner)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)
        h.issued_banner_label = label("", "IssuedBannerText", h.issued_banner)
        h.issued_banner_label.setWordWrap(True)
        row.addWidget(h.issued_banner_label, 1)
        h.reopen_button = self.button(
            "Reopen for editing",
            h.reopen_issued_list,
            "Make this list active again so it can be changed",
            "Ctrl+R",
        )
        row.addWidget(h.reopen_button)
        h.issued_banner.hide()
        return h.issued_banner

    def _available_card(self) -> QFrame:
        h = self.host
        h.available_card = card()
        layout = QVBoxLayout(h.available_card)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(14, 0, 14, 0)
        title_row.addWidget(label("Available bars", "CardTitle"))
        h.available_count_label = label("", "Muted")
        title_row.addWidget(h.available_count_label, 1)
        layout.addLayout(title_row)
        filter_box = QVBoxLayout()
        filter_box.setContentsMargins(14, 0, 14, 4)
        filter_box.setSpacing(4)
        weight_label = label("FILTER BY WEIGHT (G)", "Eyebrow")
        filter_box.addWidget(weight_label)
        h.weight_search_edit = QLineEdit()
        h.weight_search_edit.setObjectName("SilverBarWeightInput")
        h.weight_search_edit.setAccessibleName(
            "Filter available bars by weight in grams"
        )
        h.weight_search_edit.setPlaceholderText(
            "Showing all bars. Type a weight, e.g. 40"
        )
        h.weight_search_edit.setToolTip(
            "↑/↓ choose, Enter adds · Type a weight to filter (optional) · "
            "Ctrl+F shows bars"
        )
        h.weight_search_edit.setMinimumWidth(110)
        h.weight_search_edit.setClearButtonEnabled(True)
        h.weight_search_edit.installEventFilter(h)
        weight_label.setBuddy(h.weight_search_edit)
        filter_box.addWidget(h.weight_search_edit)
        layout.addLayout(filter_box)
        h.suggestions_panel = QFrame(h.available_card)
        h.suggestions_panel.setObjectName("SilverBarSuggestions")
        suggestions_layout = QVBoxLayout(h.suggestions_panel)
        suggestions_layout.setContentsMargins(0, 0, 0, 0)
        suggestions_layout.setSpacing(0)
        h.suggestions_table, h.suggestions_model = self.table(
            "SilverBarSuggestionsTable"
        )
        h.suggestions_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h.suggestions_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        suggestions_layout.addWidget(h.suggestions_table, 1)
        h.suggestions_panel.hide()
        h.suggestions_panel.installEventFilter(h)
        layout.addWidget(h.suggestions_panel, 1)
        layout.addWidget(self._available_empty_state(), 1)
        h.suggestions_hint = self.hint("↑ ↓ choose    Enter add to list    Esc clear")
        layout.addWidget(h.suggestions_hint)
        return h.available_card

    def _available_empty_state(self) -> QWidget:
        h = self.host
        h.available_empty = QWidget(h.available_card)
        layout = QVBoxLayout(h.available_empty)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        h.available_empty_title = label("Loading available bars…", "EmptyStateTitle")
        h.available_empty_body = label("", "EmptyStateBody")
        for widget in (h.available_empty_title, h.available_empty_body):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.setWordWrap(True)
            layout.addWidget(widget)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        h.show_all_bars_button = self.button(
            "Show all bars", h.show_all_available, "Clear the weight filter", "Esc"
        )
        h.find_in_history_button = self.button(
            "Find in history", h.open_history, "Search every bar", "Ctrl+H"
        )
        buttons.addWidget(h.show_all_bars_button)
        buttons.addWidget(h.find_in_history_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        return h.available_empty

    def _list_card(self) -> QFrame:
        h = self.host
        h.list_card = card()
        layout = QVBoxLayout(h.list_card)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(8)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(14, 0, 14, 0)
        title_row.addWidget(label("In this list", "CardTitle"))
        h.list_count_label = label("", "Muted")
        h.list_count_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        title_row.addWidget(h.list_count_label, 1)
        layout.addLayout(title_row)
        h.list_bars_table, h.list_bars_model = self.table("SilverBarListTable")
        h.list_bars_table.installEventFilter(h)
        h.list_bars_table.setTabKeyNavigation(False)
        h.list_bars_table.setMinimumHeight(100)
        layout.addWidget(h.list_bars_table, 1)
        h._empty_state = install_table_empty_state(
            h.list_bars_table,
            "No bars yet.\n\nPick a bar on the left and press Enter. The list gets "
            "its number and saves itself when the first bar is added.",
        )
        hint_row = QHBoxLayout()
        hint_row.setContentsMargins(0, 0, 14, 0)
        h.list_hint = self.hint("Del remove selected    Shift+Tab available bars")
        hint_row.addWidget(h.list_hint, 1)
        h.load_more_button = self.button("Load more", h.load_more_list_rows)
        h.load_more_button.hide()
        hint_row.addWidget(h.load_more_button)
        layout.addLayout(hint_row)
        h.list_totals_label = TotalsStrip(
            ("Bars", "Total weight", "Total fine"), parent=h.list_card
        )
        layout.addWidget(h.list_totals_label)
        return h.list_card

    def _footer(self) -> QFrame:
        h = self.host
        bar = QFrame(h)
        bar.setObjectName("ScreenFooterBar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(16, 5, 16, 5)
        h.status_label = QLabel()
        h.status_label.setObjectName("SilverBarStatus")
        h.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        row.addWidget(h.status_label, 1)
        row.addWidget(label("F1 all shortcuts", "Muted"))
        return bar

    def hint(self, text: str) -> QLabel:
        hint = label(text, "HintText")
        hint.setContentsMargins(14, 2, 14, 8)
        hint.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return hint

    def button(
        self, text, callback, tooltip: str = "", key_hint: str = ""
    ) -> QPushButton:
        button = KeyHintButton(text, key_hint, self.host)
        button.setObjectName("SilverBarSecondaryButton")
        button.setToolTip(f"{tooltip} · {key_hint}" if key_hint else tooltip)
        button.clicked.connect(lambda _=False: callback())
        return button

    def table(self, name: str) -> tuple[QTableView, SilverBarEntryModel]:
        table = QTableView(self.host)
        table.setObjectName(name)
        model = SilverBarEntryModel(table)
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in ((0, 84), (1, 70), (2, 76), (4, 50)):
            table.setColumnWidth(column, width)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        polish_dense_table(
            table,
            row_height=32,
            header_height=32,
            show_grid=False,
            hide_vertical_header=True,
        )
        table.setFrameShape(QFrame.Shape.NoFrame)
        return table, model
