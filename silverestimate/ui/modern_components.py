"""Reusable compact widgets and helpers for the desktop UI refresh."""

from __future__ import annotations

from collections.abc import Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .theme_tokens import DENSE_HEADER_HEIGHT, DENSE_ROW_HEIGHT


def polish_dense_table(
    table: QTableView,
    *,
    row_height: int = DENSE_ROW_HEIGHT,
    header_height: int = DENSE_HEADER_HEIGHT,
    show_grid: bool | None = None,
    hide_vertical_header: bool | None = None,
) -> None:
    """Apply shared dense table metrics without replacing the table model."""

    table.setAlternatingRowColors(True)
    table.setWordWrap(False)
    table.verticalHeader().setDefaultSectionSize(int(row_height))
    table.verticalHeader().setMinimumSectionSize(max(22, int(row_height) - 2))
    table.horizontalHeader().setMinimumSectionSize(42)
    table.horizontalHeader().setDefaultSectionSize(88)
    table.horizontalHeader().setFixedHeight(int(header_height))
    table.horizontalHeader().setDefaultAlignment(
        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
    )
    if show_grid is not None:
        table.setShowGrid(bool(show_grid))
    if hide_vertical_header is not None:
        table.verticalHeader().setVisible(not bool(hide_vertical_header))


class BottomStatusStrip(QFrame):
    """Compact footer strip for shortcuts and status metadata."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomStatusStrip")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        layout.setSpacing(18)
        self._left = QLabel("")
        self._left.setObjectName("StatusStripText")
        self._right = QLabel("")
        self._right.setObjectName("StatusStripText")
        self._right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._left, 1)
        layout.addWidget(self._right, 0)
        self.setFixedHeight(24)

    def set_left_items(self, items: Iterable[str]) -> None:
        self._left.setText("  |  ".join(str(item) for item in items if str(item)))

    def set_right_items(self, items: Iterable[str]) -> None:
        self._right.setText("  |  ".join(str(item) for item in items if str(item)))


class DetailsStrip(QFrame):
    """Horizontal selected-record details strip."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailsStrip")
        self.setMinimumHeight(58)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.setSpacing(16)
        self._title = title
        self.set_items([])

    def set_items(self, items: Iterable[tuple[str, object]]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        if self._title:
            title_label = QLabel(self._title)
            title_label.setObjectName("DetailsStripTitle")
            title_label.setMinimumWidth(120)
            title_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            title_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._layout.addWidget(title_label)
        for label, value in items:
            group = QWidget(self)
            group.setMinimumWidth(84)
            group.setSizePolicy(
                QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Preferred
            )
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(2)
            label_widget = QLabel(str(label))
            label_widget.setObjectName("DetailsStripLabel")
            value_widget = QLabel(str(value))
            value_widget.setObjectName("DetailsStripValue")
            group_layout.addWidget(label_widget)
            group_layout.addWidget(value_widget)
            self._layout.addWidget(group)
        self._layout.addStretch(1)


class StatStrip(QFrame):
    """Small multi-value summary strip used by management tables."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatStrip")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._layout.setSpacing(14)

    def set_stats(self, stats: Iterable[tuple[str, object]]) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        for label, value in stats:
            box = QWidget(self)
            box_layout = QVBoxLayout(box)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(1)
            label_widget = QLabel(str(label))
            label_widget.setObjectName("StatStripLabel")
            value_widget = QLabel(str(value))
            value_widget.setObjectName("StatStripValue")
            box_layout.addWidget(label_widget)
            box_layout.addWidget(value_widget)
            self._layout.addWidget(box, 1)
