#!/usr/bin/env python
"""Measure a frozen artifact repeatedly and enforce a p95 startup budget."""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable


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


def measure_artifact(
    artifact: Path,
    *,
    samples: int,
    timeout_seconds: float,
    runner: Callable[..., Any] | None = None,
    clock: Callable[[], float] | None = None,
) -> list[float]:
    """Return complete process durations in milliseconds."""

    run_process = runner or subprocess.run
    now = clock or time.perf_counter
    env = dict(os.environ)
    env["SILVER_SHOW_CONSOLE"] = "1"
    durations = []
    for sample_number in range(1, samples + 1):
        started_at = now()
        result = run_process(
            [str(artifact), "--artifact-smoke"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
        duration_ms = (now() - started_at) * 1000.0
        if result.returncode != 0:
            output = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(
                f"Artifact startup sample {sample_number} failed with exit code "
                f"{result.returncode}: {output}"
            )
        durations.append(duration_ms)
        print(f"sample={sample_number} startup={duration_ms:.2f}ms")
    return durations


def evaluate_startup(samples: list[float], budget_ms: float) -> tuple[str, bool]:
    p95_ms = percentile(samples, 95.0)
    message = (
        f"artifact_startup samples={len(samples)} p95={p95_ms:.2f}ms "
        f"budget={budget_ms:.2f}ms"
    )
    return message, p95_ms <= budget_ms


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--p95-budget-ms", type=float, default=3000.0)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    args = parser.parse_args()

    if not args.artifact.is_file():
        print(f"Startup gate failed: artifact not found: {args.artifact}")
        return 1
    if args.samples < 2:
        print("Startup gate failed: --samples must be at least 2.")
        return 1
    if args.p95_budget_ms <= 0 or args.timeout_seconds <= 0:
        print("Startup gate failed: budgets and timeouts must be positive.")
        return 1

    try:
        samples = measure_artifact(
            args.artifact,
            samples=args.samples,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"Startup gate failed: {exc}")
        return 1

    message, passed = evaluate_startup(samples, args.p95_budget_ms)
    print(message)
    if not passed:
        print("Startup gate failed: p95 budget exceeded.")
        return 1
    print("Frozen artifact startup satisfies its p95 budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
