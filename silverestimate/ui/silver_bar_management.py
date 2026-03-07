#!/usr/bin/env python
"""Silver bar management dialog facade."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from .shared_screen_theme import build_management_screen_stylesheet
from .silver_bar_list_lifecycle_controller import SilverBarListLifecycleController
from .silver_bar_list_print_controller import SilverBarListPrintController
from .silver_bar_load_controller import SilverBarLoadController, _BarsLoadWorker
from .silver_bar_management_state import SilverBarManagementStateStore
from .silver_bar_management_ui import SilverBarManagementUiBuilder
from .silver_bar_optimization_controller import SilverBarOptimizationController
from .silver_bar_selection_state_controller import SilverBarSelectionStateController
from .silver_bar_table_controller import SilverBarTableController
from .silver_bar_transfer_controller import SilverBarTransferController


class SilverBarDialog(QDialog):
    """Dialog for managing silver bars and grouping them into lists."""

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.current_list_id = None
        self._active_load_workers = {}
        self._available_load_request_id = 0
        self._list_load_request_id = 0
        self._load_started_at = {}

        self._ui_builder = SilverBarManagementUiBuilder(self)
        self._load_controller = SilverBarLoadController(self)
        self._list_lifecycle_controller = SilverBarListLifecycleController(self)
        self._list_print_controller = SilverBarListPrintController(self)
        self._optimization_controller = SilverBarOptimizationController(self)
        self._selection_state_controller = SilverBarSelectionStateController(self)
        self._table_controller = SilverBarTableController(self)
        self._transfer_controller = SilverBarTransferController(self)
        self._state_store = SilverBarManagementStateStore(self)

        self.init_ui()
        self.load_lists()
        self.load_available_bars()

    def showEvent(self, event):
        try:
            self.load_available_bars()
            if self.current_list_id is not None:
                self.load_bars_in_selected_list()
        except Exception as exc:
            self.logger.warning(
                "Failed to refresh silver bar data on showEvent: %s",
                exc,
                exc_info=True,
            )
        super().showEvent(event)

    def closeEvent(self, event):
        self._cancel_active_loads()
        try:
            self._save_ui_state()
            if self._is_embedded():
                self._navigate_back_to_estimate()
                event.ignore()
                return
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed during silver bar dialog close: %s", exc)
        super().closeEvent(event)

    def accept(self):
        self._cancel_active_loads()
        try:
            self._save_ui_state()
            if self._is_embedded():
                self._navigate_back_to_estimate()
                return
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed during silver bar dialog accept: %s", exc)
        super().accept()

    def reject(self):
        self._cancel_active_loads()
        try:
            self._save_ui_state()
            if self._is_embedded():
                self._navigate_back_to_estimate()
                return
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            self.logger.debug("Failed during silver bar dialog reject: %s", exc)
        super().reject()

    def generate_optimal_list(self):
        return self._optimization_controller.generate_optimal_list(OptimalListDialog)


class OptimalListDialog(QDialog):
    """Collect target weight inputs for optimal list generation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Optimal List")
        self.setMinimumSize(450, 400)
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
                    color: #475569;
                    font-size: 9pt;
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

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(12, 12, 12, 12)

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
        self.min_weight_spin = QDoubleSpinBox()
        self.min_weight_spin.setDecimals(1)
        self.min_weight_spin.setRange(0.1, 999999.9)
        self.min_weight_spin.setSingleStep(1.0)
        self.min_weight_spin.setValue(95.0)
        min_group.addWidget(self.min_weight_spin)
        minmax_layout.addLayout(min_group)

        max_group = QVBoxLayout()
        max_group.addWidget(QLabel("Maximum:"))
        self.max_weight_spin = QDoubleSpinBox()
        self.max_weight_spin.setDecimals(1)
        self.max_weight_spin.setRange(0.1, 999999.9)
        self.max_weight_spin.setSingleStep(1.0)
        self.max_weight_spin.setValue(105.0)
        max_group.addWidget(self.max_weight_spin)
        minmax_layout.addLayout(max_group)

        weight_layout.addLayout(minmax_layout)
        range_explanation = QLabel(
            "The algorithm will find bars with total fine weight between these values."
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
        self.min_bars_radio = QRadioButton("Minimum number of silver bars")
        self.min_bars_radio.setChecked(True)
        self.max_bars_radio = QRadioButton("Maximum number of silver bars")
        self.opt_button_group.addButton(self.min_bars_radio, 0)
        self.opt_button_group.addButton(self.max_bars_radio, 1)
        opt_layout.addWidget(self.min_bars_radio)
        opt_layout.addWidget(self.max_bars_radio)

        explanation = QLabel(
            "Minimum bars prefers fewer bars. Maximum bars uses as many bars as possible within range."
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
        layout.addLayout(button_layout)

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


def _delegate(controller_attr: str, method_name: str):
    def _method(self, *args, **kwargs):
        controller = getattr(self, controller_attr)
        return object.__getattribute__(controller, method_name)(*args, **kwargs)

    _method.__name__ = method_name
    _method.__qualname__ = f"SilverBarDialog.{method_name}"
    return _method


for _method_name in ("init_ui",):
    setattr(SilverBarDialog, _method_name, _delegate("_ui_builder", _method_name))

for _method_name in (
    "_schedule_available_reload",
    "_save_available_limit_setting",
    "_table_result_limit",
    "_next_load_request_id",
    "_is_latest_load",
    "_start_bars_load",
    "_on_bars_load_ready",
    "_on_bars_load_error",
    "_on_bars_load_finished",
    "_cancel_active_loads",
    "load_available_bars",
    "load_lists",
    "list_selection_changed",
    "load_bars_in_selected_list",
):
    setattr(SilverBarDialog, _method_name, _delegate("_load_controller", _method_name))

for _method_name in (
    "_bulk_assign_to_list",
    "_bulk_remove_from_list",
    "add_selected_to_list",
    "remove_selected_from_list",
    "add_all_filtered_to_list",
    "remove_all_from_list",
    "export_current_list_to_csv",
):
    setattr(
        SilverBarDialog,
        _method_name,
        _delegate("_transfer_controller", _method_name),
    )

for _method_name in (
    "create_new_list",
    "_create_list_from_selection",
    "edit_list_note",
    "delete_selected_list",
    "mark_list_as_issued",
):
    setattr(
        SilverBarDialog,
        _method_name,
        _delegate("_list_lifecycle_controller", _method_name),
    )

for _method_name in (
    "print_selected_list",
    "_next_print_preview_request_id",
    "_start_list_print_preview_build",
    "_on_list_print_preview_ready",
    "_on_list_print_preview_error",
    "_finish_list_print_preview_build",
):
    setattr(
        SilverBarDialog,
        _method_name,
        _delegate("_list_print_controller", _method_name),
    )

for _method_name in (
    "_table_cell_value",
    "_table_cell_text",
    "_bar_id_from_table",
    "_clear_management_table",
    "_populate_table",
    "_show_available_context_menu",
    "_show_list_context_menu",
    "_copy_selected_rows",
    "_clear_filters",
):
    setattr(
        SilverBarDialog,
        _method_name,
        _delegate("_table_controller", _method_name),
    )

for _method_name in (
    "_settings",
    "_save_table_sort_state",
    "_save_ui_state",
    "_restore_ui_state",
    "_restore_selected_list_from_settings",
    "_get_table_column_widths",
    "_apply_table_column_widths",
    "_restore_table_column_widths",
    "_toggle_auto_refresh",
    "_current_date_range",
    "_find_main_window",
    "_is_embedded",
    "_navigate_back_to_estimate",
):
    setattr(SilverBarDialog, _method_name, _delegate("_state_store", _method_name))

for _method_name in (
    "_update_transfer_buttons_state",
    "_on_selection_changed",
    "_update_selection_summaries",
):
    setattr(
        SilverBarDialog,
        _method_name,
        _delegate("_selection_state_controller", _method_name),
    )


def show_silver_bar_management(db_manager, parent=None):
    dialog = SilverBarDialog(db_manager, parent)
    return dialog.exec_()


def show_silver_bars(db_manager, parent=None):
    return show_silver_bar_management(db_manager, parent)


__all__ = [
    "SilverBarDialog",
    "OptimalListDialog",
    "_BarsLoadWorker",
    "show_silver_bar_management",
    "show_silver_bars",
]
