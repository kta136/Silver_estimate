"""Grouped keyboard shortcuts for the silver bar workspace (F1)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from .shortcuts_dialog import ShortcutGroups, ShortcutsDialog

SHORTCUT_GROUPS: ShortcutGroups = (
    (
        "Adding bars",
        (
            ("Ctrl+F", "Weight filter and available bars"),
            ("↑ ↓", "Choose a bar"),
            ("Enter", "Add the bar and save"),
            ("Esc", "Hide bars, clear the weight, then go back"),
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
            ("Ctrl+I", "Retry issuing without printing again"),
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


class SilverBarShortcutsDialog(ShortcutsDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            SHORTCUT_GROUPS, parent, window_title="Silver Bar Keyboard Shortcuts"
        )
