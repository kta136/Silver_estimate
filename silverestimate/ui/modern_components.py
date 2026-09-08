"""Reusable compact widgets and helpers for the desktop UI refresh."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
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

    table.setProperty("denseTable", True)
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
    from .appearance import apply_table_appearance

    apply_table_appearance(table)


class BottomStatusStrip(QFrame):
    """Compact footer strip for shortcuts and status metadata."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomStatusStrip")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 1, 6, 1)
        layout.setSpacing(10)
        self._left = QLabel("")
        self._left.setObjectName("StatusStripText")
        self._right = QLabel("")
        self._right.setObjectName("StatusStripText")
        self._right.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._left, 1)
        layout.addWidget(self._right, 0)
        self._sync_metrics()
        self._left.setMinimumWidth(0)
        self._left.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )

    def _sync_metrics(self) -> None:
        font = self.font()
        font.setPointSizeF(max(8.0, font.pointSizeF() - 1.0))
        for label in (self._left, self._right):
            label.setFont(font)
        self.setFixedHeight(max(22, self._left.fontMetrics().height() + 4))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.FontChange and hasattr(self, "_left"):
            self._sync_metrics()

    def set_left_items(self, items: Iterable[str]) -> None:
        self._left.setText("  |  ".join(str(item) for item in items if str(item)))
        self._left.setToolTip(self._left.text())

    def set_right_items(self, items: Iterable[str]) -> None:
        self._right.setText("  |  ".join(str(item) for item in items if str(item)))


class DetailsStrip(QFrame):
    """Horizontal selected-record details strip."""

    def __init__(self, title: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DetailsStrip")
        self.setMinimumHeight(64)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(12, 8, 12, 8)
        self._layout.setSpacing(12)
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
            title_label.setMinimumWidth(96)
            title_label.setSizePolicy(
                QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
            )
            title_label.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._layout.addWidget(title_label)
        for label, value in items:
            group = QWidget(self)
            group.setMinimumWidth(76)
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
            value_widget.setToolTip(str(value))
            group_layout.addWidget(label_widget)
            group_layout.addWidget(value_widget)
            self._layout.addWidget(group)
        self._layout.addStretch(1)


class RecordInspector(QFrame):
    """Readable selected-record details, independent of the source table model."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("RecordInspector")
        self.setStyleSheet(
            "QFrame#RecordInspector { background: white; border: 1px solid #d9dde2; border-radius: 6px; }"
            "QWidget#RecordInspectorBody { background: white; }"
        )
        self.setMinimumWidth(260)
        self.setMaximumWidth(380)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        heading = QLabel(title.upper())
        layout.addWidget(heading)
        self._fields = QVBoxLayout()
        self._fields.setSpacing(12)
        self._fields.setAlignment(Qt.AlignmentFlag.AlignTop)
        body = QWidget()
        body.setObjectName("RecordInspectorBody")
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.addLayout(self._fields)
        body_layout.addStretch()
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)
        self.action_layout = QVBoxLayout()
        self.action_layout.setSpacing(10)
        layout.addLayout(self.action_layout)

    def set_items(self, items: Iterable[tuple[str, object]]) -> None:
        while self._fields.count():
            item = self._fields.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for title, value in items:
            row = QWidget()
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            layout = (
                QVBoxLayout(row)
                if title in {"Note", "Name", "Voucher No"}
                else QHBoxLayout(row)
            )
            layout.setContentsMargins(0, 0, 0, 0)
            label, content = QLabel(title), QLabel(str(value))
            content.setWordWrap(True)
            content.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            content.setMinimumWidth(0)
            layout.addWidget(label)
            layout.addWidget(content, 1 if isinstance(layout, QHBoxLayout) else 0)
            if isinstance(layout, QHBoxLayout):
                content.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            if title in {"Grand Total", "Total"}:
                row.setStyleSheet(
                    "background: #007f89; border-radius: 5px; padding: 7px;"
                )
                label.setStyleSheet("color: white; font-weight: bold;")
                content.setStyleSheet("color: white; font-weight: bold;")
            self._fields.addWidget(row)


class TableEmptyStateOverlay(QLabel):
    """Centered empty-state message that tracks a table model and viewport."""

    def __init__(self, table: QTableView, text: str) -> None:
        super().__init__(text, table.viewport())
        self._table = table
        self.setObjectName("TableEmptyStateOverlay")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        table.viewport().installEventFilter(self)

        model = table.model()
        if model is not None:
            for signal_name in (
                "modelReset",
                "rowsInserted",
                "rowsRemoved",
                "layoutChanged",
            ):
                signal = getattr(model, signal_name, None)
                if signal is not None:
                    signal.connect(lambda *_: self.refresh())
        self.refresh()

    def eventFilter(self, watched, event) -> bool:
        if watched is self._table.viewport() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self._sync_geometry()
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        model = self._table.model()
        is_empty = model is None or model.rowCount() == 0
        self.setVisible(is_empty)
        if is_empty:
            self._sync_geometry()
            self.raise_()

    def _sync_geometry(self) -> None:
        self.setGeometry(self._table.viewport().rect().adjusted(24, 24, -24, -24))


def install_table_empty_state(table: QTableView, text: str) -> TableEmptyStateOverlay:
    """Install and return a model-aware empty-state overlay for ``table``."""

    return TableEmptyStateOverlay(table, text)
