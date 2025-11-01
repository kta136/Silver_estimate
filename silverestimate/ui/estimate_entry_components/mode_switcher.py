"""Mode switcher component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class ModeSwitcher(QWidget):
    """Component for toggling between Return and Silver Bar entry modes.

    This component provides checkable buttons for Return mode and Silver Bar mode,
    with keyboard shortcuts and mutual exclusivity.
    """

    # Signals
    return_mode_toggled = pyqtSignal(bool)
    silver_bar_mode_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        """Initialize the mode switcher.

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
            QFrame#SecondaryActionStrip {
                background-color: palette(window);
                border: 1px dashed palette(mid);
                border-radius: 8px;
            }
            QFrame#SecondaryActionStrip QPushButton {
                padding: 4px 10px;
            }
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 6, 12, 6)

        # Mode indicator label (for EstimateLogic compatibility)
        self.mode_label = QLabel("Mode: Regular")
        self.mode_label.setStyleSheet("""
            font-weight: bold;
            color: palette(windowText);
            background-color: palette(window);
            border: 1px solid palette(mid);
            border-radius: 3px;
            padding: 2px 6px;
        """)
        self.mode_label.setVisible(False)  # Hidden by default, toolbar has its own
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

        layout.addStretch()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
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

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.return_toggle_button.toggled.connect(self._on_return_toggled)
        self.silver_bar_toggle_button.toggled.connect(self._on_silver_bar_toggled)

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
