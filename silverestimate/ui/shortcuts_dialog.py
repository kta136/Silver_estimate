"""Grouped keyboard-shortcut help, shared by every screen (F1)."""

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

ShortcutGroups = tuple[tuple[str, tuple[tuple[str, str], ...]], ...]

# Shortcuts for the main window. The Silver Bars window lists its own.
APP_SHORTCUT_GROUPS: ShortcutGroups = (
    (
        "Estimate",
        (
            ("Ctrl+S", "Save, then open the print preview"),
            ("Ctrl+P", "Print preview"),
            ("Ctrl+N", "New estimate"),
            ("Ctrl+H", "Estimate history"),
            ("Enter", "In Voucher: load that estimate"),
        ),
    ),
    (
        "Rows",
        (
            ("Enter / Tab", "Confirm the field and move on"),
            ("Page Up / Page Down", "Move through rows"),
            ("Ctrl+D", "Delete the current row"),
            ("Ctrl+Shift+D", "Undo the last row deletion"),
            ("Ctrl+R", "Return mode on or off"),
            ("Ctrl+B", "Silver Bar mode on or off"),
        ),
    ),
    (
        "Sales reports",
        (
            ("F5", "View the report"),
            ("Enter", "Open the selected row"),
            ("Backspace", "Go back a level"),
            ("Ctrl+E", "Export the table as CSV"),
        ),
    ),
    (
        "Screens",
        (
            ("Alt+E", "Estimate entry"),
            ("Alt+I", "Item Master"),
            ("Alt+R", "Sales reports"),
            ("Alt+B", "Silver bars"),
            ("Esc", "Item Master: clear the form"),
            ("F1", "This list (Silver Bars has its own)"),
        ),
    ),
)

_STYLE = """
QDialog#ShortcutsDialog { background: __SURFACE_BG__; }
QLabel#ShortcutKey {
    background: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-bottom: 2px solid __CARD_BORDER__;
    border-radius: 4px;
    color: __HEADER_TEXT__;
    font-weight: 600;
    padding: 1px 6px;
}
QPushButton#ShortcutsClose {
    background: __PRIMARY_BG__; border: 1px solid __PRIMARY_BG__; color: __SURFACE_BG__;
    border-radius: 6px; font-weight: 600; padding: 6px 16px;
}
"""


class ShortcutsDialog(QDialog):
    """Shortcuts in titled groups, two groups to a row."""

    def __init__(
        self,
        groups: ShortcutGroups = APP_SHORTCUT_GROUPS,
        parent: QWidget | None = None,
        *,
        window_title: str = "Keyboard Shortcuts",
    ) -> None:
        super().__init__(parent)
        self._groups = groups
        self.setWindowTitle(window_title)
        self.setObjectName("ShortcutsDialog")
        self.setStyleSheet(apply_theme_tokens(SCREEN_QSS + _STYLE))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(16)
        layout.addWidget(label("Keyboard shortcuts", "ScreenTitle"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(36)
        grid.setVerticalSpacing(18)
        for index, (title, rows) in enumerate(groups):
            # Top-aligned, so the headings of two groups of different length
            # line up instead of each group centring in its row.
            grid.addWidget(
                self._group(title, rows),
                index // 2,
                index % 2,
                Qt.AlignmentFlag.AlignTop,
            )
        layout.addLayout(grid)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        close = QPushButton("Close")
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
            for _, rows in self._groups
            for keys, description in rows
        )


__all__ = ["APP_SHORTCUT_GROUPS", "ShortcutGroups", "ShortcutsDialog"]
