"""Grouped keyboard shortcuts for the silver bar workspace (F1)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .screen_widgets import SCREEN_QSS, label
from .theme_tokens import apply_theme_tokens

SHORTCUT_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Adding bars",
        (
            ("Ctrl+F", "Weight filter and available bars"),
            ("↑ ↓", "Choose a bar"),
            ("Enter", "Add the bar and save"),
            ("Esc", "Hide bars, clear the weight, then close"),
        ),
    ),
    (
        "This list",
        (
            ("Tab", "Move to the list"),
            ("Delete", "Remove selected bars and save"),
            ("F2", "Edit note"),
            ("Alt+M", "More actions"),
        ),
    ),
    (
        "Printing",
        (
            ("Ctrl+P", "Print, issue, and start a new list"),
            ("Ctrl+Shift+P", "Preview, PDF, printer settings"),
            ("Alt+I", "Retry issuing without printing again"),
        ),
    ),
    (
        "Lists",
        (
            ("Ctrl+N", "New list"),
            ("Ctrl+G", "Generate optimal list"),
            ("Ctrl+H / Ctrl+O", "History of lists and bars"),
            ("Ctrl+R", "Reopen an issued list"),
        ),
    ),
)

_STYLE = """
QDialog#SilverBarShortcutsDialog { background: __SURFACE_BG__; }
QLabel#ShortcutKey {
    background: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-bottom: 2px solid __CARD_BORDER__;
    border-radius: 4px;
    color: #334155;
    font-weight: 600;
    padding: 1px 6px;
}
QPushButton#ShortcutsClose {
    background: __PRIMARY_BG__; border: 1px solid __PRIMARY_BG__; color: #ffffff;
    border-radius: 6px; font-weight: 600; padding: 6px 16px;
}
"""


class SilverBarShortcutsDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Silver bar keyboard shortcuts")
        self.setObjectName("SilverBarShortcutsDialog")
        self.setStyleSheet(apply_theme_tokens(SCREEN_QSS + _STYLE))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(label("Keyboard shortcuts", "ScreenTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(36)
        grid.setVerticalSpacing(18)
        for index, (title, rows) in enumerate(SHORTCUT_GROUPS):
            grid.addWidget(self._group(title, rows), index // 2, index % 2)
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Got it")
        close.setObjectName("ShortcutsClose")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def _group(self, title: str, rows: tuple[tuple[str, str], ...]) -> QWidget:
        group = QWidget(self)
        layout = QGridLayout(group)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(6)
        layout.addWidget(label(title.upper(), "Eyebrow"), 0, 0, 1, 2)
        for row, (keys, description) in enumerate(rows, start=1):
            key = QLabel(keys)
            key.setObjectName("ShortcutKey")
            layout.addWidget(key, row, 0, Qt.AlignmentFlag.AlignRight)
            layout.addWidget(label(description), row, 1)
        layout.setColumnStretch(1, 1)
        return group

    def text(self) -> str:
        return "\n".join(
            f"{keys}: {description}"
            for _, rows in SHORTCUT_GROUPS
            for keys, description in rows
        )
