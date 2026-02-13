import types

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTableWidgetItem

from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_components.totals_panel import TotalsPanel
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
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
    net = max(0.0, float(item["gross"]) - float(item["poly"]))
    fine = net * (float(item["purity"]) / 100.0)
    wage = net * float(item["wage_rate"])

    table.setItem(row, COL_NET_WT, QTableWidgetItem(f"{net:.2f}"))
    table.setItem(row, COL_FINE_WT, QTableWidgetItem(f"{fine:.2f}"))
    table.setItem(row, COL_WAGE_AMT, QTableWidgetItem(f"{wage:.0f}"))

    # Manually set type for test
    type_item = table.item(row, COL_TYPE) or QTableWidgetItem()
    if item.get("is_silver_bar"):
        type_item.setText("silver_bar")
    elif item.get("is_return"):
        type_item.setText("return")
    else:
        type_item.setText("regular")
    table.setItem(row, COL_TYPE, type_item)

    widget.calculate_totals()

    return table


class _RepositoryStub:
    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        loader = getattr(self.db, "get_estimate_by_voucher", None)
        if callable(loader):
            return loader(voucher_no)
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def estimate_exists(self, voucher_no):
        return bool(self.load_estimate(voucher_no))

    def notify_silver_bars_for_estimate(self, voucher_no):
        deleter = getattr(self.db, "delete_silver_bars_for_estimate", None)
        if callable(deleter):
            deleter(voucher_no)

    def save_estimate(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        saver = getattr(self.db, "save_estimate_with_returns", None)
        if callable(saver):
            return bool(
                saver(
                    voucher_no,
                    date,
                    silver_rate,
                    list(regular_items or []),
                    list(return_items or []),
                    dict(totals or {}),
                )
            )
        return True

    def fetch_silver_bars_for_estimate(self, voucher_no):
        fetcher = getattr(self.db, "get_silver_bars", None)
        if callable(fetcher):
            rows = fetcher(estimate_voucher_no=voucher_no) or []
            return [dict(row) for row in rows]
        return []

    def update_silver_bar(self, bar_id, weight, purity):
        updater = getattr(self.db, "update_silver_bar_values", None)
        if callable(updater):
            return bool(updater(bar_id, weight, purity))
        return True

    def add_silver_bar(self, voucher_no, weight, purity):
        adder = getattr(self.db, "add_silver_bar", None)
        if callable(adder):
            return adder(voucher_no, weight, purity)
        return None

    def last_error(self):
        return getattr(self.db, "last_error", None)

    def delete_estimate(self, voucher_no):
        deleter = getattr(self.db, "delete_single_estimate", None)
        if callable(deleter):
            return bool(deleter(voucher_no))
        return True


def _make_widget(db_manager):
    main_window_stub = types.SimpleNamespace(
        show_inline_status=lambda *a, **k: None,
        show_silver_bars=lambda: None,
    )
    repository = _RepositoryStub(db_manager)
    widget = EstimateEntryWidget(db_manager, main_window_stub, repository)
    widget.presenter.handle_item_code = lambda row, code: False
    try:
        widget.item_table.cellChanged.disconnect(widget.handle_cell_changed)
    except TypeError:
        pass
    return widget


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

    assert float(table.item(0, COL_NET_WT).text()) == pytest.approx(9.00)
    expected_fine = (10 - 1) * (92.5 / 100.0)
    # Using larger tolerance due to rounding issues (8.325 -> 8.33)
    assert float(table.item(0, COL_FINE_WT).text()) == pytest.approx(
        expected_fine, abs=0.01
    )
    assert float(table.item(0, COL_WAGE_AMT).text()) == pytest.approx(90.0)

    assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.total_net_label.text()) == pytest.approx(9.0)
    assert float(widget.total_fine_label.text()) == pytest.approx(8.325, abs=0.01)

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

    # Note: EstimateTableView displays "No", "Return", "Silver Bar" even if we set "regular" internally
    assert table.item(0, COL_TYPE).text() == "No"
    assert table.item(1, COL_TYPE).text() == "Return"
    assert table.item(2, COL_TYPE).text() == "Silver Bar"

    assert float(widget.total_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.return_gross_label.text()) == pytest.approx(2.5)
    assert float(widget.bar_gross_label.text()) == pytest.approx(3.0)

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

    # Patch the correct QMessageBox
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.QMessageBox",
        _MsgBoxStub,
        raising=False,
    )

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


