#!/usr/bin/env python
"""Build deterministic scale data and emit all required performance samples."""

from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from silverestimate.domain.estimate_models import EstimateLine, EstimateLineCategory
from silverestimate.persistence.database_driver import (
    SqlCipherConnectionBroker,
    export_database,
)
from silverestimate.persistence.estimates_repository import fetch_estimate_history_page
from silverestimate.persistence.silver_bars_snapshot_repository import (
    SilverBarsSnapshotRepository,
)
from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    parse_current_rates,
)
from silverestimate.services.dda_rate_stream import apply_sse_rate_event
from silverestimate.services.estimate_calculator import compute_totals
from silverestimate.ui.view_models.estimate_entry_view_model import (
    EstimateEntryRowState,
    EstimateEntryViewModel,
)

ITEM_COUNT = 10_000
BAR_COUNT = 50_000
ESTIMATE_COUNT = 10_000
ESTIMATE_LINE_COUNT = 50_000
VIEW_MODEL_ROW_COUNT = 500
ENCRYPTED_PLAINTEXT_SIZE = 10 * 1024 * 1024
HOT_SAMPLES = 20
FLUSH_SAMPLES = 5

ResultT = TypeVar("ResultT")


def create_deterministic_dataset(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = OFF;
            PRAGMA synchronous = OFF;
            CREATE TABLE items (
                code TEXT PRIMARY KEY,
                normalized_code TEXT NOT NULL,
                name TEXT NOT NULL
            );
            CREATE TABLE estimates (
                voucher_no TEXT PRIMARY KEY,
                voucher_no_int INTEGER,
                date TEXT,
                note TEXT,
                silver_rate REAL,
                total_gross REAL,
                total_net REAL,
                total_fine REAL,
                total_wage REAL,
                last_balance_amount REAL
            );
            CREATE TABLE estimate_items (
                item_id INTEGER PRIMARY KEY,
                voucher_no TEXT NOT NULL,
                item_code TEXT NOT NULL,
                gross REAL,
                net_wt REAL
            );
            CREATE TABLE silver_bar_lists (
                list_id INTEGER PRIMARY KEY,
                list_identifier TEXT,
                issued_date TEXT
            );
            CREATE TABLE silver_bars (
                bar_id INTEGER PRIMARY KEY,
                estimate_voucher_no TEXT,
                weight REAL,
                purity REAL,
                fine_weight REAL,
                status TEXT,
                date_added TEXT,
                list_id INTEGER
            );
            """
        )
        connection.executemany(
            "INSERT INTO items(code, normalized_code, name) VALUES (?, ?, ?)",
            (
                (f"I{index:05d}", f"i{index:05d}", f"Item {index:05d}")
                for index in range(ITEM_COUNT)
            ),
        )
        connection.executemany(
            """
            INSERT INTO estimates(
                voucher_no, voucher_no_int, date, note, silver_rate,
                total_gross, total_net, total_fine, total_wage,
                last_balance_amount
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    f"V{index:06d}",
                    index,
                    f"2026-06-{(index % 28) + 1:02d}",
                    f"Estimate {index:06d}",
                    225_000.0,
                    500.0,
                    495.0,
                    490.0,
                    1_250.0,
                    0.0,
                )
                for index in range(ESTIMATE_COUNT)
            ),
        )
        connection.executemany(
            """
            INSERT INTO estimate_items(
                item_id, voucher_no, item_code, gross, net_wt
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                (
                    index,
                    f"V{index // 5:06d}",
                    f"I{index % ITEM_COUNT:05d}",
                    100.0 + (index % 25),
                    99.0 + (index % 25),
                )
                for index in range(ESTIMATE_LINE_COUNT)
            ),
        )
        connection.executemany(
            """
            INSERT INTO silver_bars(
                bar_id, estimate_voucher_no, weight, purity, fine_weight,
                status, date_added, list_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    index + 1,
                    f"V{index % ESTIMATE_COUNT:06d}",
                    1_000.0 + (index % 250),
                    99.0,
                    (1_000.0 + (index % 250)) * 0.99,
                    "In Stock" if index % 3 else "Issued",
                    f"2026-06-{(index % 28) + 1:02d}T12:{index % 60:02d}:00Z",
                    None,
                )
                for index in range(BAR_COUNT)
            ),
        )
        connection.executescript(
            """
            CREATE INDEX idx_items_normalized_code
                ON items(normalized_code, code);
            CREATE INDEX idx_estimates_voucher_order
                ON estimates(voucher_no_int DESC, voucher_no DESC);
            CREATE INDEX idx_estimate_items_voucher
                ON estimate_items(voucher_no);
            CREATE INDEX idx_silver_bars_history
                ON silver_bars(date_added DESC, bar_id DESC);
            CREATE INDEX idx_silver_bars_availability
                ON silver_bars(status, list_id, weight, date_added DESC, bar_id DESC);
            """
        )
        connection.commit()
    finally:
        connection.close()


def _measure(operation: Callable[[], ResultT]) -> tuple[float, ResultT]:
    started = time.perf_counter()
    result = operation()
    return (time.perf_counter() - started) * 1000.0, result


