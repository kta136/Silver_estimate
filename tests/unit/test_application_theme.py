from __future__ import annotations

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QGroupBox,
    QListView,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QTableView,
    QTabWidget,
    QToolButton,
)

from silverestimate.ui.application_theme import (
    LIGHT_APPLICATION_STYLESHEET,
    apply_light_application_theme,
    build_light_application_stylesheet,
    build_light_palette,
)
from silverestimate.ui.theme_tokens import (
    CARD_BORDER,
    CARD_BORDER_SOFT,
    FOCUS_RING,
    HEADER_BG,
    INPUT_BORDER,
    PAGE_BG,
    SELECTION_BG,
    SURFACE_BG,
    TEXT_MUTED,
    TEXT_STRONG,
)


def _color_name(
    palette: QPalette,
    group: QPalette.ColorGroup,
    role: QPalette.ColorRole,
) -> str:
    return palette.color(group, role).name()


def test_build_light_palette_sets_enabled_and_inactive_roles():
    palette = build_light_palette()

    for group in (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive):
        assert _color_name(palette, group, QPalette.ColorRole.Window) == PAGE_BG
        assert _color_name(palette, group, QPalette.ColorRole.WindowText) == TEXT_STRONG
        assert _color_name(palette, group, QPalette.ColorRole.Base) == SURFACE_BG
        assert (
            _color_name(palette, group, QPalette.ColorRole.AlternateBase) == HEADER_BG
        )
        assert _color_name(palette, group, QPalette.ColorRole.Highlight) == SELECTION_BG
        assert (
            _color_name(palette, group, QPalette.ColorRole.HighlightedText)
            == TEXT_STRONG
        )
        assert _color_name(palette, group, QPalette.ColorRole.Link) == FOCUS_RING


def test_build_light_palette_sets_disabled_roles():
    palette = build_light_palette()
    disabled = QPalette.ColorGroup.Disabled

    assert _color_name(palette, disabled, QPalette.ColorRole.Window) == PAGE_BG
    assert _color_name(palette, disabled, QPalette.ColorRole.WindowText) == TEXT_MUTED
    assert _color_name(palette, disabled, QPalette.ColorRole.Text) == TEXT_MUTED
    assert _color_name(palette, disabled, QPalette.ColorRole.ButtonText) == TEXT_MUTED
    assert _color_name(palette, disabled, QPalette.ColorRole.Base) == HEADER_BG
    assert _color_name(palette, disabled, QPalette.ColorRole.Button) == CARD_BORDER_SOFT
    assert (
        _color_name(palette, disabled, QPalette.ColorRole.Highlight) == CARD_BORDER_SOFT
    )


def test_build_light_application_stylesheet_covers_popup_dialog_and_view_surfaces():
    stylesheet = build_light_application_stylesheet()

    assert stylesheet == LIGHT_APPLICATION_STYLESHEET
    assert "__" not in stylesheet
    for selector in (
        "QDialog",
        "QMessageBox",
        "QToolTip",
        "QGroupBox",
        "QTabWidget::pane",
        "QTabBar::tab:selected",
        "QMenu",
        "QMenu::item:disabled",
        "QComboBox::drop-down",
        "QComboBox QAbstractItemView",
        "QAbstractItemView::item:selected:!active",
        "QListView::item:selected:!active",
        "QTableView::item:selected:!active",
        "QSpinBox::up-button",
        "QDoubleSpinBox::down-button",
        "QPushButton:disabled",
        "QToolButton:disabled",
        "QCheckBox::indicator:checked",
        "QRadioButton::indicator:checked",
        "QScrollBar::handle:vertical",
        "QStatusBar",
        "QDialogButtonBox QPushButton",
        "QMessageBox QPushButton:default",
        "QDialogButtonBox QPushButton:disabled",
    ):
        assert selector in stylesheet

    for color in (
        PAGE_BG,
        SURFACE_BG,
        CARD_BORDER,
        CARD_BORDER_SOFT,
        INPUT_BORDER,
        SELECTION_BG,
        TEXT_MUTED,
        TEXT_STRONG,
    ):
        assert color in stylesheet


def test_apply_light_application_theme_sets_stub_app_palette_and_qss():
    class StubApp:
        def __init__(self):
            self.style = None
            self.palette = None
            self.stylesheet = ""

        def setStyle(self, style):
            self.style = style

        def setPalette(self, palette):
            self.palette = palette

        def setStyleSheet(self, stylesheet):
            self.stylesheet = stylesheet

    app = StubApp()

    apply_light_application_theme(app)

    assert app.style == "Fusion"
    assert isinstance(app.palette, QPalette)
    assert app.stylesheet == LIGHT_APPLICATION_STYLESHEET
    assert (
        _color_name(
            app.palette, QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight
        )
        == SELECTION_BG
    )


def test_apply_light_application_theme_allows_headless_widget_instantiation(qt_app):
    previous_palette = qt_app.palette()
    previous_stylesheet = qt_app.styleSheet()
    widgets = []

    try:
        apply_light_application_theme(qt_app, force_fusion=False)

        widgets = [
            QMessageBox(),
            QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok
                | QDialogButtonBox.StandardButton.Cancel
            ),
            QComboBox(),
            QListView(),
            QTableView(),
            QGroupBox("Group"),
            QCheckBox("Check"),
            QRadioButton("Radio"),
            QTabWidget(),
            QScrollArea(),
            QToolButton(),
        ]

        assert qt_app.styleSheet() == LIGHT_APPLICATION_STYLESHEET
        assert (
            _color_name(
                qt_app.palette(),
                QPalette.ColorGroup.Active,
                QPalette.ColorRole.Window,
            )
            == PAGE_BG
        )
        assert all(not widget.isVisible() for widget in widgets)
    finally:
        for widget in widgets:
            widget.deleteLater()
        qt_app.setStyleSheet(previous_stylesheet)
        qt_app.setPalette(previous_palette)
