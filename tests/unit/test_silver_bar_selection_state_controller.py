import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QTableView,
)

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.silver_bar_selection_state_controller import (
    SilverBarSelectionStateController,
)


class _SelectionHost(QDialog):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test-silver-bar-selection-state")
        self.current_list_id = 10

        self.available_bars_table = QTableView(self)
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)
        self.available_bars_table.setSelectionBehavior(QTableView.SelectRows)

        self.list_bars_table = QTableView(self)
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)
        self.list_bars_table.setSelectionBehavior(QTableView.SelectRows)

        self.add_to_list_button = QPushButton(self)
        self.remove_from_list_button = QPushButton(self)
        self.add_all_button = QPushButton(self)
        self.remove_all_button = QPushButton(self)

        self.available_selection_label = QLabel(self)
        self.list_selection_label = QLabel(self)

    @staticmethod
    def _table_cell_value(table, row: int, column: int, role: int = Qt.DisplayRole):
        model = table.model()
        if model is None:
            return None
        index = model.index(row, column)
        if not index.isValid():
            return None
        return model.data(index, role)


def test_selection_state_controller_updates_buttons_and_summaries(qtbot):
    host = _SelectionHost()
    host.available_bars_model.set_rows(
        [
            {
                "bar_id": 1,
                "estimate_voucher_no": "V001",
                "estimate_note": "Alpha",
                "weight": 10.5,
                "purity": 99.9,
                "fine_weight": 10.489,
                "date_added": "2026-02-15 10:00:00",
                "status": "In Stock",
            }
        ]
    )
    host.list_bars_model.set_rows(
        [
            {
                "bar_id": 2,
                "estimate_voucher_no": "V002",
                "estimate_note": "Beta",
                "weight": 9.0,
                "purity": 98.0,
                "fine_weight": 8.820,
                "date_added": "2026-02-14 10:00:00",
                "status": "Assigned",
            }
        ]
    )
    controller = SilverBarSelectionStateController(host)

    host.available_bars_table.selectRow(0)
    host.list_bars_table.selectRow(0)
    qtbot.waitUntil(
        lambda: (
            len(host.available_bars_table.selectionModel().selectedRows()) == 1
            and len(host.list_bars_table.selectionModel().selectedRows()) == 1
        ),
        timeout=1000,
    )

    controller._on_selection_changed()

    assert host.add_to_list_button.isEnabled() is True
    assert host.remove_from_list_button.isEnabled() is True
    assert host.add_all_button.isEnabled() is True
    assert host.remove_all_button.isEnabled() is True
    assert host.available_selection_label.text() == (
        "Selected: 1 | Weight: 10.500 g | Fine: 10.489 g"
    )
    assert host.list_selection_label.text() == (
        "Selected: 1 | Weight: 9.000 g | Fine: 8.820 g"
    )
