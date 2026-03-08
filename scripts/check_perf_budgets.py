#!/usr/bin/env python
"""Fail CI when p95 performance telemetry exceeds configured budgets."""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

METRIC_BUDGETS_MS = {
    "estimate_entry.cell_edit": 60.0,
    "estimate_entry.apply_loaded_estimate": 800.0,
    "item_master.load_items": 150.0,
    "silver_bars.load_available": 500.0,
    "silver_bars.load_list": 500.0,
    "startup.qt_ready_ms": 450.0,
    "startup.auth_dialog_accepted_ms": 1200.0,
    "startup.db_ready_ms": 900.0,
    "startup.main_window_show_ms": 2200.0,
    "startup.main_window_first_idle_ms": 2600.0,
}

PERF_RE = re.compile(
    r"\[perf\]\s+([a-zA-Z0-9_.]+)=([0-9]+(?:\.[0-9]+)?)(?:ms)?\b"
)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * max(0.0, min(100.0, pct)) / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def parse_metrics(log_text: str) -> dict[str, list[float]]:
    metrics: dict[str, list[float]] = defaultdict(list)
    for line in log_text.splitlines():
        match = PERF_RE.search(line)
        if not match:
            continue
        metric = match.group(1)
        duration_ms = float(match.group(2))
        metrics[metric].append(duration_ms)
    return metrics


def find_missing_metrics(
    metrics: dict[str, list[float]],
    required_metrics: list[str],
) -> list[str]:
    return [
        metric
        for metric in required_metrics
        if not metrics.get(metric)
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-file", required=True, help="Path to captured test/app log"
    )
    parser.add_argument(
        "--require-metric",
        action="append",
        default=[],
        help="Metric name that must appear at least once in the log. Repeat as needed.",
    )
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Perf gate failed: log file not found: {log_path}")
        return 1

    metrics = parse_metrics(log_path.read_text(encoding="utf-8", errors="replace"))
    if not metrics:
        print("Perf gate failed: no [perf] telemetry lines were found in the log.")
        return 1

    missing_metrics = find_missing_metrics(metrics, list(args.require_metric or []))
    if missing_metrics:
        print("Perf gate failed: required metrics were not observed:")
        for metric in missing_metrics:
            print(f"- {metric}")
        return 1

    failed: list[tuple[str, float, float, int]] = []
    for metric, budget_ms in METRIC_BUDGETS_MS.items():
        samples = metrics.get(metric)
        if not samples:
            continue
        p95 = percentile(samples, 95.0)
        print(
            f"metric={metric} samples={len(samples)} p95={p95:.2f}ms budget={budget_ms:.2f}ms"
        )
        if p95 > budget_ms:
            failed.append((metric, p95, budget_ms, len(samples)))

    if failed:
        print("\nPerf budget violations:")
        for metric, p95, budget, count in failed:
            print(f"- {metric}: p95={p95:.2f}ms > {budget:.2f}ms (samples={count})")
        return 1

    print("All observed performance metrics are within configured budgets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
