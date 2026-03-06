"""Pure optimization helpers for silver-bar list generation."""

from __future__ import annotations


def find_optimal_combination(
    available_bars, min_target: float, max_target: float, optimization_type: str
):
    """Find a bar combination within the target range."""
    bars = sorted(available_bars, key=lambda row: row["fine_weight"], reverse=True)
    if optimization_type == "min_bars":
        return find_min_bars_combination(bars, min_target, max_target)
    return find_max_bars_combination(bars, min_target, max_target)


def find_min_bars_combination(bars, min_target: float, max_target: float):
    """Prefer the smallest number of bars within the target range."""
    selected = []
    current_total = 0.0

    for bar in bars:
        if current_total + bar["fine_weight"] <= max_target:
            selected.append(bar)
            current_total += bar["fine_weight"]
            if current_total >= min_target:
                break

    if min_target <= current_total <= max_target:
        return selected

    if len(bars) <= 50:
        return dp_combination_range(bars, min_target, max_target)

    return []


def find_max_bars_combination(bars, min_target: float, max_target: float):
    """Prefer the largest number of bars while staying in the range."""
    bars_asc = sorted(bars, key=lambda row: row["fine_weight"])
    selected = []
    current_total = 0.0

    for bar in bars_asc:
        if current_total + bar["fine_weight"] <= max_target:
            selected.append(bar)
            current_total += bar["fine_weight"]

    return selected if min_target <= current_total <= max_target else []


def dp_combination_range(bars, min_target: float, max_target: float):
    """Find a minimum-bar solution using a DP range search."""
    min_target_int = int(min_target * 10)
    max_target_int = int(max_target * 10)

    dp = {0: (0, [])}

    for index, bar in enumerate(bars):
        bar_weight = int(bar["fine_weight"] * 10)
        new_dp = dp.copy()

        for weight, (count, indices) in dp.items():
            new_weight = weight + bar_weight
            if new_weight <= max_target_int:
                if new_weight not in new_dp or new_dp[new_weight][0] > count + 1:
                    new_dp[new_weight] = (count + 1, indices + [index])

        dp = new_dp

    best_solution = None
    best_bars_count = float("inf")

    for weight, (count, indices) in dp.items():
        if min_target_int <= weight <= max_target_int and count < best_bars_count:
            best_bars_count = count
            best_solution = indices

    if best_solution:
        return [bars[index] for index in best_solution]

    return []
