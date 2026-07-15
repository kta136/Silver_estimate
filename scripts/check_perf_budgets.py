#!/usr/bin/env python
"""Fail CI unless every deterministic p95 performance budget is satisfied."""

from __future__ import annotations

import argparse
import math
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MetricBudget:
    p95_ms: float
    minimum_samples: int


METRIC_BUDGETS: dict[str, MetricBudget] = {
    "estimate_history.page": MetricBudget(250.0, 20),
    "silver_bar_history.page": MetricBudget(250.0, 20),
    "estimate_totals.recompute": MetricBudget(60.0, 20),
    "view_model.synchronize": MetricBudget(120.0, 20),
    "encrypted_flush": MetricBudget(150.0, 5),
    "dda_current.parse": MetricBudget(20.0, 20),
    "dda_sse.parse_apply": MetricBudget(20.0, 20),
}

PERF_PREFIX_RE = re.compile(r"\[perf\]")
PERF_VALUE_RE = re.compile(r"\[perf\]\s+([a-zA-Z0-9_.]+)=([^\s]+)(?:\s+.*)?$")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        raise ValueError("A percentile requires at least one value.")
    ordered = sorted(values)
    rank = (len(ordered) - 1) * max(0.0, min(100.0, pct)) / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def parse_metrics(log_text: str) -> tuple[dict[str, list[float]], list[str]]:
    metrics: dict[str, list[float]] = defaultdict(list)
    malformed: list[str] = []
    for line_number, line in enumerate(log_text.splitlines(), start=1):
        if not PERF_PREFIX_RE.search(line):
            continue
        match = PERF_VALUE_RE.search(line)
        if match is None:
            malformed.append(f"line {line_number}: {line.strip()}")
            continue
        raw_value = match.group(2)
        if raw_value.endswith("ms"):
            raw_value = raw_value[:-2]
        try:
            duration_ms = float(raw_value)
        except ValueError:
            malformed.append(f"line {line_number}: {line.strip()}")
            continue
        if not math.isfinite(duration_ms) or duration_ms < 0:
            malformed.append(f"line {line_number}: {line.strip()}")
            continue
        metrics[match.group(1)].append(duration_ms)
    return dict(metrics), malformed


def evaluate_metrics(metrics: dict[str, list[float]]) -> tuple[list[str], list[str]]:
    messages: list[str] = []
    failures: list[str] = []
    for metric, budget in METRIC_BUDGETS.items():
        samples = metrics.get(metric, [])
        if not samples:
            failures.append(f"missing:{metric}")
            continue
        if len(samples) < budget.minimum_samples:
            failures.append(
                f"insufficient:{metric}:samples={len(samples)},required={budget.minimum_samples}"
            )
            continue
        p95 = percentile(samples, 95.0)
        messages.append(
            f"metric={metric} samples={len(samples)} p95={p95:.2f}ms "
            f"budget={budget.p95_ms:.2f}ms"
        )
        if p95 > budget.p95_ms:
            failures.append(
                f"exceeded:{metric}:p95={p95:.2f}ms,budget={budget.p95_ms:.2f}ms,"
                f"samples={len(samples)}"
            )
    return messages, failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--log-file", required=True, help="Path to deterministic telemetry"
    )
    args = parser.parse_args()

    log_path = Path(args.log_file)
    if not log_path.exists():
        print(f"Perf gate failed: log file not found: {log_path}")
        return 1

    metrics, malformed = parse_metrics(
        log_path.read_text(encoding="utf-8", errors="replace")
    )
    if malformed:
        print("Perf gate failed: malformed telemetry:")
        for detail in malformed:
            print(f"- {detail}")
        return 1

    missing = [name for name in METRIC_BUDGETS if not metrics.get(name)]
    if missing:
        print("Perf gate failed: configured metrics were not observed:")
        for name in missing:
            print(f"- {name}")
        return 1

    messages, failures = evaluate_metrics(metrics)
    for message in messages:
        print(message)
    insufficient = [
        failure for failure in failures if failure.startswith("insufficient:")
    ]
    exceeded = [failure for failure in failures if failure.startswith("exceeded:")]
    if insufficient:
        print("\nPerf gate failed: insufficient samples:")
        for failure in insufficient:
            _, metric, detail = failure.split(":", 2)
            print(f"- {metric}: {detail}")
    if exceeded:
        print("\nPerf budget violations:")
        for failure in exceeded:
            _, metric, detail = failure.split(":", 2)
            print(f"- {metric}: {detail}")
    if failures:
        return 1

    print("All configured performance metrics satisfy their p95 budgets.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
