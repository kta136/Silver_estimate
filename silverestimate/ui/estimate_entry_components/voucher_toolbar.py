"""Voucher toolbar component for estimate entry."""

from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QLocale, QObject, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QButtonGroup,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from silverestimate.ui.themed_controls import ThemedDateEdit

MODE_LABELS = ("Regular", "Return", "Silver Bar")
MODE_SHORTCUT_HINTS = ("", "Ctrl+R", "Ctrl+B")
# Mode-switch labels, widest first; the switch shows the first set that fits.
# The shortcuts are also in each button's tooltip, so the full mode name wins
# over the hint when there is not room for both.
PANEL_MODE_LABELS = (
    ("Regular", "Return  Ctrl+R", "Silver Bar  Ctrl+B"),
    MODE_LABELS,
    ("Regular", "Return", "Bar"),
)


class VoucherToolbar(QWidget):
    """Voucher fields, laid out as the card at the top of the side panel.

    The entry-mode switch and the status badge are created here and placed by
    the owner: the switch below this card, the badge beside Save.
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
        self._rate_companion: QWidget | None = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
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
            # The buttons share whatever width the side panel has and their
            # labels shorten to fit, so the switch never widens the panel.
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            self.mode_buttons.addButton(button, index)
            mode_layout.addWidget(button)
        self.mode_buttons.button(0).setChecked(True)
        self.mode_selector.installEventFilter(self)
        self._fit_mode_labels()

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
        self.date_edit = ThemedDateEdit()
        self.date_edit.setObjectName("EstimateDateEdit")
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        self.date_edit.setDisplayFormat("dd/MM/yyyy  ddd")
        self.date_edit.setToolTip("Estimate date")

        self.rate_label = self._field_label("Rate ₹/g")
        self.silver_rate_spin = QDoubleSpinBox()
        self.silver_rate_spin.setObjectName("SilverRateSpin")
        self.silver_rate_spin.setRange(0, 1000000)
        self.silver_rate_spin.setDecimals(2)
        # Group digits the Indian way, like the totals beside this field.
        self.silver_rate_spin.setLocale(
            QLocale(QLocale.Language.English, QLocale.Country.India)
        )
        self.silver_rate_spin.setGroupSeparatorShown(True)
        self.silver_rate_spin.setValue(0.0)
        self.silver_rate_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.silver_rate_spin.setToolTip("Estimate silver rate in rupees per gram")
        self.silver_rate_spin.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.note_label = self._field_label("Note")
        self.note_edit = QLineEdit()
        self.note_edit.setObjectName("EstimateNoteEdit")
        self.note_edit.setPlaceholderText("Customer, instructions...")
        self.note_edit.setToolTip("Customer name or optional estimate instructions")

        self._build_layout()

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("VoucherFieldLabel")
        return label

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.mode_selector and event.type() == QEvent.Type.Resize:
            self._fit_mode_labels()
        return super().eventFilter(watched, event)

    def _fit_mode_labels(self) -> None:
        layout = self.mode_selector.layout()
        margins = layout.contentsMargins()
        available = (
            self.mode_selector.width()
            - margins.left()
            - margins.right()
            - layout.spacing() * (len(MODE_LABELS) - 1)
        )
        buttons = self.mode_buttons.buttons()
        for labels in PANEL_MODE_LABELS:
            self._set_mode_labels(labels)
            hints = [button.sizeHint().width() for button in buttons]
            if sum(hints) <= available:
                break
        # Share the width in proportion to each label, so a long label is not
        # clipped while a short one has room to spare.
        for index, hint in enumerate(hints):
            layout.setStretch(index, max(1, hint))

    def _set_mode_labels(self, labels: tuple[str, ...]) -> None:
        for index, text in enumerate(labels):
            button = self.mode_buttons.button(index)
            if button.text() != text:
                button.setText(text)

    def _build_layout(self) -> None:
        layout = QGridLayout(self)
        self._grid = layout
        layout.setContentsMargins(8, 7, 8, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(2)

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
        layout.addWidget(self.silver_rate_spin, 3, 0)
        layout.addWidget(self.note_label, 4, 0, 1, 2)
        layout.addWidget(self.note_edit, 5, 0, 1, 2)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)

    def set_rate_companion(self, widget: QWidget) -> None:
        """Show ``widget`` (the live rate) beside the rate field."""
        if widget is self._rate_companion:
            return
        if self._rate_companion is not None:
            self._grid.removeWidget(self._rate_companion)
        self._rate_companion = widget
        self._grid.addWidget(widget, 2, 1, 2, 1)
        widget.show()

    def _connect_signals(self) -> None:
        """Connect internal widget signals."""
        self.load_button.clicked.connect(self.load_clicked.emit)
        self.voucher_edit.textChanged.connect(self.voucher_number_changed.emit)
        self.date_edit.dateChanged.connect(self.date_changed.emit)
        self.note_edit.textChanged.connect(self.note_changed.emit)
        self.note_edit.textChanged.connect(self._sync_note_tooltip)
        self.mode_buttons.idClicked.connect(self.mode_selected.emit)

    def _sync_note_tooltip(self, text: str) -> None:
        """Show the whole note on hover; the field is narrower than a long one."""
        self.note_edit.setToolTip(
            text.strip() or "Customer name or optional estimate instructions"
        )

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
        badge = self.unsaved_badge
        badge.setProperty("dirty", "true" if show else "false")
        badge.setVisible(True)
        style = badge.style()
        style.unpolish(badge)
        style.polish(badge)
        # Hold the width of the longer text so the menu-bar strip beside the
        # badge never gets squeezed when the state flips.
        widths = []
        for text in ("● Ready", "● Unsaved"):
            badge.setText(text)
            widths.append(badge.sizeHint().width())
        badge.setMinimumWidth(max(widths))
        badge.setText("● Unsaved" if show else "● Ready")
        badge.update()
