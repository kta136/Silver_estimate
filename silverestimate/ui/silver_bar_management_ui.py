"""Single-workspace UI for keyboard-driven silver-bar entry."""

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
from .shared_screen_theme import build_management_screen_stylesheet
from .window_sizing import resize_to_available_screen

if TYPE_CHECKING:
    from .silver_bar_management import SilverBarDialog


class SilverBarManagementUiBuilder:
    def __init__(self, host: SilverBarDialog) -> None:
        self.host = host

    def init_ui(self) -> None:
        h = self.host
        h.setWindowTitle("Silver Bar Management")
        h.setObjectName("SilverBarManagementDialog")
        h.setMinimumSize(760, 520)
        resize_to_available_screen(h, preferred_width=1080, preferred_height=760)
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
                extra_rules="""
                QLineEdit#SilverBarWeightInput { font-size: 12pt; padding: 3px 7px; min-height: 24px; }
                QPushButton#SilverBarSecondaryButton, QPushButton#SilverBarPrimaryButton { padding: 3px 7px; min-height: 24px; }
                QLabel#SilverBarTotals { font-weight: 600; padding: 0; }
                QLabel#SilverBarStatus[error="true"] { color: __TEXT_STRONG__; background-color: __DANGER_BG__; }
                QFrame#SilverBarSuggestions { background: __SURFACE_BG__; border: 1px solid __INPUT_BORDER__; border-radius: 4px; }
            """,
            )
        )
        layout = QVBoxLayout(h)
        layout.setContentsMargins(10, 8, 10, 6)
        layout.setSpacing(6)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        h.list_info_label = QLabel("New list")
        toolbar.addWidget(h.list_info_label)
        weight_label = QLabel("Weight (g)")
        toolbar.addWidget(weight_label)
        h.weight_search_edit = QLineEdit()
        h.weight_search_edit.setObjectName("SilverBarWeightInput")
        h.weight_search_edit.setAccessibleName(
            "Filter available bars by weight in grams"
        )
        h.weight_search_edit.setPlaceholderText("All bars · Type to filter")
        h.weight_search_edit.setToolTip(
            "↑/↓ choose, Enter adds · Type a weight to filter (optional) · Ctrl+F shows bars"
        )
        h.weight_search_edit.setMinimumWidth(110)
        h.weight_search_edit.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        h.weight_search_edit.setClearButtonEnabled(True)
        h.weight_search_edit.installEventFilter(h)
        weight_label.setBuddy(h.weight_search_edit)
        toolbar.addWidget(h.weight_search_edit, 1)
        h.new_list_button = self.button("New", h.create_new_list, "New list · Ctrl+N")
        h.open_list_button = self.button(
            "History", h.open_saved_list, "Open lists and bar history · Ctrl+O / Ctrl+H"
        )
        h.edit_note_button = self.button(
            "Note", h.edit_list_note, "Edit list note · F2"
        )
        h.generate_optimal_button = self.button(
            "Optimal", h.generate_optimal_list, "Generate optimal list · Ctrl+G"
        )
        for button in (
            h.new_list_button,
            h.open_list_button,
            h.edit_note_button,
            h.generate_optimal_button,
        ):
            toolbar.addWidget(button)
        h.retry_issue_button = self.button(
            "Issue", h.retry_issue, "Retry issuing · Alt+I"
        )
        h.retry_issue_button.hide()
        toolbar.addWidget(h.retry_issue_button)
        h.print_list_button = self.button(
            "Print && new",
            h.print_selected_list,
            "Print, issue, and start a new list · Ctrl+P",
        )
        h.print_list_button.setObjectName("SilverBarPrimaryButton")
        toolbar.addWidget(h.print_list_button)
        h.more_button = QToolButton()
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
        toolbar.addWidget(h.more_button)
        layout.addLayout(toolbar)
        h.suggestions_panel = QFrame(h)
        h.suggestions_panel.setObjectName("SilverBarSuggestions")
        suggestions_layout = QVBoxLayout(h.suggestions_panel)
        suggestions_layout.setContentsMargins(0, 0, 0, 6)
        h.suggestions_table, h.suggestions_model = self.table(
            "SilverBarSuggestionsTable"
        )
        h.suggestions_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        h.suggestions_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        h.suggestions_table.setMaximumHeight(164)
        suggestions_layout.addWidget(h.suggestions_table)
        h.suggestions_hint = QLabel("  ↑ ↓ Choose     Enter Add bar     Esc Dismiss")
        suggestions_layout.addWidget(h.suggestions_hint)
        h.suggestions_panel.hide()
        h.list_bars_table, h.list_bars_model = self.table("SilverBarListTable")
        h.list_bars_table.installEventFilter(h)
        h.list_bars_table.setTabKeyNavigation(False)
        h.list_bars_table.setMinimumHeight(100)
        layout.addWidget(h.list_bars_table, 1)
        h._empty_state = install_table_empty_state(
            h.list_bars_table,
            "Choose an available bar above and press Enter. Type a weight to filter.",
        )
        footer = QHBoxLayout()
        h.status_label = QLabel()
        h.status_label.setObjectName("SilverBarStatus")
        h.status_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        footer.addWidget(h.status_label, 1)
        h.load_more_button = self.button("Load more", h.load_more_list_rows)
        h.load_more_button.hide()
        footer.addWidget(h.load_more_button)
        h.list_totals_label = QLabel(
            "0 bars     Total weight  0.00 g     Total fine  0.00 g"
        )
        h.list_totals_label.setObjectName("SilverBarTotals")
        footer.addWidget(h.list_totals_label)
        layout.addLayout(footer)
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

    def button(self, label, callback, tooltip: str = "") -> QPushButton:
        button = QPushButton(label, self.host)
        button.setObjectName("SilverBarSecondaryButton")
        button.setAutoDefault(False)
        button.setToolTip(tooltip)
        button.clicked.connect(callback)
        return button

    def table(self, name: str) -> tuple[QTableView, SilverBarEntryModel]:
        table = QTableView(self.host)
        table.setObjectName(name)
        model = SilverBarEntryModel(table)
        table.setModel(model)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )
        for column, width in ((0, 140), (1, 110), (2, 150), (4, 85)):
            table.setColumnWidth(column, width)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        polish_dense_table(
            table,
            row_height=30,
            header_height=30,
            show_grid=False,
            hide_vertical_header=True,
        )
        return table, model
