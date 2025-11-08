"""Voucher toolbar component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import QDate, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class VoucherToolbar(QWidget):
    """Header form for voucher metadata.

    This component manages the voucher number, date, note, and silver rate fields.
    Action buttons are in separate PrimaryActionsBar and SecondaryActionsBar components.
    """

    # Signals
    load_clicked = pyqtSignal()
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
        """Set up the user interface with improved visual hierarchy and grouping."""
        # Main layout with better spacing
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(16)  # Increased spacing between groups
        main_layout.setContentsMargins(12, 8, 12, 8)  # Add padding around the toolbar

        # === GROUP 1: Voucher Information ===
        voucher_group, voucher_layout = self._create_group_box("Voucher Information")

        # Voucher number
        voucher_label = QLabel("Voucher No:")
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMinimumWidth(150)
        self.voucher_edit.setToolTip(
            "Enter an existing voucher number to load or leave blank for a new estimate.\n"
            "Format: Any alphanumeric code (e.g., EST001, V-2024-001)\n"
            "Press Tab or Enter to load estimate"
        )
        voucher_layout.addWidget(voucher_label, 0, 0)
        voucher_layout.addWidget(self.voucher_edit, 0, 1)

        # Load button
        self.load_button = QPushButton("Load")
        self.load_button.setMinimumWidth(80)
        self.load_button.setToolTip(
            "Load the estimate with the entered voucher number.\n"
            "Shortcut: Enter in Voucher field\n"
            "Will show error if voucher not found"
        )
        voucher_layout.addWidget(self.load_button, 0, 2)

        # Note field (full width in second row)
        note_label = QLabel("Note:")
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Customer name, special instructions...")
        self.note_edit.setToolTip(
            "Optional notes or comments for this estimate.\n"
            "Examples: Customer name, special instructions, etc.\n"
            "Saved with the estimate"
        )
        voucher_layout.addWidget(note_label, 1, 0)
        voucher_layout.addWidget(self.note_edit, 1, 1, 1, 2)  # Span 2 columns

        main_layout.addWidget(voucher_group, stretch=2)

        # Divider
        main_layout.addWidget(self._create_vertical_divider())

        # === GROUP 2: Settings ===
        settings_group, settings_layout = self._create_group_box("Settings")

        # Date
        date_label = QLabel("Date:")
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMinimumWidth(130)
        self.date_edit.setToolTip(
            "Date of the estimate.\n"
            "Click calendar icon to choose date\n"
            "Format: DD/MM/YYYY\n"
            "Defaults to today's date"
        )
        settings_layout.addWidget(date_label, 0, 0)
        settings_layout.addWidget(self.date_edit, 0, 1)

        # Silver rate
        silver_rate_label = QLabel("Silver Rate:")
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setValue(0.0)
        self.silver_rate_spin.setMinimumWidth(130)
        self.silver_rate_spin.setToolTip("Silver rate per kg (₹)")
        settings_layout.addWidget(silver_rate_label, 1, 0)
        settings_layout.addWidget(self.silver_rate_spin, 1, 1)

        main_layout.addWidget(settings_group, stretch=1)

        # Divider
        main_layout.addWidget(self._create_vertical_divider())

        # === GROUP 3: Status ===
        status_group, status_layout = self._create_group_box("Status", use_vbox=True)

        # Unsaved changes badge
        self.unsaved_badge = QLabel("")
        self.unsaved_badge.setObjectName("UnsavedBadge")
        self.unsaved_badge.setAccessibleName("Unsaved Changes Indicator")
        self.unsaved_badge.setVisible(False)
        self.unsaved_badge.setToolTip("Indicates there are unsaved changes in this estimate")
        self.unsaved_badge.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.unsaved_badge.setAlignment(Qt.AlignCenter)
        self.unsaved_badge.setStyleSheet("""
            QLabel#UnsavedBadge {
                color: #b45309;
                background-color: #fff7ed;
                border: 1px solid #f97316;
                border-radius: 11px;
                padding: 4px 12px;
                font-weight: 600;
                font-size: 11pt;
            }
        """)
        status_layout.addWidget(self.unsaved_badge)

        # Mode indicator
        self.mode_indicator_label = QLabel("Mode: Regular Items")
        self.mode_indicator_label.setAlignment(Qt.AlignCenter)
        self.mode_indicator_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: palette(windowText);
                background-color: #dbeafe;
                border: 1px solid #3b82f6;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10pt;
            }
        """)
        self.mode_indicator_label.setToolTip(
            "Shows which entry mode is active.\nCtrl+R: Return Items\nCtrl+B: Silver Bars"
        )
        status_layout.addWidget(self.mode_indicator_label)

        main_layout.addWidget(status_group, stretch=1)

        # Status message label (hidden, for EstimateLogic compatibility)
        self.status_message_label = QLabel("")
        self.status_message_label.setVisible(False)

    def _create_group_box(self, title: str, use_vbox: bool = False) -> tuple[QFrame, QGridLayout | QVBoxLayout]:
        """Create a styled group box with title.

        Args:
            title: The title for the group
            use_vbox: If True, use QVBoxLayout instead of QGridLayout for content

        Returns:
            A tuple of (QFrame, content_layout)
        """
        frame = QFrame()
        frame.setObjectName("GroupBox")
        frame.setStyleSheet("""
            QFrame#GroupBox {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 6px;
            }
            QFrame#GroupBox QLabel {
                background-color: transparent;
                border: none;
            }
        """)

        # Create title label
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                color: palette(dark);
                font-size: 9pt;
                padding: 2px 4px;
                background-color: palette(window);
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
        """)
        title_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Container layout for the entire frame
        container_layout = QVBoxLayout(frame)
        container_layout.setSpacing(6)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.addWidget(title_label)

        # Content layout (what caller will use)
        if use_vbox:
            content_layout = QVBoxLayout()
            content_layout.setSpacing(6)
        else:
            content_layout = QGridLayout()
            content_layout.setSpacing(8)

        container_layout.addLayout(content_layout)

        return frame, content_layout

    def _create_vertical_divider(self) -> QFrame:
        """Create a vertical divider line.

        Returns:
            A vertical divider frame
        """
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setStyleSheet("QFrame { color: palette(mid); }")
        return divider

    def _connect_signals(self) -> None:
        """Connect internal widget signals."""
        self.load_button.clicked.connect(self.load_clicked.emit)
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

    def set_mode_indicator(self, mode_text: str) -> None:
        """Set the mode indicator text with color coding.

        Args:
            mode_text: The mode text to display (e.g., "Mode: Return Items")
        """
        self.mode_indicator_label.setText(mode_text)

        # Update colors based on mode
        if "Return" in mode_text:
            # Orange theme for return mode
            self.mode_indicator_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #7c2d12;
                    background-color: #fed7aa;
                    border: 1px solid #f97316;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }
            """)
        elif "Silver Bar" in mode_text:
            # Gray/Silver theme for silver bar mode
            self.mode_indicator_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: #27272a;
                    background-color: #d4d4d8;
                    border: 1px solid #71717a;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }
            """)
        else:
            # Blue theme for regular mode (default)
            self.mode_indicator_label.setStyleSheet("""
                QLabel {
                    font-weight: bold;
                    color: palette(windowText);
                    background-color: #dbeafe;
                    border: 1px solid #3b82f6;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 10pt;
                }
            """)

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
        self.show_unsaved_badge(False)
