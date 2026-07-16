from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.check_startup_budgets import (
    evaluate_startup,
    measure_artifact,
    percentile,
)


def test_percentile_interpolates_samples():
    assert percentile([100.0, 200.0, 300.0, 400.0, 500.0], 95.0) == pytest.approx(480.0)


def test_measure_artifact_waits_for_each_process_and_records_duration():
    ticks = iter((1.0, 1.1, 2.0, 2.25))
    calls = []

    def _runner(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    samples = measure_artifact(
        Path("SilverEstimate.exe"),
        samples=2,
        timeout_seconds=10.0,
        runner=_runner,
        clock=lambda: next(ticks),
    )

    assert samples == pytest.approx([100.0, 250.0])
    assert all(call[0][-1] == "--artifact-smoke" for call in calls)
    assert all(call[1]["env"]["SILVER_SHOW_CONSOLE"] == "1" for call in calls)


def test_measure_artifact_rejects_failed_process():
    result = SimpleNamespace(returncode=3, stdout="", stderr="boom")

    with pytest.raises(RuntimeError, match="exit code 3: boom"):
        measure_artifact(
            Path("SilverEstimate.exe"),
            samples=2,
            timeout_seconds=10.0,
            runner=lambda *_args, **_kwargs: result,
            clock=iter((1.0, 1.1)).__next__,
        )


def test_evaluate_startup_enforces_p95_budget():
    message, passed = evaluate_startup([100.0, 120.0, 140.0], 150.0)
    assert passed is True
    assert "p95=" in message

    _, passed = evaluate_startup([100.0, 200.0, 400.0], 150.0)
    assert passed is False
