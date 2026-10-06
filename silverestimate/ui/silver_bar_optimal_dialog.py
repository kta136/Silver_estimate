"""Keyboard-accessible target range settings for bar optimization."""

from datetime import datetime

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .shared_screen_theme import build_management_screen_stylesheet
from .themed_controls import ThemedDoubleSpinBox
from .window_sizing import resize_to_available_screen


class OptimalListDialog(QDialog):
    """Collect target weight inputs for optimal list generation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Optimal List")
        self.setMinimumSize(520, 480)
        resize_to_available_screen(
            self,
            preferred_width=600,
            preferred_height=640,
        )
        self.setObjectName("OptimalListDialog")
        self.setStyleSheet(
            build_management_screen_stylesheet(
                root_selector="QDialog#OptimalListDialog",
                card_names=[
                    "OptimalListHeaderCard",
                    "OptimalListWeightCard",
                    "OptimalListNameCard",
                    "OptimalListPreferenceCard",
                ],
                title_label="OptimalListTitleLabel",
                subtitle_label="OptimalListSubtitleLabel",
                field_label="OptimalListFieldLabel",
                primary_button="OptimalListPrimaryButton",
                secondary_button="OptimalListSecondaryButton",
                input_selectors=["QLineEdit", "QDoubleSpinBox"],
                extra_rules="""
                QLabel#OptimalListBodyLabel {
                    color: __FIELD_TEXT__;

                }
                QLabel#OptimalListRangeSummary {
                    background-color: __HEADER_BG__;
                    border: 1px solid __CARD_BORDER__;
                    border-radius: 6px;
                    color: __TEXT_STRONG__;
                    font-weight: 700;
                    padding: 8px;
                }
                """,
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
        outer.setContentsMargins(12, 12, 12, 12)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        header_card = QFrame(self)
        header_card.setObjectName("OptimalListHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(12, 12, 12, 12)
        header_layout.setSpacing(2)
        title = QLabel("Generate Optimal Silver Bar List")
        title.setObjectName("OptimalListTitleLabel")
        header_layout.addWidget(title)
        subtitle = QLabel(
            "Define a target weight range and let the optimizer build the best list."
        )
        subtitle.setObjectName("OptimalListSubtitleLabel")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_card)

        weight_group = QFrame(self)
        weight_group.setObjectName("OptimalListWeightCard")
        weight_layout = QVBoxLayout(weight_group)
        weight_layout.setSpacing(12)
        weight_layout.setContentsMargins(12, 12, 12, 12)

        weight_title = QLabel("Target Fine Weight Range (grams):")
        weight_title.setObjectName("OptimalListFieldLabel")
        weight_layout.addWidget(weight_title)

        minmax_layout = QHBoxLayout()
        minmax_layout.setSpacing(12)

        min_group = QVBoxLayout()
        min_group.addWidget(QLabel("Minimum:"))
        self.min_weight_spin = ThemedDoubleSpinBox()
        self.min_weight_spin.setDecimals(1)
        self.min_weight_spin.setRange(0.1, 999999.9)
        self.min_weight_spin.setSingleStep(1.0)
        self.min_weight_spin.setValue(95.0)
        self.min_weight_spin.setMinimumWidth(150)
        min_group.addWidget(self.min_weight_spin)
        minmax_layout.addLayout(min_group)

        max_group = QVBoxLayout()
        max_group.addWidget(QLabel("Maximum:"))
        self.max_weight_spin = ThemedDoubleSpinBox()
        self.max_weight_spin.setDecimals(1)
        self.max_weight_spin.setRange(0.1, 999999.9)
        self.max_weight_spin.setSingleStep(1.0)
        self.max_weight_spin.setValue(105.0)
        self.max_weight_spin.setMinimumWidth(150)
        max_group.addWidget(self.max_weight_spin)
        minmax_layout.addLayout(max_group)

        weight_layout.addLayout(minmax_layout)
        weight_layout.addSpacing(2)
        self.range_summary_label = QLabel()
        self.range_summary_label.setObjectName("OptimalListRangeSummary")
        weight_layout.addWidget(self.range_summary_label)
        self.min_weight_spin.valueChanged.connect(self._update_range_summary)
        self.max_weight_spin.valueChanged.connect(self._update_range_summary)
        self._update_range_summary()
        range_explanation = QLabel(
            "Only combinations whose total fine weight falls inside this range are considered."
        )
        range_explanation.setObjectName("OptimalListBodyLabel")
        range_explanation.setWordWrap(True)
        weight_layout.addWidget(range_explanation)
        layout.addWidget(weight_group)

        list_name_group = QFrame(self)
        list_name_group.setObjectName("OptimalListNameCard")
        list_name_layout = QVBoxLayout(list_name_group)
        list_name_layout.setSpacing(8)
        list_name_layout.setContentsMargins(12, 12, 12, 12)
        list_name_label = QLabel("List Name")
        list_name_label.setObjectName("OptimalListFieldLabel")
        list_name_layout.addWidget(list_name_label)
        self.list_name_edit = QLineEdit()
        self.list_name_edit.setPlaceholderText("Enter a name for the new list")
        self.list_name_edit.setText(f"Optimal-{datetime.now():%Y%m%d-%H%M}")
        list_name_layout.addWidget(self.list_name_edit)
        layout.addWidget(list_name_group)

        opt_group = QFrame(self)
        opt_group.setObjectName("OptimalListPreferenceCard")
        opt_layout = QVBoxLayout(opt_group)
        opt_layout.setSpacing(12)
        opt_layout.setContentsMargins(12, 12, 12, 12)
        preference_label = QLabel("Optimization Preference")
        preference_label.setObjectName("OptimalListFieldLabel")
        opt_layout.addWidget(preference_label)

        self.opt_button_group = QButtonGroup(self)
        self.min_bars_radio = QRadioButton("Use the fewest bars")
        self.min_bars_radio.setChecked(True)
        self.max_bars_radio = QRadioButton("Use the most bars")
        self.opt_button_group.addButton(self.min_bars_radio, 0)
        self.opt_button_group.addButton(self.max_bars_radio, 1)
        opt_layout.addWidget(self.min_bars_radio)
        opt_layout.addWidget(self.max_bars_radio)

        explanation = QLabel(
            "Choose fewer bars for simpler handling, or more bars to spread the target across inventory."
        )
        explanation.setObjectName("OptimalListBodyLabel")
        explanation.setWordWrap(True)
        opt_layout.addWidget(explanation)
        layout.addWidget(opt_group)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("OptimalListSecondaryButton")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        generate_button = QPushButton("Generate List")
        generate_button.setObjectName("OptimalListPrimaryButton")
        generate_button.setDefault(True)
        generate_button.clicked.connect(self.accept)
        button_layout.addWidget(generate_button)
        outer.addLayout(button_layout)

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
