"""Printing settings page."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
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
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        form = QFormLayout()
        self._configure_form(form)

        self._add_print_target_controls(form)
        self._add_margin_controls(form)
        self._controller.load_to_ui(self.widgets())

        from .settings_print_preview import SettingsPrintPreview

        self.controls = QWidget()
        self.controls.setMaximumWidth(440)
        self.controls_layout = QVBoxLayout(self.controls)
        self.controls_layout.addWidget(QLabel("Printer & paper"))
        self.controls_layout.addLayout(form)
        self.controls_layout.addStretch()
        layout.addWidget(self.controls)
        self.preview = SettingsPrintPreview(self)
        layout.addWidget(self.preview, 1)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._refresh_preview)
        self.changed.connect(self._preview_timer.start)

    def attach_font_controls(self, appearance_page) -> None:
        self._appearance_page = appearance_page
        self.controls_layout.insertWidget(
            self.controls_layout.count() - 1, appearance_page.print_font_controls
        )
        appearance_page.print_font_controls.show()
        appearance_page.changed.connect(self._preview_timer.start)
        self._preview_timer.start()

    def _refresh_preview(self) -> None:
        if hasattr(self, "_appearance_page"):
            self.preview.render_preferences(
                self.state(), self._appearance_page._current_print_font
            )

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
            self._polish_field(spin, width=115)
            spin.valueChanged.connect(self._emit_changed)

        margins_layout.setHorizontalSpacing(12)
        margins_layout.setVerticalSpacing(4)
        margins_layout.addWidget(
            QLabel("Top"), 0, 1, alignment=Qt.AlignmentFlag.AlignCenter
        )
        margins_layout.addWidget(self.margin_top_spin, 1, 1)
        page = QFrame()
        page.setFixedSize(100, 92)
        page.setStyleSheet("QFrame { background: white; border: 1px solid #8b929a; }")
        inside = QFrame(page)
        inside.setGeometry(10, 10, 80, 72)
        inside.setStyleSheet("border: 1px dashed #b9bfc5;")
        margins_layout.addWidget(page, 3, 1, alignment=Qt.AlignmentFlag.AlignCenter)
        for column, label, spin in (
            (0, "Left", self.margin_left_spin),
            (2, "Right", self.margin_right_spin),
        ):
            side = QVBoxLayout()
            side.addWidget(QLabel(label))
            side.addWidget(spin)
            margins_layout.addLayout(side, 3, column)
        margins_layout.addWidget(
            QLabel("Bottom"), 4, 1, alignment=Qt.AlignmentFlag.AlignCenter
        )
        margins_layout.addWidget(self.margin_bottom_spin, 5, 1)
        form.addRow(QLabel("Margins (mm)"))
        form.addRow(margins_layout)

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
        form.addRow("Default zoom:", self.preview_zoom_spin)

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
