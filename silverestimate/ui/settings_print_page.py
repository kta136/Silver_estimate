"""Printing settings page."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QValidator
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
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


class ZoomPercentSpinBox(ThemedDoubleSpinBox):
    """Hold a zoom factor (1.25) and show it as a percentage (125 %).

    The print preview shows its zoom as a percentage, so the default
    for it is entered the same way.
    """

    def textFromValue(self, value: float) -> str:
        return str(round(value * 100))

    def valueFromText(self, text: str) -> float:
        try:
            return int(self._digits(text)) / 100
        except ValueError:
            return self.value()

    def validate(self, text: str, pos: int):
        digits = self._digits(text)
        if not digits:
            return QValidator.State.Intermediate, text, pos
        if not digits.isdigit() or int(digits) / 100 > self.maximum():
            return QValidator.State.Invalid, text, pos
        if int(digits) / 100 < self.minimum():
            return QValidator.State.Intermediate, text, pos
        return QValidator.State.Acceptable, text, pos

    def _digits(self, text: str) -> str:
        return text.replace(self.suffix(), "").replace("%", "").strip()


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
        )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Printing")
        title.setObjectName("SettingsTitleLabel")
        outer.addWidget(title)
        intro = QLabel(
            "Printer, paper, margins and the print font. The sample page "
            "follows your choices."
        )
        intro.setObjectName("SettingsMutedDescription")
        intro.setWordWrap(True)
        outer.addWidget(intro)
        layout = QHBoxLayout()
        layout.setSpacing(12)
        outer.addLayout(layout, 1)
        form = QFormLayout()
        self._configure_form(form)

        self._add_print_target_controls(form)
        self._add_margin_controls(form)
        self._controller.load_to_ui(self.widgets())

        from .settings_print_preview import SettingsPrintPreview

        self.controls = QWidget()
        self.controls.setMaximumWidth(460)
        self.controls_layout = QVBoxLayout(self.controls)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        section = QLabel("Printer and paper")
        section.setStyleSheet("font-weight: 700;")
        self.controls_layout.addWidget(section)
        self.controls_layout.addLayout(form)
        self.controls_layout.addStretch()
        layout.addWidget(self.controls)
        preview_column = QVBoxLayout()
        preview_column.setSpacing(4)
        # Above the page, so it stays visible however short the window is.
        preview_hint = QLabel("Sample estimate. Click the page to enlarge it.")
        preview_hint.setObjectName("SettingsMutedDescription")
        preview_column.addWidget(preview_hint)
        self.preview = SettingsPrintPreview(self)
        preview_column.addWidget(self.preview, 1)
        layout.addLayout(preview_column, 1)
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
        margins_layout = QVBoxLayout()
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
            # No unit in the box: the row is headed "Margins (mm)", and the
            # suffix did not fit beside the arrows.
            self._polish_field(spin, width=92)
            spin.valueChanged.connect(self._emit_changed)

        # Each box carries its caption beside it: short enough to leave room
        # for the rest of this page on a 1366x768 screen. Plain box layouts,
        # because a grid row would not keep the page sketch clear of the
        # Bottom box.
        margins_layout.setSpacing(6)
        page = QFrame()
        page.setFixedSize(84, 72)
        page.setStyleSheet("QFrame { background: white; border: 1px solid #8b929a; }")
        inside = QFrame(page)
        inside.setGeometry(8, 8, 68, 56)
        inside.setStyleSheet("border: 1px dashed #b9bfc5;")
        middle = QHBoxLayout()
        middle.setSpacing(12)
        middle.addLayout(self._captioned("Left", self.margin_left_spin, width=40))
        middle.addWidget(page)
        middle.addLayout(self._captioned("Right", self.margin_right_spin, width=40))
        margins_layout.addLayout(
            self._centered(self._captioned("Top", self.margin_top_spin))
        )
        margins_layout.addLayout(middle)
        margins_layout.addLayout(
            self._centered(self._captioned("Bottom", self.margin_bottom_spin))
        )
        form.addRow(QLabel("Margins (mm)"))
        form.addRow(margins_layout)

    @staticmethod
    def _captioned(caption: str, spin: QWidget, *, width: int = 0) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(caption)
        if width:
            label.setMinimumWidth(width)
        row.addWidget(label)
        row.addWidget(spin)
        return row

    @staticmethod
    def _centered(content: QHBoxLayout) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        row.addLayout(content)
        row.addStretch(1)
        return row

    def _add_print_target_controls(self, form: QFormLayout) -> None:
        self.preview_zoom_spin = ZoomPercentSpinBox()
        self.preview_zoom_spin.setRange(0.1, 5.0)
        self.preview_zoom_spin.setSingleStep(0.05)
        self.preview_zoom_spin.setDecimals(2)
        self.preview_zoom_spin.setSuffix(" %")
        self.preview_zoom_spin.setToolTip(
            "Zoom the print preview opens at, from 10 % to 500 %"
        )
        self._polish_field(self.preview_zoom_spin, width=160)
        self.preview_zoom_spin.valueChanged.connect(self._emit_changed)
        form.addRow("Default zoom:", self.preview_zoom_spin)

        self.printer_combo = ThemedComboBox()
        self.printer_combo.setToolTip("Default printer for printing and quick print")
        self._polish_field(self.printer_combo, width=320)
        self._controller.refresh_printer_list(self.printer_combo)
        self.printer_combo.currentIndexChanged.connect(self._emit_changed)
        # A long printer name is cut by the field; hovering shows all of it.
        self.printer_combo.currentTextChanged.connect(self.printer_combo.setToolTip)
        self.printer_combo.setToolTip(self.printer_combo.currentText())
        form.addRow("Default printer:", self.printer_combo)

        self.page_size_combo = ThemedComboBox()
        self.page_size_combo.addItems(["A4", "A5", "Letter", "Legal"])
        self.page_size_combo.setToolTip("Default page size for printing")
        self._polish_field(self.page_size_combo, width=240)
        self.page_size_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Page size:", self.page_size_combo)

        self.orientation_combo = ThemedComboBox()
        self.orientation_combo.addItems(["Portrait", "Landscape"])
        self.orientation_combo.setToolTip("Default page orientation for printing")
        self._polish_field(self.orientation_combo, width=240)
        self.orientation_combo.currentIndexChanged.connect(self._emit_changed)
        form.addRow("Orientation:", self.orientation_combo)

    def _emit_changed(self, *_args: object) -> None:
        self.changed.emit()

    @staticmethod
    def _configure_form(form: QFormLayout) -> None:
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setLabelAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
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


__all__ = ["PrintSettingsPage", "ZoomPercentSpinBox"]