def test_populate_row_updates_code_cell(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        if table.rowCount() == 0:
            widget.add_empty_row()

        table.setItem(0, COL_CODE, QTableWidgetItem("old-code"))
        widget.populate_row(
            0,
            {"code": "new123", "name": "New Item", "purity": 91.6, "wage_rate": 10.0},
        )

        assert table.item(0, COL_CODE).text() == "NEW123"
        assert table.item(0, COL_ITEM_NAME).text() == "New Item"
        assert table.item(0, COL_CODE).data(Qt.UserRole) == "new123"
    finally:
        widget.deleteLater()


def test_totals_position_switching_and_persistence(qt_app, fake_db, settings_stub):
    widget = _make_widget(fake_db)
    try:
        splitter = widget._content_splitter
        assert splitter.orientation() == Qt.Horizontal

        widget._apply_totals_position("left")
        assert splitter.orientation() == Qt.Horizontal
        assert splitter.widget(0) is widget.totals_panel
        assert widget._settings().value("ui/estimate_totals_position", type=str) == "left"

        widget._on_totals_position_requested("bottom")
        assert splitter.orientation() == Qt.Vertical
        assert splitter.widget(1) is widget.totals_panel
        assert widget._settings().value("ui/estimate_totals_position", type=str) == "bottom"

        widget._on_totals_position_requested("right")
        assert splitter.orientation() == Qt.Horizontal
        assert splitter.widget(1) is widget.totals_panel
        assert widget._settings().value("ui/estimate_totals_position", type=str) == "right"
    finally:
        widget.deleteLater()


def test_totals_section_order_sync_and_persistence(qt_app, fake_db, settings_stub):
    widget = _make_widget(fake_db)
    try:
        new_order = ["silver_bar", "return", "regular", "totals"]
        expected_order = TotalsPanel.normalize_section_order(new_order)
        widget._apply_totals_section_order(new_order, persist=True)

        assert widget._totals_panel_sidebar.section_order() == expected_order
        assert widget._totals_panel_bottom.section_order() == expected_order
        assert (
            widget._settings().value("ui/estimate_totals_section_order", type=str)
            == ",".join(expected_order)
        )

        widget_loaded = _make_widget(fake_db)
        try:
            assert widget_loaded._totals_panel_sidebar.section_order() == expected_order
            assert widget_loaded._totals_panel_bottom.section_order() == expected_order
        finally:
            widget_loaded.deleteLater()
    finally:
        widget.deleteLater()


def test_column_width_auto_fits_content_expand_and_shrink(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        col = COL_ITEM_NAME

        table.setItem(0, col, QTableWidgetItem("A"))
        widget._schedule_columns_autofit([col], delay_ms=0)
        widget._apply_pending_column_autofit()
        base_width = table.columnWidth(col)

        table.setItem(
            0,
            col,
            QTableWidgetItem("Very Long Item Name For Dynamic Width Testing 12345"),
        )
        widget._schedule_columns_autofit([col], delay_ms=0)
        widget._apply_pending_column_autofit()
        expanded_width = table.columnWidth(col)

        table.setItem(0, col, QTableWidgetItem("AB"))
        widget._schedule_columns_autofit([col], delay_ms=0)
        widget._apply_pending_column_autofit()
        shrink_width = table.columnWidth(col)

        assert expanded_width > base_width
        assert shrink_width < expanded_width
    finally:
        widget.deleteLater()
