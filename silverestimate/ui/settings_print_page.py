"""Printing settings page."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .settings_print_controller import (
    PrintSettingsState,
    PrintSettingsWidgets,
    SettingsPrintController,
)
from .themed_controls import ThemedComboBox, ThemedDoubleSpinBox, ThemedSpinBox


class PrintSettingsPage(QWidget):
    """Own printing controls and expose typed page operations."""

    changed = Signal()

    def __init__(
        self,
        controller: SettingsPrintController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._build_ui()

    def state(self) -> PrintSettingsState:
        return self._controller.state_from_ui(self.widgets())

    def validate(self) -> None:
        self._controller.validate_state(self.state())

    def apply(self) -> PrintSettingsState:
        return self._controller.save_from_ui(self.widgets())

    def restore_defaults(self) -> None:
        self._controller.apply_defaults_to_ui(self.widgets())
        self.changed.emit()

    def widgets(self) -> PrintSettingsWidgets:
        return PrintSettingsWidgets(
            margin_left_spin=self.margin_left_spin,
            margin_top_spin=self.margin_top_spin,
            margin_right_spin=self.margin_right_spin,
            margin_bottom_spin=self.margin_bottom_spin,
            preview_zoom_spin=self.preview_zoom_spin,
            printer_combo=self.printer_combo,
            page_size_combo=self.page_size_combo,
            orientation_combo=self.orientation_combo,
            estimate_format_combo=self.estimate_format_combo,
        )

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        form = QFormLayout()
        self._configure_form(form)

        self._add_margin_controls(form)
        self._add_print_target_controls(form)
        self._controller.load_to_ui(self.widgets())

        layout.addLayout(form)
        layout.addStretch()

    def _add_margin_controls(self, form: QFormLayout) -> None:
        margins_layout = QGridLayout()
        self.margin_left_spin = ThemedSpinBox()
        self.margin_top_spin = ThemedSpinBox()
        self.margin_right_spin = ThemedSpinBox()
        self.margin_bottom_spin = ThemedSpinBox()
        for spin in (
            self.margin_left_spin,
            self.margin_top_spin,
            self.margin_right_spin,
            self.margin_bottom_spin,
        ):
            spin.setRange(0, 50)
            spin.setSuffix(" mm")
            self._polish_field(spin, width=135)
            spin.valueChanged.connect(self._emit_changed)

        margins_layout.setHorizontalSpacing(10)
        margins_layout.setVerticalSpacing(8)
        margins_layout.addWidget(QLabel("Left:"), 0, 0)
        margins_layout.addWidget(self.margin_left_spin, 0, 1)
        margins_layout.addWidget(QLabel("Top:"), 0, 2)
        margins_layout.addWidget(self.margin_top_spin, 0, 3)
        margins_layout.addWidget(QLabel("Right:"), 1, 0)
        margins_layout.addWidget(self.margin_right_spin, 1, 1)
        margins_layout.addWidget(QLabel("Bottom:"), 1, 2)
        margins_layout.addWidget(self.margin_bottom_spin, 1, 3)
        form.addRow(QLabel("Page Margins (mm):"), margins_layout)

    def _add_print_target_controls(self, form: QFormLayout) -> None:
        self.preview_zoom_spin = ThemedDoubleSpinBox()
        self.preview_zoom_spin.setRange(0.1, 5.0)
        self.preview_zoom_spin.setSingleStep(0.1)
        self.preview_zoom_spin.setDecimals(2)
        self.preview_zoom_spin.setSuffix(" x")
        self.preview_zoom_spin.setToolTip(
            "Default zoom factor for print preview (e.g., 1.0 = 100%, 1.25 = 125%)"
        )
        self._polish_field(self.preview_zoom_spin, width=160)
        self.preview_zoom_spin.valueChanged.connect(self._emit_changed)
        form.addRow("Preview Default Zoom:", self.preview_zoom_spin)

        self.printer_combo = ThemedComboBox()
        self.printer_combo.setToolTip("Default printer for printing and quick print")
        self._polish_field(self.printer_combo, width=320)
        self._controller.refresh_printer_list(self.printer_combo)
        self.printer_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Default Printer:", self.printer_combo)

        self.page_size_combo = ThemedComboBox()
        self.page_size_combo.addItems(["A4", "A5", "Letter", "Legal", "Thermal 80mm"])
        self.page_size_combo.setToolTip("Default page size for printing")
        self._polish_field(self.page_size_combo, width=240)
        self.page_size_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Page Size:", self.page_size_combo)

        self.orientation_combo = ThemedComboBox()
        self.orientation_combo.addItems(["Portrait", "Landscape"])
        self.orientation_combo.setToolTip("Default page orientation for printing")
        self._polish_field(self.orientation_combo, width=240)
        self.orientation_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Orientation:", self.orientation_combo)

        self.estimate_format_combo = ThemedComboBox()
        self.estimate_format_combo.addItem("Classic", "classic")
        self.estimate_format_combo.addItem("Modern", "modern")
        self.estimate_format_combo.setToolTip(
            "Choose the default estimate format; it can also be changed in preview"
        )
        self._polish_field(self.estimate_format_combo, width=240)
        self.estimate_format_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Estimate Format:", self.estimate_format_combo)

    def _emit_changed(self, *_args: object) -> None:
        self.changed.emit()

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    @staticmethod
    def _polish_field(widget: QWidget, *, width: int) -> None:
        widget.setMinimumWidth(min(width, 180))
        widget.setMaximumWidth(width)
        widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )


__all__ = ["PrintSettingsPage"]
