"""Profile production encrypted workflows using disposable synthetic data."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from silverestimate.domain.pagination import (
    AvailableBarCursor,
    EstimateHistoryCursor,
    ItemCursor,
    SilverBarHistoryCursor,
)
from silverestimate.persistence.database_manager import DatabaseManager
from silverestimate.persistence.estimates_repository import fetch_estimate_history_page
from silverestimate.persistence.items_repository import fetch_item_catalog_page
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)

SYNTHETIC_PASSWORD = "synthetic-benchmark-password"
SYNTHETIC_DEVICE_SECRET = b"B" * 32
BASE_DATE = datetime(2026, 8, 1)


@dataclass(frozen=True)
class DatasetScale:
    estimates: int
    bars: int
    items: int


PROFILES = {
    "small": DatasetScale(10_000, 50_000, 10_000),
    "large": DatasetScale(100_000, 500_000, 50_000),
}


def seed_database(db: DatabaseManager, scale: DatasetScale) -> None:
    """Populate the production schema; retain its encryption and writer policy."""
    conn = db.conn
    assert conn is not None
    with conn:
        conn.executemany(
            "INSERT INTO items(code,name,purity,wage_type,wage_rate) "
            "VALUES(?,?,92.5,'WT',10)",
            (
                (f"I{i:06d}", f"Synthetic item {i:06d}")
                for i in range(1, scale.items + 1)
            ),
        )
        conn.executemany(
            "INSERT INTO estimates(voucher_no,voucher_no_int,date,note,silver_rate,"
            "total_gross,total_net,total_fine,total_wage,last_balance_amount) "
            "VALUES(?,?,?,?,100,100,99,91.575,990,0)",
            (
                (
                    str(i),
                    i,
                    f"2026-08-{i % 28 + 1:02d}",
                    f"Synthetic customer {i % 1000:04d}",
                )
                for i in range(1, scale.estimates + 1)
            ),
        )
        conn.executemany(
            "INSERT INTO estimate_items(voucher_no,item_code,item_name,gross,poly,"
            "net_wt,purity,wage_rate,wage_type,wage,fine,line_key) "
            "VALUES(?,?,?,20,0.2,19.8,92.5,10,'WT',198,18.315,?)",
            (
                (
                    str(i // 5 + 1),
                    f"I{i % scale.items + 1:06d}",
                    "Synthetic item",
                    f"line-{i}",
                )
                for i in range(scale.estimates * 5)
            ),
        )
        conn.execute(
            "INSERT INTO silver_bar_lists(list_identifier,creation_date) "
            "VALUES('SYNTHETIC','2026-08-01')"
        )
        conn.executemany(
            "INSERT INTO silver_bars(estimate_voucher_no,weight,purity,fine_weight,"
            "date_added,status,list_id,source_line_key) VALUES(?,?,99,?,?,?,?,?)",
            (
                (
                    str(i % scale.estimates + 1),
                    1000 + i % 250,
                    (1000 + i % 250) * 0.99,
                    (BASE_DATE + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S"),
                    "In Stock" if i % 3 else "Issued",
                    None if i % 3 else 1,
                    f"bar-{i}",
                )
                for i in range(1, scale.bars + 1)
            ),
        )
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def measure(operation: Callable[[], object], samples: int) -> dict:
    """Warm once, then time stable results; use nearest-rank p95."""
    expected = repr(operation())
    durations = []
    for _ in range(samples):
        started = time.perf_counter()
        result = operation()
        durations.append((time.perf_counter() - started) * 1000)
        if repr(result) != expected:
            raise RuntimeError("Benchmark results changed between identical requests")
    return {
        "median_ms": round(statistics.median(durations), 3),
        "p95_ms": round(sorted(durations)[math.ceil(0.95 * samples) - 1], 3),
        "samples_ms": [round(value, 3) for value in durations],
        "result_sha256": hashlib.sha256(expected.encode()).hexdigest(),
    }


def query_operations(db: DatabaseManager, scale: DatasetScale) -> dict[str, Callable]:
    repo = SilverBarsSnapshotRepository(db.open_read_connection)
    bar_key = max(1, scale.bars // 10)
    bar_date = (BASE_DATE + timedelta(seconds=bar_key)).strftime("%Y-%m-%d %H:%M:%S")
    estimate_key = max(1, scale.estimates // 10)
    item_key = f"I{max(1, int(scale.items * 0.9)):06d}"

    def estimate_page(**kwargs):
        with db.open_read_connection() as conn:
            return fetch_estimate_history_page(conn.cursor(), **kwargs)

    def item_page(term="", **kwargs):
        with db.open_read_connection() as conn:
            return fetch_item_catalog_page(conn.cursor(), term, **kwargs)

    return {
        "estimate_first_page": lambda: estimate_page(),
        "estimate_deep_page": lambda: estimate_page(
            page_cursor=EstimateHistoryCursor(estimate_key, str(estimate_key))
        ),
        "estimate_substring_search": lambda: estimate_page(voucher_search="123"),
        "bar_history_first_page": repo.search_history_bars_page,
        "bar_history_deep_page": lambda: repo.search_history_bars_page(
            cursor=SilverBarHistoryCursor(bar_date, bar_key)
        ),
        "bar_history_status": lambda: repo.search_history_bars_page(
            status_text="In Stock"
        ),
        "bar_history_substring": lambda: repo.search_history_bars_page(
            voucher_term="0123"
        ),
        "available_first_page": repo.get_available_bars_keyset_page,
        "available_deep_page": lambda: repo.get_available_bars_keyset_page(
            cursor=AvailableBarCursor(bar_date, bar_key)
        ),
        "available_weight_filter": lambda: repo.get_available_bars_keyset_page(
            weight_query=1100
        ),
        "estimate_append_page": lambda: estimate_page(
            page_cursor=EstimateHistoryCursor(estimate_key, str(estimate_key)),
            include_total=False,
        ),
        "bar_history_append_page": lambda: repo.search_history_bars_page(
            cursor=SilverBarHistoryCursor(bar_date, bar_key), include_total=False
        ),
        "available_append_page": lambda: repo.get_available_bars_keyset_page(
            cursor=AvailableBarCursor(bar_date, bar_key), include_total=False
        ),
        "item_first_page": lambda: item_page(),
        "item_deep_page": lambda: item_page(page_cursor=ItemCursor(item_key, item_key)),
        "item_prefix": lambda: item_page("I00"),
        "item_substring": lambda: item_page("123"),
    }


def run_benchmark(
    scale: DatasetScale, *, samples: int = 11, lifecycle_samples: int = 3
) -> dict:
    if min(scale.estimates, scale.bars, scale.items, samples, lifecycle_samples) < 1:
        raise ValueError("Dataset sizes and sample counts must be positive")
    result = {
        "fixture_version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "scale": asdict(scale),
        "method": "Production SQLCipher schema and WAL; warm-cache requests; one warm-up; nearest-rank p95. Open includes close/checkpoint. No candidate indexes applied.",
    }
    with tempfile.TemporaryDirectory(prefix="silverestimate-benchmark-") as temp:
        folder = Path(temp)
        path = folder / "synthetic.db"

        def open_database():
            return DatabaseManager(
                str(path), SYNTHETIC_PASSWORD, device_secret=SYNTHETIC_DEVICE_SECRET
            )

        db = open_database()
        try:
            seed_database(db, scale)
            result["driver"] = asdict(db.driver_identity)
            result["driver"]["compile_options"] = sorted(
                db.driver_identity.compile_options
            )
            result["database_bytes"] = path.stat().st_size
            assert db.conn is not None
            result["counts"] = {
                table: db.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # nosec B608 -- fixed table names
                for table in ("estimates", "estimate_items", "silver_bars", "items")
            }
            result["queries"] = {
                name: measure(operation, samples)
                for name, operation in query_operations(db, scale).items()
            }
            result["lifecycle"] = {
                "validation": measure(
                    lambda: db.validate_database(db.conn), lifecycle_samples
                ),
                "backup": measure(
                    lambda: (
                        db.create_encrypted_backup(
                            folder / "synthetic.sedbbackup"
                        ).status.value
                    ),
                    lifecycle_samples,
                ),
            }
        finally:
            db.close()

        def reopen():
            reopened = open_database()
            reopened.close()

        result["lifecycle"]["open_and_close"] = measure(reopen, lifecycle_samples)
    return result


def positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("Must be positive")
    return number


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILES, default="small")
    parser.add_argument("--samples", type=positive_int, default=11)
    parser.add_argument("--lifecycle-samples", type=positive_int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or Path(f"artifacts/performance/sqlcipher-{args.profile}.json")
    result = run_benchmark(
        PROFILES[args.profile],
        samples=args.samples,
        lifecycle_samples=args.lifecycle_samples,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"SQLCipher {args.profile} benchmark written to {output}")
    for group in ("queries", "lifecycle"):
        for name, metric in result[group].items():
            print(
                f"{name}: median={metric['median_ms']:.2f}ms p95={metric['p95_ms']:.2f}ms"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
