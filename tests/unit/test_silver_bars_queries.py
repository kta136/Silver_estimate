from silverestimate.persistence.silver_bars_queries import (
    build_available_bars_queries,
    build_bars_in_list_queries,
    build_history_bars_query,
    normalize_row_limit,
)


def test_normalize_row_limit_uses_default_for_invalid_values():
    assert normalize_row_limit("not-a-number", default=2000) == 2000
    assert normalize_row_limit(None, default=1500) == 1500
    assert normalize_row_limit(50, default=1500) == 100


def test_build_available_bars_queries_applies_filters_and_limit():
    statements = build_available_bars_queries(
        weight_query="10",
        weight_tolerance=0.5,
        min_purity=90.0,
        max_purity=99.5,
        date_range=("2026-02-01", "2026-02-28"),
        limit=250,
    )

    assert "sb.status = 'In Stock' AND sb.list_id IS NULL" in statements.query.query
    assert "sb.weight BETWEEN ? AND ?" in statements.query.query
    assert "sb.purity >= ?" in statements.query.query
    assert "sb.purity <= ?" in statements.query.query
    assert "sb.date_added >= ?" in statements.query.query
    assert "sb.date_added <= ?" in statements.query.query
    assert statements.query.query.endswith("ORDER BY sb.date_added DESC, sb.bar_id DESC LIMIT ?")
    assert statements.query.params == (
        9.5,
        10.5,
        90.0,
        99.5,
        "2026-02-01",
        "2026-02-28",
        250,
    )
    assert statements.count_query.params == (
        9.5,
        10.5,
        90.0,
        99.5,
        "2026-02-01",
        "2026-02-28",
    )


def test_build_bars_in_list_queries_only_adds_offset_when_limited():
    statements = build_bars_in_list_queries(12, limit=50, offset=25)
    assert statements.query.query.endswith("WHERE sb.list_id = ? ORDER BY sb.bar_id LIMIT ? OFFSET ?")
    assert statements.query.params == (12, 50, 25)
    assert statements.count_query.query == "SELECT COUNT(*) FROM silver_bars WHERE list_id = ?"
    assert statements.count_query.params == (12,)

    unlimited = build_bars_in_list_queries(12, offset=25)
    assert "OFFSET" not in unlimited.query.query
    assert unlimited.query.params == (12,)


def test_build_history_bars_query_applies_filters_and_normalizes_limit():
    statement = build_history_bars_query(
        voucher_term="V001",
        weight_text="12.5",
        status_text="Assigned",
        limit=25,
    )

    assert "(sb.estimate_voucher_no LIKE ? OR e.note LIKE ?)" in statement.query
    assert "sb.weight = ?" in statement.query
    assert "sb.status = ?" in statement.query
    assert statement.query.endswith("ORDER BY sb.date_added DESC, sb.bar_id DESC LIMIT ?")
    assert statement.params == ("%V001%", "%V001%", 12.5, "Assigned", 100)


def test_build_history_bars_query_ignores_invalid_weight_filter():
    statement = build_history_bars_query(
        voucher_term="",
        weight_text="bad-value",
        status_text="All Statuses",
        limit=2000,
    )

    assert "sb.weight = ?" not in statement.query
    assert "sb.status = ?" not in statement.query
    assert statement.params == (2000,)
