"""Shared building blocks for the Silver Bar and Sales Reports screens."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionButton,
    QStyleOptionViewItem,
    QStylePainter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from .theme_tokens import (
    CARD_BORDER,
    HEADER_BG,
    INFO_BG,
    INFO_BORDER,
    INFO_TEXT,
    SUCCESS_BG,
    SUCCESS_BORDER,
    SUCCESS_TEXT,
    TEXT_MUTED,
    TEXT_STRONG,
    WARNING_BG,
    WARNING_BORDER,
    WARNING_TEXT,
)

# Colours used only by these screens.
ZERO_TEXT = "#94a3b8"
# Pale enough to sit behind dark figures without hurting their contrast.
DATA_BAR_FILL = "#cfe9eb"

SCREEN_QSS = """
QFrame#ScreenCard {
    background-color: __SURFACE_BG__;
    border: 1px solid __CARD_BORDER__;
    border-radius: 8px;
}
QFrame#ScreenHeaderBar {
    background-color: __SURFACE_BG__;
    border: none;
    border-bottom: 1px solid __CARD_BORDER__;
}
QFrame#ScreenFooterBar {
    background-color: __SURFACE_BG__;
    border: none;
    border-top: 1px solid __CARD_BORDER__;
}
QLabel#ScreenTitle { font-size: 15pt; font-weight: 700; color: __TEXT_STRONG__; }
QLabel#CardTitle { font-size: 11pt; font-weight: 700; color: __TEXT_STRONG__; }
QLabel#Muted, QLabel#HintText { color: __TEXT_MUTED__; }
QLabel#Eyebrow { color: __TEXT_MUTED__; font-weight: 600; font-size: 8pt; }
QLabel#EyebrowSale { color: __INFO_TEXT__; font-weight: 700; font-size: 8pt; }
QLabel#EyebrowReturn { color: __WARNING_TEXT__; font-weight: 700; font-size: 8pt; }
QLabel#MetricValue { font-size: 15pt; font-weight: 700; color: __TEXT_STRONG__; }
QLabel#MetricValue[accent="true"] { color: __INFO_TEXT__; font-size: 17pt; }
QLabel#MetricValue[empty="true"] { color: #94a3b8; }
QFrame#TotalsStrip {
    background-color: __HEADER_BG__;
    border: none;
    border-top: 1px solid __CARD_BORDER__;
    border-bottom-left-radius: 8px;
    border-bottom-right-radius: 8px;
}
QFrame#TotalsStrip[flat="true"] {
    border-radius: 0;
    border-bottom: 1px solid __CARD_BORDER_SOFT__;
}
QFrame#TotalsStrip[accent="true"] { background-color: __INFO_BG__; border-top-color: __INFO_BORDER__; }
QFrame#MetricDivider { background-color: __CARD_BORDER_SOFT__; border: none; }
QLabel#StatusPill {
    border-radius: 10px;
    padding: 2px 10px;
    font-weight: 600;
    font-size: 8pt;
}
QLabel#StatusPill[pillState="new"] { background: #f1f3f5; color: __FIELD_TEXT__; border: 1px solid __CARD_BORDER__; }
QLabel#StatusPill[pillState="active"] { background: __INFO_BG__; color: __INFO_TEXT__; border: 1px solid __INFO_BORDER__; }
QLabel#StatusPill[pillState="issued"] { background: __WARNING_BG__; color: __WARNING_TEXT__; border: 1px solid __WARNING_BORDER__; }
QLabel#StatusPill[pillState="available"] { background: __SUCCESS_BG__; color: __SUCCESS_TEXT__; border: 1px solid __SUCCESS_BORDER__; }
QFrame#SegmentGroup {
    background-color: #eceff2;
    border: none;
    border-radius: 8px;
}
QPushButton#SegmentButton {
    background: transparent;
    border: none;
    border-radius: 6px;
    color: __FIELD_TEXT__;
    font-weight: 600;
    padding: 4px 14px;
    min-height: 22px;
}
QPushButton#SegmentButton:hover { color: __TEXT_STRONG__; }
QPushButton#SegmentButton:checked {
    background: __SURFACE_BG__;
    color: __TEXT_STRONG__;
    border: 1px solid __CARD_BORDER__;
}
QPushButton#SegmentButton:disabled { color: #94a3b8; }
QPushButton#ChipButton, QToolButton#ChipButton {
    background: __SURFACE_BG__;
    border: 1px solid __INPUT_BORDER__;
    border-radius: 14px;
    color: __HEADER_TEXT__;
    font-weight: 600;
    padding: 4px 14px;
    min-height: 20px;
}
/* Room for the arrow that says the chip opens a list. */
QToolButton#ChipButton { padding-right: 24px; }
QToolButton#ChipButton::menu-indicator {
    subcontrol-origin: padding;
    subcontrol-position: right center;
    right: 9px;
}
QPushButton#ChipButton:hover, QToolButton#ChipButton:hover { border-color: #94a3b8; }
QPushButton#ChipButton:disabled, QToolButton#ChipButton:disabled {
    background: __DISABLED_BG__;
    border-color: __DISABLED_BORDER__;
    color: __DISABLED_TEXT__;
}
QPushButton#ChipButton:checked {
    background: __PRIMARY_BG__;
    border-color: __PRIMARY_BG__;
    color: __SURFACE_BG__;
}
QPushButton#LinkButton {
    background: transparent;
    border: none;
    color: __INFO_TEXT__;
    font-weight: 600;
    padding: 4px 6px;
    text-align: left;
}
QPushButton#LinkButton:hover { color: #004f56; text-decoration: underline; }
QPushButton#LinkButton:disabled { color: __TEXT_MUTED__; }
QFrame#IssuedBanner {
    background-color: __WARNING_BG__;
    border: 1px solid __WARNING_BORDER__;
    border-radius: 8px;
}
QLabel#IssuedBannerText { color: #7c2d12; }
QFrame#ScreenCard[focused="true"] { border: 2px solid __PRIMARY_BG__; }
QFrame#EmptyStatePanel { background: transparent; border: none; }
QLabel#EmptyStateTitle { font-size: 11pt; font-weight: 600; color: __TEXT_STRONG__; }
QLabel#EmptyStateBody { color: __TEXT_MUTED__; }
QTableView#ScreenTable {
    border: none;
    border-radius: 0;
    border-top: 1px solid __CARD_BORDER_SOFT__;
}
QTableView#ScreenTable QHeaderView::section {
    border-right: none;
    font-weight: 600;
}
"""


class KeyHintButton(QPushButton):
    """Push button that draws its keyboard shortcut as a small key cap."""

    _GAP = 8
    _PAD = 5

    def __init__(
        self, text: str = "", key_hint: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(text, parent)
        self._key_hint = key_hint
        self.setAutoDefault(False)

    def key_hint(self) -> str:
        return self._key_hint

    def _chip_font(self):
        font = self.font()
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1.5))
        font.setBold(True)
        return font

    def _chip_size(self) -> QSize:
        if not self._key_hint:
            return QSize(0, 0)
        metrics = QFontMetrics(self._chip_font())
        return QSize(
            metrics.horizontalAdvance(self._key_hint) + self._PAD * 2,
            metrics.height() + 2,
        )

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        chip = self._chip_size()
        if chip.width():
            hint.setWidth(hint.width() + chip.width() + self._GAP)
        return hint

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def paintEvent(self, event) -> None:
        if not self._key_hint:
            super().paintEvent(event)
            return
        chip = self._chip_size()
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        painter.drawControl(QStyle.ControlElement.CE_PushButtonBevel, option)
        label = QStyleOptionButton(option)
        label.rect = option.rect.adjusted(0, 0, -(chip.width() + self._GAP), 0)
        painter.drawControl(QStyle.ControlElement.CE_PushButtonLabel, label)
        primary = "Primary" in self.objectName()
        text_width = self.fontMetrics().horizontalAdvance(
            self.text().replace("&&", "&")
        )
        center = label.rect.center().x() + text_width // 2 + self._GAP
        chip_rect = QRect(
            center, (self.height() - chip.height()) // 2, chip.width(), chip.height()
        )
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        foreground = QColor("#ffffff" if primary else TEXT_MUTED)
        border = QColor(255, 255, 255, 150) if primary else QColor(CARD_BORDER)
        if not self.isEnabled():
            foreground.setAlpha(140)
            border.setAlpha(120)
        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(chip_rect.adjusted(0, 0, -1, -1), 4, 4)
        painter.setFont(self._chip_font())
        painter.setPen(foreground)
        painter.drawText(chip_rect, Qt.AlignmentFlag.AlignCenter, self._key_hint)


class OptionGroup(QFrame):
    """Exclusive choice shown as a segmented switch or as filter chips.

    It mirrors the parts of the QComboBox API the screens use, so filter code
    and tests can keep reading ``currentText()`` and ``currentData()``.
    """

    currentIndexChanged = Signal(int)

    def __init__(self, variant: str = "segmented", parent: QWidget | None = None):
        super().__init__(parent)
        self._variant = variant
        self.setObjectName("SegmentGroup" if variant == "segmented" else "ChipGroup")
        self._layout = QHBoxLayout(self)
        margin = 3 if variant == "segmented" else 0
        self._layout.setContentsMargins(margin, margin, margin, margin)
        self._layout.setSpacing(2 if variant == "segmented" else 8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idClicked.connect(self.setCurrentIndex)
        self._buttons: list[QPushButton] = []
        self._data: list[Any] = []
        self._index = -1
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def addItem(self, text: str, data: Any = None, key_hint: str = "") -> None:
        button = KeyHintButton(text, key_hint, self)
        button.setObjectName(
            "SegmentButton" if self._variant == "segmented" else "ChipButton"
        )
        button.setCheckable(True)
        button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._group.addButton(button, len(self._buttons))
        self._buttons.append(button)
        self._data.append(text if data is None else data)
        self._layout.addWidget(button)
        if self._index < 0:
            self._index = 0
            button.setChecked(True)

    def addItems(self, texts: Iterable[str]) -> None:
        for text in texts:
            self.addItem(text)

    def button(self, index: int) -> QPushButton:
        return self._buttons[index]

    def count(self) -> int:
        return len(self._buttons)

    def currentIndex(self) -> int:
        return self._index

    def setCurrentIndex(self, index: int) -> None:
        if not 0 <= index < len(self._buttons):
            return
        self._buttons[index].setChecked(True)
        if index != self._index:
            self._index = index
            self.currentIndexChanged.emit(index)

    def itemText(self, index: int) -> str:
        return self._buttons[index].text() if 0 <= index < self.count() else ""

    def setItemText(self, index: int, text: str) -> None:
        self._buttons[index].setText(text)

    def itemData(self, index: int) -> Any:
        return self._data[index] if 0 <= index < self.count() else None

    def currentText(self) -> str:
        return self.itemText(self._index)

    def currentData(self) -> Any:
        return self.itemData(self._index)

    def findText(self, text: str) -> int:
        return next(
            (i for i, button in enumerate(self._buttons) if button.text() == text), -1
        )

    def setCurrentText(self, text: str) -> None:
        index = self.findText(text)
        if index >= 0:
            self.setCurrentIndex(index)


class StatusPill(QLabel):
    """Rounded state label: new, active, issued or available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("StatusPill")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_state(self, state: str, text: str) -> None:
        self.setText(f"● {text}" if state != "new" else text)
        self.setAccessibleName(f"State: {text}")
        self.setProperty("pillState", state)
        self.style().unpolish(self)
        self.style().polish(self)


