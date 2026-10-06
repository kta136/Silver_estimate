"""Representative saved estimates shared by report integration and UI checks."""

from contextlib import contextmanager

from silverestimate.persistence.database_manager import DatabaseManager
from tests.factories import estimate_totals, regular_item, return_item, silver_bar_item


@contextmanager
def report_database(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "sales.db"), "password", device_secret=b"R" * 32
    )
    try:
        for code in ("REG001", "OTHER", "BAR001"):
            assert db.add_item(code, code, 125.5, "WT", 0)
        save_report_estimate(
            db,
            "1",
            "2026-09-30",
            [
                regular_item(name="Old name", purity=125.5, fine=12.55),
                regular_item(
                    code="OTHER", name="Other item", gross=2, net_wt=2, fine=1.8
                ),
                silver_bar_item(gross=50, net_wt=50, fine=50),
            ],
            [
                return_item(
                    code="REG001", gross=3, poly=0, net_wt=3, purity=125.5, fine=3.77
                )
            ],
        )
        save_report_estimate(
            db,
            "2",
            "2026-10-01",
            [
                regular_item(name="New name", gross=5, net_wt=5, purity=80, fine=4),
                regular_item(
                    name="New name", gross=1, net_wt=1, purity=33.3, fine=0.333
                ),
            ],
            [return_item(code="OTHER", gross=2, poly=0, net_wt=2, fine=1.5)],
        )
        save_report_estimate(
            db,
            "3",
            "2026-10-31",
            [],
            [
                return_item(
                    code="REG001",
                    name="New name",
                    gross=1,
                    poly=0,
                    net_wt=1,
                    purity=150,
                    fine=1.5,
                ),
            ],
        )
        save_report_estimate(
            db, "4", "2026-11-01", [regular_item(gross=7, net_wt=7, fine=7)]
        )
        save_report_estimate(
            db, "5", "2025-10-01", [regular_item(gross=11, net_wt=11, fine=11)]
        )
        yield db
    finally:
        db.close()


def save_report_estimate(db, voucher, date, regular, returns=()):
    # The save API receives silver-bar lines in its deductions collection.
    bars = [item for item in regular if item.get("is_silver_bar")]
    sales = [item for item in regular if not item.get("is_silver_bar")]
    result = db.save_estimate_atomic(
        voucher,
        date,
        100,
        sales,
        list(returns) + bars,
        estimate_totals(last_balance_silver=999, last_balance_amount=888),
    )
    assert result.success, result.error_detail
