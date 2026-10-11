from silverestimate.persistence.silver_bar_query_repository import (
    build_history_bars_query,
    normalize_row_limit,
)


def test_normalize_row_limit_uses_default_for_invalid_values():
    assert normalize_row_limit("not-a-number", default=2000) == 2000
    assert normalize_row_limit(None, default=1500) == 1500
    assert normalize_row_limit(50, default=1500) == 100


def test_build_history_bars_query_applies_filters_and_normalizes_limit():
    statement = build_history_bars_query(
        voucher_term="V001",
        weight_text="12.5",
        status_text="Assigned",
        limit=25,
    )

    assert (
        "(sb.estimate_voucher_no LIKE ? OR sb.estimate_voucher_no IN (SELECT voucher_no FROM estimates WHERE note LIKE ?))"
        in statement.query
    )
    assert "sb.weight = ?" in statement.query
    assert "sb.status = ?" in statement.query
    assert statement.query.endswith(
        "ORDER BY COALESCE(sb.date_added, '') DESC, sb.bar_id DESC LIMIT ?"
    )
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


def test_keyset_queries_bind_stable_cursor_values():
    history = build_history_bars_query(
        limit=11,
        after_date_added="2026-07-15T01:00:00",
        after_bar_id=42,
    )
    assert "COALESCE(sb.date_added, '') < ?" in history.query
    assert history.params == (
        "2026-07-15T01:00:00",
        "2026-07-15T01:00:00",
        "2026-07-15T01:00:00",
        42,
        100,
    )
