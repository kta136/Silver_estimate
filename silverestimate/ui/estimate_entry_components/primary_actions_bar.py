"""Primary actions bar component for estimate entry."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAction,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class PrimaryActionsBar(QWidget):
    """Primary action buttons for estimate entry.

    This component provides the main action buttons:
    - Save: Save the current estimate
    - Print: Print the estimate
    - New: Create a new estimate
    - Delete This Estimate: Delete the currently loaded estimate
    - Estimate History: View past estimates
    """

    # Signals
    save_clicked = pyqtSignal()
    print_clicked = pyqtSignal()
    new_clicked = pyqtSignal()
    delete_estimate_clicked = pyqtSignal()
    history_clicked = pyqtSignal()

    def __init__(self, parent=None):
        """Initialize the primary actions bar.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        self.setObjectName("PrimaryActionStrip")
        self.setStyleSheet("""
            QWidget#PrimaryActionStrip {
                background-color: #f0f9ff;
                border: 2px solid #0ea5e9;
                border-radius: 8px;
            }
            QWidget#PrimaryActionStrip QPushButton {
                background-color: #0284c7;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 600;
                min-width: 80px;
            }
            QWidget#PrimaryActionStrip QPushButton:hover {
                background-color: #0369a1;
            }
            QWidget#PrimaryActionStrip QPushButton:pressed {
                background-color: #075985;
            }
            QWidget#PrimaryActionStrip QPushButton:disabled {
                background-color: #cbd5e1;
                color: #94a3b8;
            }
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 8, 12, 8)

        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.setToolTip(
            "Save the current estimate\n"
            "Keyboard: Ctrl+S\n"
            "Creates new estimate or updates existing one"
        )
        layout.addWidget(self.save_button)

        # Print button
        self.print_button = QPushButton("Print")
        self.print_button.setToolTip(
            "Print the current estimate\n"
            "Keyboard: Ctrl+P\n"
            "Opens print preview dialog"
        )
        layout.addWidget(self.print_button)

        # New button
        self.new_button = QPushButton("New")
        self.new_button.setToolTip(
            "Create a new estimate\n"
            "Keyboard: Ctrl+N\n"
            "Clears current estimate and starts fresh"
        )
        layout.addWidget(self.new_button)

        # Delete This Estimate button
        self.delete_estimate_button = QPushButton("Delete This Estimate")
        self.delete_estimate_button.setToolTip(
            "Delete the currently loaded estimate\n"
            "Permanently removes estimate from database\n"
            "Only enabled when estimate is loaded\n"
            "Cannot be undone - use with caution"
        )
        self.delete_estimate_button.setEnabled(False)
        layout.addWidget(self.delete_estimate_button)

        # Estimate History button
        self.history_button = QPushButton("Estimate History")
        self.history_button.setToolTip(
            "View, load, or print past estimates\n"
            "Keyboard: Ctrl+H\n"
            "Browse all saved estimates\n"
            "Double-click to load an estimate"
        )
        layout.addWidget(self.history_button)

        layout.addStretch()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts."""
        # Save shortcut (Ctrl+S)
        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_clicked.emit)
        self.addAction(save_action)

        # Print shortcut (Ctrl+P)
        print_action = QAction("Print", self)
        print_action.setShortcut("Ctrl+P")
        print_action.triggered.connect(self.print_clicked.emit)
        self.addAction(print_action)

        # New shortcut (Ctrl+N)
        new_action = QAction("New", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_clicked.emit)
        self.addAction(new_action)

        # History shortcut (Ctrl+H)
        history_action = QAction("Show History", self)
        history_action.setShortcut("Ctrl+H")
        history_action.triggered.connect(self.history_clicked.emit)
        self.addAction(history_action)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.print_button.clicked.connect(self.print_clicked.emit)
        self.new_button.clicked.connect(self.new_clicked.emit)
        self.delete_estimate_button.clicked.connect(self.delete_estimate_clicked.emit)
        self.history_button.clicked.connect(self.history_clicked.emit)

    # Public methods

    def enable_delete_estimate(self, enabled: bool) -> None:
        """Enable or disable the delete estimate button.

        Args:
            enabled: True to enable, False to disable
        """
        self.delete_estimate_button.setEnabled(enabled)
