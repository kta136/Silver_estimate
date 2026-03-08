"""Secondary actions bar component for estimate entry."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QShortcut,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from silverestimate.ui.icons import get_icon


class SecondaryActionsBar(QWidget):
    """Complete secondary actions bar with all estimate entry controls.

    This component provides:
    - Delete Row button
    - Return mode and Silver Bar mode toggles
    - Last Balance button
    - Estimate History button
    - Manage Silver Bars button
    - Delete Estimate button
    - Live Silver Rate display with refresh button
    """

    # Signals
    delete_row_clicked = pyqtSignal()
    return_mode_toggled = pyqtSignal(bool)
    silver_bar_mode_toggled = pyqtSignal(bool)
    last_balance_clicked = pyqtSignal()
    history_clicked = pyqtSignal()
    silver_bars_clicked = pyqtSignal()
    refresh_rate_clicked = pyqtSignal()
    delete_estimate_clicked = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        shortcut_parent: Optional[QWidget] = None,
    ):
        """Initialize the secondary actions bar.

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
        """Set up the user interface with compact spacing."""
        self.setObjectName("SecondaryActionStrip")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(4, 4, 4, 4)
        self._main_layout = layout

        self._left_actions_layout = QHBoxLayout()
        self._left_actions_layout.setSpacing(3)
        self._left_actions_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._left_actions_layout)

        layout.addStretch(1)

        self._right_actions_layout = QHBoxLayout()
        self._right_actions_layout.setSpacing(4)
        self._right_actions_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self._right_actions_layout)

        # Delete Row button
        self.delete_row_button = QPushButton()
        self.delete_row_button.setObjectName("DeleteRowButton")
        self.delete_row_button.setIcon(
            get_icon("delete_row", widget=self, color="#dc2626")
        )
        self._configure_icon_button(self.delete_row_button, label="Delete Row")
        self.delete_row_button.setToolTip(
            "Delete the currently selected row\n"
            "Keyboard: Ctrl+D\n"
            "Removes the active row from the estimate\n"
            "Cannot be undone"
        )
        self._left_actions_layout.addWidget(self.delete_row_button)
        self._left_actions_layout.addWidget(self._create_divider())

        # Return mode toggle
        self.return_toggle_button = QPushButton()
        self.return_toggle_button.setObjectName("ReturnModeButton")
        self.return_toggle_button.setIcon(
            get_icon("return_mode", widget=self, color="#2563eb")
        )
        self._configure_icon_button(self.return_toggle_button, label="Return")
        self.return_toggle_button.setToolTip(
            "Toggle Return Item entry mode for new rows\n"
            "Keyboard: Ctrl+R\n"
            "New rows will be marked as Return items\n"
            "Affects calculations and item type"
        )
        self.return_toggle_button.setCheckable(True)
        self._left_actions_layout.addWidget(self.return_toggle_button)

        # Silver bar mode toggle
        self.silver_bar_toggle_button = QPushButton()
        self.silver_bar_toggle_button.setObjectName("SilverBarModeButton")
        self.silver_bar_toggle_button.setIcon(
            get_icon("bar_mode", widget=self, color="#0f766e")
        )
        self._configure_icon_button(self.silver_bar_toggle_button, label="Bar Mode")
        self.silver_bar_toggle_button.setToolTip(
            "Toggle Silver Bar entry mode for new rows\n"
            "Keyboard: Ctrl+B\n"
            "New rows will be marked as Silver Bar items\n"
            "Cannot use both Return and Silver Bar modes"
        )
        self.silver_bar_toggle_button.setCheckable(True)
        self._left_actions_layout.addWidget(self.silver_bar_toggle_button)

        self._left_actions_layout.addWidget(self._create_divider())

        # Last Balance button
        self.last_balance_button = QToolButton()
        self.last_balance_button.setObjectName("BalanceButton")
        self.last_balance_button.setIcon(get_icon("balance", widget=self))
        self._configure_icon_button(self.last_balance_button, label="Balance")
        self.last_balance_button.setToolTip(
            "Add Last Balance to this estimate\n"
            "Adds previous unpaid balance\n"
            "Useful for ongoing customer accounts\n"
            "Will show dialog if multiple balances available"
        )
        self.last_balance_button.setAutoRaise(True)
        self._left_actions_layout.addWidget(self.last_balance_button)

        # Estimate history button
        self.history_button = QToolButton()
        self.history_button.setObjectName("HistoryButton")
        self.history_button.setIcon(get_icon("history", widget=self))
        self._configure_icon_button(self.history_button, label="History")
        self.history_button.setToolTip(
            "View, load, or print past estimates\n"
            "Keyboard: Ctrl+H\n"
            "Browse all saved estimates\n"
            "Double-click to load an estimate"
        )
        self.history_button.setAutoRaise(True)
        self._left_actions_layout.addWidget(self.history_button)

        # Manage Silver Bars button
        self.silver_bars_button = QToolButton()
        self.silver_bars_button.setObjectName("BarListButton")
        self.silver_bars_button.setIcon(get_icon("silver_bars", widget=self))
        self._configure_icon_button(self.silver_bars_button, label="Bar List")
        self.silver_bars_button.setToolTip(
            "View and manage silver bar inventory\n"
            "Add, edit, or assign silver bars\n"
            "Track bar usage across estimates\n"
            "Manage bar transfers"
        )
        self.silver_bars_button.setAutoRaise(True)
        self._left_actions_layout.addWidget(self.silver_bars_button)

        # Live rate value and meta info in vertical layout
        self.live_rate_container = QWidget()
        self.live_rate_container.setObjectName("LiveRateCard")
        self.live_rate_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        rate_layout = QHBoxLayout(self.live_rate_container)
        rate_layout.setContentsMargins(6, 5, 6, 5)
        rate_layout.setSpacing(4)

        left_stack = QVBoxLayout()
        left_stack.setContentsMargins(0, 0, 0, 0)
        left_stack.setSpacing(0)

        value_row = QHBoxLayout()
        value_row.setContentsMargins(0, 0, 0, 0)
        value_row.setSpacing(4)

        self.live_rate_value_label = QLabel("…")
        self.live_rate_value_label.setObjectName("LiveRateValue")
        self.live_rate_value_label.setMinimumWidth(96)
        self.live_rate_value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        rate_layout.addWidget(self.live_rate_value_label)

        self.refresh_rate_button = QToolButton()
        self.refresh_rate_button.setToolTip("Refresh live silver rate and set it here")
        self.refresh_rate_button.setIcon(
            get_icon("refresh", widget=self, color="#0f766e")
        )
        self._configure_icon_button(self.refresh_rate_button, label="Refresh Silver Rate")
        self.refresh_rate_button.setAutoRaise(True)
        self.refresh_rate_button.setCursor(Qt.PointingHandCursor)
        self.refresh_rate_button.setAccessibleName("Refresh Silver Rate")
        value_row.addWidget(self.refresh_rate_button)

        left_stack.addLayout(value_row)

        self.live_rate_meta_label = QLabel("")
        self.live_rate_meta_label.setObjectName("LiveRateMeta")
        self.live_rate_meta_label.setAccessibleName("Live Rate Status")
        self.live_rate_meta_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        left_stack.addWidget(self.live_rate_meta_label)

        rate_layout.addLayout(left_stack)

        self._right_actions_layout.addWidget(self.live_rate_container)
        self.live_rate_divider = self._create_divider()
        self._right_actions_layout.addWidget(self.live_rate_divider)

        # Delete estimate button (isolated on the far right as destructive action)
        self.delete_estimate_button = QToolButton()
        self.delete_estimate_button.setObjectName("DeleteEstimateButton")
        self.delete_estimate_button.setIcon(
            get_icon("delete_estimate", widget=self, color="#dc2626")
        )
        self._configure_icon_button(
            self.delete_estimate_button,
            label="Delete Estimate",
        )
        self.delete_estimate_button.setToolTip(
            "Delete the currently loaded estimate\n"
            "Permanently removes estimate from database\n"
            "Only enabled when estimate is loaded\n"
            "Cannot be undone - use with caution"
        )
        self.delete_estimate_button.setEnabled(False)
        self.delete_estimate_button.setAutoRaise(False)
        self._right_actions_layout.addWidget(self.delete_estimate_button)

    def show_live_rate_in_header(self, show_divider: bool = True) -> None:
        """Ensure live-rate card is attached in the header action strip."""
        layout = getattr(self, "_right_actions_layout", None)
        if not isinstance(layout, QHBoxLayout):
            return
        if getattr(self, "live_rate_container", None) is None:
            return
        if getattr(self, "live_rate_divider", None) is None:
            return
        if getattr(self, "delete_estimate_button", None) is None:
            return

        insert_index = layout.indexOf(self.delete_estimate_button)
        if insert_index < 0:
            insert_index = layout.count()

        if layout.indexOf(self.live_rate_container) == -1:
            layout.insertWidget(insert_index, self.live_rate_container)
            insert_index += 1
        if layout.indexOf(self.live_rate_divider) == -1:
            layout.insertWidget(insert_index, self.live_rate_divider)

        self.live_rate_divider.setVisible(bool(show_divider))

    def _create_divider(self) -> QFrame:
        """Create a vertical divider line.

        Returns:
            QFrame configured as a vertical line divider
        """
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setFixedHeight(18)
        return divider

    @staticmethod
    def _configure_icon_button(
        button: QPushButton | QToolButton,
        *,
        label: str,
    ) -> None:
        button.setAccessibleName(label)
        if button.icon().isNull():
            button.setText(label)
            button.setProperty("iconOnly", False)
            return
        button.setText("")
        button.setProperty("iconOnly", True)
        button.setIconSize(QSize(18, 18))

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
        delete_row_shortcut.setContext(Qt.WindowShortcut)
        delete_row_shortcut.activated.connect(self.delete_row_clicked.emit)
        self._shortcuts.append(delete_row_shortcut)

        return_shortcut = QShortcut(QKeySequence("Ctrl+R"), target)
        return_shortcut.setContext(Qt.WindowShortcut)
        return_shortcut.activated.connect(self._toggle_return_mode)
        self._shortcuts.append(return_shortcut)

        silver_bar_shortcut = QShortcut(QKeySequence("Ctrl+B"), target)
        silver_bar_shortcut.setContext(Qt.WindowShortcut)
        silver_bar_shortcut.activated.connect(self._toggle_silver_bar_mode)
        self._shortcuts.append(silver_bar_shortcut)

        history_shortcut = QShortcut(QKeySequence("Ctrl+H"), target)
        history_shortcut.setContext(Qt.WindowShortcut)
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

    def set_return_mode(self, enabled: bool) -> None:
        """Set the return mode state.

        Args:
            enabled: True to enable return mode, False to disable
        """
        self.return_toggle_button.setChecked(enabled)

    def set_silver_bar_mode(self, enabled: bool) -> None:
        """Set the silver bar mode state.

        Args:
            enabled: True to enable silver bar mode, False to disable
        """
        self.silver_bar_toggle_button.setChecked(enabled)

    def get_return_mode(self) -> bool:
        """Get the return mode state.

        Returns:
            True if return mode is enabled, False otherwise
        """
        return self.return_toggle_button.isChecked()

    def get_silver_bar_mode(self) -> bool:
        """Get the silver bar mode state.

        Returns:
            True if silver bar mode is enabled, False otherwise
        """
        return self.silver_bar_toggle_button.isChecked()

    def reset_modes(self) -> None:
        """Reset both modes to disabled state."""
        self.return_toggle_button.setChecked(False)
        self.silver_bar_toggle_button.setChecked(False)

    def enable_delete_estimate(self, enabled: bool) -> None:
        """Enable or disable the delete estimate button."""
        self.delete_estimate_button.setEnabled(enabled)
