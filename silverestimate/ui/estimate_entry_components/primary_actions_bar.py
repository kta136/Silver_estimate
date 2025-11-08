"""Primary actions bar component for estimate entry."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QSizePolicy, QWidget, QShortcut


class PrimaryActionsBar(QWidget):
    """Primary action buttons styled to match the classic estimate form."""

    save_clicked = pyqtSignal()
    print_clicked = pyqtSignal()
    new_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None, shortcut_parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._shortcut_parent = shortcut_parent
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface with improved spacing and visual hierarchy."""
        self.setObjectName("PrimaryActionStrip")
        self.setStyleSheet("""
            QWidget#PrimaryActionStrip {
                background-color: palette(base);
                border: 1px solid palette(midlight);
                border-radius: 8px;
            }
            QWidget#PrimaryActionStrip QPushButton {
                font-weight: 600;
                padding: 8px 16px;
                min-width: 110px;
                min-height: 32px;
                font-size: 10pt;
            }
            QWidget#PrimaryActionStrip QPushButton:hover {
                background-color: palette(light);
            }
            QWidget#PrimaryActionStrip QPushButton:disabled {
                color: palette(mid);
            }
        """)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(12)  # Increased from 8
        layout.setContentsMargins(16, 10, 16, 10)  # Increased padding

        # Save button (primary action - will get emphasis later)
        self.save_button = QPushButton("💾 Save")
        self.save_button.setToolTip(
            "Save the current estimate details (Ctrl+S)\n\n"
            "Saves all items and totals to database\n"
            "Required before printing"
        )
        layout.addWidget(self.save_button)

        # Print button
        self.print_button = QPushButton("🖨 Print")
        self.print_button.setToolTip(
            "Preview and print the current estimate (Ctrl+P)\n\n"
            "Requires saving the estimate first\n"
            "Opens print preview dialog"
        )
        layout.addWidget(self.print_button)

        # New button
        self.new_button = QPushButton("📄 New")
        self.new_button.setToolTip(
            "Clear the form to start a new estimate (Ctrl+N)\n\n"
            "Resets all fields and generates new voucher\n"
            "Will ask for confirmation if unsaved changes"
        )
        layout.addWidget(self.new_button)

        layout.addStretch()

    def _setup_shortcuts(self) -> None:
        """Set up keyboard shortcuts.

        NOTE: Ctrl+S and Ctrl+P shortcuts are NOT registered here to avoid
        conflicts with the application-wide menu shortcuts in NavigationController.
        Those are registered as QActions with ApplicationShortcut context.

        Ctrl+N is registered here as it's specific to the estimate entry widget.
        """
        target = self._shortcut_parent if isinstance(self._shortcut_parent, QWidget) else self
        self._shortcuts: list[QShortcut] = []

        # Ctrl+S and Ctrl+P are handled by menu bar (ApplicationShortcut)
        # Only register Ctrl+N here for new estimate
        new_shortcut = QShortcut(QKeySequence("Ctrl+N"), target)
        new_shortcut.setContext(Qt.WindowShortcut)
        new_shortcut.activated.connect(self.new_clicked.emit)
        self._shortcuts.append(new_shortcut)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.print_button.clicked.connect(self.print_clicked.emit)
        self.new_button.clicked.connect(self.new_clicked.emit)
