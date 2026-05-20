from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from silverestimate.ui.shared_screen_theme import build_management_screen_stylesheet
from silverestimate.ui.theme_tokens import HEADER_TEXT
from silverestimate.ui.themed_controls import (
    ThemedComboBox,
    ThemedDateEdit,
    ThemedSpinBox,
)


def _right_edge_color_count(widget, color_name: str) -> int:
    image = widget.grab().toImage()
    target = QColor(color_name)
    count = 0
    for x in range(max(0, image.width() - 36), image.width()):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if (
                abs(color.red() - target.red()) <= 2
                and abs(color.green() - target.green()) <= 2
                and abs(color.blue() - target.blue()) <= 2
            ):
                count += 1
    return count


def test_themed_spin_and_combo_arrows_remain_visible_under_qss(qt_app):
    host = QWidget()
    host.setStyleSheet(
        build_management_screen_stylesheet(
            root_selector="QWidget",
            card_names=[],
            title_label="TitleLabel",
            subtitle_label="SubtitleLabel",
            input_selectors=["QSpinBox", "QComboBox"],
        )
    )
    layout = QVBoxLayout(host)
    spin = ThemedSpinBox(host)
    spin.setRange(1, 20)
    spin.setValue(16)
    spin.setSuffix(" pt")
    date_edit = ThemedDateEdit(host)
    combo = ThemedComboBox(host)
    combo.addItems(["Right Side", "Left Side"])
    layout.addWidget(spin)
    layout.addWidget(date_edit)
    layout.addWidget(combo)

    try:
        host.resize(260, 150)
        host.show()
        qt_app.processEvents()

        assert _right_edge_color_count(spin, HEADER_TEXT) > 8
        assert _right_edge_color_count(date_edit, HEADER_TEXT) > 8
        assert _right_edge_color_count(combo, HEADER_TEXT) > 8
    finally:
        host.close()
        host.deleteLater()


def test_management_stylesheet_covers_popup_and_dialog_surfaces():
    stylesheet = build_management_screen_stylesheet(
        root_selector="QWidget#Host",
        card_names=[],
        title_label="TitleLabel",
        subtitle_label="SubtitleLabel",
        input_selectors=["QLineEdit", "QComboBox", "QSpinBox"],
        include_table=True,
    )

    for selector in (
        "QComboBox QAbstractItemView",
        "QComboBox QAbstractItemView::item:selected:!active",
        "QMenu::item:selected",
        "QToolTip",
        "QDialogButtonBox QPushButton:disabled",
    ):
        assert selector in stylesheet
    assert "__" not in stylesheet
