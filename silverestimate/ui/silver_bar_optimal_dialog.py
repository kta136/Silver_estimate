"""Keyboard-accessible target range settings for bar optimization."""

from datetime import datetime

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from .screen_widgets import SCREEN_QSS, KeyHintButton, OptionGroup, label
from .shared_screen_theme import build_management_screen_stylesheet
from .themed_controls import ThemedDoubleSpinBox

_DIALOG_QSS = """
QLabel#OptimalListFieldLabel { color: __TEXT_MUTED__; font-weight: 600; }
QLabel#OptimalListRangeSummary { color: __TEXT_MUTED__; }
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

    def _init_ui(self):  # noqa: PLR0915 - declarative dialog layout
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        body = QVBoxLayout()
        body.setContentsMargins(24, 20, 24, 20)
        body.setSpacing(6)
        outer.addLayout(body)
        body.addWidget(label("Generate optimal list", "ScreenTitle"))
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

        buttons = QFrame(self)
        buttons.setObjectName("OptimalListButtons")
        button_layout = QHBoxLayout(buttons)
        button_layout.setContentsMargins(24, 12, 24, 12)
        button_layout.setSpacing(10)
        button_layout.addStretch()
        cancel_button = KeyHintButton("Cancel", "Esc")
        cancel_button.setObjectName("OptimalListSecondaryButton")
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        generate_button = KeyHintButton("Generate list", "Enter")
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
        spin.setDecimals(1)
        spin.setRange(0.1, 999999.9)
        spin.setSingleStep(1.0)
        spin.setValue(value)
        spin.setSuffix(" g")
        spin.setMinimumWidth(150)
        spin.setAccessibleName(name)
        return spin

    def _update_range_summary(self) -> None:
        minimum = self.min_weight_spin.value()
        maximum = self.max_weight_spin.value()
        midpoint = (minimum + maximum) / 2
        self.range_summary_label.setText(
            f"{minimum:,.1f}–{maximum:,.1f} g fine · midpoint {midpoint:,.1f} g"
        )

    def accept(self):
        min_val = self.min_weight_spin.value()
        max_val = self.max_weight_spin.value()

        if min_val <= 0 or max_val <= 0:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter valid weight values greater than 0.",
            )
            return

        if min_val >= max_val:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Minimum weight must be less than maximum weight.",
            )
            return

        if not self.list_name_edit.text().strip():
            QMessageBox.warning(
                self, "Invalid Input", "Please enter a name for the list."
            )
            return

        self.min_target = min_val
        self.max_target = max_val
        self.target_fine_weight = (min_val + max_val) / 2
        self.list_name = self.list_name_edit.text().strip()
        self.optimization_type = (
            "min_bars" if self.min_bars_radio.isChecked() else "max_bars"
        )
        super().accept()
