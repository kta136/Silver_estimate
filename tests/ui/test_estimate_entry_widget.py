import types
import pytest
from PyQt5.QtWidgets import QTableWidgetItem

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)

from tests.factories import regular_item, return_item, silver_bar_item


@pytest.fixture()
def fake_db(tmp_path):
    class _DB:
        def __init__(self):
            self.item_cache_controller = None
            self.generate_calls = 0

        def generate_voucher_no(self):
            self.generate_calls += 1
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


def _set_row(widget, row, item):
    table = widget.item_table
    while table.rowCount() <= row:
        widget.add_empty_row()
    table.setItem(row, COL_CODE, QTableWidgetItem(str(item["code"])))
    table.setItem(row, COL_GROSS, QTableWidgetItem(str(item["gross"])))
    table.setItem(row, COL_POLY, QTableWidgetItem(str(item["poly"])))
    table.setItem(row, COL_PURITY, QTableWidgetItem(str(item["purity"])))
    table.setItem(row, COL_WAGE_RATE, QTableWidgetItem(str(item["wage_rate"])))
    table.setItem(row, COL_PIECES, QTableWidgetItem(str(item["pieces"])))
    widget.current_row = row
    widget.calculate_net_weight()
    widget.calculate_totals()
    widget._update_row_type_visuals(row)

    type_item = table.item(row, COL_TYPE) or QTableWidgetItem()
    if item.get("is_silver_bar"):
        type_item.setText("Silver Bar")
    elif item.get("is_return"):
        type_item.setText("Return")
    else:
        type_item.setText("No")
    table.setItem(row, COL_TYPE, type_item)

    return table


def _make_widget(db_manager):
    return EstimateEntryWidget(db_manager, types.SimpleNamespace(show_inline_status=lambda *a, **k: None))

def test_widget_generates_voucher_on_init(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        assert fake_db.generate_calls == 1
        assert widget.voucher_edit.text() == "TEST123"
    finally:
        widget.deleteLater()


def test_widget_calculates_totals(qt_app, fake_db):
    widget = _make_widget(fake_db)
    table = _set_row(
        widget,
        0,
        regular_item(gross=10, poly=1, purity=92.5, wage_rate=10),
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

    _set_row(widget, 0, regular_item(gross=10, poly=1, purity=92.5, wage_rate=10))

    widget.toggle_return_mode()
    _set_row(widget, 1, return_item(gross=2.5, poly=0.5, purity=80, wage_rate=0))
    widget.toggle_return_mode()

    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, silver_bar_item(gross=3.0, poly=0.0, purity=99.9, wage_rate=0))
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

    _set_row(widget, 0, regular_item(gross=10, poly=1, purity=92.5, wage_rate=10))

    widget.toggle_return_mode()
    _set_row(widget, 1, return_item(gross=1.5, poly=0.3, purity=75.0, wage_rate=0))
    widget.toggle_return_mode()

    widget.toggle_silver_bar_mode()
    _set_row(widget, 2, silver_bar_item(gross=2.0, poly=0.0, purity=99.9, wage_rate=0))
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

    type_values = []
    for r in range(widget.item_table.rowCount()):
        type_item = widget.item_table.item(r, COL_TYPE)
        type_values.append(type_item.text() if type_item else None)
    print('type_values_before_save', type_values)

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



def test_toggle_modes_updates_empty_row(qt_app, fake_db):
    widget = _make_widget(fake_db)
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.item(last_row, COL_TYPE).text() == "No"
    widget.toggle_return_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.item(last_row, COL_TYPE).text() == "Return"
    widget.toggle_silver_bar_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.item(last_row, COL_TYPE).text() == "Silver Bar"
    widget.toggle_silver_bar_mode()
    last_row = widget.item_table.rowCount() - 1
    assert widget.item_table.item(last_row, COL_TYPE).text() == "No"
    assert widget.item_table.item(last_row, COL_TYPE).text() == "Silver Bar"
