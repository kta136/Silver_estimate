"""Voucher toolbar component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import QDate, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QDateEdit,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
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
        self.setObjectName("VoucherToolbar")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up a compact ribbon with optional detail drawer."""
        container_layout = QVBoxLayout(self)
        container_layout.setSpacing(2)
        container_layout.setContentsMargins(6, 2, 6, 2)
        self.setStyleSheet(
            """
            QWidget#VoucherToolbar {
                background-color: transparent;
            }
            QLabel#NotePreviewLabel {
                min-height: 22px;
            }
            """
        )

        # Main layout - single row, minimal padding
        main_layout = QHBoxLayout()
        main_layout.setSpacing(6)
        container_layout.addLayout(main_layout)

        # Unsaved changes badge (compact)
        self.unsaved_badge = QLabel("")
        self.unsaved_badge.setObjectName("UnsavedBadge")
        self.unsaved_badge.setAccessibleName("Unsaved Changes Indicator")
        self.unsaved_badge.setVisible(False)
        self.unsaved_badge.setToolTip("Unsaved changes")
        self.unsaved_badge.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.unsaved_badge.setMaximumHeight(28)
        self.unsaved_badge.setAlignment(Qt.AlignCenter)
        self.unsaved_badge.setStyleSheet("""
            QLabel#UnsavedBadge {
                color: #b45309;
                background-color: #fff7ed;
                border: 1px solid #f97316;
                border-radius: 10px;
                padding: 3px 10px;
                font-weight: 600;
                font-size: 9pt;
            }
        """)
        main_layout.addWidget(self.unsaved_badge)

        # Compact divider
        main_layout.addWidget(self._create_vertical_divider())

        # Voucher number (compact)
        voucher_label = QLabel("V#:")
        voucher_label.setMaximumHeight(28)
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setMaximumWidth(90)
        self.voucher_edit.setMaximumHeight(28)
        self.voucher_edit.setToolTip("Voucher number (Enter to load)")
        main_layout.addWidget(voucher_label)
        main_layout.addWidget(self.voucher_edit)

        # Load button (compact)
        self.load_button = QPushButton("Load")
        self.load_button.setMaximumWidth(56)
        self.load_button.setMaximumHeight(28)
        self.load_button.setToolTip("Load estimate (Enter)")
        main_layout.addWidget(self.load_button)

        # Compact divider
        main_layout.addWidget(self._create_vertical_divider())

        # Date (compact)
        date_label = QLabel("Date:")
        date_label.setMaximumHeight(28)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setMaximumWidth(90)
        self.date_edit.setMaximumHeight(28)
        self.date_edit.setToolTip("Estimate date")
        main_layout.addWidget(date_label)
        main_layout.addWidget(self.date_edit)

        # Compact divider
        main_layout.addWidget(self._create_vertical_divider())

        # Silver rate (compact)
        silver_rate_label = QLabel("Rate:")
        silver_rate_label.setMaximumHeight(28)
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setValue(0.0)
        self.silver_rate_spin.setMaximumWidth(85)
        self.silver_rate_spin.setMaximumHeight(28)
        self.silver_rate_spin.setToolTip("Silver rate (₹/kg)")
        main_layout.addWidget(silver_rate_label)
        main_layout.addWidget(self.silver_rate_spin)

        # Push infrequently used controls to the right edge
        main_layout.addStretch(1)

        # Detail toggle manages a collapsible drawer for extra voucher metadata
        self.details_toggle = QToolButton()
        self.details_toggle.setText("Details")
        self.details_toggle.setToolTip(
            "Show or hide rarely edited voucher fields (notes, inline status)."
        )
        self.details_toggle.setCheckable(True)
        self.details_toggle.setChecked(False)
        self.details_toggle.setArrowType(Qt.RightArrow)
        self.details_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.details_toggle.setAutoRaise(True)
        self.details_toggle.setMaximumHeight(28)
        main_layout.addWidget(self.details_toggle)

        self.note_preview_label = QLabel("")
        self.note_preview_label.setObjectName("NotePreviewLabel")
        self.note_preview_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.note_preview_label.setStyleSheet(
            "color: palette(mid); font-style: italic; padding-left: 4px;"
        )
        self.note_preview_label.setVisible(False)
        main_layout.addWidget(self.note_preview_label, stretch=1)

        # Drawer content with note + inline status
        self.details_container = QFrame()
        self.details_container.setObjectName("VoucherDetailsContainer")
        self.details_container.setFrameShape(QFrame.NoFrame)
        self.details_container.setVisible(False)

        details_layout = QHBoxLayout(self.details_container)
        details_layout.setContentsMargins(6, 0, 0, 0)
        details_layout.setSpacing(8)

        note_label = QLabel("Note:")
        note_label.setMaximumHeight(28)
        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Customer, instructions...")
        self.note_edit.setMaximumHeight(28)
        self.note_edit.setToolTip("Optional notes")
        details_layout.addWidget(note_label)
        details_layout.addWidget(self.note_edit, stretch=1)
        container_layout.addWidget(self.details_container)

        # Status message label (hidden, for EstimateLogic compatibility)
        self.status_message_label = QLabel("")
        self.status_message_label.setVisible(False)
        details_layout.addWidget(self.status_message_label)

        # Hidden mode indicator kept for backward compatibility (actual badge moved to totals panel)
        self.mode_indicator_label = QLabel("Regular")
        self.mode_indicator_label.setVisible(False)

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
        self.note_edit.textChanged.connect(self._update_note_preview)
        self.details_toggle.toggled.connect(self._on_details_toggled)

        # Initialize preview state
        self._update_note_preview(self.note_edit.text())

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
        self._update_note_preview(note)

    def get_note(self) -> str:
        """Get the current note text.

        Returns:
            The note text
        """
        return self.note_edit.text()

    # Internal helpers -------------------------------------------------

    def _on_details_toggled(self, expanded: bool) -> None:
        """Show or hide the secondary voucher metadata drawer."""
        self.details_toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.details_container.setVisible(expanded)
        self._update_note_preview(self.note_edit.text())

    def _update_note_preview(self, text: str) -> None:
        """Refresh the compact note preview when the drawer is collapsed."""
        trimmed = (text or "").strip()
        if not trimmed or self.details_toggle.isChecked():
            self.note_preview_label.clear()
            self.note_preview_label.setVisible(False)
            return

        if len(trimmed) > 48:
            trimmed = f"{trimmed[:45]}…"
        self.note_preview_label.setText(trimmed)
        self.note_preview_label.setVisible(True)

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