def card(name: str = "ScreenCard", parent: QWidget | None = None) -> QFrame:
    frame = QFrame(parent)
    frame.setObjectName("ScreenCard")
    if name != "ScreenCard":
        frame.setAccessibleName(name)
    return frame


def label(text: str = "", name: str = "", parent: QWidget | None = None) -> QLabel:
    widget = QLabel(text, parent)
    if name:
        widget.setObjectName(name)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    return widget


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class TotalsStrip(QFrame):
    """A row of captioned totals; the last value can be highlighted."""

    def __init__(
        self,
        captions: Sequence[str],
        *,
        accent_last: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("TotalsStrip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.values: list[QLabel] = []
        self._summary = ""
        for index, caption in enumerate(captions):
            if index:
                divider = QFrame(self)
                divider.setObjectName("MetricDivider")
                divider.setFixedWidth(1)
                layout.addWidget(divider)
            cell = QWidget(self)
            cell_layout = QVBoxLayout(cell)
            cell_layout.setContentsMargins(14, 10, 14, 10)
            cell_layout.setSpacing(2)
            cell_layout.addWidget(label(caption.upper(), "Eyebrow", cell))
            value = label("", "MetricValue", cell)
            value.setProperty("accent", accent_last and index == len(captions) - 1)
            cell_layout.addWidget(value)
            layout.addWidget(cell, 1)
            self.values.append(value)

    def set_values(
        self, values: Sequence[str], *, empty: bool = False, summary: str = ""
    ) -> None:
        for widget, value in zip(self.values, values, strict=True):
            widget.setText(value)
            widget.setProperty("empty", empty)
            repolish(widget)
        self._summary = summary
        self.setAccessibleDescription(summary)

    def set_accent(self, accent: bool) -> None:
        self.setProperty("accent", accent)
        repolish(self)

    def text(self) -> str:
        return self._summary or "   ".join(value.text() for value in self.values)


class EmptyStatePanel(QFrame):
    """Centered empty state with optional actions, laid over a table viewport."""

    def __init__(self, table: QTableView, title: str = "", body: str = "") -> None:
        super().__init__(table.viewport())
        self._table = table
        self.setObjectName("EmptyStatePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(8)
        layout.addStretch(1)
        self.title_label = label(title, "EmptyStateTitle", self)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.body_label = label(body, "EmptyStateBody", self)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_label.setWordWrap(True)
        layout.addWidget(self.body_label)
        self._actions = QHBoxLayout()
        self._actions.setSpacing(8)
        self._actions.addStretch(1)
        self._actions.addStretch(1)
        layout.addLayout(self._actions)
        layout.addStretch(1)
        self.title_label.setVisible(bool(title))
        table.viewport().installEventFilter(self)
        model = table.model()
        if model is not None:
            for signal_name in ("modelReset", "rowsInserted", "rowsRemoved"):
                getattr(model, signal_name).connect(lambda *_: self.refresh())
        self.refresh()

    def add_action(self, text: str, callback: Callable[[], Any]) -> QPushButton:
        button = QPushButton(text, self)
        button.setObjectName("EmptyStateAction")
        button.setAutoDefault(False)
        button.clicked.connect(lambda _=False: callback())
        self._actions.insertWidget(self._actions.count() - 1, button)
        return button

    def set_actions_visible(self, visible: bool) -> None:
        for index in range(self._actions.count()):
            widget = self._actions.itemAt(index).widget()
            if widget is not None:
                widget.setVisible(visible)

    def setText(self, text: str) -> None:  # noqa: N802 - mirrors QLabel
        self.body_label.setText(text)

    def text(self) -> str:
        return self.body_label.text()

    def set_title(self, title: str) -> None:
        self.title_label.setText(title)
        self.title_label.setVisible(bool(title))

    def eventFilter(self, watched, event) -> bool:
        if watched is self._table.viewport() and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Show,
        }:
            self.setGeometry(self._table.viewport().rect())
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        model = self._table.model()
        empty = model is None or model.rowCount() == 0
        self.setVisible(empty)
        if empty:
            self.setGeometry(self._table.viewport().rect())
            self.raise_()


class TableTotalsFooter(QWidget):
    """Bold totals drawn under a table, aligned to its visible columns."""

    def __init__(self, table: QTableView, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = table
        self._values: dict[int, str] = {}
        self._first = "Total"
        self.setObjectName("TableTotalsFooter")
        header = table.horizontalHeader()
        header.sectionResized.connect(lambda *_: self.update())
        header.sectionMoved.connect(lambda *_: self.update())
        table.horizontalScrollBar().valueChanged.connect(lambda *_: self.update())
        self.setFixedHeight(table.verticalHeader().defaultSectionSize() + 6)

    def set_values(self, values: dict[int, str], *, first: str = "Total") -> None:
        self._values = values
        self._first = first
        self.update()

    def values(self) -> dict[int, str]:
        """The totals by column, as shown."""
        return dict(self._values)

    def clear(self) -> None:
        self._values = {}
        self.update()

    def text(self) -> str:
        return " ".join(self._values[key] for key in sorted(self._values))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(HEADER_BG))
        painter.setPen(QColor(CARD_BORDER))
        painter.drawLine(0, 0, self.width(), 0)
        if not self._values:
            return
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(TEXT_STRONG))
        header = self._table.horizontalHeader()
        offset = self._table.viewport().x() + self._table.x() - self.x()
        for column in range(header.count()):
            if header.isSectionHidden(column):
                continue
            left = header.sectionViewportPosition(column) + offset
            rect = QRect(left + 8, 0, header.sectionSize(column) - 16, self.height())
            if column == 0:
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                    self._first,
                )
            elif column in self._values:
                painter.drawText(
                    rect,
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    self._values[column],
                )


