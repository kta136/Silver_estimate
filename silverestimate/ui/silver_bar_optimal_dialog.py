"""Keyboard-accessible target range settings for bar optimization."""

from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
)

from silverestimate.domain.numeric_policy import WEIGHT_PLACES

from .screen_widgets import SCREEN_QSS, KeyHintButton, OptionGroup, label
from .shared_screen_theme import build_management_screen_stylesheet
from .themed_controls import ThemedDoubleSpinBox

RANGE_ERROR = "The first weight must be lower than the second."

_DIALOG_QSS = """
QLabel#OptimalListFieldLabel { color: __TEXT_MUTED__; font-weight: 600; }
QLabel#OptimalListRangeSummary { color: __TEXT_MUTED__; }
QLabel#OptimalListRangeSummary[invalid="true"] { color: __DANGER_TEXT__; font-weight: 600; }
QLabel#OptimalListError { color: __DANGER_TEXT__; font-weight: 600; }
QFrame#OptimalListButtons {
    background-color: __HEADER_BG__;
    border: none;
    border-top: 1px solid __CARD_BORDER__;
}
QPushButton#OptimalListPrimaryButton, QPushButton#OptimalListSecondaryButton {
    padding: 6px 14px;
    min-height: 24px;
}
"""


class OptimalListDialog(QDialog):
    """Collect target weight inputs for optimal list generation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Optimal List")
        self.setObjectName("OptimalListDialog")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#OptimalListDialog",
                card_names=[],
                title_label="OptimalListTitleLabel",
                subtitle_label="OptimalListSubtitleLabel",
                field_label="OptimalListFieldLabel",
                primary_button="OptimalListPrimaryButton",
                secondary_button="OptimalListSecondaryButton",
                input_selectors=["QLineEdit", "QDoubleSpinBox"],
                extra_rules=SCREEN_QSS + _DIALOG_QSS,
            )
        )
        self.target_fine_weight = 0.0
        self.list_name = ""
        self.optimization_type = "min_bars"
        self.min_target = 0.0
        self.max_target = 0.0
        self._init_ui()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(6)
        outer.addLayout(body)
        body.addWidget(label("Generate Optimal List", "ScreenTitle"))
        intro = label(
            "Builds a new list from available bars whose total fine weight lands "
            "in your range. Your current list is not changed.",
            "Muted",
        )
        intro.setWordWrap(True)
        body.addWidget(intro)
        body.addSpacing(14)

        body.addWidget(label("Target fine weight", "OptimalListFieldLabel"))
        range_row = QHBoxLayout()
        range_row.setSpacing(10)
        self.min_weight_spin = self._weight_spin(95.0, "Minimum fine weight")
        self.max_weight_spin = self._weight_spin(105.0, "Maximum fine weight")
        range_row.addWidget(self.min_weight_spin, 1)
        range_row.addWidget(label("to", "Muted"))
        range_row.addWidget(self.max_weight_spin, 1)
        body.addLayout(range_row)
        self.range_summary_label = label("", "Muted")
        self.range_summary_label.setObjectName("OptimalListRangeSummary")
        self.range_summary_label.setToolTip(
            "Only combinations whose total fine weight falls inside this range "
            "are considered."
        )
        body.addWidget(self.range_summary_label)
        self.min_weight_spin.valueChanged.connect(self._update_range_summary)
        self.max_weight_spin.valueChanged.connect(self._update_range_summary)
        self._update_range_summary()
        body.addSpacing(14)

        body.addWidget(label("Prefer", "OptimalListFieldLabel"))
        self.preference_group = OptionGroup("segmented", self)
        self.preference_group.addItem("Fewest bars", "min_bars")
        self.preference_group.addItem("Most bars", "max_bars")
        self.preference_group.setAccessibleName("Optimization preference")
        self.preference_group.setToolTip(
            "Fewer bars are simpler to handle; more bars spread the target "
            "across inventory."
        )
        self.min_bars_radio = self.preference_group.button(0)
        self.max_bars_radio = self.preference_group.button(1)
        body.addWidget(self.preference_group)
        body.addSpacing(14)

        body.addWidget(label("Note for the new list", "OptimalListFieldLabel"))
        self.list_name_edit = QLineEdit()
        self.list_name_edit.setPlaceholderText("Enter a note for the new list")
        self.list_name_edit.setText(f"Optimal-{datetime.now():%Y%m%d-%H%M}")
        body.addWidget(self.list_name_edit)
        self.error_label = label("", "OptimalListError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        body.addWidget(self.error_label)
        for field in (self.min_weight_spin, self.max_weight_spin):
            field.valueChanged.connect(self._clear_error)
        self.list_name_edit.textEdited.connect(self._clear_error)
        # Spare height goes above the button bar, not into it.
        outer.addStretch(1)

        buttons = QFrame(self)
        buttons.setObjectName("OptimalListButtons")
        buttons.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(24, 12, 24, 12)
        button_layout.setSpacing(10)
        button_layout.addStretch()
        cancel_button = KeyHintButton("Cancel", "Esc")
        cancel_button.setObjectName("OptimalListSecondaryButton")
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        generate_button = KeyHintButton("Generate List", "Enter")
        generate_button.setObjectName("OptimalListPrimaryButton")
        generate_button.setDefault(True)
        generate_button.clicked.connect(self.accept)
        button_layout.addWidget(generate_button)
        outer.addWidget(buttons)
        self.min_weight_spin.setFocus()
        self.min_weight_spin.selectAll()

    @staticmethod
    def _weight_spin(value: float, name: str) -> ThemedDoubleSpinBox:
        spin = ThemedDoubleSpinBox()
        spin.setDecimals(WEIGHT_PLACES)
        spin.setRange(0.01, 999999.99)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" g")
        spin.setMinimumWidth(150)
        spin.setAccessibleName(name)
        return spin

    def _update_range_summary(self) -> None:
        minimum = self.min_weight_spin.value()
        maximum = self.max_weight_spin.value()
        # A range that runs backwards is said here, under the two weights,
        # instead of being summarised as if it made sense.
        invalid = minimum >= maximum
        if invalid:
            text = RANGE_ERROR
        else:
            midpoint = (minimum + maximum) / 2
            text = f"{minimum:,.2f}–{maximum:,.2f} g fine · midpoint {midpoint:,.2f} g"
        self.range_summary_label.setText(text)
        if bool(self.range_summary_label.property("invalid")) != invalid:
            self.range_summary_label.setProperty("invalid", invalid)
            style = self.range_summary_label.style()
            style.unpolish(self.range_summary_label)
            style.polish(self.range_summary_label)

    def _show_error(self, message: str, field) -> None:
        """Say what to fix beside its field and put the cursor there."""
        if field is not self.list_name_edit and message == RANGE_ERROR:
            # Already shown under the weights.
            self._update_range_summary()
        else:
            self.error_label.setText(message)
            self.error_label.show()
        field.setFocus()
        field.selectAll()

    def _clear_error(self, *_args) -> None:
        self.error_label.clear()
        self.error_label.hide()

    def accept(self):
        min_val = self.min_weight_spin.value()
        max_val = self.max_weight_spin.value()

        if min_val <= 0 or max_val <= 0:
            self._show_error("Enter weights greater than 0.", self.min_weight_spin)
            return

        if min_val >= max_val:
            self._show_error(RANGE_ERROR, self.min_weight_spin)
            return

        if not self.list_name_edit.text().strip():
            self._show_error("Enter a note for the new list.", self.list_name_edit)
            return

        self.min_target = min_val
        self.max_target = max_val
        self.target_fine_weight = (min_val + max_val) / 2
        self.list_name = self.list_name_edit.text().strip()
        self.optimization_type = (
            "min_bars" if self.min_bars_radio.isChecked() else "max_bars"
        )
        super().accept()
