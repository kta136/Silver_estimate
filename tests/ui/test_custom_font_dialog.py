from PyQt5.QtGui import QFont

from silverestimate.ui.custom_font_dialog import CustomFontDialog


def test_custom_font_dialog_returns_selected_font(qtbot):
    initial = QFont("Arial", 10)
    dialog = CustomFontDialog(initial_font=initial)
    qtbot.addWidget(dialog)
    try:
        dialog.size_spinbox.setValue(11.5)
        dialog.bold_checkbox.setChecked(True)

        selected = dialog.get_selected_font()

        assert selected.pointSize() == 12
        assert getattr(selected, "float_size") == 11.5
        assert selected.bold() is True
    finally:
        dialog.deleteLater()
