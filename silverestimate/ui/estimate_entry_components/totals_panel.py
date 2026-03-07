"""Totals panel component for estimate entry."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PyQt5.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from silverestimate.domain.estimate_models import TotalsResult
from silverestimate.ui.estimate_table_formatting import format_indian_number


class _SummarySectionsListWidget(QListWidget):
    """List widget that swaps cards when dropped onto another card."""

    swap_requested = pyqtSignal(int, int)

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

    section_order_changed = pyqtSignal(list)

    if TYPE_CHECKING:
        mode_indicator_label: QLabel
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
                ("Total Gross Wt:", "overall_gross_label", "0.0"),
                ("Total Poly Wt:", "overall_poly_label", "0.0"),
            ],
        ),
        "regular": (
            "Regular",
            [
                ("Gross Wt:", "total_gross_label", "0.0"),
                ("Net Wt:", "total_net_label", "0.0"),
                ("Fine Wt:", "total_fine_label", "0.0"),
            ],
        ),
        "return": (
            "Return",
            [
                ("Gross Wt:", "return_gross_label", "0.0"),
                ("Net Wt:", "return_net_label", "0.0"),
                ("Fine Wt:", "return_fine_label", "0.0"),
            ],
        ),
        "silver_bar": (
            "Silver Bar",
            [
                ("Gross Wt:", "bar_gross_label", "0.0"),
                ("Net Wt:", "bar_net_label", "0.0"),
                ("Fine Wt:", "bar_fine_label", "0.0"),
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
        if cls._FINAL_SECTION_KEY not in deduped:
            deduped.insert(0, cls._FINAL_SECTION_KEY)
        for key in cls._DEFAULT_SECTION_ORDER:
            if key not in deduped:
                deduped.append(key)
        return deduped

    def __init__(self, parent=None, *, layout_mode: str = "horizontal"):
        """Initialize the totals panel.

        Args:
            parent: Optional parent widget
            layout_mode: "horizontal" (legacy footer) or "sidebar" (right panel)
        """
        super().__init__(parent)
        self._layout_mode = (layout_mode or "horizontal").strip().lower()
        self._section_order = list(self._DEFAULT_SECTION_ORDER)
        self._suspend_section_order_signals = False
        self._sidebar_size_sync_timer = QTimer(self)
        self._sidebar_size_sync_timer.setSingleShot(True)
        self._sidebar_size_sync_timer.setInterval(0)
        self._sidebar_size_sync_timer.timeout.connect(self._sync_sidebar_item_sizes)
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
        if self._layout_mode == "sidebar":
            self._rebuild_sidebar_section_cards()
        else:
            self._build_horizontal_sections()

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

        final_size = None
        for attr_name in ("net_fine_label", "net_wage_label", "grand_total_label"):
            label = getattr(self, attr_name, None)
            if isinstance(label, QLabel):
                final_size = label.font().pointSize()
                break
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

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            child_widget = item.widget()
            child_layout = item.layout()
            if child_widget is not None:
                child_widget.deleteLater()
            elif child_layout is not None:
                self._clear_layout(child_layout)

    def _setup_ui(self) -> None:
        """Set up the user interface."""
        # Hidden compatibility label so existing logic can continue to update it
        self.mode_indicator_label = QLabel("Mode: Regular")
        self.mode_indicator_label.setVisible(False)

        if self._layout_mode == "sidebar":
            self._setup_sidebar_ui()
            return
        self._setup_horizontal_ui()

    def _create_breakdown_form(self, title, labels_attrs, section_key: str = "regular"):
        form = QFormLayout()
        form.setSpacing(2)
        form.setHorizontalSpacing(6)
        form.setVerticalSpacing(2)

        title_label = QLabel(f"{title}")
        title_label.setObjectName("SectionTitle")
        title_label.setProperty("sectionKind", section_key)
        title_font = title_label.font()
        title_font.setBold(True)
        title_font.setUnderline(True)
        title_label.setFont(title_font)
        form.addRow(title_label)

        for label_text, attr_name, default_value in labels_attrs:
            row_label = QLabel(label_text)
            row_label.setObjectName("MetricLabel")
            row_label.setProperty("sectionKind", section_key)

            value_label = QLabel(default_value)
            value_label.setObjectName("MetricValue")
            value_label.setProperty("sectionKind", section_key)
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            setattr(self, attr_name, value_label)
            form.addRow(row_label, value_label)
        return form

    def _create_separator(self):
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFrameShadow(QFrame.Sunken)
        return sep

    def _setup_horizontal_ui(self) -> None:
        self.setObjectName("TotalsContainer")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self._horizontal_main_layout = QHBoxLayout(self)
        self._horizontal_main_layout.setSpacing(8)
        self._horizontal_main_layout.setContentsMargins(8, 3, 12, 6)
        self._build_horizontal_sections()

    def _create_horizontal_final_calc_form(self):
        final_calc_form = QFormLayout()
        final_calc_form.setSpacing(4)
        final_calc_form.setHorizontalSpacing(8)
        final_calc_form.setVerticalSpacing(2)
        final_calc_form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        final_calc_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        final_title_label = QLabel("Final Calculation")
        final_title_label.setObjectName("SectionTitle")
        final_title_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        final_title_font = final_title_label.font()
        final_title_font.setBold(True)
        final_title_font.setUnderline(True)
        final_title_label.setFont(final_title_font)
        final_calc_form.addRow(final_title_label)

        self.net_fine_label = QLabel("0.0")
        self.net_fine_label.setObjectName("MetricValue")
        self.net_fine_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_fine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_fine_label.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Preferred
        )
        self.net_fine_label.setMinimumWidth(84)
        net_fine_header = QLabel("Net Fine Wt:")
        net_fine_header.setObjectName("FinalMetricLabel")
        net_fine_header_font = net_fine_header.font()
        net_fine_header_font.setBold(True)
        net_fine_header.setFont(net_fine_header_font)
        final_calc_form.addRow(net_fine_header, self.net_fine_label)

        self.net_wage_label = QLabel("0")
        self.net_wage_label.setObjectName("MetricValue")
        self.net_wage_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_wage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.net_wage_label.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Preferred
        )
        self.net_wage_label.setMinimumWidth(84)
        net_wage_header = QLabel("Net Wage:")
        net_wage_header.setObjectName("FinalMetricLabel")
        net_wage_header_font = net_wage_header.font()
        net_wage_header_font.setBold(True)
        net_wage_header.setFont(net_wage_header_font)
        final_calc_form.addRow(net_wage_header, self.net_wage_label)

        line_before_grand = QFrame()
        line_before_grand.setFrameShape(QFrame.HLine)
        line_before_grand.setFrameShadow(QFrame.Sunken)
        final_calc_form.addRow(line_before_grand)

        self.grand_total_label = QLabel("0")
        self.grand_total_label.setObjectName("GrandTotalValue")
        self.grand_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.grand_total_label.setSizePolicy(
            QSizePolicy.MinimumExpanding, QSizePolicy.Preferred
        )
        self.grand_total_label.setMinimumWidth(84)
        grand_total_header = QLabel("Grand Total:")
        grand_total_header.setObjectName("FinalMetricLabel")
        grand_total_header_font = grand_total_header.font()
        grand_total_header_font.setBold(True)
        grand_total_header.setFont(grand_total_header_font)
        final_calc_form.addRow(grand_total_header, self.grand_total_label)

        return final_calc_form

    def _build_horizontal_sections(self) -> None:
        snapshot = self._snapshot_display_state()
        self._clear_layout(self._horizontal_main_layout)

        breakdown_order = [
            key for key in self._section_order if key in self._SECTION_DEFINITIONS
        ]

        for idx, section_key in enumerate(breakdown_order):
            title, labels_attrs = self._SECTION_DEFINITIONS[section_key]
            self._horizontal_main_layout.addLayout(
                self._create_breakdown_form(title, labels_attrs, section_key)
            )
            if idx < len(breakdown_order) - 1:
                self._horizontal_main_layout.addWidget(self._create_separator())

        self._horizontal_main_layout.addStretch(1)
        self._horizontal_main_layout.addWidget(self._create_separator())
        self._horizontal_main_layout.addLayout(
            self._create_horizontal_final_calc_form()
        )
        self._restore_display_state(snapshot)

    def _create_sidebar_section_card(
        self, title, labels_attrs, section_key: str = "regular"
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("TotalsCard")
        card.setProperty("sectionKind", section_key)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        section_title = QLabel(title)
        section_title.setObjectName("SectionTitle")
        section_title.setProperty("sectionKind", section_key)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title_row.addWidget(section_title)
        title_row.addStretch(1)

        drag_handle = QLabel("≡")
        drag_handle.setObjectName("SectionDragHandle")
        drag_handle.setToolTip("Drag to reorder this summary card")
        title_row.addWidget(drag_handle)
        card_layout.addLayout(title_row)

        form = QFormLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(2)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for label_text, attr_name, default_value in labels_attrs:
            label_widget = QLabel(label_text)
            label_widget.setObjectName("MetricLabel")
            label_widget.setProperty("sectionKind", section_key)

            value_label = QLabel(default_value)
            value_label.setObjectName("MetricValue")
            value_label.setProperty("sectionKind", section_key)
            value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            setattr(self, attr_name, value_label)
            form.addRow(label_widget, value_label)

        card_layout.addLayout(form)
        return card

    def _create_sidebar_final_calc_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("FinalCalcCard")
        card.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        final_layout = QFormLayout(card)
        final_layout.setContentsMargins(8, 8, 8, 8)
        final_layout.setHorizontalSpacing(8)
        final_layout.setVerticalSpacing(4)
        final_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        final_title = QLabel("Final Calculation")
        final_title.setObjectName("SectionTitle")
        final_title.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(6)
        title_row.addWidget(final_title)
        title_row.addStretch(1)

        drag_handle = QLabel("≡")
        drag_handle.setObjectName("SectionDragHandle")
        drag_handle.setToolTip("Drag to reorder this summary card")
        title_row.addWidget(drag_handle)
        final_layout.addRow(title_row)

        self.net_fine_label = QLabel("0.0")
        self.net_fine_label.setObjectName("MetricValue")
        self.net_fine_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_fine_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        final_layout.addRow("Net Fine Wt:", self.net_fine_label)

        self.net_wage_label = QLabel("0")
        self.net_wage_label.setObjectName("MetricValue")
        self.net_wage_label.setProperty("sectionKind", self._FINAL_SECTION_KEY)
        self.net_wage_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        final_layout.addRow("Net Wage:", self.net_wage_label)

        line_before_grand = QFrame()
        line_before_grand.setFrameShape(QFrame.HLine)
        line_before_grand.setFrameShadow(QFrame.Sunken)
        final_layout.addRow(line_before_grand)

        self.grand_total_label = QLabel("0")
        self.grand_total_label.setObjectName("GrandTotalValue")
        self.grand_total_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        final_layout.addRow("Grand Total:", self.grand_total_label)

        return card

    def _sidebar_section_order_from_list(self) -> list[str]:
        if not hasattr(self, "_summary_sections_list"):
            return list(self._section_order)
        valid_keys = set(self._SECTION_DEFINITIONS)
        valid_keys.add(self._FINAL_SECTION_KEY)
        order: list[str] = []
        for idx in range(self._summary_sections_list.count()):
            item = self._summary_sections_list.item(idx)
            key = item.data(Qt.UserRole) if item is not None else None
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

        updated = list(self._section_order)
        updated[source_row], updated[target_row] = (
            updated[target_row],
            updated[source_row],
        )
        self._section_order = updated
        self._rebuild_sidebar_section_cards()
        self.section_order_changed.emit(list(self._section_order))

    def _schedule_sidebar_item_size_sync(self) -> None:
        if self._layout_mode != "sidebar":
            return
        if not hasattr(self, "_summary_sections_list"):
            return
        if self._sidebar_size_sync_timer.isActive():
            self._sidebar_size_sync_timer.stop()
        self._sidebar_size_sync_timer.start()

    def _sync_sidebar_item_sizes(self) -> None:
        if self._layout_mode != "sidebar":
            return
        if not hasattr(self, "_summary_sections_list"):
            return
        viewport = self._summary_sections_list.viewport()
        target_width = max(0, viewport.width() - 2)
        for idx in range(self._summary_sections_list.count()):
            item = self._summary_sections_list.item(idx)
            if item is None:
                continue
            card = self._summary_sections_list.itemWidget(item)
            card.setMinimumWidth(target_width)
            card.adjustSize()
            hint = card.sizeHint()
            item.setSizeHint(QSize(max(target_width, hint.width()), hint.height()))

    def _rebuild_sidebar_section_cards(self) -> None:
        if not hasattr(self, "_summary_sections_list"):
            return
        snapshot = self._snapshot_display_state()
        self._suspend_section_order_signals = True
        try:
            self._summary_sections_list.clear()
            for section_key in self._section_order:
                if section_key == self._FINAL_SECTION_KEY:
                    card = self._create_sidebar_final_calc_card()
                else:
                    title, labels_attrs = self._SECTION_DEFINITIONS[section_key]
                    card = self._create_sidebar_section_card(
                        title, labels_attrs, section_key
                    )
                item = QListWidgetItem()
                item.setData(Qt.UserRole, section_key)
                item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsDragEnabled
                )
                self._summary_sections_list.addItem(item)
                self._summary_sections_list.setItemWidget(item, card)
        finally:
            self._suspend_section_order_signals = False
        self._restore_display_state(snapshot)
        self._schedule_sidebar_item_size_sync()

    def _setup_sidebar_ui(self) -> None:
        self.setObjectName("TotalsSidebar")
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        self._sidebar_top_host = QWidget()
        self._sidebar_top_layout = QVBoxLayout(self._sidebar_top_host)
        self._sidebar_top_layout.setContentsMargins(0, 0, 0, 0)
        self._sidebar_top_layout.setSpacing(6)
        self._sidebar_top_host.setVisible(False)
        main_layout.addWidget(self._sidebar_top_host)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(6)
        summary_title = QLabel("Summary")
        summary_title.setObjectName("SectionTitle")
        header_row.addWidget(summary_title)
        drag_hint = QLabel("Drag cards to reorder")
        drag_hint.setObjectName("SummaryDragHint")
        header_row.addWidget(drag_hint)
        header_row.addStretch(1)
        main_layout.addLayout(header_row)
        self._summary_sections_list = _SummarySectionsListWidget()
        self._summary_sections_list.setObjectName("SummarySectionsList")
        self._summary_sections_list.setSpacing(6)
        self._summary_sections_list.setDragDropMode(QAbstractItemView.InternalMove)
        self._summary_sections_list.setDefaultDropAction(Qt.MoveAction)
        self._summary_sections_list.setDragDropOverwriteMode(False)
        self._summary_sections_list.setDropIndicatorShown(True)
        self._summary_sections_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._summary_sections_list.setUniformItemSizes(False)
        self._summary_sections_list.setVerticalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )
        self._summary_sections_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._summary_sections_list.swap_requested.connect(
            self._on_sidebar_section_swap_requested
        )
        self._summary_sections_list.model().rowsMoved.connect(
            self._on_sidebar_section_rows_moved
        )
        main_layout.addWidget(self._summary_sections_list, 1)
        self._rebuild_sidebar_section_cards()

    def set_sidebar_top_widget(self, widget: QWidget | None) -> None:
        """Attach a widget above the sidebar summary cards."""
        if self._layout_mode != "sidebar":
            return
        if not hasattr(self, "_sidebar_top_layout") or not hasattr(
            self, "_sidebar_top_host"
        ):
            return

        while self._sidebar_top_layout.count():
            item = self._sidebar_top_layout.takeAt(0)
            child_widget = item.widget()
            if child_widget is not None:
                child_widget.setParent(cast(QWidget, None))

        if widget is None:
            self._sidebar_top_host.setVisible(False)
            return

        self._sidebar_top_layout.addWidget(widget)
        self._sidebar_top_host.setVisible(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._schedule_sidebar_item_size_sync()

    # Public methods for updating totals

    @staticmethod
    def _format_weight(value: float) -> str:
        """Format weight values with two decimals."""
        try:
            return format_indian_number(value, 2)
        except Exception:
            return "0.00"

    @staticmethod
    def _format_whole(value: float) -> str:
        """Format whole-number values."""
        try:
            return format_indian_number(value, 0)
        except Exception:
            return "0"

    @staticmethod
    def _format_currency(value: float) -> str:
        """Format currency with separators."""
        return f"₹ {TotalsPanel._format_whole(value)}"

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

        # Final calculations
        self.net_fine_label.setText(self._format_weight(totals.net_fine))
        self.net_wage_label.setText(self._format_whole(totals.net_wage))
        self.grand_total_label.setText(self._format_currency(totals.grand_total))
        self._schedule_sidebar_item_size_sync()

    def clear_totals(self) -> None:
        """Reset all totals to zero."""
        # Overall totals
        self.overall_gross_label.setText("0.0")
        self.overall_poly_label.setText("0.0")

        # Regular items
        self.total_gross_label.setText("0.0")
        self.total_net_label.setText("0.0")
        self.total_fine_label.setText("0.0")

        # Return items
        self.return_gross_label.setText("0.0")
        self.return_net_label.setText("0.0")
        self.return_fine_label.setText("0.0")

        # Silver bars
        self.bar_gross_label.setText("0.0")
        self.bar_net_label.setText("0.0")
        self.bar_fine_label.setText("0.0")

        # Final calculations
        self.net_fine_label.setText("0.0")
        self.net_wage_label.setText(self._format_whole(0))
        self.grand_total_label.setText(self._format_currency(0))
        self._schedule_sidebar_item_size_sync()

    # Font size methods for EstimateLogic compatibility

    def set_breakdown_font_size(self, size: int) -> None:
        """Apply font size to breakdown totals labels.

        Args:
            size: Font point size
        """
        labels = [
            self.overall_gross_label,
            self.overall_poly_label,
            self.total_gross_label,
            self.total_net_label,
            self.total_fine_label,
            self.return_gross_label,
            self.return_net_label,
            self.return_fine_label,
            self.bar_gross_label,
            self.bar_net_label,
            self.bar_fine_label,
        ]
        for label in labels:
            font = label.font()
            font.setPointSize(int(size))
            label.setFont(font)
        self._schedule_sidebar_item_size_sync()

    def set_final_calc_font_size(self, size: int) -> None:
        """Apply font size to final calculation labels.

        Args:
            size: Font point size
        """
        # Preserve stylesheet while setting font size
        for label in [self.net_fine_label, self.net_wage_label]:
            font = label.font()
            font.setPointSize(int(size))
            label.setFont(font)

        # Grand total - preserve bold and color
        font = self.grand_total_label.font()
        font.setPointSize(int(size))
        self.grand_total_label.setFont(font)
        self._schedule_sidebar_item_size_sync()
