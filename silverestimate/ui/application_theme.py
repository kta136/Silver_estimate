"""Application-level light theme helpers for PyQt widgets."""

from __future__ import annotations

import logging
from typing import Protocol

from PyQt6.QtGui import QColor, QPalette

from .theme_tokens import (
    CARD_BORDER,
    CARD_BORDER_SOFT,
    FIELD_TEXT,
    FOCUS_RING,
    HEADER_BG,
    HEADER_TEXT,
    INPUT_BORDER,
    PAGE_BG,
    PRIMARY_BG,
    PRIMARY_BG_HOVER,
    SELECTION_BG,
    SURFACE_BG,
    TEXT_MUTED,
    TEXT_STRONG,
)


class ApplicationThemeTarget(Protocol):
    """Subset of QApplication used by the theme helper."""

    def setStyle(self, style: str) -> object: ...

    def setPalette(self, palette: QPalette) -> object: ...

    def setStyleSheet(self, stylesheet: str) -> object: ...


_ENABLED_GROUPS = (
    QPalette.ColorGroup.Active,
    QPalette.ColorGroup.Inactive,
)


def _set_color(
    palette: QPalette,
    role: QPalette.ColorRole,
    value: str,
    *,
    groups: tuple[QPalette.ColorGroup, ...],
) -> None:
    color = QColor(value)
    for group in groups:
        palette.setColor(group, role, color)


def _set_optional_color(
    palette: QPalette,
    role_name: str,
    value: str,
    *,
    groups: tuple[QPalette.ColorGroup, ...],
) -> None:
    role = getattr(QPalette.ColorRole, role_name, None)
    if role is not None:
        _set_color(palette, role, value, groups=groups)


def build_light_palette() -> QPalette:
    """Build a strict light palette for active, inactive, and disabled widgets."""

    palette = QPalette()

    for role, value in (
        (QPalette.ColorRole.Window, PAGE_BG),
        (QPalette.ColorRole.WindowText, TEXT_STRONG),
        (QPalette.ColorRole.Base, SURFACE_BG),
        (QPalette.ColorRole.AlternateBase, HEADER_BG),
        (QPalette.ColorRole.ToolTipBase, SURFACE_BG),
        (QPalette.ColorRole.ToolTipText, TEXT_STRONG),
        (QPalette.ColorRole.Text, TEXT_STRONG),
        (QPalette.ColorRole.Button, HEADER_BG),
        (QPalette.ColorRole.ButtonText, TEXT_STRONG),
        (QPalette.ColorRole.BrightText, SURFACE_BG),
        (QPalette.ColorRole.Highlight, SELECTION_BG),
        (QPalette.ColorRole.HighlightedText, TEXT_STRONG),
        (QPalette.ColorRole.Link, FOCUS_RING),
        (QPalette.ColorRole.Light, SURFACE_BG),
        (QPalette.ColorRole.Mid, CARD_BORDER),
        (QPalette.ColorRole.Dark, INPUT_BORDER),
        (QPalette.ColorRole.Shadow, CARD_BORDER_SOFT),
    ):
        _set_color(palette, role, value, groups=_ENABLED_GROUPS)

    _set_optional_color(
        palette,
        "PlaceholderText",
        TEXT_MUTED,
        groups=_ENABLED_GROUPS,
    )
    _set_optional_color(
        palette,
        "Accent",
        PRIMARY_BG,
        groups=_ENABLED_GROUPS,
    )

    disabled = (QPalette.ColorGroup.Disabled,)
    for role, value in (
        (QPalette.ColorRole.Window, PAGE_BG),
        (QPalette.ColorRole.WindowText, TEXT_MUTED),
        (QPalette.ColorRole.Base, HEADER_BG),
        (QPalette.ColorRole.AlternateBase, HEADER_BG),
        (QPalette.ColorRole.ToolTipBase, SURFACE_BG),
        (QPalette.ColorRole.ToolTipText, TEXT_MUTED),
        (QPalette.ColorRole.Text, TEXT_MUTED),
        (QPalette.ColorRole.Button, CARD_BORDER_SOFT),
        (QPalette.ColorRole.ButtonText, TEXT_MUTED),
        (QPalette.ColorRole.BrightText, SURFACE_BG),
        (QPalette.ColorRole.Highlight, CARD_BORDER_SOFT),
        (QPalette.ColorRole.HighlightedText, TEXT_MUTED),
        (QPalette.ColorRole.Link, TEXT_MUTED),
        (QPalette.ColorRole.Light, SURFACE_BG),
        (QPalette.ColorRole.Mid, CARD_BORDER_SOFT),
        (QPalette.ColorRole.Dark, INPUT_BORDER),
        (QPalette.ColorRole.Shadow, CARD_BORDER_SOFT),
    ):
        _set_color(palette, role, value, groups=disabled)

    _set_optional_color(palette, "PlaceholderText", TEXT_MUTED, groups=disabled)
    _set_optional_color(palette, "Accent", CARD_BORDER_SOFT, groups=disabled)

    return palette


