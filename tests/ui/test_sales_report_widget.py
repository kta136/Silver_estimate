from decimal import Decimal

import pytest
from PySide6.QtCore import QDate, Qt

from silverestimate.domain.sales_report import SalesReportResult, SalesWeights
from silverestimate.ui.models.sales_report_table_model import format_period
from silverestimate.ui.sales_report import WEIGHT_WIDTH, SalesReportWidget
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
    # Each message is shown once, in the middle of the empty table.
    assert "From date" in widget._empty_state.text()
    assert widget.status_label.text() == ""
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
    assert "No sales" in widget._empty_state.title_label.text()
    assert widget.status_label.text() == ""
    widget._failed(widget._load_runner.generation, RuntimeError("temporary error"))
    assert "temporary error" in widget._empty_state.text()
    assert widget.total_labels[0].text() == "—"


def test_open_saved_report_voucher_protects_unsaved_entry(
    qtbot, tmp_path, make_estimate_widget, confirmations
):
    with report_database(tmp_path) as db:
        widget = make_estimate_widget(db)
        widget.note_edit.setText("Unsaved draft")
        widget._mark_unsaved()
        old_voucher = widget.voucher_edit.text()
        confirmations.always("Cancel")
        assert not widget.open_saved_estimate("2")
        assert widget.note_edit.text() == "Unsaved draft"
        assert widget.voucher_edit.text() == old_voucher
        confirmations.always("Discard")
        assert widget.open_saved_estimate("2")
        assert widget.voucher_edit.text() == "2"
        assert not widget.has_unsaved_changes()
        widget.stop_background_work()


def test_export_writes_the_table_shown_with_its_totals(
    sales_screen, qtbot, tmp_path, monkeypatch
):
    widget, _db = sales_screen
    assert not widget.export_button.isEnabled()
    load_range(qtbot, widget)
    assert widget.export_button.isEnabled()
    target = tmp_path / "report.csv"
    monkeypatch.setattr(
        "silverestimate.ui.sales_report.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), "CSV (*.csv)"),
    )

    widget.export_button.click()

    lines = target.read_text(encoding="utf-8-sig").splitlines()
    assert lines[0] == (
        "Date,Sale Net (g),Sale Fine (g),Return Net (g),Return Fine (g)"
    )
    assert len(lines) == widget.model.rowCount() + 2
    assert lines[-1] == "Total,18.00,18.68,6.00,6.77"
    assert str(target) in widget.status_label.text()


@pytest.mark.parametrize(
    ("name", "today", "expected"),
    [
        ("last_7_days", (2026, 10, 10), ((2026, 10, 4), (2026, 10, 10))),
        ("last_month", (2026, 3, 31), ((2026, 2, 1), (2026, 2, 28))),
        ("last_month", (2026, 1, 15), ((2025, 12, 1), (2025, 12, 31))),
        ("this_fy", (2026, 10, 10), ((2026, 4, 1), (2026, 10, 10))),
        ("this_fy", (2026, 2, 10), ((2025, 4, 1), (2026, 2, 10))),
        ("last_fy", (2026, 10, 10), ((2025, 4, 1), (2026, 3, 31))),
        ("last_fy", (2026, 2, 10), ((2024, 4, 1), (2025, 3, 31))),
    ],
)
def test_preset_date_ranges(name, today, expected):
    start, end = SalesReportWidget.preset_range(name, QDate(*today))
    assert (start, end) == (QDate(*expected[0]), QDate(*expected[1]))


def test_breadcrumb_count_agrees_with_one_row(sales_screen, qtbot):
    widget, _db = sales_screen
    widget.date_from.setDate(QDate(2026, 9, 30))
    widget.date_to.setDate(QDate(2026, 9, 30))
    widget.refresh_button.click()
    qtbot.waitUntil(lambda: not widget._loading)
    assert widget.model.rowCount() == 1
    assert "1 day with sales or returns" in widget.breadcrumb.text()


def test_grouping_applies_at_once_and_the_caption_follows_the_drill_down(
    sales_screen, qtbot
):
    from PySide6.QtWidgets import QHeaderView

    widget, _db = sales_screen
    load_range(qtbot, widget)
    assert widget.model.headerData(0, Qt.Orientation.Horizontal) == "Date"
    assert " to " in widget.scope_label.text()

    # No second step: choosing Month regroups the report straight away.
    widget.grouping.setCurrentIndex(1)
    qtbot.waitUntil(lambda: not widget._loading and widget.model.rowCount() > 0)
    assert widget.model.headerData(0, Qt.Orientation.Horizontal) == "Month"

    month = widget.model.rows[0].key
    open_row(qtbot, widget, month)
    # The totals beside the caption are for this month, so it names the month.
    assert widget.scope_label.text() == f"{format_period(month)} · all items"
    assert widget.scope_label.toolTip().startswith("Report dates:")

    # In the item view the name takes the spare width, not the figures.
    header = widget.table.horizontalHeader()
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Fixed
    assert header.sectionSize(widget.model.weight_offset) == WEIGHT_WIDTH

    code = widget.model.rows[0].key
    open_row(qtbot, widget, code)
    assert widget.scope_label.text() == f"{format_period(month)} · item {code}"
