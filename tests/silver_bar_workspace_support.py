"""Real encrypted inventory fixture shared by the keyboard-workspace tests."""

from silverestimate.domain.numeric_policy import fine_weight
from silverestimate.persistence.database_manager import DatabaseManager
from tests.factories import estimate_totals, silver_bar_item


def seed_workspace_db(tmp_path):
    db = DatabaseManager(
        str(tmp_path / "bars.db"), "test-pass", device_secret=b"K" * 32
    )
    assert db.add_item("BAR001", "Silver", 99, "WT", 0)
    values = [
        (40, 99.9),
        (40, 98.5),
        (40.25, 125.5),
        (402.5, 99.9),
        (85.25, 99),
        (10, 125.5),
        (54.3, 98.5),
    ]
    items = [
        silver_bar_item(
            line_key=f"bar-{i}",
            gross=weight,
            net_wt=weight,
            purity=purity,
            fine=fine_weight(weight, purity),
        )
        for i, (weight, purity) in enumerate(values)
    ]
    assert db.save_estimate_atomic(
        "1", "2026-10-04", 100, [], items, estimate_totals()
    ).success
    return db


def bar_list_count(db, *, include_issued=True):
    """Count saved silver-bar lists straight from the writer connection."""
    query = "SELECT COUNT(*) FROM silver_bar_lists"
    if not include_issued:
        query += " WHERE issued_date IS NULL"
    return db.conn.execute(query).fetchone()[0]