def _emit(metric: str, duration_ms: float) -> None:
    print(f"[perf] {metric}={duration_ms:.4f}ms")


def _dda_payload() -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "view": "default",
        "sequence": 42,
        "serverTime": "2026-07-15T09:30:00Z",
        "items": [
            {
                "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                "name": "A future renamed product",
                "unit": "PER_KG",
                "baseRate": 1,
                "finalRate": 224_867,
            }
        ],
        "feedStatus": {"marketState": {"isOpen": True}},
    }


def _measure_encrypted_exports(temp_root: Path) -> None:
    encrypted_source = temp_root / "ten-mib.sqlcipher"
    source_broker = SqlCipherConnectionBroker(encrypted_source, b"K" * 32)
    source, _ = source_broker.open_writer(create=True)
    try:
        source.execute("CREATE TABLE payload(value BLOB NOT NULL)")
        source.execute(
            "INSERT INTO payload(value) VALUES (zeroblob(?))",
            (ENCRYPTED_PLAINTEXT_SIZE,),
        )
        source.commit()
        for sample in range(FLUSH_SAMPLES):
            encrypted = temp_root / f"backup-{sample}.sqlcipher"
            duration, _ = _measure(
                lambda encrypted=encrypted: export_database(
                    source, encrypted, b"B" * 32
                )
            )
            assert encrypted.stat().st_size >= ENCRYPTED_PLAINTEXT_SIZE
            _emit("encrypted_backup_export", duration)
    finally:
        source.close()


def run(output_path: Path) -> None:
    now = datetime(2026, 7, 15, 9, 30, tzinfo=timezone.utc)
    rows = tuple(
        EstimateEntryRowState(
            code=f"I{index:05d}",
            name=f"Item {index:05d}",
            gross=100.0,
            poly=1.0,
            net_weight=99.0,
            purity=99.0,
            wage_rate=2.0,
            wage_amount=198.0,
            fine_weight=98.01,
            row_index=index + 1,
        )
        for index in range(VIEW_MODEL_ROW_COUNT)
    )
    lines = tuple(
        EstimateLine(
            code=row.code,
            category=EstimateLineCategory.REGULAR,
            gross=row.gross,
            poly=row.poly,
            net_weight=row.net_weight,
            fine_weight=row.fine_weight,
            wage_amount=row.wage_amount,
        )
        for row in rows
    )
    current_json = json.dumps(_dda_payload(), separators=(",", ":"))

    with tempfile.TemporaryDirectory(prefix="silverestimate-perf-") as temp_dir:
        temp_root = Path(temp_dir)
        database_path = temp_root / "scale.sqlite"
        create_deterministic_dataset(database_path)

        def open_snapshot(_cancel_event=None):
            snapshot = sqlite3.connect(database_path)
            snapshot.row_factory = sqlite3.Row
            return snapshot

        snapshot_repository = SilverBarsSnapshotRepository(open_snapshot)
        connection = sqlite3.connect(database_path)
        connection.row_factory = sqlite3.Row
        try:
            for _ in range(HOT_SAMPLES):
                duration, page = _measure(
                    lambda: fetch_estimate_history_page(connection.cursor(), limit=500)
                )
                assert len(page.items) == 500 and page.total == ESTIMATE_COUNT
                _emit("estimate_history.page", duration)

                duration, page = _measure(
                    lambda: snapshot_repository.search_history_bars_page(limit=1_000)
                )
                assert len(page.items) == 1_000 and page.total == BAR_COUNT
                _emit("silver_bar_history.page", duration)

                duration, totals = _measure(
                    lambda: compute_totals(lines, silver_rate=225_000.0)
                )
                assert totals.regular.gross == 50_000.0
                _emit("estimate_totals.recompute", duration)

                model = EstimateEntryViewModel()
                duration, _ = _measure(lambda model=model: model.set_rows(rows))
                assert len(model.rows()) == VIEW_MODEL_ROW_COUNT
                _emit("view_model.synchronize", duration)

                duration, current = _measure(
                    lambda: parse_current_rates(current_json, received_at=now)
                )
                assert current.final_rate == 224_867
                _emit("dda_current.parse", duration)

                rate_event = {
                    "schemaVersion": 1,
                    "view": "default",
                    "sequence": current.sequence + 1,
                    "items": [
                        {
                            "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                            "finalRate": 224_868,
                        }
                    ],
                }
                duration, applied = _measure(
                    lambda rate_event=rate_event, current=current: apply_sse_rate_event(
                        rate_event, previous=current, received_at=now
                    )
                )
                assert applied[1] is not None and applied[1].final_rate == 224_868
                _emit("dda_sse.parse_apply", duration)
        finally:
            connection.close()

        _measure_encrypted_exports(temp_root)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    # Capture stdout as the canonical telemetry artifact while keeping a readable log.
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        run(args.output)
    telemetry = buffer.getvalue()
    args.output.write_text(telemetry, encoding="utf-8")
    print(telemetry, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