class WeightBarDelegate(QStyledItemDelegate):
    """Draws a weight with zeros muted, and optionally a share-of-largest bar.

    The bar is a tinted band behind the figure, anchored to the right like
    the number itself, so it never crosses the digits.

    Item colours are painted here because the screen stylesheet overrides the
    model's foreground colour.
    """

    def __init__(
        self, value_at: Callable[[int], float] | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self._value_at = value_at
        self._maximum = 0.0

    def set_maximum(self, maximum: float) -> None:
        self._maximum = max(0.0, float(maximum))

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        text = item.text
        item.text = ""
        style = item.widget.style() if item.widget is not None else None
        if style is not None:
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, item, painter, item.widget
            )
        self._paint_bar(painter, option, index)
        zero = text.strip() in {"0", "0.00", "0.000"}
        painter.save()
        painter.setPen(QColor(ZERO_TEXT if zero else TEXT_STRONG))
        painter.setFont(item.font)
        painter.drawText(
            option.rect.adjusted(8, 0, -10, 0),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            text,
        )
        painter.restore()

    def _paint_bar(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        if self._value_at is None or self._maximum <= 0:
            return
        try:
            value = float(self._value_at(index.row()))
        except IndexError, TypeError, ValueError:
            return
        if value <= 0:
            return
        share = min(1.0, value / self._maximum)
        rect = option.rect.adjusted(4, 4, -4, -4)
        width = max(3, int(rect.width() * share))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(DATA_BAR_FILL))
        painter.drawRoundedRect(
            QRect(rect.right() - width + 1, rect.top(), width, rect.height()),
            3,
            3,
        )
        painter.restore()


