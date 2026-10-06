from decimal import Decimal

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QMessageBox

from silverestimate.domain.sales_report import SalesReportResult, SalesWeights
from silverestimate.ui.sales_report import SalesReportWidget
from tests.factories import regular_item
from tests.sales_report_support import report_database, save_report_estimate


@pytest.fixture
def sales_screen(qtbot, tmp_path):
    with report_database(tmp_path) as db:
        widget = SalesReportWidget(db)
        qtbot.addWidget(widget)
        widget.resize(1100, 700)
        widget.show()
        qtbot.waitUntil(lambda: not widget._loading)
        yield widget, db
        widget.shutdown_workers()


def load_range(qtbot, widget):
    widget.date_from.setDate(QDate(2026, 9, 30))
    widget.date_to.setDate(QDate(2026, 10, 31))
    widget.refresh_button.click()
    qtbot.waitUntil(lambda: not widget._loading)


def open_row(qtbot, widget, key):
    position = next(i for i, row in enumerate(widget.model.rows) if row.key == key)
    widget.table.selectRow(position)
    widget.open_button.click()
    qtbot.waitUntil(lambda: not widget._loading)


def test_today_default_daily_monthly_items_and_voucher_navigation(sales_screen, qtbot):
    widget, _db = sales_screen
    assert widget.date_from.date() == widget.date_to.date() == QDate.currentDate()
    assert widget.grouping.currentData() == "day"
    load_range(qtbot, widget)
    assert widget.model.rowCount() == 3
    assert [label.text() for label in widget.total_labels] == [
        "18.00 g",
        "18.68 g",
        "6.00 g",
        "6.77 g",
    ]
    widget.grouping.setCurrentIndex(1)
    widget.refresh_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget.model.rowCount() == 2
    open_row(qtbot, widget, "2026-10")
    assert widget._level == "item"
    assert {row.key for row in widget.model.rows} == {"REG001", "OTHER"}
    assert widget.model.columnCount() == 6
    open_row(qtbot, widget, "REG001")
    assert widget._level == "voucher"
    assert {row.key for row in widget.model.rows} == {"2", "3"}
    assert widget.total_labels[1].text() == "4.33 g"
    with qtbot.waitSignal(widget.voucher_requested, timeout=1000) as emitted:
        open_row(qtbot, widget, "2")
    assert emitted.args == ["2"]
    widget.back_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget._level == "item" and widget._period == "2026-10"
    widget.back_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget._level == "period" and widget._period is None


def test_code_search_whole_range_totals_and_numeric_sort(sales_screen, qtbot):
    widget, _db = sales_screen
    load_range(qtbot, widget)
    widget.all_items_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    widget.table.sortByColumn(3, Qt.SortOrder.DescendingOrder)
    assert widget.model.rows[0].key == "REG001"
    assert widget.model.data(widget.model.index(0, 3)) == "16.88"
    widget.item_search.setText("reg")
    assert widget.model.rowCount() == 0
    widget.all_items_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert [row.key for row in widget.model.rows] == ["REG001"]
    assert widget.total_labels[0].text() == "16.00 g"


def test_reopening_reflects_edit_and_delete_without_manual_refresh(sales_screen, qtbot):
    widget, db = sales_screen
    load_range(qtbot, widget)
    widget.hide()
    save_report_estimate(
        db, "2", "2026-10-01", [regular_item(gross=20, net_wt=20, purity=150, fine=30)]
    )
    widget.show()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget.total_labels[0].text() == "32.00 g"
    widget.hide()
    assert db.delete_single_estimate("2")
    widget.show()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget.total_labels[0].text() == "12.00 g"


def test_invalid_empty_failed_and_stale_results_do_not_show_old_totals(
    sales_screen, qtbot
):
    widget, _db = sales_screen
    load_range(qtbot, widget)
    previous_generation = widget._load_runner.generation
    widget.date_from.setDate(QDate(2026, 11, 1))
    widget.refresh_button.click()
    assert "From date" in widget.status_label.text()
    widget._loaded(
        previous_generation, SalesReportResult((), SalesWeights(sale_net=Decimal(999)))
    )
    assert widget.total_labels[0].text() == "—"
    assert not widget.open_button.isEnabled()
    load_range(qtbot, widget)
    widget.item_search.setText("absent")
    widget.refresh_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget.total_labels[0].text() == "0.00 g"
    assert "No sales" in widget.status_label.text()
    widget._failed(widget._load_runner.generation, RuntimeError("temporary error"))
    assert "temporary error" in widget.status_label.text()
    assert widget.total_labels[0].text() == "—"


def test_open_saved_report_voucher_protects_unsaved_entry(
    qtbot, tmp_path, make_estimate_widget, monkeypatch
):
    with report_database(tmp_path) as db:
        widget = make_estimate_widget(db)
        widget.note_edit.setText("Unsaved draft")
        widget._mark_unsaved()
        old_voucher = widget.voucher_edit.text()
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Cancel
        )
        assert not widget.open_saved_estimate("2")
        assert widget.note_edit.text() == "Unsaved draft"
        assert widget.voucher_edit.text() == old_voucher
        monkeypatch.setattr(
            QMessageBox, "question", lambda *args: QMessageBox.StandardButton.Discard
        )
        assert widget.open_saved_estimate("2")
        assert widget.voucher_edit.text() == "2"
        assert not widget.has_unsaved_changes()
        widget.stop_background_work()
