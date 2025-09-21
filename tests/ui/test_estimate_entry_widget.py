import types
import pytest
from PyQt5.QtWidgets import QTableWidgetItem

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_GROSS,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_RATE,
    COL_NET_WT,
    COL_FINE_WT,
    COL_WAGE_AMT,
    COL_TYPE,
)


@pytest.fixture()
def fake_db(tmp_path):
    class _DB:
        def __init__(self):
            self.item_cache_controller = None

        def generate_voucher_no(self):
            return "TEST123"

        def drop_tables(self):
            return True

        def setup_database(self):
            return True

        def delete_all_estimates(self):
            return True

        def get_item_by_code(self, code):
            return {"wage_type": "WT", "wage_rate": 10}

    return _DB()


def _set_row(widget, row, *, code, gross, poly, purity, wage_rate):
    table = widget.item_table
    while table.rowCount() <= row:
        widget.add_empty_row()
    table.setItem(row, COL_CODE, QTableWidgetItem(code))
    table.setItem(row, COL_GROSS, QTableWidgetItem(str(gross)))
    table.setItem(row, COL_POLY, QTableWidgetItem(str(poly)))
    table.setItem(row, COL_PURITY, QTableWidgetItem(str(purity)))
    table.setItem(row, COL_WAGE_RATE, QTableWidgetItem(str(wage_rate)))
    widget.current_row = row
    widget.calculate_net_weight()
    widget.calculate_totals()
    widget._update_row_type_visuals(row)
    return table


def _make_widget(db_manager):
    return EstimateEntryWidget(db_manager, types.SimpleNamespace(show_inline_status=lambda *a, **k: None))


def test_widget_calculates_totals(qt_app, fake_db):
    widget = _make_widget(fake_db)
    table = _set_row(
        widget,
        0,
        code="REG001",
        gross=10,
        poly=1,
        purity=92.5,
        wage_rate=10,
    )

    assert table.item(0, COL_NET_WT).text() == "9.000"
    assert table.item(0, COL_FINE_WT).text() == "8.325"
    assert table.item(0, COL_WAGE_AMT).text() == "90"

    assert widget.total_gross_label.text() == "10.0"
    assert widget.total_net_label.text() == "9.0"
    assert widget.total_fine_label.text() == "8.3"

    widget.deleteLater()


def test_widget_multi_row_totals(qt_app, fake_db):
    widget = _make_widget(fake_db)

    # Regular row
    _set_row(widget, 0, code="REG001", gross=10, poly=1, purity=92.5, wage_rate=10)

    # Return row
    widget.toggle_return_mode()
    _set_row(widget, 1, code="RET001", gross=2.5, poly=0.5, purity=80, wage_rate=0)
    widget.toggle_return_mode()

    # Silver bar row
    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, code="BAR001", gross=3.0, poly=0.0, purity=99.9, wage_rate=0)
    widget.toggle_silver_bar_mode()

    table = widget.item_table
    widget.calculate_totals()

    assert table.item(0, COL_TYPE).text() == "No"
    assert table.item(1, COL_TYPE).text() == "Return"
    assert table.item(2, COL_TYPE).text() == "Silver Bar"

    assert widget.total_gross_label.text() == "10.0"
    assert widget.return_gross_label.text() == "2.5"
    assert widget.bar_gross_label.text() == "3.0"

    widget.deleteLater()


def test_widget_save_and_reload(qt_app, tmp_path, settings_stub, monkeypatch):
    db_path = tmp_path / "ui" / "estimate.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    manager = DatabaseManager(str(db_path), "test-pass")

    manager.items_repo.add_item("REG001", "Regular", 92.5, "WT", 10)
    manager.items_repo.add_item("RET001", "Return", 80.0, "WT", 0)
    manager.items_repo.add_item("BAR001", "Bar", 99.9, "WT", 0)

    widget = _make_widget(manager)
    widget.voucher_edit.setText("SAVE01")

    _set_row(widget, 0, code="REG001", gross=10, poly=1, purity=92.5, wage_rate=10)

    widget.toggle_return_mode()
    _set_row(widget, 1, code="RET001", gross=1.5, poly=0.3, purity=75.0, wage_rate=0)
    widget.toggle_return_mode()

    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, code="BAR001", gross=2.0, poly=0.0, purity=99.9, wage_rate=0)
    widget.toggle_silver_bar_mode()

    from PyQt5.QtWidgets import QMessageBox as _QtMessageBox

    class _MsgBoxStub:
        Yes = _QtMessageBox.Yes
        No = _QtMessageBox.No
        Ok = _QtMessageBox.Ok

        @staticmethod
        def warning(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def information(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def critical(*args, **kwargs):
            return _QtMessageBox.Ok

        @staticmethod
        def question(*args, **kwargs):
            return _QtMessageBox.Yes

    monkeypatch.setattr("silverestimate.ui.estimate_entry_logic.QMessageBox", _MsgBoxStub, raising=False)

    widget.print_estimate = lambda: None
    widget.save_estimate()

    widget_loaded = _make_widget(manager)
    widget_loaded.voucher_edit.setText("SAVE01")
    widget_loaded.safe_load_estimate()

    table = widget_loaded.item_table
    rows = []
    for row in range(table.rowCount()):
        code_item = table.item(row, COL_CODE)
        if code_item and code_item.text().strip():
            rows.append((code_item.text(), table.item(row, COL_TYPE).text()))

    assert rows == [
        ("REG001", "No"),
        ("BAR001", "Silver Bar"),
        ("RET001", "Return"),
    ]

    assert float(table.item(0, COL_NET_WT).text()) == pytest.approx(9.0)
    assert float(table.item(1, COL_NET_WT).text()) == pytest.approx(2.0)
    assert float(table.item(2, COL_NET_WT).text()) == pytest.approx(1.2)

    widget.deleteLater()
    widget_loaded.deleteLater()
    manager.close()