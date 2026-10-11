"""Apply persisted screen typography and table density consistently."""

from typing import cast

from PySide6.QtCore import QAbstractItemModel, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings

from .application_theme import apply_application_font

# What the table stylesheets put around a header label: 4 px of padding
# above and below, the bottom border, and a pixel of slack.
_HEADER_CHROME = 10


def header_height(table: QTableView, minimum: int = 28) -> int:
    """Return a header height that does not cut off its bold labels.

    A height derived from the row height alone clipped the tails of
    "g", "y" and brackets at the default text size.
    """
    font = QFont(table.horizontalHeader().font())
    font.setBold(True)
    return max(minimum, QFontMetrics(font).height() + _HEADER_CHROME)


def set_table_font(table: QTableView, font: QFont) -> None:
    """Keep headers and their painted sections at the table's chosen size."""
    table.setFont(font)
    for header in (table.horizontalHeader(), table.verticalHeader()):
        header.setFont(font)
        header.setStyleSheet(f"QHeaderView {{ font-size: {font.pointSizeF():g}pt; }}")


def apply_table_appearance(table: QTableView) -> None:
    settings = get_app_settings()
    font = QFont(
        settings.get_text(SettingsKey.UI_FONT_FAMILY, "Segoe UI"),
        settings.get_int(SettingsKey.UI_TABLE_FONT_SIZE, 11, minimum=7, maximum=16),
    )
    set_table_font(table, font)
    comfortable = (
        settings.get_text(SettingsKey.UI_ROW_DENSITY, "compact") == "comfortable"
    )
    height = max(24, table.fontMetrics().height() + (12 if comfortable else 4))
    table.verticalHeader().setMinimumSectionSize(height)
    table.verticalHeader().setDefaultSectionSize(height)
    table.horizontalHeader().setFixedHeight(max(height + 2, header_height(table)))
    table.setAlternatingRowColors(
        settings.get_bool(SettingsKey.UI_ALTERNATING_ROWS, True)
    )
    fit_table_headers(table)


def fit_table_headers(table: QTableView) -> None:
    """Keep labels readable; horizontal scrolling handles constrained widths."""
    model = cast(QAbstractItemModel | None, table.model())
    if model is None:
        return
    header = table.horizontalHeader()
    for column in range(model.columnCount()):
        if header.sectionResizeMode(column) == QHeaderView.ResizeMode.Interactive:
            title = str(model.headerData(column, Qt.Orientation.Horizontal) or "")
            width = header.fontMetrics().horizontalAdvance(title) + 30
            table.setColumnWidth(column, max(table.columnWidth(column), width))


def apply_interface_appearance(
    family: str, size: int, density: str, alternating: bool
) -> None:
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    font = QFont(family, size)
    app.setFont(font)
    # Re-polish styled controls: font-weight rules otherwise retain the old size.
    app.setStyleSheet(app.styleSheet())
    apply_application_font(app, font)
    for widget in app.allWidgets():
        if isinstance(widget, QTableView) and widget.property("denseTable"):
            set_table_font(widget, font)
            height = max(
                24,
                widget.fontMetrics().height() + (12 if density == "comfortable" else 4),
            )
            widget.verticalHeader().setMinimumSectionSize(height)
            widget.verticalHeader().setDefaultSectionSize(height)
            widget.horizontalHeader().setFixedHeight(
                max(height + 2, header_height(widget))
            )
            widget.setAlternatingRowColors(alternating)
            fit_table_headers(widget)