def build_light_application_stylesheet() -> str:
    """Build QSS that keeps common Qt popup and dialog surfaces light."""

    return f"""
QMainWindow,
QDialog,
QMessageBox,
QInputDialog,
QProgressDialog,
QCalendarWidget {{
    background-color: {PAGE_BG};
    color: {TEXT_STRONG};
}}

QDialog QLabel,
QMessageBox QLabel,
QInputDialog QLabel,
QProgressDialog QLabel {{
    color: {TEXT_STRONG};
}}

QFrame,
QStackedWidget,
QScrollArea,
QScrollArea QWidget {{
    color: {TEXT_STRONG};
}}

QScrollArea {{
    background-color: {PAGE_BG};
    border: none;
}}

QGroupBox {{
    background-color: {SURFACE_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    color: {TEXT_STRONG};
    font-weight: 700;
    margin-top: 12px;
    padding: 12px 12px 10px 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}}

QTabWidget::pane {{
    background-color: {SURFACE_BG};
    border: 1px solid {CARD_BORDER};
    border-radius: 10px;
    top: -1px;
}}

QTabBar::tab {{
    background-color: {HEADER_BG};
    border: 1px solid {CARD_BORDER};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: {HEADER_TEXT};
    min-height: 24px;
    padding: 6px 12px;
}}

QTabBar::tab:selected {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
    font-weight: 700;
}}

QTabBar::tab:hover:!selected {{
    background-color: {SELECTION_BG};
    color: {TEXT_STRONG};
}}

QTabBar::tab:disabled {{
    background-color: {HEADER_BG};
    color: {TEXT_MUTED};
}}

QMenuBar {{
    background-color: {HEADER_BG};
    color: {TEXT_STRONG};
    border-bottom: 1px solid {CARD_BORDER};
}}

QMenuBar::item {{
    background-color: transparent;
    color: {TEXT_STRONG};
    padding: 4px 8px;
}}

QMenuBar::item:selected,
QMenuBar::item:pressed {{
    background-color: {SELECTION_BG};
    color: {TEXT_STRONG};
}}

QMenuBar::item:disabled {{
    color: {TEXT_MUTED};
}}

QMenu {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
    border: 1px solid {INPUT_BORDER};
}}

QMenu::item {{
    background-color: transparent;
    color: {TEXT_STRONG};
    padding: 5px 24px 5px 24px;
}}

QMenu::item:selected,
QMenu::item:pressed {{
    background-color: {SELECTION_BG};
    color: {TEXT_STRONG};
}}

QMenu::item:disabled {{
    color: {TEXT_MUTED};
}}

QMenu::separator {{
    background-color: {CARD_BORDER_SOFT};
    height: 1px;
    margin: 4px 8px;
}}

QToolTip {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 4px;
    padding: 4px 6px;
    opacity: 255;
}}

QComboBox {{
    background-color: {SURFACE_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    color: {TEXT_STRONG};
    min-height: 22px;
    padding: 4px 28px 4px 8px;
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_STRONG};
}}

QComboBox:hover {{
    border-color: {FOCUS_RING};
}}

QComboBox:focus {{
    border: 2px solid {FOCUS_RING};
}}

QComboBox:disabled {{
    background-color: {HEADER_BG};
    border-color: {CARD_BORDER_SOFT};
    color: {TEXT_MUTED};
}}

QComboBox::drop-down {{
    background-color: {HEADER_BG};
    border-left: 1px solid {INPUT_BORDER};
    border-top-right-radius: 8px;
    border-bottom-right-radius: 8px;
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 30px;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
    border: 1px solid {INPUT_BORDER};
    outline: 0;
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_STRONG};
}}

QComboBox QAbstractItemView::item {{
    min-height: 24px;
    padding: 4px 8px;
}}

QComboBox QAbstractItemView::item:selected,
QComboBox QAbstractItemView::item:selected:!active {{
    background-color: {SELECTION_BG};
    color: {TEXT_STRONG};
}}

QCalendarWidget {{
    background-color: {SURFACE_BG};
    border: 1px solid {CARD_BORDER};
    color: {TEXT_STRONG};
}}

QCalendarWidget QWidget {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
}}

QCalendarWidget QToolButton {{
    background-color: {HEADER_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    color: {TEXT_STRONG};
    margin: 2px;
    padding: 4px 8px;
}}

QCalendarWidget QToolButton:hover {{
    background-color: {SELECTION_BG};
    border-color: {FOCUS_RING};
}}

QCalendarWidget QMenu {{
    background-color: {SURFACE_BG};
    border: 1px solid {INPUT_BORDER};
    color: {TEXT_STRONG};
}}

QCalendarWidget QSpinBox {{
    background-color: {SURFACE_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 6px;
    color: {TEXT_STRONG};
    min-width: 72px;
    padding: 3px 28px 3px 6px;
}}

QCalendarWidget QAbstractItemView {{
    background-color: {SURFACE_BG};
    color: {TEXT_STRONG};
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_STRONG};
}}

QAbstractItemView,
QListView,
QListWidget,
QTreeView,
QTableView {{
    alternate-background-color: {HEADER_BG};
    background-color: {SURFACE_BG};
    border: 1px solid {CARD_BORDER_SOFT};
    color: {TEXT_STRONG};
    gridline-color: {CARD_BORDER_SOFT};
    outline: 0;
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_STRONG};
}}

QAbstractItemView::item,
QListView::item,
QListWidget::item,
QTreeView::item,
QTableView::item {{
    color: {TEXT_STRONG};
}}

QAbstractItemView::item:hover,
QListView::item:hover,
QListWidget::item:hover,
QTreeView::item:hover,
QTableView::item:hover {{
    background-color: {HEADER_BG};
}}

QAbstractItemView::item:selected,
QAbstractItemView::item:selected:active,
QAbstractItemView::item:selected:!active,
QListView::item:selected,
QListView::item:selected:active,
QListView::item:selected:!active,
QListWidget::item:selected,
QListWidget::item:selected:active,
QListWidget::item:selected:!active,
QTreeView::item:selected,
QTreeView::item:selected:active,
QTreeView::item:selected:!active,
QTableView::item:selected,
QTableView::item:selected:active,
QTableView::item:selected:!active {{
    background-color: {SELECTION_BG};
    color: {TEXT_STRONG};
}}

QAbstractItemView:disabled,
QListView:disabled,
QListWidget:disabled,
QTreeView:disabled,
QTableView:disabled {{
    background-color: {HEADER_BG};
    border-color: {CARD_BORDER_SOFT};
    color: {TEXT_MUTED};
}}

QHeaderView::section {{
    background-color: {HEADER_BG};
    border: none;
    border-right: 1px solid {CARD_BORDER_SOFT};
    border-bottom: 1px solid {CARD_BORDER_SOFT};
    color: {HEADER_TEXT};
    font-weight: 700;
    padding: 6px 8px;
}}

QPushButton,
QToolButton {{
    background-color: {HEADER_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    color: {TEXT_STRONG};
    font-weight: 600;
    min-height: 22px;
    padding: 5px 10px;
}}

QPushButton:hover,
QToolButton:hover {{
    background-color: {SELECTION_BG};
    border-color: {FOCUS_RING};
}}

QPushButton:pressed,
QToolButton:pressed {{
    background-color: {CARD_BORDER_SOFT};
    border-color: {HEADER_TEXT};
}}

QPushButton:default {{
    background-color: {PRIMARY_BG};
    border-color: {PRIMARY_BG};
    color: {SURFACE_BG};
}}

QPushButton:default:hover {{
    background-color: {PRIMARY_BG_HOVER};
    border-color: {PRIMARY_BG_HOVER};
    color: {SURFACE_BG};
}}

QPushButton:disabled,
QToolButton:disabled {{
    background-color: {CARD_BORDER_SOFT};
    border-color: {CARD_BORDER};
    color: {TEXT_MUTED};
}}

QLineEdit,
QTextEdit,
QPlainTextEdit,
QSpinBox,
QDoubleSpinBox,
QDateEdit,
QTimeEdit,
QDateTimeEdit {{
    background-color: {SURFACE_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    color: {FIELD_TEXT};
    min-height: 20px;
    padding: 4px 8px;
    selection-background-color: {SELECTION_BG};
    selection-color: {TEXT_STRONG};
}}

QSpinBox,
QDoubleSpinBox,
QDateEdit,
QTimeEdit,
QDateTimeEdit {{
    padding-right: 30px;
}}

QSpinBox::up-button,
QDoubleSpinBox::up-button,
QDateEdit::up-button,
QTimeEdit::up-button,
QDateTimeEdit::up-button {{
    background-color: {HEADER_BG};
    border-left: 1px solid {INPUT_BORDER};
    border-top-right-radius: 8px;
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 26px;
}}

QSpinBox::down-button,
QDoubleSpinBox::down-button,
QDateEdit::down-button,
QTimeEdit::down-button,
QDateTimeEdit::down-button {{
    background-color: {HEADER_BG};
    border-left: 1px solid {INPUT_BORDER};
    border-bottom-right-radius: 8px;
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 26px;
}}

QLineEdit:focus,
QTextEdit:focus,
QPlainTextEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QDateEdit:focus,
QTimeEdit:focus,
QDateTimeEdit:focus {{
    border: 2px solid {FOCUS_RING};
}}

QLineEdit:disabled,
QTextEdit:disabled,
QPlainTextEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QDateEdit:disabled,
QTimeEdit:disabled,
QDateTimeEdit:disabled {{
    background-color: {HEADER_BG};
    border-color: {CARD_BORDER_SOFT};
    color: {TEXT_MUTED};
}}

QCheckBox,
QRadioButton {{
    color: {TEXT_STRONG};
    spacing: 8px;
}}

QCheckBox:disabled,
QRadioButton:disabled {{
    color: {TEXT_MUTED};
}}

QCheckBox::indicator,
QRadioButton::indicator {{
    background-color: {SURFACE_BG};
    border: 1px solid {INPUT_BORDER};
    height: 14px;
    width: 14px;
}}

QCheckBox::indicator {{
    border-radius: 4px;
}}

QRadioButton::indicator {{
    border-radius: 7px;
}}

QCheckBox::indicator:hover,
QRadioButton::indicator:hover {{
    border-color: {FOCUS_RING};
}}

QCheckBox::indicator:checked,
QRadioButton::indicator:checked {{
    background-color: {PRIMARY_BG};
    border-color: {PRIMARY_BG};
}}

QCheckBox::indicator:disabled,
QRadioButton::indicator:disabled {{
    background-color: {HEADER_BG};
    border-color: {CARD_BORDER_SOFT};
}}

QScrollBar:vertical,
QScrollBar:horizontal {{
    background-color: {HEADER_BG};
    border: none;
    margin: 0;
}}

QScrollBar:vertical {{
    width: 12px;
}}

QScrollBar:horizontal {{
    height: 12px;
}}

QScrollBar::handle:vertical,
QScrollBar::handle:horizontal {{
    background-color: {INPUT_BORDER};
    border-radius: 6px;
    min-height: 24px;
    min-width: 24px;
}}

QScrollBar::handle:vertical:hover,
QScrollBar::handle:horizontal:hover {{
    background-color: {TEXT_MUTED};
}}

QScrollBar::add-line,
QScrollBar::sub-line,
QScrollBar::add-page,
QScrollBar::sub-page {{
    background: transparent;
    border: none;
}}

QSplitter::handle {{
    background-color: {CARD_BORDER_SOFT};
}}

QStatusBar,
QToolBar {{
    background-color: {HEADER_BG};
    border-top: 1px solid {CARD_BORDER};
    color: {TEXT_STRONG};
}}

QProgressBar {{
    background-color: {HEADER_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    color: {TEXT_STRONG};
    min-height: 16px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {PRIMARY_BG};
    border-radius: 7px;
}}

QDialogButtonBox QPushButton,
QMessageBox QPushButton {{
    background-color: {HEADER_BG};
    border: 1px solid {INPUT_BORDER};
    border-radius: 8px;
    color: {TEXT_STRONG};
    font-weight: 600;
    min-height: 24px;
    min-width: 72px;
    padding: 5px 12px;
}}

QDialogButtonBox QPushButton:hover,
QMessageBox QPushButton:hover {{
    background-color: {SELECTION_BG};
    border-color: {FOCUS_RING};
}}

QDialogButtonBox QPushButton:default,
QMessageBox QPushButton:default {{
    background-color: {PRIMARY_BG};
    border-color: {PRIMARY_BG};
    color: {SURFACE_BG};
}}

QDialogButtonBox QPushButton:default:hover,
QMessageBox QPushButton:default:hover {{
    background-color: {PRIMARY_BG_HOVER};
    border-color: {PRIMARY_BG_HOVER};
    color: {SURFACE_BG};
}}

QDialogButtonBox QPushButton:disabled,
QMessageBox QPushButton:disabled {{
    background-color: {CARD_BORDER_SOFT};
    border-color: {CARD_BORDER};
    color: {TEXT_MUTED};
}}
""".strip()


LIGHT_APPLICATION_STYLESHEET = build_light_application_stylesheet()


def apply_light_application_theme(
    app: ApplicationThemeTarget,
    logger: logging.Logger | None = None,
    *,
    force_fusion: bool = True,
) -> None:
    """Apply the strict light palette and QSS to a QApplication-like object."""

    if force_fusion:
        try:
            app.setStyle("Fusion")
        except Exception as exc:
            if logger:
                logger.debug("Failed to force Fusion Qt style: %s", exc)

    try:
        app.setPalette(build_light_palette())
    except Exception as exc:
        if logger:
            logger.debug("Failed to apply light Qt palette: %s", exc)

    try:
        app.setStyleSheet(LIGHT_APPLICATION_STYLESHEET)
    except Exception as exc:
        if logger:
            logger.debug("Failed to apply light application stylesheet: %s", exc)
