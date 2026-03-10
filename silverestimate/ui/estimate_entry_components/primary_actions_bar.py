"""Primary actions bar component for estimate entry."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QHBoxLayout, QPushButton, QShortcut, QSizePolicy, QWidget

from silverestimate.ui.icons import get_icon


class PrimaryActionsBar(QWidget):
    """Primary action buttons styled to match the classic estimate form."""

    save_clicked = pyqtSignal()
    print_clicked = pyqtSignal()
    new_clicked = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        shortcut_parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._shortcut_parent = shortcut_parent
        self._setup_ui()
        self._setup_shortcuts()
        self._connect_signals()

    def _setup_ui(self) -> None:
        """Set up the user interface with compact spacing."""
        self.setObjectName("PrimaryActionStrip")
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        layout = QHBoxLayout(self)
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)

        # Save button (primary action - will get emphasis later)
        self.save_button = QPushButton()
        self.save_button.setObjectName("SavePrimaryButton")
        self.save_button.setIcon(get_icon("save", widget=self, color="#ffffff"))
        self._configure_icon_button(self.save_button, label="Save")
        self.save_button.setToolTip(
            "Save the current estimate details (Ctrl+S)\n\n"
            "Saves all items and totals to database\n"
            "Required before printing"
        )
        layout.addWidget(self.save_button)

        # Print button
        self.print_button = QPushButton()
        self.print_button.setObjectName("PrintPrimaryButton")
        self.print_button.setIcon(get_icon("print_estimate", widget=self))
        self._configure_icon_button(self.print_button, label="Print")
        self.print_button.setToolTip(
            "Preview and print the current estimate (Ctrl+P)\n\n"
            "Requires saving the estimate first\n"
            "Opens print preview dialog"
        )
        layout.addWidget(self.print_button)

        # New button
        self.new_button = QPushButton()
        self.new_button.setObjectName("NewPrimaryButton")
        self.new_button.setIcon(get_icon("new", widget=self))
        self._configure_icon_button(self.new_button, label="New")
        self.new_button.setToolTip(
            "Clear the form to start a new estimate (Ctrl+N)\n\n"
            "Resets all fields and generates new voucher\n"
            "Will ask for confirmation if unsaved changes"
        )
        layout.addWidget(self.new_button)

    @staticmethod
    def _configure_icon_button(button: QPushButton, *, label: str) -> None:
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

        NOTE: Ctrl+S and Ctrl+P shortcuts are NOT registered here to avoid
        conflicts with the application-wide menu shortcuts in NavigationController.
        Those are registered as QActions with ApplicationShortcut context.

        Ctrl+N is registered here as it's specific to the estimate entry widget.
        """
        target = (
            self._shortcut_parent
            if isinstance(self._shortcut_parent, QWidget)
            else self
        )
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
