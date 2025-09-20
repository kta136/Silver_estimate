import types

import pytest
from PyQt5.QtWidgets import QTableWidgetItem

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


def _fill_row(widget, *, gross="10", poly="1", purity="92.5", wage_rate="10"):
    table = widget.item_table
    table.setItem(0, COL_CODE, QTableWidgetItem("REG001"))
    table.setItem(0, COL_GROSS, QTableWidgetItem(gross))
    table.setItem(0, COL_POLY, QTableWidgetItem(poly))
    table.setItem(0, COL_PURITY, QTableWidgetItem(purity))
    table.setItem(0, COL_WAGE_RATE, QTableWidgetItem(wage_rate))
    widget.current_row = 0
    widget.calculate_net_weight()
    widget.calculate_totals()
    return table


def test_widget_calculates_totals(qt_app, fake_db):
    widget = EstimateEntryWidget(fake_db, types.SimpleNamespace(show_inline_status=lambda *a, **k: None))
    table = _fill_row(widget)

    assert table.item(0, COL_NET_WT).text() == "9.000"
    assert table.item(0, COL_FINE_WT).text() == "8.325"
    assert table.item(0, COL_WAGE_AMT).text() == "90"

    assert widget.total_gross_label.text() == "10.0"
    assert widget.total_net_label.text() == "9.0"
    assert widget.total_fine_label.text() == "8.3"

    widget.deleteLater()


def test_widget_toggle_return_and_bar(qt_app, fake_db):
    widget = EstimateEntryWidget(fake_db, types.SimpleNamespace(show_inline_status=lambda *a, **k: None))

    widget.toggle_return_mode()
    table = _fill_row(widget)
    type_item = table.item(0, COL_TYPE)
    assert type_item is not None
    assert type_item.text() == "Return"
    assert widget.return_net_label.text() == "9.0"

    widget.toggle_return_mode()
    table = _fill_row(widget)
    type_item = table.item(0, COL_TYPE)
    assert type_item.text() == "No"

    widget.toggle_silver_bar_mode()
    table = _fill_row(widget)
    type_item = table.item(0, COL_TYPE)
    assert type_item.text() == "Silver Bar"
    assert widget.bar_net_label.text() == "9.0"

    widget.deleteLater()
