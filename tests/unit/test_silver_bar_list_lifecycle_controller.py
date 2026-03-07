import logging

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QTableView,
)

from silverestimate.ui.models import AvailableSilverBarsTableModel
from silverestimate.ui.silver_bar_list_lifecycle_controller import (
    SilverBarListLifecycleController,
)


class _LifecycleDbStub:
    def __init__(self):
        self.created_notes = []

    def create_silver_bar_list(self, note):
        self.created_notes.append(note)
        return 11


class _LifecycleHost(QDialog):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test-silver-bar-lifecycle")
        self.db_manager = _LifecycleDbStub()
        self.available_loads = 0
        self.list_loads = 0
        self.assigned_payloads = []

        self.list_combo = QComboBox(self)
        self.list_combo.addItem("--- Select a List ---", None)
        self.list_combo.addItem("LIST-011", 11)

        self.available_bars_table = QTableView(self)
        self.available_bars_model = AvailableSilverBarsTableModel(
            self.available_bars_table
        )
        self.available_bars_table.setModel(self.available_bars_model)
        self.available_bars_table.setSelectionBehavior(QTableView.SelectRows)
        self.available_bars_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.available_bars_model.set_rows(
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
                },
                {
                    "bar_id": 2,
                    "estimate_voucher_no": "V002",
                    "estimate_note": "Beta",
                    "weight": 9.0,
                    "purity": 98.0,
                    "fine_weight": 8.820,
                    "date_added": "2026-02-14 10:00:00",
                    "status": "In Stock",
                },
            ]
        )

    def load_lists(self):
        return None

    def load_available_bars(self):
        self.available_loads += 1

    def load_bars_in_selected_list(self):
        self.list_loads += 1

    @staticmethod
    def _bar_ids_from_indexes(table, indexes):
        model = table.model()
        return [model.bar_id_at(index.row()) for index in indexes if model is not None]

    def _run_with_wait_cursor(self, operation, **kwargs):
        del kwargs
        return operation()

    def _bulk_assign_to_list(self, bar_ids, list_id):
        self.assigned_payloads.append((list(bar_ids), int(list_id)))
        return len(list(bar_ids)), []


def test_lifecycle_controller_creates_list_from_selection_and_assigns_bars(
    qtbot, monkeypatch
):
    from PyQt5.QtWidgets import QInputDialog, QMessageBox

    host = _LifecycleHost()
    controller = SilverBarListLifecycleController(host)
    qtbot.addWidget(host)
    selection_model = host.available_bars_table.selectionModel()
    selection_model.select(
        host.available_bars_model.index(0, 0),
        selection_model.Select | selection_model.Rows,
    )
    selection_model.select(
        host.available_bars_model.index(1, 0),
        selection_model.Select | selection_model.Rows,
    )

    monkeypatch.setattr(
        QInputDialog,
        "getText",
        lambda *args, **kwargs: ("Batch note", True),
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

    controller._create_list_from_selection()

    assert host.db_manager.created_notes == ["Batch note"]
    assert host.assigned_payloads == [([1, 2], 11)]
    assert host.available_loads == 1
    assert host.list_loads == 1
    assert host.list_combo.currentData(Qt.UserRole) == 11
