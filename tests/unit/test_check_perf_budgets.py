from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_perf_budgets.py"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_perf_gate_fails_when_log_file_is_missing(tmp_path):
    result = _run_script("--log-file", str(tmp_path / "missing.log"))

    assert result.returncode == 1
    assert "log file not found" in result.stdout


def test_perf_gate_fails_when_no_perf_lines_are_present(tmp_path):
    log_path = tmp_path / "empty.log"
    log_path.write_text("plain log line\n", encoding="utf-8")

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 1
    assert "no [perf] telemetry lines" in result.stdout


def test_perf_gate_parses_startup_and_ms_suffixed_metrics(tmp_path):
    log_path = tmp_path / "perf.log"
    log_path.write_text(
        "\n".join(
            [
                "[perf] startup.qt_ready_ms=120.89 t_unix=1772972261.027531",
                "[perf] item_master.load_items=132.82ms search_term='' rows=10000",
            ]
        ),
        encoding="utf-8",
    )

    result = _run_script(
        "--log-file",
        str(log_path),
        "--require-metric",
        "startup.qt_ready_ms",
        "--require-metric",
        "item_master.load_items",
    )

    assert result.returncode == 0
    assert "metric=startup.qt_ready_ms" in result.stdout
    assert "metric=item_master.load_items" in result.stdout


def test_perf_gate_fails_when_required_metric_is_missing(tmp_path):
    log_path = tmp_path / "perf.log"
    log_path.write_text(
        "[perf] item_master.load_items=132.82ms search_term='' rows=10000\n",
        encoding="utf-8",
    )

    result = _run_script(
        "--log-file",
        str(log_path),
        "--require-metric",
        "startup.qt_ready_ms",
    )

    assert result.returncode == 1
    assert "required metrics were not observed" in result.stdout
    assert "startup.qt_ready_ms" in result.stdout


def test_perf_gate_fails_when_budget_is_exceeded(tmp_path):
    log_path = tmp_path / "perf.log"
    log_path.write_text(
        "[perf] startup.qt_ready_ms=999.00 t_unix=1772972261.027531\n",
        encoding="utf-8",
    )

    result = _run_script(
        "--log-file",
        str(log_path),
        "--require-metric",
        "startup.qt_ready_ms",
    )

    assert result.returncode == 1
    assert "Perf budget violations" in result.stdout
    assert "startup.qt_ready_ms" in result.stdout
