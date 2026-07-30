"""Appearance and estimate-layout settings page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, cast

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsStore,
    as_settings_store,
)
from silverestimate.services.settings_service import FontSettings

from .custom_font_dialog import CustomFontDialog
from .themed_controls import ThemedComboBox, ThemedSpinBox

TotalsPosition = Literal["left", "right", "bottom"]

DEFAULT_PRINT_FONT = FontSettings(family="Arial", size=8.0, bold=False)
DEFAULT_TABLE_FONT_SIZE = 9
DEFAULT_BREAKDOWN_FONT_SIZE = 9
DEFAULT_FINAL_CALC_FONT_SIZE = 10
DEFAULT_TOTALS_POSITION: TotalsPosition = "right"


@dataclass(frozen=True)
class AppearanceSettingsState:
    """Validated, Qt-independent appearance preferences."""

    print_font: FontSettings = DEFAULT_PRINT_FONT
    table_font_size: int = DEFAULT_TABLE_FONT_SIZE
    breakdown_font_size: int = DEFAULT_BREAKDOWN_FONT_SIZE
    final_calc_font_size: int = DEFAULT_FINAL_CALC_FONT_SIZE
    totals_position: TotalsPosition = DEFAULT_TOTALS_POSITION


@dataclass(frozen=True)
class AppearanceSettingsActions:
    """Narrow runtime callbacks used when appearance settings are applied."""

    apply_print_font: Callable[[FontSettings], object]
    apply_table_font_size: Callable[[int], object]
    apply_breakdown_font_size: Callable[[int], object]
    apply_final_calc_font_size: Callable[[int], object]
    apply_totals_position: Callable[[TotalsPosition], object]


class SettingsAppearanceController:
    """Load, validate, persist, and apply appearance settings."""

    def __init__(
        self,
        settings: SettingsStore,
        actions: AppearanceSettingsActions,
    ) -> None:
        self._settings = as_settings_store(settings)
        self._actions = actions

    def load_state(self) -> AppearanceSettingsState:
        default_font = DEFAULT_PRINT_FONT
        family = (
            self._settings.get_text(
                SettingsKey.FONT_FAMILY,
                default_font.family,
            )
            or default_font.family
        )
        font_size = self._settings.get_float(
            SettingsKey.FONT_SIZE,
            default_font.size,
        )
        bold = self._settings.get_bool(
            SettingsKey.FONT_BOLD,
            default_font.bold,
        )
        totals_position_value = self._settings.get_text(
            SettingsKey.UI_ESTIMATE_TOTALS_POSITION,
            DEFAULT_TOTALS_POSITION,
        )
        totals_position = (
            cast(TotalsPosition, totals_position_value)
            if totals_position_value in {"left", "right", "bottom"}
            else DEFAULT_TOTALS_POSITION
        )
        return AppearanceSettingsState(
            print_font=FontSettings(
                family=family,
                size=max(5.0, font_size),
                bold=bold,
            ),
            table_font_size=self._load_clamped_int(
                SettingsKey.UI_TABLE_FONT_SIZE,
                default=DEFAULT_TABLE_FONT_SIZE,
                minimum=7,
                maximum=16,
            ),
            breakdown_font_size=self._load_clamped_int(
                SettingsKey.UI_BREAKDOWN_FONT_SIZE,
                default=DEFAULT_BREAKDOWN_FONT_SIZE,
                minimum=7,
                maximum=16,
            ),
            final_calc_font_size=self._load_clamped_int(
                SettingsKey.UI_FINAL_CALC_FONT_SIZE,
                default=DEFAULT_FINAL_CALC_FONT_SIZE,
                minimum=8,
                maximum=20,
            ),
            totals_position=totals_position,
        )

    def apply_state(self, state: AppearanceSettingsState) -> None:
        self.validate_state(state)
        self._require_accepted(
            self._actions.apply_print_font(state.print_font),
            "print font",
        )
        self._require_accepted(
            self._actions.apply_table_font_size(state.table_font_size),
            "table font size",
        )
        self._require_accepted(
            self._actions.apply_breakdown_font_size(state.breakdown_font_size),
            "breakdown font size",
        )
        self._require_accepted(
            self._actions.apply_final_calc_font_size(state.final_calc_font_size),
            "final calculation font size",
        )
        self._require_accepted(
            self._actions.apply_totals_position(state.totals_position),
            "totals panel position",
        )

        self._settings.set(SettingsKey.FONT_FAMILY, state.print_font.family)
        self._settings.set(SettingsKey.FONT_SIZE, float(state.print_font.size))
        self._settings.set(SettingsKey.FONT_BOLD, state.print_font.bold)
        self._settings.set(SettingsKey.UI_TABLE_FONT_SIZE, state.table_font_size)
        self._settings.set(
            SettingsKey.UI_BREAKDOWN_FONT_SIZE,
            state.breakdown_font_size,
        )
        self._settings.set(
            SettingsKey.UI_FINAL_CALC_FONT_SIZE,
            state.final_calc_font_size,
        )
        self._settings.set(
            SettingsKey.UI_ESTIMATE_TOTALS_POSITION,
            state.totals_position,
        )

    @staticmethod
    def default_state() -> AppearanceSettingsState:
        return AppearanceSettingsState()

    def _load_clamped_int(
        self,
        key: SettingsKey,
        *,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        return self._settings.get_int(
            key,
            default,
            minimum=minimum,
            maximum=maximum,
        )

    @staticmethod
    def validate_state(state: AppearanceSettingsState) -> None:
        if not state.print_font.family.strip():
            raise ValueError("Print font family cannot be empty.")
        if state.print_font.size < 5.0:
            raise ValueError("Print font size must be at least 5 points.")
        if not 7 <= state.table_font_size <= 16:
            raise ValueError("Table font size must be between 7 and 16 points.")
        if not 7 <= state.breakdown_font_size <= 16:
            raise ValueError("Breakdown font size must be between 7 and 16 points.")
        if not 8 <= state.final_calc_font_size <= 20:
            raise ValueError(
                "Final calculation font size must be between 8 and 20 points."
            )
        if state.totals_position not in {"left", "right", "bottom"}:
            raise ValueError("Totals panel position is invalid.")

    @staticmethod
    def _require_accepted(result: object, label: str) -> None:
        if result is False:
            raise RuntimeError(f"Estimate view rejected {label}.")


class AppearanceSettingsPage(QWidget):
    """Own the appearance controls and expose typed page state."""

    changed = Signal()

    def __init__(
        self,
        controller: SettingsAppearanceController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        state = controller.load_state()
        self._current_print_font = state.print_font.to_qfont()
        self._build_ui(state)

    def state(self) -> AppearanceSettingsState:
        totals_position = self.totals_position_combo.currentData()
        if totals_position not in {"left", "right", "bottom"}:
            totals_position = DEFAULT_TOTALS_POSITION
        return AppearanceSettingsState(
            print_font=FontSettings.from_qfont(self._current_print_font),
            table_font_size=self.table_font_size_spin.value(),
            breakdown_font_size=self.breakdown_font_size_spin.value(),
            final_calc_font_size=self.final_calc_font_size_spin.value(),
            totals_position=cast(TotalsPosition, totals_position),
        )

    def apply(self) -> AppearanceSettingsState:
        state = self.state()
        self._controller.apply_state(state)
        return state

    def validate(self) -> None:
        self._controller.validate_state(self.state())

    def restore_defaults(self) -> None:
        self._load_to_ui(self._controller.default_state())
        self.changed.emit()

    def _build_ui(self, state: AppearanceSettingsState) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        form_layout = QFormLayout()
        self._configure_form(form_layout)

        self._add_print_font_controls(form_layout, state.print_font)
        self._add_font_size_controls(form_layout)
        self._add_totals_position_control(form_layout)

        layout.addLayout(form_layout)
        layout.addWidget(self._create_preview_panel())
        layout.addStretch()

        self._load_to_ui(state)
        self.table_font_size_spin.valueChanged.connect(self._emit_changed)
        self.breakdown_font_size_spin.valueChanged.connect(self._emit_changed)
        self.final_calc_font_size_spin.valueChanged.connect(self._emit_changed)
        self.totals_position_combo.currentIndexChanged.connect(self._emit_changed)

    def _add_print_font_controls(
        self,
        form_layout: QFormLayout,
        font: FontSettings,
    ) -> None:
        self.print_font_button = QPushButton("Configure Print Font...")
        self.print_font_button.setMinimumWidth(190)
        self.print_font_button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.print_font_button.setToolTip(
            "Set font family, size, and style for printed reports\n"
            "Affects estimates and silver-bar reports, not screen display\n"
            "Recommended: clean print fonts such as Arial or Segoe UI\n"
            "Click to open font selection dialog"
        )
        self.print_font_label = QLabel(self.font_display_text(font))
        self.print_font_label.setObjectName("SettingsValueLabel")
        self.print_font_label.setWordWrap(True)
        self.print_font_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.print_font_label.setMinimumWidth(150)
        self.print_font_button.clicked.connect(self._show_print_font_dialog)
        font_layout = QHBoxLayout()
        font_layout.setSpacing(10)
        font_layout.addWidget(self.print_font_label, 1)
        font_layout.addWidget(self.print_font_button)
        form_layout.addRow("Print Font:", font_layout)

        self.print_font_sample = QLabel("RING001  Gold Ring    9.500 g    ₹ 2,375")
        self.print_font_sample.setToolTip(
            "Live preview of the selected report font\n"
            "Shows print-like text as it will appear in reports\n"
            "Updates automatically when the font changes"
        )
        self._update_font_sample()
        form_layout.addRow("Sample:", self.print_font_sample)

    def _add_font_size_controls(self, form_layout: QFormLayout) -> None:
        self.table_font_size_spin = ThemedSpinBox()
        self.table_font_size_spin.setRange(7, 16)
        self.table_font_size_spin.setToolTip(
            "Set font size for the main estimate entry table\n"
            "Range: 7–16 points\n"
            "Affects table readability and screen space usage\n"
            "Recommended: 9-11 for most users"
        )
        self.table_font_size_spin.setSuffix(" pt")
        self._polish_field(self.table_font_size_spin, width=160)
        form_layout.addRow("Estimate Table Font Size:", self.table_font_size_spin)

        self.breakdown_font_size_spin = ThemedSpinBox()
        self.breakdown_font_size_spin.setRange(7, 16)
        self.breakdown_font_size_spin.setToolTip(
            "Text size for Regular/Return/Silver Bar totals\n"
            "Range: 7–16 points\n"
            "Controls left-side totals display\n"
            "Should match or be smaller than table font"
        )
        self.breakdown_font_size_spin.setSuffix(" pt")
        self._polish_field(self.breakdown_font_size_spin, width=160)
        form_layout.addRow("Totals (Left) Font Size:", self.breakdown_font_size_spin)

        self.final_calc_font_size_spin = ThemedSpinBox()
        self.final_calc_font_size_spin.setRange(8, 20)
        self.final_calc_font_size_spin.setToolTip(
            "Text size for Final Calculation panel\n"
            "Range: 8–20 points\n"
            "Controls right-side grand totals display\n"
            "Can be larger for emphasis"
        )
        self.final_calc_font_size_spin.setSuffix(" pt")
        self._polish_field(self.final_calc_font_size_spin, width=160)
        form_layout.addRow(
            "Final Calculation Font Size:",
            self.final_calc_font_size_spin,
        )

    def _add_totals_position_control(self, form_layout: QFormLayout) -> None:
        self.totals_position_combo = ThemedComboBox()
        self.totals_position_combo.addItem("Right Side", "right")
        self.totals_position_combo.addItem("Left Side", "left")
        self.totals_position_combo.addItem("Bottom", "bottom")
        self.totals_position_combo.setToolTip(
            "Choose where totals/final calculation appears.\n"
            "Right/Left preserves maximum table height.\n"
            "Bottom uses footer area and can reduce visible rows."
        )
        self._polish_field(self.totals_position_combo, width=260)
        form_layout.addRow("Totals Panel Position:", self.totals_position_combo)

    def _load_to_ui(self, state: AppearanceSettingsState) -> None:
        self._current_print_font = state.print_font.to_qfont()
        self.print_font_label.setText(self.font_display_text(state.print_font))
        self.table_font_size_spin.setValue(state.table_font_size)
        self.breakdown_font_size_spin.setValue(state.breakdown_font_size)
        self.final_calc_font_size_spin.setValue(state.final_calc_font_size)
        totals_index = self.totals_position_combo.findData(state.totals_position)
        if totals_index >= 0:
            self.totals_position_combo.setCurrentIndex(totals_index)
        self._update_font_sample()

    def _show_print_font_dialog(self) -> None:
        dialog = CustomFontDialog(self._current_print_font, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._current_print_font = dialog.get_selected_font()
        state = FontSettings.from_qfont(self._current_print_font)
        self.print_font_label.setText(self.font_display_text(state))
        self._update_font_sample()
        self.changed.emit()

    def _emit_changed(self, *_args: object) -> None:
        self.changed.emit()

    def _update_font_sample(self) -> None:
        sample_font = QFont(self._current_print_font)
        size = self._current_print_font.pointSizeF()
        if size:
            sample_font.setPointSizeF(max(5.0, float(size)))
        self.print_font_sample.setFont(sample_font)

    @staticmethod
    def font_display_text(font: FontSettings | None) -> str:
        if font is None:
            return "Default"
        style = " Bold" if font.bold else ""
        return f"{font.family}, {font.size:.1f}pt{style}"

    @staticmethod
    def _configure_form(form_layout: QFormLayout) -> None:
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)
        form_layout.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form_layout.setFormAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        form_layout.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

    @staticmethod
    def _polish_field(widget: QWidget, *, width: int) -> None:
        widget.setMinimumWidth(min(width, 180))
        widget.setMaximumWidth(width)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    @staticmethod
    def _create_preview_panel() -> QFrame:
        preview = QFrame()
        preview.setObjectName("SettingsPreviewCard")
        preview_layout = QVBoxLayout(preview)
        preview_layout.setContentsMargins(12, 10, 12, 12)
        preview_layout.setSpacing(8)

        title = QLabel("Preview")
        title.setObjectName("SettingsPreviewTitle")
        preview_layout.addWidget(title)

        table = QTableWidget(5, 6, preview)
        table.setObjectName("SettingsPreviewTable")
        table.setHorizontalHeaderLabels(
            ["Code", "Item Name", "Gross", "Poly", "Net Wt", "Wage Amt"]
        )
        sample_rows = [
            ("RING001", "Gold Ring", "10.000", "0.500", "9.500", "250.00"),
            ("NECK001", "Gold Necklace", "15.000", "0.750", "14.250", "325.00"),
            ("BRAC001", "Gold Bracelet", "20.000", "1.000", "19.000", "275.00"),
            ("BAR001", "Silver Bar", "40.000", "0.040", "39.960", "0.00"),
            ("ANKL001", "Silver Anklet", "25.000", "0.300", "24.700", "85.00"),
        ]
        for row, values in enumerate(sample_rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column >= 2:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                table.setItem(row, column, item)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(24)
        table.horizontalHeader().setFixedHeight(28)
        table.horizontalHeader().setMinimumSectionSize(68)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFixedHeight(154)
        preview_layout.addWidget(table)

        grand_total = QLabel(
            "Grand Total  ₹ 14,40,170.88    ·    Net Fine Wt  19.058    ·    "
            "Net Wage  ₹ 6,094.00\n"
            "Totals: Gross Wt  335.000    ·    Poly Wt  16.760"
        )
        grand_total.setObjectName("SettingsGrandTotalPreview")
        grand_total.setWordWrap(True)
        grand_total.setAlignment(Qt.AlignmentFlag.AlignTop)
        grand_total.setMinimumHeight(58)
        preview_layout.addWidget(grand_total)
        return preview


__all__ = [
    "AppearanceSettingsActions",
    "AppearanceSettingsPage",
    "AppearanceSettingsState",
    "SettingsAppearanceController",
    "TotalsPosition",
]
