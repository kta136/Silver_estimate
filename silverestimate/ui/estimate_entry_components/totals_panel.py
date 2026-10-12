"""Totals panel component for estimate entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.estimate_models import TotalsResult
from silverestimate.domain.numeric_policy import WEIGHT_PLACES
from silverestimate.ui.appearance import set_table_font
from silverestimate.ui.estimate_table_formatting import format_indian_number
from silverestimate.ui.numeric_font import numeric_table_font


class _SummarySectionsListWidget(QListWidget):
    """List widget that swaps cards when dropped onto another card."""

    swap_requested = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_row = -1

    def startDrag(self, supported_actions):
        self._drag_row = self.currentRow()
        super().startDrag(supported_actions)
        self._drag_row = -1

    def dropEvent(self, event):
        source_row = self._drag_row
        if source_row < 0:
            source_row = self.currentRow()

        target_index = self.indexAt(event.pos())
        if source_row >= 0 and target_index.isValid():
            target_row = target_index.row()
            if target_row != source_row:
                self.swap_requested.emit(source_row, target_row)
            event.acceptProposedAction()
            self._drag_row = -1
            return

        super().dropEvent(event)
        self._drag_row = -1


class TotalsPanel(QWidget):
    """Panel for displaying estimate totals and calculations.

    This component displays breakdowns by category (Regular, Return, Silver Bar)
    and final calculations (Net Fine Weight, Net Wage, Grand Total).
    """

    section_order_changed = Signal(list)

    if TYPE_CHECKING:
        overall_gross_label: QLabel
        overall_poly_label: QLabel
        total_gross_label: QLabel
        total_net_label: QLabel
        total_fine_label: QLabel
        return_gross_label: QLabel
        return_net_label: QLabel
        return_fine_label: QLabel
        bar_gross_label: QLabel
        bar_net_label: QLabel
        bar_fine_label: QLabel
        net_fine_label: QLabel
        net_wage_label: QLabel
        grand_total_label: QLabel
        _summary_sections_list: _SummarySectionsListWidget
        _sidebar_top_host: QWidget
        _sidebar_top_layout: QVBoxLayout

    _FINAL_SECTION_KEY = "final_calc"
    _DEFAULT_SECTION_ORDER = [
        "final_calc",
        "totals",
        "regular",
        "return",
        "silver_bar",
    ]

    _SECTION_DEFINITIONS = {
        "totals": (
            "Totals",
            [
                ("Total gross", "overall_gross_label", "0.00"),
                ("Poly", "overall_poly_label", "0.00"),
            ],
        ),
        "regular": (
            "Regular",
            [
                ("Gross Wt:", "total_gross_label", "0.00"),
                ("Net Wt:", "total_net_label", "0.00"),
                ("Fine Wt:", "total_fine_label", "0.00"),
            ],
        ),
        "return": (
            "Return",
            [
                ("Gross Wt:", "return_gross_label", "0.00"),
                ("Net Wt:", "return_net_label", "0.00"),
                ("Fine Wt:", "return_fine_label", "0.00"),
            ],
        ),
        "silver_bar": (
            "Silver Bar",
            [
                ("Gross Wt:", "bar_gross_label", "0.00"),
                ("Net Wt:", "bar_net_label", "0.00"),
                ("Fine Wt:", "bar_fine_label", "0.00"),
            ],
        ),
    }

    @classmethod
    def default_section_order(cls) -> list[str]:
        return list(cls._DEFAULT_SECTION_ORDER)

    @classmethod
    def normalize_section_order(cls, order) -> list[str]:
        if isinstance(order, str):
            tokens = [token.strip().lower() for token in order.split(",") if token]
        elif isinstance(order, (list, tuple)):
            tokens = [str(token).strip().lower() for token in order]
        else:
            tokens = []

        valid_keys = set(cls._SECTION_DEFINITIONS)
        valid_keys.add(cls._FINAL_SECTION_KEY)
        normalized = [key for key in tokens if key in valid_keys]
        deduped: list[str] = []
        for key in normalized:
            if key not in deduped:
                deduped.append(key)
        deduped = [key for key in deduped if key != cls._FINAL_SECTION_KEY]
        deduped.insert(0, cls._FINAL_SECTION_KEY)
        for key in cls._DEFAULT_SECTION_ORDER:
            if key not in deduped:
                deduped.append(key)
        return deduped

    def __init__(self, parent=None):
        super().__init__(parent)
        self._section_order = list(self._DEFAULT_SECTION_ORDER)
        self._category_visibility = {
            "return": False,
            "silver_bar": False,
        }
        self._suspend_section_order_signals = False
        self._sidebar_size_sync_timer = QTimer(self)
        self._sidebar_size_sync_timer.setSingleShot(True)
        self._sidebar_size_sync_timer.setInterval(0)
        self._sidebar_size_sync_timer.timeout.connect(self._sync_sidebar_item_sizes)
        self._summary_tables: list[QTableWidget] = []
        self._final_calc_font_size: int | None = None
        self._setup_ui()

    def _normalize_section_order(self, order) -> list[str]:
        return self.normalize_section_order(order)

    def section_order(self) -> list[str]:
        return list(self._section_order)

    def set_section_order(self, order) -> None:
        normalized = self._normalize_section_order(order)
        if normalized == self._section_order:
            return
        self._section_order = normalized
        self._rebuild_sidebar_section_cards()

    def _breakdown_value_attr_names(self) -> list[str]:
        attrs: list[str] = []
        for _, labels_attrs in self._SECTION_DEFINITIONS.values():
            for _, attr_name, _ in labels_attrs:
                attrs.append(attr_name)
        return attrs

    def _all_value_attr_names(self) -> list[str]:
        return self._breakdown_value_attr_names() + [
            "net_fine_label",
            "net_wage_label",
            "grand_total_label",
        ]

    def _snapshot_display_state(self) -> dict[str, object]:
        texts: dict[str, str] = {}
        snapshot: dict[str, object] = {"texts": texts}
        for attr_name in self._all_value_attr_names():
            label = getattr(self, attr_name, None)
            if isinstance(label, QLabel):
                texts[attr_name] = label.text()

        breakdown_size = None
        for attr_name in self._breakdown_value_attr_names():
            label = getattr(self, attr_name, None)
            if isinstance(label, QLabel):
                breakdown_size = label.font().pointSize()
                break
        if breakdown_size and breakdown_size > 0:
            snapshot["breakdown_size"] = int(breakdown_size)

        final_size = self._final_calc_font_size
        if not final_size:
            label = getattr(self, "grand_total_label", None)
            if isinstance(label, QLabel):
                final_size = label.font().pointSize()
        if final_size and final_size > 0:
            snapshot["final_size"] = int(final_size)

        return snapshot

    def _restore_display_state(self, snapshot: dict[str, object]) -> None:
        texts = snapshot.get("texts")
        if isinstance(texts, dict):
            for attr_name, value in texts.items():
                label = getattr(self, attr_name, None)
                if isinstance(label, QLabel):
                    label.setText(str(value))

        breakdown_size = snapshot.get("breakdown_size")
        if isinstance(breakdown_size, int) and breakdown_size > 0:
            self.set_breakdown_font_size(int(breakdown_size))

        final_size = snapshot.get("final_size")
        if isinstance(final_size, int) and final_size > 0:
            self.set_final_calc_font_size(int(final_size))

    @staticmethod
    def _create_metric_header(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("FinalMetricLabel")
        label.setProperty("sectionKind", TotalsPanel._FINAL_SECTION_KEY)
        header_font = label.font()
        header_font.setBold(True)
        label.setFont(header_font)
        return label

    def _create_sidebar_section_card(
        self, title, labels_attrs, section_key: str = "regular"
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("TotalsCard")
        card.setProperty("sectionKind", section_key)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(4)

        self._category_keys = [
            key
            for key in self._section_order
            if key in {"regular", "return", "silver_bar"}
        ]
        self.category_table = self._create_summary_table(len(self._category_keys), 4)
        self.category_table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._populate_category_table("matrix", preserve=False)
        card_layout.addWidget(self.category_table)

        # Overall gross and poly share one footer line under the categories.
        overall = self._create_summary_table(1, 2 * len(labels_attrs))
        overall.horizontalHeader().hide()
        for index, (caption, attr, default) in enumerate(labels_attrs):
            self._set_summary_caption(overall, 0, caption, 2 * index)
            self._set_summary_value(overall, 0, 2 * index + 1, attr, default)
        card_layout.addWidget(overall)
        return card

    def _populate_category_table(self, mode: str, *, preserve: bool = True) -> None:
        """Reflow the same values into narrower tables without reducing text size."""
        table = self.category_table
        values = {}
        for key in self._category_keys:
            for _, attr, default in self._SECTION_DEFINITIONS[key][1]:
                label = getattr(self, attr, None) if preserve else None
                values[attr] = label.text() if label is not None else default
        table.clearSpans()
        table.clearContents()
        table.setColumnCount({"matrix": 4, "groups": 3, "details": 2}[mode])
        table.setRowCount(
            len(self._category_keys) * {"matrix": 1, "groups": 2, "details": 4}[mode]
        )
        headers = ["Gross", "Net", "Fine"]
        table.setHorizontalHeaderLabels(
            ["", *headers]
            if mode == "matrix"
            else headers
            if mode == "groups"
            else ["", "Weight"]
        )
        for index, key in enumerate(self._category_keys):
            caption, definitions = self._SECTION_DEFINITIONS[key]
            row = index * {"matrix": 1, "groups": 2, "details": 4}[mode]
            self._set_summary_caption(table, row, caption, category=key)
            if mode != "matrix":
                table.setSpan(row, 0, 1, table.columnCount())
            for metric, (_, attr, _) in enumerate(definitions):
                value_row = (
                    row
                    if mode == "matrix"
                    else row + 1
                    if mode == "groups"
                    else row + metric + 1
                )
                value_column = (
                    metric + 1
                    if mode == "matrix"
                    else metric
                    if mode == "groups"
                    else 1
                )
                if mode == "details":
                    self._set_summary_caption(
                        table,
                        value_row,
                        ("Gross", "Net", "Fine")[metric],
                        category=key,
                    )
                self._set_summary_value(
                    table, value_row, value_column, attr, values[attr]
                ).setProperty("categoryKind", key)
        for column in range(table.columnCount()):
            table.horizontalHeaderItem(column).setFont(table.font())
        self._category_layout_mode = mode

    def _reflow_category_table(self, available: int) -> None:
        table = self.category_table
        metrics = table.fontMetrics()
        widths = [
            metrics.horizontalAdvance(text) + 12 for text in ("Gross", "Net", "Fine")
        ]
        caption_width = 0
        rows_per_category = {"matrix": 1, "groups": 2, "details": 4}[
            self._category_layout_mode
        ]
        for category_index, key in enumerate(self._category_keys):
            caption, definitions = self._SECTION_DEFINITIONS[key]
            caption_width = max(caption_width, metrics.horizontalAdvance(caption) + 12)
            caption_label = table.cellWidget(category_index * rows_per_category, 0)
            if isinstance(caption_label, QLabel):
                caption_width = max(
                    caption_width,
                    caption_label.sizeHint().width() + 2,
                    caption_label.fontMetrics().horizontalAdvance(caption) + 12,
                )
            for index, (_, attr, _) in enumerate(definitions):
                label = getattr(self, attr)
                widths[index] = max(
                    widths[index],
                    label.sizeHint().width() + 2,
                    label.fontMetrics().horizontalAdvance(label.text()) + 12,
                )
        mode = (
            "matrix"
            if caption_width + sum(widths) <= available
            else "groups"
            if sum(widths) <= available
            else "details"
        )
        if mode != self._category_layout_mode:
            self._populate_category_table(mode)

    def _create_summary_table(self, rows: int, columns: int) -> QTableWidget:
        table = QTableWidget(rows, columns)
        table.setObjectName("SummaryTable")
        table.setFrameShape(QFrame.Shape.NoFrame)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        table.horizontalHeader().setMinimumSectionSize(24)
        table.setShowGrid(True)
        table.setWordWrap(False)
        table.viewport().installEventFilter(self)
        self._summary_tables.append(table)
        return table

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.Resize
            and event.size().width() != event.oldSize().width()
        ):
            # Qt can settle the viewport width after the card's layout pass.
            self._schedule_sidebar_item_size_sync()
        return super().eventFilter(watched, event)

    @staticmethod
    def _set_summary_caption(table, row, caption, column=0, category=""):
        label = QLabel(caption)
        label.setObjectName("MetricLabel")
        label.setProperty("categoryKind", category)
        label.setFont(table.font())
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        table.setCellWidget(row, column, label)

    def _set_summary_value(self, table, row, column, attr, default) -> QLabel:
        label = QLabel(default)
        label.setObjectName("MetricValue")
        label.setProperty("categoryKind", "")
        label.setFont(numeric_table_font(table.font()))
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        setattr(self, attr, label)
        table.setCellWidget(row, column, label)
        return label

    def _fit_summary_table(self, table: QTableWidget) -> None:
        widths = []
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            width = (
                table.fontMetrics().horizontalAdvance(header.text() if header else "")
                + 12
            )
            for row in range(table.rowCount()):
                cell = table.cellWidget(row, column)
                if not isinstance(cell, QLabel) or table.columnSpan(row, column) > 1:
                    continue
                width = max(
                    width,
                    cell.sizeHint().width() + 2,
                    cell.fontMetrics().horizontalAdvance(cell.text()) + 12,
                )
            widths.append(max(24, width))
        available = table.viewport().width()
        extra = max(0, available - sum(widths))
        first = (
            0
            if table is self.category_table and self._category_layout_mode == "groups"
            else 1
        )
        for column in range(first, len(widths)):
            share = extra // (len(widths) - column)
            widths[column] += share
            extra -= share
        for column, width in enumerate(widths):
            table.setColumnWidth(column, width)
        row_height = max(22, table.fontMetrics().height() + 4)
        table.verticalHeader().setMinimumSectionSize(row_height)
        table.verticalHeader().setDefaultSectionSize(row_height)
        table.horizontalHeader().setFixedHeight(row_height)
        height = row_height * (
            table.rowCount() + int(not table.horizontalHeader().isHidden())
        )
        if sum(widths) > available:
            height += table.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent)
        table.setFixedHeight(height + 2)

    def _create_sidebar_final_calc_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("FinalCalcCard")
        card.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        outer_layout = QVBoxLayout(card)
        outer_layout.setContentsMargins(0, 0, 0, 6)
        outer_layout.setSpacing(4)

        header = QFrame(card)
        header.setObjectName("FinalCalcHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 6, 10, 6)
        header_layout.setSpacing(8)

        final_title = QLabel("Grand Total")
        final_title.setObjectName("SectionTitle")
        final_title.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self._grand_total_caption = final_title
        self._grand_total_header_layout = header_layout
        header_layout.addWidget(final_title)
        header_layout.addStretch(1)

        self.grand_total_label = QLabel(self._format_currency(0))
        self.grand_total_label.setObjectName("GrandTotalValue")
        self.grand_total_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.grand_total_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addWidget(self.grand_total_label)
        outer_layout.addWidget(header)

        final_layout = QFormLayout()
        final_layout.setContentsMargins(10, 0, 10, 0)
        final_layout.setHorizontalSpacing(8)
        final_layout.setVerticalSpacing(2)
        final_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        final_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.net_fine_label = QLabel("0.00")
        self.net_fine_label.setObjectName("MetricValue")
        self.net_fine_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_fine_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        final_layout.addRow(
            self._create_metric_header("Net Fine (g)"), self.net_fine_label
        )

        self.net_wage_label = QLabel("0.00")
        self.net_wage_label.setObjectName("MetricValue")
        self.net_wage_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_wage_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        final_layout.addRow(
            self._create_metric_header("Net Labour (₹)"), self.net_wage_label
        )
        outer_layout.addLayout(final_layout)

        return card

    def _sidebar_section_order_from_list(self) -> list[str]:
        valid_keys = set(self._SECTION_DEFINITIONS)
        valid_keys.add(self._FINAL_SECTION_KEY)
        order: list[str] = []
        for idx in range(self._summary_sections_list.count()):
            item = self._summary_sections_list.item(idx)
            key = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
            key = str(key).strip().lower() if key is not None else ""
            if key not in valid_keys and item is not None:
                card = self._summary_sections_list.itemWidget(item)
                if card is not None:
                    card_key = card.property("sectionKind")
                    key = str(card_key).strip().lower() if card_key is not None else ""
            if key in valid_keys and key not in order:
                order.append(key)
        return self._normalize_section_order(order)

    def _on_sidebar_section_rows_moved(self, *_args) -> None:
        if self._suspend_section_order_signals:
            return
        order = self._sidebar_section_order_from_list()
        changed = order != self._section_order
        self._section_order = order
        # Rebuild after every drop to avoid setItemWidget rendering glitches.
        self._rebuild_sidebar_section_cards()
        if changed:
            self.section_order_changed.emit(list(self._section_order))

    def _on_sidebar_section_swap_requested(
        self, source_row: int, target_row: int
    ) -> None:
        if self._suspend_section_order_signals:
            return
        if source_row < 0 or target_row < 0:
            return
        if source_row >= len(self._section_order) or target_row >= len(
            self._section_order
        ):
            return
        if source_row == target_row:
            self._schedule_sidebar_item_size_sync()
            return
        if self._section_order[source_row] == self._FINAL_SECTION_KEY:
            self._schedule_sidebar_item_size_sync()
            return
        if self._section_order[target_row] == self._FINAL_SECTION_KEY:
            self._schedule_sidebar_item_size_sync()
            return

        updated = list(self._section_order)
        updated[source_row], updated[target_row] = (
            updated[target_row],
            updated[source_row],
        )
        self._section_order = updated
        self._rebuild_sidebar_section_cards()
        self.section_order_changed.emit(list(self._section_order))

    def _schedule_sidebar_item_size_sync(self) -> None:
        if self._sidebar_size_sync_timer.isActive():
            self._sidebar_size_sync_timer.stop()
        self._sidebar_size_sync_timer.start()

    def _sync_sidebar_item_sizes(self) -> None:
        viewport = self._summary_sections_list.viewport()
        target_width = max(0, viewport.width() - 8)
        for idx in range(self._summary_sections_list.count()):
            item = self._summary_sections_list.item(idx)
            card = self._summary_sections_list.itemWidget(item)
            card.setFixedWidth(target_width)
            if card.property("sectionKind") == self._FINAL_SECTION_KEY:
                # Reserve the actual painted text width before choosing a layout.
                # Large totals must reflow instead of being squeezed by QFormLayout.
                self._shrink_grand_total_to_fit(target_width)
                for label in (
                    self.grand_total_label,
                    self.net_fine_label,
                    self.net_wage_label,
                ):
                    label.setMinimumWidth(
                        label.fontMetrics().horizontalAdvance(label.text()) + 2
                    )
                header_layout = self._grand_total_header_layout
                margins = header_layout.contentsMargins()
                required_width = (
                    self._grand_total_caption.sizeHint().width()
                    + self.grand_total_label.sizeHint().width()
                    + margins.left()
                    + margins.right()
                    + header_layout.spacing()
                )
                header_layout.setDirection(
                    QBoxLayout.Direction.TopToBottom
                    if required_width > target_width
                    else QBoxLayout.Direction.LeftToRight
                )
            card.layout().activate()
            if card.property("sectionKind") == "totals":
                self._reflow_category_table(
                    max(
                        0,
                        min(target_width - 2, self.category_table.viewport().width())
                        - 4,
                    )
                )
            for table in card.findChildren(QTableWidget):
                self._fit_summary_table(table)
            card_layout = card.layout()
            card_layout.activate()
            # A row that wraps (a long value under its caption) is taller than
            # the size hint, which does not know the card's width.
            height = card.sizeHint().height()
            if card_layout.hasHeightForWidth():
                height = max(height, card_layout.totalHeightForWidth(target_width))
            item.setSizeHint(QSize(target_width, height))
        # From the size hints just set, not sizeHintForRow(), which still
        # reports the old heights until the list has laid itself out again.
        self._summary_sections_list.setFixedHeight(
            sum(
                (
                    0
                    if self._summary_sections_list.item(i).isHidden()
                    else self._summary_sections_list.item(i).sizeHint().height()
                )
                + 4
                for i in range(self._summary_sections_list.count())
            )
            + 8
        )

    # The grand total is shown smaller than the chosen size, down to this,
    # before it gives up the caption's line.
    _GRAND_TOTAL_MIN_POINT_SIZE = 11

    def _shrink_grand_total_to_fit(self, card_width: int) -> None:
        """Keep the grand total on the caption's line while it can be read.

        A large or negative total (₹ -10,00,000.00) outgrows the side panel
        at the chosen size. Stacking it under the caption costs a line of
        height, which pushes the panel's buttons out of a short window, so
        the value gets smaller first and only stacks if even that is too wide.
        """
        label = self.grand_total_label
        base = self._final_calc_font_size or label.font().pointSize()
        if base <= 0:
            return
        margins = self._grand_total_header_layout.contentsMargins()
        spare = (
            card_width
            - margins.left()
            - margins.right()
            - self._grand_total_header_layout.spacing()
            - self._grand_total_caption.sizeHint().width()
        )
        floor = min(base, self._GRAND_TOTAL_MIN_POINT_SIZE)
        size = base
        while size > floor:
            font = QFont(label.font())
            font.setPointSize(size)
            font.setBold(True)
            if QFontMetrics(font).horizontalAdvance(label.text()) + 2 <= spare:
                break
            size -= 1
        font = QFont(label.font())
        font.setPointSize(size)
        font.setBold(True)
        if font.pointSize() != label.font().pointSize():
            label.setFont(font)

    def _rebuild_sidebar_section_cards(self) -> None:
        snapshot = self._snapshot_display_state()
        self._suspend_section_order_signals = True
        try:
            self._summary_tables.clear()
            self._summary_sections_list.clear()
            for section_key in (self._FINAL_SECTION_KEY, "totals"):
                if section_key == self._FINAL_SECTION_KEY:
                    card = self._create_sidebar_final_calc_card()
                else:
                    title, labels_attrs = self._SECTION_DEFINITIONS[section_key]
                    card = self._create_sidebar_section_card(
                        title, labels_attrs, section_key
                    )
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, section_key)
                item_flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                if section_key != self._FINAL_SECTION_KEY:
                    card.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    card.setToolTip(
                        "Right-click to change the order of the Regular, "
                        "Return and Silver Bar rows"
                    )
                card.customContextMenuRequested.connect(
                    lambda pos, widget=card: self._show_category_menu(widget, pos)
                )
                item.setFlags(item_flags)
                self._summary_sections_list.addItem(item)
                self._summary_sections_list.setItemWidget(item, card)
                if section_key in self._category_visibility:
                    item.setHidden(not self._category_visibility[section_key])
        finally:
            self._suspend_section_order_signals = False
        self._restore_display_state(snapshot)
        self._schedule_sidebar_item_size_sync()

    def _show_category_menu(self, card, pos):
        """Offer to reorder the Regular, Return and Silver Bar rows."""
        menu = QMenu(card)
        heading = menu.addAction("Order of These Rows")
        heading.setEnabled(False)
        order = [
            key
            for key in self._section_order
            if key in {"regular", "return", "silver_bar"}
        ]
        for index, key in enumerate(order):
            menu.addSeparator()
            title = self._SECTION_DEFINITIONS[key][0]
            for delta, direction in ((-1, "Up"), (1, "Down")):
                action = menu.addAction(f"Move {title} {direction}")
                # The first row cannot go up, nor the last one down.
                action.setEnabled(0 <= index + delta < len(order))
                action.triggered.connect(
                    lambda checked=False, category=key, step=delta: self.move_category(
                        category, step
                    )
                )
        menu.exec(card.mapToGlobal(pos))

    def move_category(self, key, delta):
        categories = [
            value
            for value in self._section_order
            if value in {"regular", "return", "silver_bar"}
        ]
        index = categories.index(key)
        destination = index + delta
        if 0 <= destination < len(categories):
            self._on_sidebar_section_swap_requested(
                self._section_order.index(key),
                self._section_order.index(categories[destination]),
            )

    def _setup_ui(self) -> None:
        self.setObjectName("TotalsSidebar")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        contents = QWidget()
        scroll.setWidget(contents)
        outer.addWidget(scroll)
        main_layout = QVBoxLayout(contents)
        self._contents_layout = main_layout
        main_layout.setContentsMargins(4, 4, 4, 4)
        # Tight enough that the whole panel fits the smallest window (a
        # maximized one on a 1280x720 screen) with no scrollbar and a little to
        # spare.
        main_layout.setSpacing(4)

        self._sidebar_top_host = QWidget()
        self._sidebar_top_layout = QVBoxLayout(self._sidebar_top_host)
        self._sidebar_top_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_top_layout.setSpacing(4)
        self._sidebar_top_host.setVisible(False)
        main_layout.addWidget(self._sidebar_top_host)

        self._summary_sections_list = _SummarySectionsListWidget()
        self._summary_sections_list.setObjectName("SummarySectionsList")
        self._summary_sections_list.setSpacing(4)
        self._summary_sections_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self._summary_sections_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._summary_sections_list.setDragDropOverwriteMode(False)
        self._summary_sections_list.setDropIndicatorShown(True)
        self._summary_sections_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._summary_sections_list.setUniformItemSizes(False)
        self._summary_sections_list.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self._summary_sections_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._summary_sections_list.swap_requested.connect(
            self._on_sidebar_section_swap_requested
        )
        self._summary_sections_list.model().rowsMoved.connect(
            self._on_sidebar_section_rows_moved
        )
        main_layout.addWidget(self._summary_sections_list)
        self.sidebar_actions_host = QWidget(self)
        self.sidebar_actions_layout = QVBoxLayout(self.sidebar_actions_host)
        self.sidebar_actions_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.sidebar_actions_host)
        main_layout.addStretch(1)
        self._rebuild_sidebar_section_cards()

    def content_minimum_width(self) -> int:
        """The narrowest the panel can be without cutting off its contents."""
        return self._contents_layout.minimumSize().width()

    def set_sidebar_top_widgets(self, widgets: list[QWidget]) -> None:
        """Attach widgets, top to bottom, above the sidebar summary cards."""
        while self._sidebar_top_layout.count():
            item = self._sidebar_top_layout.takeAt(0)
            child_widget = item.widget()
            if child_widget is not None and child_widget not in widgets:
                child_widget.setParent(cast(QWidget, None))

        for widget in widgets:
            self._sidebar_top_layout.addWidget(widget)
        self._sidebar_top_host.setVisible(bool(widgets))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_sidebar_item_size_sync()

    # Public methods for updating totals

    def _set_category_visibility(self, section_key: str, visible: bool) -> None:
        if section_key not in self._category_visibility:
            return
        self._category_visibility[section_key] = bool(visible)
        for index in range(self._summary_sections_list.count()):
            item = self._summary_sections_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == section_key:
                item.setHidden(not visible)
                break
        self._schedule_sidebar_item_size_sync()

    @staticmethod
    def _category_has_value(category) -> bool:
        return any(
            abs(float(getattr(category, field, 0.0) or 0.0)) > 0.000001
            for field in ("gross", "net", "fine")
        )

    @staticmethod
    def _format_weight(value: float) -> str:
        """Format weights in grams to the shared weight precision."""
        try:
            return format_indian_number(value, WEIGHT_PLACES)
        except Exception:
            return "0.00"

    @staticmethod
    def _format_amount(value: float) -> str:
        """Format monetary amounts to paise."""
        try:
            return format_indian_number(value, 2)
        except Exception:
            return "0.00"

    @staticmethod
    def _format_currency(value: float) -> str:
        """Format currency with separators."""
        return f"₹ {TotalsPanel._format_amount(value)}"

    def set_totals(self, totals: TotalsResult) -> None:
        """Update all totals from a TotalsResult.

        Args:
            totals: The totals result containing all calculations
        """
        # Overall totals
        self.overall_gross_label.setText(self._format_weight(totals.overall_gross))
        self.overall_poly_label.setText(self._format_weight(totals.overall_poly))

        # Regular items
        self.total_gross_label.setText(self._format_weight(totals.regular.gross))
        self.total_net_label.setText(self._format_weight(totals.regular.net))
        self.total_fine_label.setText(self._format_weight(totals.regular.fine))

        # Return items
        self.return_gross_label.setText(self._format_weight(totals.returns.gross))
        self.return_net_label.setText(self._format_weight(totals.returns.net))
        self.return_fine_label.setText(self._format_weight(totals.returns.fine))

        # Silver bars
        self.bar_gross_label.setText(self._format_weight(totals.silver_bars.gross))
        self.bar_net_label.setText(self._format_weight(totals.silver_bars.net))
        self.bar_fine_label.setText(self._format_weight(totals.silver_bars.fine))

        self._set_category_visibility(
            "return", self._category_has_value(totals.returns)
        )
        self._set_category_visibility(
            "silver_bar", self._category_has_value(totals.silver_bars)
        )

        # Final calculations
        self.net_fine_label.setText(self._format_weight(totals.net_fine))
        self.net_wage_label.setText(self._format_amount(totals.net_wage))
        self.grand_total_label.setText(self._format_currency(totals.grand_total))
        self._schedule_sidebar_item_size_sync()

    # Font size methods used by the estimate layout controller.

    def set_breakdown_font_size(self, size: int) -> None:
        """Apply font size to breakdown totals labels.

        Args:
            size: Font point size
        """
        self._breakdown_font_size = int(size)
        for label in self.findChildren(QLabel):
            if label.property("sectionKind") == self._FINAL_SECTION_KEY:
                continue
            if label.objectName() not in {
                "MetricLabel",
                "MetricValue",
                "SectionTitle",
                "FinalMetricLabel",
            }:
                continue
            font = label.font()
            font.setPointSize(int(size))
            if label.objectName() == "MetricValue":
                font = numeric_table_font(font)
            label.setFont(font)
        for table in self._summary_tables:
            font = table.font()
            font.setPointSize(int(size))
            set_table_font(table, font)
            for column in range(table.columnCount()):
                header = table.horizontalHeaderItem(column)
                if header is not None:
                    header.setFont(font)
            self._fit_summary_table(table)
        self._schedule_sidebar_item_size_sync()

    def set_final_calc_font_size(self, size: int) -> None:
        """Apply font size to final calculation labels.

        Args:
            size: Font point size
        """
        self._final_calc_font_size = int(size)
        for label in self.findChildren(QLabel):
            if label.property("sectionKind") != self._FINAL_SECTION_KEY:
                continue
            font = label.font()
            font.setPointSize(int(size))
            if label.objectName() == "MetricValue":
                font = numeric_table_font(font)
                font.setBold(False)
            elif label.objectName() == "GrandTotalValue":
                font.setBold(True)
            label.setFont(font)
        self._schedule_sidebar_item_size_sync()
