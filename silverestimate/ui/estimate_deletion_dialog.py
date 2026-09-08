"""Compact deletion confirmation shared by entry and history."""

from html import escape

from PySide6.QtWidgets import QMessageBox

from .confirmation_layout import polish_confirmation


def confirm_estimate_deletion(parent, voucher_no: str) -> bool:
    dialog = QMessageBox(parent)
    dialog.setWindowTitle("Delete Estimate")
    dialog.setText(f"<b>Delete estimate {escape(voucher_no)}?</b>")
    dialog.setInformativeText(
        "This estimate will be permanently deleted. This action cannot be undone."
    )
    dialog.setStandardButtons(
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
    )
    cancel = dialog.button(QMessageBox.StandardButton.Cancel)
    delete = dialog.button(QMessageBox.StandardButton.Yes)
    delete.setText("Delete Estimate")
    delete.setStyleSheet(
        "QPushButton { background: #c72735; color: white; border: 1px solid #c72735; "
        "border-radius: 5px; padding: 8px 16px; }"
        "QPushButton:hover { background: #a91e2c; }"
    )
    dialog.setDefaultButton(QMessageBox.StandardButton.Cancel)
    dialog.setEscapeButton(cancel)
    polish_confirmation(dialog)
    try:
        return dialog.exec() == QMessageBox.StandardButton.Yes
    finally:
        dialog.deleteLater()
