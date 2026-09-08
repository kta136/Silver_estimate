from __future__ import annotations

import json

import pytest

from scripts.benchmark_sqlcipher import DatasetScale, measure, run_benchmark


def test_encrypted_benchmark_uses_valid_production_data_and_complete_workflows():
    result = run_benchmark(DatasetScale(12, 60, 15), samples=2, lifecycle_samples=1)
    result = json.loads(json.dumps(result))
    assert result["counts"] == {
        "estimates": 12,
        "estimate_items": 60,
        "silver_bars": 60,
        "items": 15,
    }
    assert result["driver"]["sqlcipher_version"]
    assert result["database_bytes"] > 0
    assert set(result["lifecycle"]) == {"validation", "backup", "open_and_close"}
    for group in ("queries", "lifecycle"):
        for metric in result[group].values():
            assert 0 <= metric["median_ms"] <= metric["p95_ms"]
            assert len(metric["result_sha256"]) == 64


def test_benchmark_rejects_unstable_results():
    values = iter(["same", "changed"])
    with pytest.raises(RuntimeError, match="results changed"):
        measure(lambda: next(values), samples=1)
