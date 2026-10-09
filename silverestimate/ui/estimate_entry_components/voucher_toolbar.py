"""Voucher toolbar component for estimate entry."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QDateEdit,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

MODE_LABELS = ("Regular", "Return", "Silver Bar")
MODE_SHORTCUT_HINTS = ("", "Ctrl+R", "Ctrl+B")


class VoucherToolbar(QWidget):
    """Voucher metadata fields and the entry-mode switch.

    The same widgets are laid out as one row (header placement) or as a compact
    grid (side-panel placement); ``set_panel_layout`` switches between them.
    Action buttons are in separate PrimaryActionsBar and SecondaryActionsBar components.
    """

    # Signals
    load_clicked = Signal()
    voucher_number_changed = Signal(str)
    date_changed = Signal(QDate)
    note_changed = Signal(str)
    mode_selected = Signal(int)

    def __init__(self, parent=None):
        """Initialize the voucher toolbar.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self.setObjectName("VoucherToolbar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._panel_layout = False
        self._owns_unsaved_badge = True
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Create the fields once; layouts only arrange them."""
        self.unsaved_badge = QLabel("", self)
        self.unsaved_badge.setObjectName("UnsavedBadge")
        self.unsaved_badge.setAccessibleName("Unsaved Changes Indicator")
        self.unsaved_badge.setText("● Ready")
        self.unsaved_badge.setProperty("dirty", "false")
        self.unsaved_badge.setVisible(True)
        self.unsaved_badge.setToolTip("Current estimate status")
        self.unsaved_badge.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.unsaved_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.mode_indicator_label = QLabel("Mode: Regular")
        self.mode_indicator_label.setObjectName("EstimateModeBadge")
        self.mode_indicator_label.setProperty("modeState", "regular")
        self.mode_indicator_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mode_indicator_label.setToolTip(
            "Current mode: Regular Items\nCtrl+R: Return Items\nCtrl+B: Silver Bars"
        )
        self.mode_indicator_label.hide()

        self.mode_selector = QWidget(self)
        self.mode_selector.setObjectName("EntryModeSelector")
        self.mode_selector.setAccessibleName("Entry mode")
        mode_layout = QHBoxLayout(self.mode_selector)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(2)
        self.mode_buttons = QButtonGroup(self)
        self.mode_buttons.setExclusive(True)
        for index, (label, hint) in enumerate(
            zip(MODE_LABELS, MODE_SHORTCUT_HINTS, strict=True)
        ):
            button = QPushButton(label)
            button.setObjectName("EntryModeButton")
            button.setCheckable(True)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.setAccessibleName(f"{label} mode")
            button.setToolTip(f"{label} items ({hint})" if hint else "Regular items")
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.mode_buttons.addButton(button, index)
            mode_layout.addWidget(button)
        self.mode_buttons.button(0).setChecked(True)

        self.status_message_label = QLabel("")
        self.status_message_label.setObjectName("EstimateStatusLabel")
        self.status_message_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.status_message_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        self.status_message_label.hide()

        self.voucher_label = self._field_label("Voucher")
        self.voucher_edit = QLineEdit()
        self.voucher_edit.setObjectName("VoucherNumberEdit")
        self.voucher_edit.setToolTip("Voucher number (Enter to load)")

        self.load_button = QPushButton("Load")
        self.load_button.setObjectName("VoucherLoadButton")
        self.load_button.setToolTip("Load estimate (Enter)")

        self.date_label = self._field_label("Date")
        self.date_edit = QDateEdit()
        self.date_edit.setObjectName("EstimateDateEdit")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setToolTip("Estimate date")

        self.rate_label = self._field_label("Rate ₹/g")
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setObjectName("SilverRateSpin")
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        self.silver_rate_spin.setValue(0.0)
        self.silver_rate_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.silver_rate_spin.setToolTip("Estimate silver rate in rupees per gram")
        self.silver_rate_spin.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.note_label = self._field_label("Note")
        self.note_edit = QLineEdit()
        self.note_edit.setObjectName("EstimateNoteEdit")
        self.note_edit.setPlaceholderText("Customer, instructions...")
        self.note_edit.setToolTip("Customer name or optional estimate instructions")

        self._apply_layout()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("VoucherFieldLabel")
        return label

    def release_unsaved_badge(self) -> QLabel:
        """Hand the status badge to another container (the menu-bar strip)."""
        if self._owns_unsaved_badge:
            self._owns_unsaved_badge = False
            self._apply_layout()
        return self.unsaved_badge

    def is_panel_layout(self) -> bool:
        return self._panel_layout

    def set_panel_layout(self, panel: bool) -> None:
        """Arrange the fields as a side-panel grid (True) or a single row."""
        panel = bool(panel)
        if panel == self._panel_layout:
            return
        self._panel_layout = panel
        self._apply_layout()

    def _apply_layout(self) -> None:
        old_layout = self.layout()
        if old_layout is not None:
            while old_layout.count():
                old_layout.takeAt(0)
            # Re-home the old layout so a new one can be installed on self.
            QWidget().setLayout(old_layout)

        self.setProperty("placement", "panel" if self._panel_layout else "row")
        if self._panel_layout:
            self._build_panel_layout()
        else:
            self._build_row_layout()
        self.style().unpolish(self)
        self.style().polish(self)

    def _build_row_layout(self) -> None:
        layout = QHBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)
        for label, text in (
            (self.voucher_label, "Voucher:"),
            (self.date_label, "Date:"),
            (self.rate_label, "Rate ₹/g:"),
            (self.note_label, "Note:"),
        ):
            label.setText(text)
        self.voucher_edit.setMaximumWidth(96)
        self.date_edit.setMaximumWidth(126)
        self.silver_rate_spin.setMaximumWidth(116)
        self.note_edit.setMinimumWidth(160)

        if self._owns_unsaved_badge:
            layout.addWidget(self.unsaved_badge)
        layout.addWidget(self.mode_selector)
        layout.addWidget(self.voucher_label)
        layout.addWidget(self.voucher_edit)
        layout.addWidget(self.load_button)
        layout.addWidget(self.date_label)
        layout.addWidget(self.date_edit)
        layout.addWidget(self.rate_label)
        layout.addWidget(self.silver_rate_spin)
        layout.addWidget(self.note_label)
        layout.addWidget(self.note_edit, 1)

    def _build_panel_layout(self) -> None:
        layout = QGridLayout(self)
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(2)
        for label, text in (
            (self.voucher_label, "Voucher"),
            (self.date_label, "Date"),
            (self.rate_label, "Rate ₹/g"),
            (self.note_label, "Note"),
        ):
            label.setText(text)
        unbounded = 16777215
        self.voucher_edit.setMaximumWidth(unbounded)
        self.date_edit.setMaximumWidth(unbounded)
        self.silver_rate_spin.setMaximumWidth(unbounded)
        self.note_edit.setMinimumWidth(0)

        voucher_row = QHBoxLayout()
        voucher_row.setContentsMargins(0, 0, 0, 0)
        voucher_row.setSpacing(4)
        voucher_row.addWidget(self.voucher_edit, 1)
        voucher_row.addWidget(self.load_button)

        layout.addWidget(self.voucher_label, 0, 0)
        layout.addWidget(self.date_label, 0, 1)
        layout.addLayout(voucher_row, 1, 0)
        layout.addWidget(self.date_edit, 1, 1)
        layout.addWidget(self.rate_label, 2, 0)
        layout.addWidget(self.note_label, 2, 1)
        layout.addWidget(self.silver_rate_spin, 3, 0)
        layout.addWidget(self.note_edit, 3, 1)
        layout.setRowMinimumHeight(4, 6)
        layout.addWidget(self.mode_selector, 5, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def _connect_signals(self) -> None:
        """Connect internal widget signals."""
        self.load_button.clicked.connect(self.load_clicked.emit)
        self.voucher_edit.textChanged.connect(self.voucher_number_changed.emit)
        self.date_edit.dateChanged.connect(self.date_changed.emit)
        self.note_edit.textChanged.connect(self.note_changed.emit)
        self.mode_buttons.idClicked.connect(self.mode_selected.emit)

    # Public methods for data access

    def mode_index(self) -> int:
        return max(0, self.mode_buttons.checkedId())

    def set_mode_index(self, index: int) -> None:
        """Show the active entry mode without emitting ``mode_selected``."""
        button = self.mode_buttons.button(int(index))
        if button is not None and not button.isChecked():
            button.setChecked(True)

    def set_voucher_number(self, number: str) -> None:
        """Set the voucher number.

        Args:
            number: The voucher number to display
        """
        self.voucher_edit.setText(number)

    def show_unsaved_badge(self, show: bool) -> None:
        """Show or hide the unsaved changes badge.

        Args:
            show: True to show, False to hide
        """
        if show:
            self.unsaved_badge.setText("● Unsaved")
            self.unsaved_badge.setProperty("dirty", "true")
        else:
            self.unsaved_badge.setText("● Ready")
            self.unsaved_badge.setProperty("dirty", "false")
        self.unsaved_badge.setVisible(True)
        style = self.unsaved_badge.style()
        style.unpolish(self.unsaved_badge)
        style.polish(self.unsaved_badge)
        self.unsaved_badge.update()