_PILL_COLOURS = {
    "active": (INFO_BG, INFO_BORDER, INFO_TEXT),
    "issued": (WARNING_BG, WARNING_BORDER, WARNING_TEXT),
    "available": (SUCCESS_BG, SUCCESS_BORDER, SUCCESS_TEXT),
    "other": ("#f1f3f5", CARD_BORDER, "#475569"),
}


class StatusPillDelegate(QStyledItemDelegate):
    """Draws a table cell's status text as a rounded, coloured label."""

    def __init__(self, states: dict[str, str], parent=None) -> None:
        super().__init__(parent)
        self._states = states

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        text = str(index.data() or "")
        item = QStyleOptionViewItem(option)
        self.initStyleOption(item, index)
        item.text = ""
        style = item.widget.style() if item.widget is not None else None
        if style is not None:
            style.drawControl(
                QStyle.ControlElement.CE_ItemViewItem, item, painter, item.widget
            )
        if not text:
            return
        background, border, foreground = _PILL_COLOURS[self._states.get(text, "other")]
        font = QFont(option.font)
        font.setBold(True)
        font.setPointSizeF(max(7.0, font.pointSizeF() - 1))
        metrics = QFontMetrics(font)
        label_text = f"● {text}"
        width = metrics.horizontalAdvance(label_text) + 18
        height = metrics.height() + 6
        rect = QRect(
            option.rect.left() + 8,
            option.rect.center().y() - height // 2,
            min(width, option.rect.width() - 12),
            height,
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, height / 2, height / 2)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label_text)
        painter.restore()
