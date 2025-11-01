"""Voucher toolbar component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import QDate, pyqtSignal
from PyQt5.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class VoucherToolbar(QWidget):
    """Toolbar for voucher metadata and primary actions.

    This component manages the voucher number, date, note, and provides
    buttons for save, load, history, delete, and new estimate operations.
    """

    # Signals
    save_clicked = pyqtSignal()
    load_clicked = pyqtSignal()
    history_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    new_clicked = pyqtSignal()
    voucher_number_changed = pyqtSignal(str)
    date_changed = pyqtSignal(QDate)
    note_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        """Initialize the voucher toolbar.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Mode indicator
        self.mode_indicator_label = QLabel("Mode: Regular Items")
        self.mode_indicator_label.setStyleSheet("""
            font-weight: bold;
            color: palette(windowText);
            background-color: palette(window);
            border: 1px solid palette(mid);
            border-radius: 3px;
            padding: 2px 6px;
        """)
        self.mode_indicator_label.setToolTip(
            "Shows which entry mode is active.\nCtrl+R: Return Items\nCtrl+B: Silver Bars"
        )
        layout.addWidget(self.mode_indicator_label)

        # Unsaved changes badge
        self.unsaved_badge = QLabel("")
        self.unsaved_badge.setObjectName("UnsavedBadge")
        self.unsaved_badge.setAccessibleName("Unsaved Changes Indicator")
        self.unsaved_badge.setVisible(False)
        self.unsaved_badge.setToolTip("Indicates there are unsaved changes in this estimate")
        self.unsaved_badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.unsaved_badge.setStyleSheet("""
            QLabel#UnsavedBadge {
                color: #b45309;
                background-color: #fff7ed;
                border: 1px solid #f97316;
                border-radius: 11px;
                padding: 2px 10px;
                font-weight: 600;
            }
        """)
        layout.addWidget(self.unsaved_badge)

        # Voucher number
        voucher_label = QLabel("Voucher No:")
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(140)
        self.voucher_edit.setToolTip(
            "Enter an existing voucher number to load or leave blank for a new estimate.\n"
            "Format: Any alphanumeric code (e.g., EST001, V-2024-001)\n"
            "Press Tab or Enter to load estimate"
        )
        layout.addWidget(voucher_label)
        layout.addWidget(self.voucher_edit)

        # Load button
        self.load_button = QPushButton("Load")
        self.load_button.setToolTip(
            "Load the estimate with the entered voucher number.\n"
            "Shortcut: Enter in Voucher field\n"
            "Will show error if voucher not found"
        )
        layout.addWidget(self.load_button)

        # Date
        date_label = QLabel("Date:")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(120)
        self.date_edit.setToolTip(
            "Date of the estimate.\n"
            "Click calendar icon to choose date\n"
            "Format: DD/MM/YYYY\n"
            "Defaults to today's date"
        )
        layout.addWidget(date_label)
        layout.addWidget(self.date_edit)

        # Note
        note_label = QLabel("Note:")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Optional notes for this estimate...")
        self.note_edit.setToolTip(
            "Optional notes or comments for this estimate.\n"
            "Examples: Customer name, special instructions, etc.\n"
            "Saved with the estimate"
        )
        layout.addWidget(note_label)
        layout.addWidget(self.note_edit)

        layout.addStretch()

        # Action buttons
        self.save_button = QPushButton("Save")
        self.save_button.setToolTip(
            "Save the current estimate to database.\n"
            "Generates voucher number if new estimate\n"
            "Updates existing estimate if voucher loaded"
        )
        layout.addWidget(self.save_button)

        self.history_button = QPushButton("History")
        self.history_button.setToolTip(
            "View, load, or print past estimates\n"
            "Keyboard: Ctrl+H\n"
            "Browse all saved estimates\n"
            "Double-click to load an estimate"
        )
        layout.addWidget(self.history_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setToolTip(
            "Delete the currently loaded estimate\n"
            "Permanently removes estimate from database\n"
            "Only enabled when estimate is loaded\n"
            "Cannot be undone - use with caution"
        )
        self.delete_button.setEnabled(False)
        layout.addWidget(self.delete_button)

        self.new_button = QPushButton("New")
        self.new_button.setToolTip(
            "Clear the form to start a new estimate\n"
            "Keyboard: Ctrl+N\n"
            "Resets all fields and generates new voucher\n"
            "Will ask for confirmation if unsaved changes"
        )
        layout.addWidget(self.new_button)

    def _connect_signals(self) -> None:
        """Connect internal widget signals."""
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.load_button.clicked.connect(self.load_clicked.emit)
        self.history_button.clicked.connect(self.history_clicked.emit)
        self.delete_button.clicked.connect(self.delete_clicked.emit)
        self.new_button.clicked.connect(self.new_clicked.emit)

        self.voucher_edit.textChanged.connect(self.voucher_number_changed.emit)
        self.date_edit.dateChanged.connect(self.date_changed.emit)
        self.note_edit.textChanged.connect(self.note_changed.emit)

    # Public methods for data access

    def set_voucher_number(self, number: str) -> None:
        """Set the voucher number.

        Args:
            number: The voucher number to display
        """
        self.voucher_edit.setText(number)

    def get_voucher_number(self) -> str:
        """Get the current voucher number.

        Returns:
            The voucher number text
        """
        return self.voucher_edit.text()

    def set_date(self, date: QDate) -> None:
        """Set the estimate date.

        Args:
            date: The date to set
        """
        self.date_edit.setDate(date)

    def get_date(self) -> QDate:
        """Get the current estimate date.

        Returns:
            The selected date
        """
        return self.date_edit.date()

    def set_note(self, note: str) -> None:
        """Set the note text.

        Args:
            note: The note text to display
        """
        self.note_edit.setText(note)

    def get_note(self) -> str:
        """Get the current note text.

        Returns:
            The note text
        """
        return self.note_edit.text()

    def enable_delete(self, enabled: bool) -> None:
        """Enable or disable the delete button.

        Args:
            enabled: True to enable, False to disable
        """
        self.delete_button.setEnabled(enabled)

    def set_mode_indicator(self, mode_text: str) -> None:
        """Set the mode indicator text.

        Args:
            mode_text: The mode text to display (e.g., "Mode: Return Items")
        """
        self.mode_indicator_label.setText(mode_text)

    def show_unsaved_badge(self, show: bool) -> None:
        """Show or hide the unsaved changes badge.

        Args:
            show: True to show, False to hide
        """
        if show:
            self.unsaved_badge.setText("● Unsaved")
        self.unsaved_badge.setVisible(show)

    def clear_voucher_metadata(self) -> None:
        """Clear all voucher metadata fields."""
        self.voucher_edit.clear()
        self.date_edit.setDate(QDate.currentDate())
        self.note_edit.clear()
        self.enable_delete(False)
        self.show_unsaved_badge(False)
