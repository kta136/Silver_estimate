#!/usr/bin/env python
import sys
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QDialogButtonBox, QApplication
)
from PyQt5.QtCore import Qt

class TableFontSizeDialog(QDialog):
    """Dialog to select font size for the estimate table."""

    def __init__(self, current_size=9, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Table Font Size")
        self.setMinimumWidth(250)

        # --- Widgets ---
        self.size_spinbox = QSpinBox(self)
        self.size_spinbox.setRange(7, 16) # Same range as before
        self.size_spinbox.setValue(current_size)
        self.size_spinbox.setSuffix(" pt")

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)

        # --- Layout ---
        layout = QVBoxLayout(self)
        h_layout = QHBoxLayout()
        h_layout.addWidget(QLabel("Table Font Size:"))
        h_layout.addWidget(self.size_spinbox)
        layout.addLayout(h_layout)
        layout.addWidget(self.button_box)

        # --- Connections ---
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def get_selected_size(self):
        """Return the selected font size."""
        return self.size_spinbox.value()

# Example usage (for testing)
if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Example: Assume current size is 10
    dialog = TableFontSizeDialog(current_size=10)
    if dialog.exec_() == QDialog.Accepted:
        size = dialog.get_selected_size()
        import logging
        logging.getLogger(__name__).debug(f"Selected table font size: {size}pt")
    sys.exit()
