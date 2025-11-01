"""Secondary actions bar component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class SecondaryActionsBar(QWidget):
    """Complete secondary actions bar with all estimate entry controls.

    This component provides:
    - Delete Row button
    - Return mode and Silver Bar mode toggles
    - Last Balance button
    - Estimate History button (moved from toolbar)
    - Manage Silver Bars button
    - Delete This Estimate button (moved from toolbar)
    - Live Silver Rate display with refresh button
    """

    # Signals
    delete_row_clicked = pyqtSignal()
    return_mode_toggled = pyqtSignal(bool)
    silver_bar_mode_toggled = pyqtSignal(bool)
    last_balance_clicked = pyqtSignal()
    history_clicked = pyqtSignal()
    silver_bars_clicked = pyqtSignal()
    delete_estimate_clicked = pyqtSignal()
    refresh_rate_clicked = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the secondary actions bar.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setObjectName("SecondaryActionStrip")
        self.setStyleSheet("""
            QWidget#SecondaryActionStrip {
                background-color: palette(window);
                border: 1px dashed palette(mid);
                border-radius: 8px;
            }
            QWidget#SecondaryActionStrip QPushButton {
                padding: 4px 10px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 6, 12, 6)

        # Delete Row button
        self.delete_row_button = QPushButton("Delete Row")
        self.delete_row_button.setToolTip(
            "Delete the currently selected row\n"
            "Keyboard: Ctrl+D\n"
            "Removes the active row from the estimate\n"
            "Cannot be undone"
        )
        layout.addWidget(self.delete_row_button)
        layout.addWidget(self._create_divider())

        # Mode indicator label (hidden, for EstimateLogic compatibility)
        self.mode_label = QLabel("Mode: Regular")
        self.mode_label.setStyleSheet("""
            font-weight: bold;
            color: palette(windowText);
            background-color: palette(window);
            border: 1px solid palette(mid);
            border-radius: 3px;
            padding: 2px 6px;
        """)
        self.mode_label.setVisible(False)  # Hidden, toolbar has visible one
        layout.addWidget(self.mode_label)

        # Return mode toggle
        self.return_toggle_button = QPushButton("↩ Return Items")
        self.return_toggle_button.setToolTip(
            "Toggle Return Item entry mode for new rows\n"
            "Keyboard: Ctrl+R\n"
            "New rows will be marked as Return items\n"
            "Affects calculations and item type"
        )
        self.return_toggle_button.setCheckable(True)
        self.return_toggle_button.setMaximumWidth(150)
        self.return_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 4px;
                font-weight: normal;
                color: palette(buttonText);
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: palette(light);
            }
            QPushButton:checked {
                background-color: #fef3c7;
                border: 2px solid #f59e0b;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.return_toggle_button)

        # Silver bar mode toggle
        self.silver_bar_toggle_button = QPushButton("🥈 Silver Bars")
        self.silver_bar_toggle_button.setToolTip(
            "Toggle Silver Bar entry mode for new rows\n"
            "Keyboard: Ctrl+B\n"
            "New rows will be marked as Silver Bar items\n"
            "Cannot use both Return and Silver Bar modes"
        )
        self.silver_bar_toggle_button.setCheckable(True)
        self.silver_bar_toggle_button.setMaximumWidth(150)
        self.silver_bar_toggle_button.setStyleSheet("""
            QPushButton {
                background-color: palette(button);
                border: 1px solid palette(mid);
                border-radius: 4px;
                font-weight: normal;
                color: palette(buttonText);
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: palette(light);
            }
            QPushButton:checked {
                background-color: #e0e7ff;
                border: 2px solid #6366f1;
                font-weight: bold;
            }
        """)
        layout.addWidget(self.silver_bar_toggle_button)

        # Backward compatibility aliases
        self.return_button = self.return_toggle_button
        self.silver_bar_button = self.silver_bar_toggle_button

        layout.addWidget(self._create_divider())

        # Last Balance button
        self.last_balance_button = QPushButton("LB")
        self.last_balance_button.setToolTip(
            "Add Last Balance to this estimate\n"
            "Adds previous unpaid balance\n"
            "Useful for ongoing customer accounts\n"
            "Will show dialog if multiple balances available"
        )
        layout.addWidget(self.last_balance_button)

        layout.addWidget(self._create_divider())

        # History button (moved from toolbar to match original UI)
        self.history_button = QPushButton("Estimate History")
        self.history_button.setToolTip(
            "View, load, or print past estimates\n"
            "Keyboard: Ctrl+H\n"
            "Browse all saved estimates\n"
            "Double-click to load an estimate"
        )
        layout.addWidget(self.history_button)

        # Manage Silver Bars button
        self.silver_bars_button = QPushButton("Manage Silver Bars")
        self.silver_bars_button.setToolTip(
            "View and manage silver bar inventory\n"
            "Add, edit, or assign silver bars\n"
            "Track bar usage across estimates\n"
            "Manage bar transfers"
        )
        layout.addWidget(self.silver_bars_button)

        layout.addWidget(self._create_divider())

        # Delete This Estimate button (moved from toolbar)
        self.delete_estimate_button = QPushButton("Delete This Estimate")
        self.delete_estimate_button.setToolTip(
            "Delete the currently loaded estimate\n"
            "Permanently removes estimate from database\n"
            "Only enabled when estimate is loaded\n"
            "Cannot be undone - use with caution"
        )
        self.delete_estimate_button.setEnabled(False)
        layout.addWidget(self.delete_estimate_button)

        layout.addStretch()

        # Live rate display (read-only)
        self.live_rate_label = QLabel("Live Silver Rate:")
        self.live_rate_label.setToolTip("Latest rate fetched from DDASilver.com (read-only)")
        self.live_rate_label.setStyleSheet("font-weight: 600; color: #222;")
        layout.addWidget(self.live_rate_label)

        # Live rate value and meta info in vertical layout
        rate_container = QWidget()
        rate_layout = QVBoxLayout(rate_container)
        rate_layout.setContentsMargins(0, 0, 0, 0)
        rate_layout.setSpacing(2)

        self.live_rate_value_label = QLabel("…")
        self.live_rate_value_label.setObjectName("LiveRateValue")
        self.live_rate_value_label.setStyleSheet("""
            QLabel#LiveRateValue {
                color: #0f172a;
                background-color: #e6f0ff;
                border: 1px solid #93c5fd;
                border-radius: 10px;
                padding: 2px 8px;
                font-weight: 700;
                font-size: 11pt;
            }
        """)
        self.live_rate_value_label.setMinimumWidth(110)
        self.live_rate_value_label.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        rate_layout.addWidget(self.live_rate_value_label)

        self.live_rate_meta_label = QLabel("Waiting…")
        self.live_rate_meta_label.setObjectName("LiveRateMeta")
        self.live_rate_meta_label.setAccessibleName("Live Rate Status")
        self.live_rate_meta_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.live_rate_meta_label.setStyleSheet("color: #475569; font-size: 9pt;")
        rate_layout.addWidget(self.live_rate_meta_label)

        layout.addWidget(rate_container)

        # Refresh rate button
        self.refresh_rate_button = QToolButton()
        self.refresh_rate_button.setToolTip("Refresh live silver rate and set it here")
        self.refresh_rate_button.setIcon(
            self.style().standardIcon(QStyle.SP_BrowserReload)
        )
        self.refresh_rate_button.setAutoRaise(True)
        self.refresh_rate_button.setCursor(Qt.PointingHandCursor)
        self.refresh_rate_button.setAccessibleName("Refresh Silver Rate")
        layout.addWidget(self.refresh_rate_button)

    def _create_divider(self) -> QFrame:
        """Create a vertical divider line.

        Returns:
            QFrame configured as a vertical line divider
        """
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Sunken)
        divider.setFixedHeight(28)
        return divider

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # Delete row shortcut (Ctrl+D)
        delete_row_action = QAction("Delete Row", self)
        delete_row_action.setShortcut("Ctrl+D")
        delete_row_action.triggered.connect(self.delete_row_clicked.emit)
        self.addAction(delete_row_action)

        # Return mode shortcut (Ctrl+R)
        return_action = QAction("Toggle Return Mode", self)
        return_action.setShortcut("Ctrl+R")
        return_action.triggered.connect(self._toggle_return_mode)
        self.addAction(return_action)

        # Silver bar mode shortcut (Ctrl+B)
        silver_bar_action = QAction("Toggle Silver Bar Mode", self)
        silver_bar_action.setShortcut("Ctrl+B")
        silver_bar_action.triggered.connect(self._toggle_silver_bar_mode)
        self.addAction(silver_bar_action)

        # History shortcut (Ctrl+H)
        history_action = QAction("Show History", self)
        history_action.setShortcut("Ctrl+H")
        history_action.triggered.connect(self.history_clicked.emit)
        self.addAction(history_action)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.delete_row_button.clicked.connect(self.delete_row_clicked.emit)
        self.return_toggle_button.toggled.connect(self._on_return_toggled)
        self.silver_bar_toggle_button.toggled.connect(self._on_silver_bar_toggled)
        self.last_balance_button.clicked.connect(self.last_balance_clicked.emit)
        self.history_button.clicked.connect(self.history_clicked.emit)
        self.silver_bars_button.clicked.connect(self.silver_bars_clicked.emit)
        self.delete_estimate_button.clicked.connect(self.delete_estimate_clicked.emit)
        self.refresh_rate_button.clicked.connect(self.refresh_rate_clicked.emit)

    def _toggle_return_mode(self) -> None:
        """Toggle return mode state."""
        self.return_toggle_button.setChecked(not self.return_toggle_button.isChecked())

    def _toggle_silver_bar_mode(self) -> None:
        """Toggle silver bar mode state."""
        self.silver_bar_toggle_button.setChecked(not self.silver_bar_toggle_button.isChecked())

    def _on_return_toggled(self, checked: bool) -> None:
        """Handle return mode toggle.

        Args:
            checked: True if return mode is enabled
        """
        # If enabling return mode, disable silver bar mode
        if checked and self.silver_bar_toggle_button.isChecked():
            self.silver_bar_toggle_button.setChecked(False)

        self.return_mode_toggled.emit(checked)

    def _on_silver_bar_toggled(self, checked: bool) -> None:
        """Handle silver bar mode toggle.

        Args:
            checked: True if silver bar mode is enabled
        """
        # If enabling silver bar mode, disable return mode
        if checked and self.return_toggle_button.isChecked():
            self.return_toggle_button.setChecked(False)

        self.silver_bar_mode_toggled.emit(checked)

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
        """Enable or disable the delete estimate button.

        Args:
            enabled: True to enable, False to disable
        """
        self.delete_estimate_button.setEnabled(enabled)
