from silverestimate.ui.silver_bar_optimization import (
    find_max_bars_combination,
    find_min_bars_combination,
)


def _bar(bar_id: int, fine_weight: float) -> dict:
    return {"bar_id": bar_id, "fine_weight": fine_weight}


def test_find_min_bars_combination_falls_back_to_dp_for_range_match():
    bars = [_bar(1, 60.0), _bar(2, 40.0), _bar(3, 35.0)]

    selected = find_min_bars_combination(bars, 70.0, 80.0)

    assert [row["bar_id"] for row in selected] == [2, 3]
    assert sum(row["fine_weight"] for row in selected) == 75.0


def test_find_max_bars_combination_prefers_more_bars_within_range():
    bars = [_bar(1, 50.0), _bar(2, 25.0), _bar(3, 25.0), _bar(4, 25.0)]

    selected = find_max_bars_combination(bars, 70.0, 80.0)

    assert [row["bar_id"] for row in selected] == [2, 3, 4]
    assert sum(row["fine_weight"] for row in selected) == 75.0
