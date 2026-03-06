import logging

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QLineEdit,
    QSplitter,
    QTableView,
)

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.silver_bar_management_state import (
    SilverBarManagementStateStore,
)


class _StateHost(QDialog):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test-silver-bar-state")
        self.current_list_id = None

        self._splitter = QSplitter(Qt.Horizontal, self)

        self.available_bars_table = QTableView(self)
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)
        self._splitter.addWidget(self.available_bars_table)

        self.list_bars_table = QTableView(self)
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)
        self._splitter.addWidget(self.list_bars_table)

        self.weight_search_edit = QLineEdit(self)

        self.weight_tol_spin = QDoubleSpinBox(self)
        self.weight_tol_spin.setRange(0.0, 999999.0)
        self.purity_min_spin = QDoubleSpinBox(self)
        self.purity_min_spin.setRange(0.0, 100.0)
        self.purity_max_spin = QDoubleSpinBox(self)
        self.purity_max_spin.setRange(0.0, 100.0)

        self.date_range_combo = QComboBox(self)
        self.date_range_combo.addItems(
            ["Any", "Today", "Last 7 days", "Last 30 days", "This Month"]
        )

        self.auto_refresh_checkbox = QCheckBox(self)
        self._auto_refresh_timer = QTimer(self)

        self.list_combo = QComboBox(self)
        self.list_combo.addItem("--- Select a List ---", None)
        self.list_combo.addItem("LIST-010", 10)


def test_state_store_round_trips_filters_and_selected_list(qt_app, settings_stub):
    del qt_app, settings_stub
    host = _StateHost()
    store = SilverBarManagementStateStore(host)

    host.weight_search_edit.setText("190")
    host.weight_tol_spin.setValue(0.250)
    host.purity_min_spin.setValue(95.0)
    host.purity_max_spin.setValue(99.9)
    host.date_range_combo.setCurrentText("Last 7 days")
    host.auto_refresh_checkbox.setChecked(True)
    host.list_combo.setCurrentIndex(1)
    host.current_list_id = 10

    store._save_ui_state()

    host.weight_search_edit.clear()
    host.weight_tol_spin.setValue(0.001)
    host.purity_min_spin.setValue(0.0)
    host.purity_max_spin.setValue(100.0)
    host.date_range_combo.setCurrentText("Any")
    host.auto_refresh_checkbox.setChecked(False)
    host.list_combo.setCurrentIndex(0)
    host.current_list_id = None

    store._restore_ui_state()
    store._restore_selected_list_from_settings()

    assert host.weight_search_edit.text() == "190"
    assert host.weight_tol_spin.value() == 0.250
    assert host.purity_min_spin.value() == 95.0
    assert host.purity_max_spin.value() == 99.9
    assert host.date_range_combo.currentText() == "Last 7 days"
    assert host.auto_refresh_checkbox.isChecked() is True
    assert host.list_combo.currentData() == 10


def test_state_store_tolerates_invalid_sort_values_after_restoring_filters(
    qt_app, settings_stub
):
    del qt_app, settings_stub
    host = _StateHost()
    store = SilverBarManagementStateStore(host)
    settings = store._settings()

    settings.setValue("ui/silver_bars/weight_query", "250")
    settings.setValue("ui/silver_bars/weight_tol", 0.5)
    settings.setValue("ui/silver_bars/date_range", "Today")
    settings.setValue("ui/silver_bars/auto_refresh", "true")
    settings.setValue("ui/silver_bars/available_sort_col", 1)
    settings.setValue("ui/silver_bars/available_sort_order", "bad-value")

    store._restore_ui_state()

    assert host.weight_search_edit.text() == "250"
    assert host.weight_tol_spin.value() == 0.5
    assert host.date_range_combo.currentText() == "Today"
    assert host.auto_refresh_checkbox.isChecked() is True
