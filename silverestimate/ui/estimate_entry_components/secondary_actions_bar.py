"""Secondary actions for estimate entry: their buttons, shortcuts and signals."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.icons import get_icon


class SecondaryActionsBar(QWidget):
    """Owns the estimate screen's secondary actions.

    It creates the buttons, the live-rate field and the keyboard shortcuts, and
    relays them as signals. The side panel shows the buttons and the field;
    this widget itself is never shown, and only keeps the two entry-mode
    toggles, which the mode switch and the shortcuts drive.
    """

    # Signals
    delete_row_clicked = Signal()
    last_balance_clicked = Signal()
    history_clicked = Signal()
    silver_bars_clicked = Signal()
    refresh_rate_clicked = Signal()
    delete_estimate_clicked = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        shortcut_parent: Optional[QWidget] = None,
    ):
        """Initialize the secondary actions.

        Args:
            parent: Optional parent widget.
            shortcut_parent: Optional widget that should own the shortcuts. When
                provided, keyboard shortcuts are bound to that container so they
                work regardless of which child has focus.
        """
        super().__init__(parent)
        self._shortcut_parent = shortcut_parent
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.delete_row_button = QPushButton("Delete Row", self)
        self.delete_row_button.setObjectName("DeleteRowButton")
        self.delete_row_button.setAccessibleName("Delete Row")
        self.delete_row_button.setToolTip(
            "Delete the currently selected row\n"
            "Keyboard: Ctrl+D\n"
            "Removes the active row from the estimate\n"
            "Cannot be undone"
        )

        # The entry-mode toggles hold the state; the mode switch shows it.
        self.return_toggle_button = QPushButton(self)
        self.return_toggle_button.setObjectName("ReturnModeButton")
        self.return_toggle_button.setAccessibleName("Return")
        self.return_toggle_button.setCheckable(True)

        self.silver_bar_toggle_button = QPushButton(self)
        self.silver_bar_toggle_button.setObjectName("SilverBarModeButton")
        self.silver_bar_toggle_button.setAccessibleName("Bar Mode")
        self.silver_bar_toggle_button.setCheckable(True)

        self.last_balance_button = QToolButton(self)
        self.last_balance_button.setObjectName("BalanceButton")
        self.last_balance_button.setText("Last Balance")
        self.last_balance_button.setAccessibleName("Balance")
        self.last_balance_button.setToolTip(
            "Add Last Balance to this estimate\n"
            "Adds previous unpaid balance\n"
            "Useful for ongoing customer accounts\n"
            "Will show dialog if multiple balances available"
        )
        self.last_balance_button.setAutoRaise(True)

        self.history_button = QToolButton(self)
        self.history_button.setObjectName("HistoryButton")
        self.history_button.setText("History  Ctrl+H")
        self.history_button.setAccessibleName("History")
        self.history_button.setToolTip(
            "View, load, or print past estimates\n"
            "Keyboard: Ctrl+H\n"
            "Browse all saved estimates\n"
            "Double-click to load an estimate"
        )
        self.history_button.setAutoRaise(True)

        self.silver_bars_button = QToolButton(self)
        self.silver_bars_button.setObjectName("BarListButton")
        self.silver_bars_button.setText("Silver Bars")
        self.silver_bars_button.setAccessibleName("Bar List")
        self.silver_bars_button.setToolTip(
            "View and manage silver bar inventory\n"
            "Add, edit, or assign silver bars\n"
            "Track bar usage across estimates\n"
            "Manage bar transfers"
        )
        self.silver_bars_button.setAutoRaise(True)

        self.delete_estimate_button = QToolButton(self)
        self.delete_estimate_button.setObjectName("DeleteEstimateButton")
        self.delete_estimate_button.setText("Delete Estimate")
        self.delete_estimate_button.setAccessibleName("Delete Estimate")
        self.delete_estimate_button.setToolTip(
            "Delete the currently loaded estimate\n"
            "Permanently removes estimate from database\n"
            "Only enabled when estimate is loaded\n"
            "Cannot be undone - use with caution"
        )
        self.delete_estimate_button.setEnabled(False)
        self.delete_estimate_button.setAutoRaise(False)

        for button in (
            self.delete_row_button,
            self.last_balance_button,
            self.history_button,
            self.silver_bars_button,
            self.delete_estimate_button,
        ):
            self.fit_panel_button(button)

        self._setup_live_rate_field()

    @staticmethod
    def fit_panel_button(button: QAbstractButton) -> None:
        """Size a text button for the side panel's two-column grid."""
        if isinstance(button, QToolButton):
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setMinimumSize(0, 30)
        # Two equal buttons share each row; never let them push the side
        # panel wider than its splitter pane.
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

    def _setup_live_rate_field(self) -> None:
        """Build the live rate: "Live rate  2 min ago" over "128.40  [refresh]".

        It is the height of a labelled form field and sits beside the rate.
        """
        self.live_rate_container = QWidget(self)
        self.live_rate_container.setObjectName("LiveRateCard")
        self.live_rate_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.live_rate_title_label = QLabel("Live rate")
        self.live_rate_title_label.setObjectName("VoucherFieldLabel")

        self.live_rate_value_label = QLabel("Loading…")
        self.live_rate_value_label.setObjectName("LiveRateValue")
        self.live_rate_value_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.live_rate_value_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        rate_font = self.live_rate_value_label.font()
        rate_font.setBold(True)
        self.live_rate_value_label.setFont(rate_font)

        self.refresh_rate_button = QToolButton()
        self.refresh_rate_button.setObjectName("RefreshRateButton")
        self.refresh_rate_button.setToolTip("Refresh live silver rate and set it here")
        self.refresh_rate_button.setIcon(
            get_icon("refresh", widget=self, color="#007f89")
        )
        self.refresh_rate_button.setIconSize(QSize(14, 14))
        self.refresh_rate_button.setFixedSize(QSize(28, 24))
        self.refresh_rate_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.refresh_rate_button.setAutoRaise(True)
        self.refresh_rate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_rate_button.setAccessibleName("Refresh Silver Rate")

        self.live_rate_meta_label = QLabel("Not updated")
        self.live_rate_meta_label.setObjectName("LiveRateMeta")
        self.live_rate_meta_label.setAccessibleName("Live Rate Status")
        self.live_rate_meta_label.setMinimumWidth(0)
        self.live_rate_meta_label.setMaximumWidth(125)
        self.live_rate_meta_label.setWordWrap(False)
        self.live_rate_meta_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout = QVBoxLayout(self.live_rate_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(4)
        top.addWidget(self.live_rate_title_label)
        top.addWidget(self.live_rate_meta_label, 1)
        bottom = QHBoxLayout()
        bottom.setSpacing(4)
        bottom.addWidget(self.live_rate_value_label, 1)
        bottom.addWidget(self.refresh_rate_button)
        layout.addLayout(top)
        layout.addLayout(bottom)

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts.

        Uses WindowShortcut context so shortcuts work even when table cells
        are being edited (cell editors are not considered children in Qt's
        shortcut propagation).
        """
        target = (
            self._shortcut_parent
            if isinstance(self._shortcut_parent, QWidget)
            else self
        )
        self._shortcuts: list[QShortcut] = []

        delete_row_shortcut = QShortcut(QKeySequence("Ctrl+D"), target)
        delete_row_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        delete_row_shortcut.activated.connect(self.delete_row_clicked.emit)
        self._shortcuts.append(delete_row_shortcut)

        return_shortcut = QShortcut(QKeySequence("Ctrl+R"), target)
        return_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        return_shortcut.activated.connect(self._toggle_return_mode)
        self._shortcuts.append(return_shortcut)

        silver_bar_shortcut = QShortcut(QKeySequence("Ctrl+B"), target)
        silver_bar_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        silver_bar_shortcut.activated.connect(self._toggle_silver_bar_mode)
        self._shortcuts.append(silver_bar_shortcut)

        history_shortcut = QShortcut(QKeySequence("Ctrl+H"), target)
        history_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        history_shortcut.activated.connect(self.history_clicked.emit)
        self._shortcuts.append(history_shortcut)

    def _connect_signals(self) -> None:
        """Connect internal signals.

        Note: Return and Silver Bar mode toggle buttons are NOT connected here.
        They are connected directly to the mixin toggle methods in estimate_entry.py
        to avoid signal routing conflicts.
        """
        self.delete_row_button.clicked.connect(self.delete_row_clicked.emit)
        # NOTE: return_toggle_button and silver_bar_toggle_button are connected externally
        self.last_balance_button.clicked.connect(self.last_balance_clicked.emit)
        self.history_button.clicked.connect(self.history_clicked.emit)
        self.silver_bars_button.clicked.connect(self.silver_bars_clicked.emit)
        self.refresh_rate_button.clicked.connect(self.refresh_rate_clicked.emit)
        self.delete_estimate_button.clicked.connect(self.delete_estimate_clicked.emit)

    def _toggle_return_mode(self) -> None:
        """Toggle return mode state (called by keyboard shortcut)."""
        if self.return_toggle_button.isEnabled():
            # Use click so downstream handlers wired to clicked() also run
            self.return_toggle_button.click()

    def _toggle_silver_bar_mode(self) -> None:
        """Toggle silver bar mode state (called by keyboard shortcut)."""
        if self.silver_bar_toggle_button.isEnabled():
            self.silver_bar_toggle_button.click()

    # Public methods

    def enable_delete_estimate(self, enabled: bool) -> None:
        """Enable or disable the delete estimate button."""
        self.delete_estimate_button.setEnabled(enabled)
