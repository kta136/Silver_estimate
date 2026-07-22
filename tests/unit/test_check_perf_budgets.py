from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_perf_budgets.py"

METRICS = {
    "estimate_history.page": (20, 20.0),
    "silver_bar_history.page": (20, 20.0),
    "estimate_totals.recompute": (20, 5.0),
    "view_model.synchronize": (20, 5.0),
    "encrypted_backup_export": (5, 50.0),
    "dda_current.parse": (20, 1.0),
    "dda_sse.parse_apply": (20, 1.0),
}


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _valid_telemetry() -> str:
    return "\n".join(
        f"[perf] {metric}={duration:.2f}ms"
        for metric, (count, duration) in METRICS.items()
        for _ in range(count)
    )


def test_perf_gate_fails_when_log_file_is_missing(tmp_path: Path) -> None:
    result = _run_script("--log-file", str(tmp_path / "missing.log"))

    assert result.returncode == 1
    assert "log file not found" in result.stdout


def test_perf_gate_requires_every_configured_metric(tmp_path: Path) -> None:
    log_path = tmp_path / "perf.log"
    log_path.write_text("[perf] estimate_history.page=10.0ms\n", encoding="utf-8")

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 1
    assert "configured metrics were not observed" in result.stdout
    assert "dda_sse.parse_apply" in result.stdout


def test_perf_gate_rejects_malformed_telemetry(tmp_path: Path) -> None:
    log_path = tmp_path / "perf.log"
    log_path.write_text(
        f"{_valid_telemetry()}\n[perf] encrypted_backup_export=not-a-number\n",
        encoding="utf-8",
    )

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 1
    assert "malformed telemetry" in result.stdout


def test_perf_gate_rejects_insufficient_samples(tmp_path: Path) -> None:
    log_path = tmp_path / "perf.log"
    telemetry = _valid_telemetry().replace(
        "[perf] encrypted_backup_export=50.00ms\n", "", 1
    )
    log_path.write_text(telemetry, encoding="utf-8")

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 1
    assert "insufficient samples" in result.stdout
    assert "encrypted_backup_export" in result.stdout


def test_perf_gate_rejects_exceeded_p95(tmp_path: Path) -> None:
    log_path = tmp_path / "perf.log"
    telemetry = _valid_telemetry().replace(
        "[perf] encrypted_backup_export=50.00ms",
        "[perf] encrypted_backup_export=999.00ms",
    )
    log_path.write_text(telemetry, encoding="utf-8")

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 1
    assert "Perf budget violations" in result.stdout
    assert "encrypted_backup_export" in result.stdout


def test_perf_gate_accepts_complete_telemetry(tmp_path: Path) -> None:
    log_path = tmp_path / "perf.log"
    log_path.write_text(_valid_telemetry(), encoding="utf-8")

    result = _run_script("--log-file", str(log_path))

    assert result.returncode == 0
    assert "All configured performance metrics" in result.stdout
