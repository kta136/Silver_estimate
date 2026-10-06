from dataclasses import replace
from decimal import Decimal
from threading import Event

import pytest

from silverestimate.domain.sales_report import SalesReportQuery, SalesWeights
from silverestimate.infrastructure.latest_request_runner import RequestCancelledError
from silverestimate.persistence.sales_report_repository import fetch_sales_report
from tests.factories import regular_item
from tests.sales_report_support import report_database, save_report_estimate


@pytest.fixture
def sales_db(tmp_path):
    with report_database(tmp_path) as db:
        yield db


def report(db, **overrides):
    query = replace(SalesReportQuery("2026-09-30", "2026-10-31"), **overrides)
    with db.open_read_connection() as connection:
        return fetch_sales_report(connection.cursor(), query)


def test_daily_and_monthly_totals_keep_returns_separate_and_exclude_bars(sales_db):
    daily = report(sales_db)
    assert [row.key for row in daily.rows] == ["2026-10-31", "2026-10-01", "2026-09-30"]
    assert daily.totals.values() == tuple(map(Decimal, ("18", "18.683", "6", "6.77")))
    assert daily.rows[0].weights == SalesWeights(
        return_net=Decimal(1), return_fine=Decimal("1.5")
    )
    assert daily.rows[-1].weights.sale_fine == Decimal("14.35")
    monthly = report(sales_db, grouping="month")
    assert [row.key for row in monthly.rows] == ["2026-10", "2026-09"]
    assert monthly.totals == daily.totals
    assert monthly.rows[0].weights.values() == tuple(
        map(Decimal, ("6", "4.333", "3", "3"))
    )


def test_item_and_voucher_drilldown_reconcile_with_the_selected_period(sales_db):
    items = report(sales_db, level="item", grouping="month", period="2026-10")
    assert [row.key for row in items.rows] == ["OTHER", "REG001"]
    item = items.rows[1]
    assert item.detail == "New name"
    assert item.weights.values() == tuple(map(Decimal, ("6", "4.333", "1", "1.5")))
    vouchers = report(
        sales_db,
        level="voucher",
        grouping="month",
        period="2026-10",
        item_code="REG001",
    )
    assert [row.key for row in vouchers.rows] == ["3", "2"]
    assert vouchers.totals == item.weights
    assert vouchers.rows[1].weights.sale_fine == Decimal("4.333")
    assert report(sales_db, grouping="month").rows[0].weights == items.totals


def test_catalog_changes_do_not_change_reported_codes_names_or_weights(sales_db):
    before = report(sales_db, level="item")
    assert sales_db.delete_item("REG001")
    assert report(sales_db, level="item") == before
    assert sales_db.add_item("REG001", "Replacement catalog name", 30, "WT", 0)
    assert report(sales_db, level="item") == before
    assert report(sales_db, item_search=" reg001 ").totals.sale_fine == Decimal(
        "16.883"
    )


@pytest.mark.parametrize("search", ["%", "_", "' OR 1=1 --", "missing"])
def test_item_code_filter_is_literal_and_does_not_match_names(sales_db, search):
    assert report(sales_db, item_search=search).rows == ()
    assert report(sales_db, item_search="New name").rows == ()


def test_edited_backdated_and_deleted_estimates_are_reflected(sales_db):
    save_report_estimate(
        sales_db,
        "2",
        "2026-09-30",
        [regular_item(gross=2, net_wt=2, purity=150, fine=3)],
    )
    result = report(sales_db, grouping="month")
    assert result.rows[0].weights.sale_net == 0
    assert result.rows[1].weights.sale_net == 14
    assert sales_db.delete_single_estimate("2")
    assert report(sales_db).totals.sale_net == 12


def test_inclusive_dates_year_boundaries_and_empty_range(sales_db):
    assert (
        report(sales_db, date_from="2026-10-01", date_to="2026-10-01").totals.sale_net
        == 6
    )
    assert report(
        sales_db, date_from="2026-10-31", date_to="2026-10-31"
    ).totals.return_fine == Decimal("1.5")
    assert (
        report(sales_db, date_from="2026-10-02", date_to="2026-10-30").totals
        == SalesWeights()
    )
    rows = report(sales_db, date_from="2025-10-01", grouping="month").rows
    assert [row.key for row in rows] == ["2026-10", "2026-09", "2025-10"]


def test_invalid_dates_and_cancellation(sales_db):
    with pytest.raises(ValueError, match="From date"):
        report(sales_db, date_from="2026-11-01")
    with pytest.raises(ValueError):
        report(sales_db, date_from="2026-02-30")
    cancelled = Event()
    cancelled.set()
    with (
        sales_db.open_read_connection() as connection,
        pytest.raises(RequestCancelledError),
    ):
        fetch_sales_report(
            connection.cursor(), SalesReportQuery("2026-09-30", "2026-10-31"), cancelled
        )
