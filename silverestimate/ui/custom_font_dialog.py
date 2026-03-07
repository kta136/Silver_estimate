#!/usr/bin/env python
import sys

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFontComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from .shared_screen_theme import build_management_screen_stylesheet


class CustomFontDialog(QDialog):
    """A custom dialog for selecting font properties with decimal sizes and min size 5."""

    fontSelected = pyqtSignal(QFont)

    def __init__(self, initial_font=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Font Settings")
        self.setMinimumWidth(400)
        self.setObjectName("CustomFontDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#CustomFontDialog",
                card_names=[
                    "CustomFontHeaderCard",
                    "CustomFontSettingsCard",
                    "CustomFontPreviewCard",
                ],
                title_label="CustomFontTitleLabel",
                subtitle_label="CustomFontSubtitleLabel",
                field_label="CustomFontFieldLabel",
                primary_button="CustomFontPrimaryButton",
                secondary_button="CustomFontSecondaryButton",
                input_selectors=["QFontComboBox", "QDoubleSpinBox"],
                extra_rules="""
                QLabel#CustomFontPreviewLabel {
                    color: #0f172a;
                    font-size: 10pt;
                    font-weight: 600;
                }
                QFrame#CustomFontSampleFrame {
                    background-color: #ffffff;
                    border: 1px solid #d8e1ec;
                    border-radius: 10px;
                }
                """,
            )
        )

        if initial_font is None:
            initial_font = QApplication.font()  # Default to application font

        # --- Widgets ---
        self.font_combo = QFontComboBox(self)
        self.font_combo.setCurrentFont(initial_font)

        self.size_spinbox = QDoubleSpinBox(self)
        self.size_spinbox.setRange(5.0, 100.0)  # Minimum size 5.0
        self.size_spinbox.setSingleStep(0.5)
        self.size_spinbox.setDecimals(1)  # Allow one decimal place
        # Set initial value carefully, QFont.pointSizeF() might be needed if available
        # QFont.pointSize() returns int, so use that for initial setting if pointSizeF isn't reliable
        initial_size = initial_font.pointSize()
        if initial_size < 5:
            initial_size = 5.0
        self.size_spinbox.setValue(float(initial_size))  # Use float for QDoubleSpinBox

        self.bold_checkbox = QCheckBox("Bold", self)
        self.bold_checkbox.setChecked(initial_font.bold())

        self.preview_label = QLabel("AaBbYyZz", self)
        self.preview_label.setMinimumHeight(60)
        self.preview_label.setAlignment(Qt.AlignCenter)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        self.button_box.button(QDialogButtonBox.Ok).setObjectName(
            "CustomFontPrimaryButton"
        )
        self.button_box.button(QDialogButtonBox.Cancel).setObjectName(
            "CustomFontSecondaryButton"
        )

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_card = QFrame(self)
        header_card.setObjectName("CustomFontHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(2)

        title = QLabel("Font Settings")
        title.setObjectName("CustomFontTitleLabel")
        header_layout.addWidget(title)

        subtitle = QLabel("Adjust family, size, and weight for printed estimates.")
        subtitle.setObjectName("CustomFontSubtitleLabel")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_card)

        settings_card = QFrame(self)
        settings_card.setObjectName("CustomFontSettingsCard")
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(10)

        form_layout = QHBoxLayout()
        family_label = QLabel("Font Family")
        family_label.setObjectName("CustomFontFieldLabel")
        form_layout.addWidget(family_label)
        form_layout.addWidget(self.font_combo, 1)  # Stretch font combo
        settings_layout.addLayout(form_layout)

        size_bold_layout = QHBoxLayout()
        size_label = QLabel("Size")
        size_label.setObjectName("CustomFontFieldLabel")
        size_bold_layout.addWidget(size_label)
        size_bold_layout.addWidget(self.size_spinbox)
        size_bold_layout.addStretch(1)
        size_bold_layout.addWidget(self.bold_checkbox)
        settings_layout.addLayout(size_bold_layout)
        layout.addWidget(settings_card)

        preview_card = QFrame(self)
        preview_card.setObjectName("CustomFontPreviewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setSpacing(8)
        preview_title = QLabel("Preview")
        preview_title.setObjectName("CustomFontPreviewLabel")
        preview_layout.addWidget(preview_title)
        preview_frame = QFrame(self)
        preview_frame.setObjectName("CustomFontSampleFrame")
        preview_frame_layout = QVBoxLayout(preview_frame)
        preview_frame_layout.setContentsMargins(12, 12, 12, 12)
        preview_frame_layout.addWidget(self.preview_label)
        preview_layout.addWidget(preview_frame)
        layout.addWidget(preview_card)
        layout.addWidget(self.button_box)

        # --- Connections ---
        self.font_combo.currentFontChanged.connect(self.update_preview)
        self.size_spinbox.valueChanged.connect(self.update_preview)
        self.bold_checkbox.stateChanged.connect(self.update_preview)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # --- Initial Preview ---
        self.update_preview()

    def update_preview(self):
        """Update the preview label font based on current selections."""
        font = self.font_combo.currentFont()
        size = self.size_spinbox.value()
        # QFont uses integer point sizes, QDoubleSpinBox value might be float
        # QFont.setPointSizeF() exists but might not be universally reliable, setPointSize is safer
        font.setPointSize(int(round(size)))  # Round to nearest integer for QFont
        font.setBold(self.bold_checkbox.isChecked())
        self.preview_label.setFont(font)

    def get_selected_font(self):
        """Return the QFont object based on the dialog's settings."""
        font = self.font_combo.currentFont()
        size = self.size_spinbox.value()
        # Store the float size for potential future use, but apply rounded int size
        font.setPointSize(int(round(size)))
        font.setBold(self.bold_checkbox.isChecked())
        # Add the float size as a custom property if needed for saving/loading exact value
        setattr(font, "float_size", size)
        return font

    def accept(self):
        """Emit the signal and accept the dialog."""
        selected_font = self.get_selected_font()
        self.fontSelected.emit(selected_font)
        super().accept()


# Example usage (for testing)
if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = CustomFontDialog()
    if dialog.exec_() == QDialog.Accepted:
        font = dialog.get_selected_font()
        import logging

        logging.getLogger(__name__).debug(
            f"Selected Font: {font.family()}, Size: {getattr(font, 'float_size', font.pointSize())} (applied as {font.pointSize()}pt), Bold: {font.bold()}"
        )
    sys.exit()
