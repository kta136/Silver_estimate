import csv
import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QComboBox, QDialog, QTableView

from silverestimate.ui.models import (
    AvailableSilverBarsTableModel,
    SelectedListSilverBarsTableModel,
)
from silverestimate.ui.silver_bar_transfer_controller import (
    SilverBarTransferController,
)


class _TransferDbStub:
    def __init__(self):
        self.assigned_calls = []

    def assign_bar_to_list(self, bar_id, list_id):
        self.assigned_calls.append((int(bar_id), int(list_id)))
        return True


class _TransferHost(QDialog):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test-silver-bar-transfer")
        self.db_manager = _TransferDbStub()
        self.current_list_id = 10
        self.available_loads = 0
        self.list_loads = 0
        self.transfer_state_refreshes = 0

        self.list_combo = QComboBox(self)
        self.list_combo.addItem("LIST-010", 10)
        self.list_combo.setCurrentIndex(0)

        self.available_bars_table = QTableView(self)
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)

        self.list_bars_table = QTableView(self)
        self.list_bars_model = SelectedListSilverBarsTableModel(self.list_bars_table)
        self.list_bars_table.setModel(self.list_bars_model)

    def load_available_bars(self):
        self.available_loads += 1

    def load_bars_in_selected_list(self):
        self.list_loads += 1

    def _update_transfer_buttons_state(self):
        self.transfer_state_refreshes += 1

    @staticmethod
    def _bar_id_from_table(table, row: int):
        model = table.model()
        return model.bar_id_at(row) if model is not None else None

    @staticmethod
    def _table_cell_text(table, row: int, column: int) -> str:
        model = table.model()
        if model is None:
            return ""
        index = model.index(row, column)
        value = model.data(index, Qt.DisplayRole) if index.isValid() else None
        return "" if value is None else str(value)


def _management_row(bar_id: int, voucher: str, note: str, weight: float, fine: float):
    return {
        "bar_id": bar_id,
        "estimate_voucher_no": voucher,
        "estimate_note": note,
        "weight": weight,
        "purity": 99.9,
        "fine_weight": fine,
        "date_added": "2026-02-15 10:00:00",
        "status": "In Stock",
    }


def test_transfer_controller_adds_all_filtered_rows_and_refreshes(qtbot, monkeypatch):
    host = _TransferHost()
    host.available_bars_model.set_rows(
        [
            _management_row(1, "V001", "Alpha", 10.5, 10.489),
            _management_row(2, "V002", "Beta", 9.0, 8.820),
        ]
    )
    controller = SilverBarTransferController(host)
    qtbot.addWidget(host)

    from PyQt5.QtWidgets import QMessageBox

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.Yes,
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.Ok,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.Ok,
    )

    controller.add_all_filtered_to_list()

    assert host.db_manager.assigned_calls == [(1, 10), (2, 10)]
    assert host.available_loads == 1
    assert host.list_loads == 1
    assert host.transfer_state_refreshes == 1


def test_transfer_controller_exports_current_list_to_csv(qtbot, monkeypatch, tmp_path):
    host = _TransferHost()
    host.list_bars_model.set_rows(
        [
            _management_row(20, "L001", "Listed", 12.0, 11.640),
        ]
    )
    controller = SilverBarTransferController(host)
    qtbot.addWidget(host)

    export_path = tmp_path / "bars.csv"

    from PyQt5.QtWidgets import QFileDialog, QMessageBox

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(export_path), "CSV Files (*.csv)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.Ok,
    )

    controller.export_current_list_to_csv()

    with export_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0] == [
        "bar_id",
        "estimate_voucher_no",
        "weight_g",
        "purity_pct",
        "fine_weight_g",
        "date_added",
        "status",
    ]
    assert rows[1] == [
        "20",
        "L001 (Listed)",
        "12.000",
        "99.90",
        "11.640",
        "2026-02-15 10:00:00",
        "In Stock",
    ]
