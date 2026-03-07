import logging

from PyQt5.QtWidgets import QComboBox, QDialog

from silverestimate.ui.silver_bar_optimization_controller import (
    SilverBarOptimizationController,
)


class _OptimizationDbStub:
    def __init__(self):
        self.created_names = []
        self.available_bars = [
            {"bar_id": 1, "fine_weight": 50.0},
            {"bar_id": 2, "fine_weight": 49.5},
        ]

    def get_silver_bars(self, **kwargs):
        del kwargs
        return list(self.available_bars)

    def create_silver_bar_list(self, name):
        self.created_names.append(name)
        return 12


class _OptimizationHost(QDialog):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("test-silver-bar-optimization")
        self.db_manager = _OptimizationDbStub()
        self.list_combo = QComboBox(self)
        self.list_combo.addItem("LIST-012", 12)
        self.bulk_assign_calls = []
        self.loaded_lists = 0
        self.loaded_available = 0

    def _bulk_assign_to_list(self, bar_ids, list_id):
        self.bulk_assign_calls.append((list(bar_ids), int(list_id)))
        return len(list(bar_ids)), []

    def load_lists(self):
        self.loaded_lists += 1

    def load_available_bars(self):
        self.loaded_available += 1


class _AcceptedDialog:
    Accepted = 1

    def __init__(self, parent=None):
        del parent
        self.min_target = 99.0
        self.max_target = 100.0
        self.list_name = "Optimal-List"
        self.optimization_type = "min_bars"

    def exec_(self):
        return self.Accepted


def test_optimization_controller_creates_and_selects_generated_list(
    qt_app, monkeypatch
):
    del qt_app
    from PyQt5.QtWidgets import QMessageBox

    host = _OptimizationHost()
    controller = SilverBarOptimizationController(host)
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.Ok,
    )

    controller.generate_optimal_list(_AcceptedDialog)

    assert host.db_manager.created_names == ["Optimal-List"]
    assert host.bulk_assign_calls == [([1, 2], 12)]
    assert host.loaded_lists == 1
    assert host.loaded_available == 1
    assert host.list_combo.currentData() == 12
