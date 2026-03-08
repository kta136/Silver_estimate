import sqlite3
from pathlib import Path

from silverestimate.ui.item_import_manager import ItemImportManager


class _DbManagerStub:
    def __init__(self, temp_db_path):
        self.temp_db_path = str(temp_db_path)
        self.flush_calls = 0

    def request_flush(self):
        self.flush_calls += 1


def _create_items_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                code TEXT PRIMARY KEY,
                name TEXT,
                purity REAL,
                wage_type TEXT,
                wage_rate REAL
            )
            """)
        conn.commit()
    finally:
        conn.close()


def _default_import_settings():
    return {
        "delimiter": "|",
        "code_column": 0,
        "name_column": 1,
        "purity_column": 2,
        "type_column": 3,
        "rate_column": 4,
        "skip_header": False,
        "use_filter": False,
        "wage_adjustment_factor": "",
        "duplicate_mode": 0,
    }


def test_import_can_be_cancelled_mid_run(qt_app, tmp_path):
    db_path = tmp_path / "import.sqlite"
    _create_items_db(db_path)
    manager = ItemImportManager(_DbManagerStub(db_path))

    import_file = tmp_path / "items.txt"
    lines = [f"C{i:03d}|Item {i}|92.50|WT|10.00\n" for i in range(1, 121)]
    import_file.write_text("".join(lines), encoding="utf-8")

    finished = []
    manager.import_finished.connect(
        lambda success, total, err: finished.append((success, total, err))
    )
    manager.progress_updated.connect(
        lambda current, total: manager.cancel_import() if current >= 10 else None
    )

    manager.import_from_file(str(import_file), _default_import_settings())

    assert finished
    imported_count, processed_count, error_message = finished[-1]
    assert error_message == "Import Cancelled"
    assert processed_count < 120
    assert imported_count <= processed_count

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        conn.close()
    assert rows < 120


def test_import_skips_rows_that_violate_item_domain_rules(qt_app, tmp_path):
    db_path = tmp_path / "import.sqlite"
    _create_items_db(db_path)
    manager = ItemImportManager(_DbManagerStub(db_path))

    import_file = tmp_path / "items_invalid.txt"
    import_file.write_text("X001|Invalid Purity|101.0|WT|10.0\n", encoding="utf-8")

    finished = []
    manager.import_finished.connect(
        lambda success, total, err: finished.append((success, total, err))
    )
    manager.import_from_file(str(import_file), _default_import_settings())

    assert finished
    imported_count, total_count, error_message = finished[-1]
    assert imported_count == 0
    assert total_count == 1
    assert error_message in (None, "")

    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    finally:
        conn.close()
    assert rows == 0


def test_import_emits_summary_for_insert_update_skip_and_errors(qt_app, tmp_path):
    db_path = tmp_path / "import.sqlite"
    _create_items_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
            ("U001", "Original", 90.0, "WT", 5.0),
        )
        conn.commit()
    finally:
        conn.close()

    manager = ItemImportManager(_DbManagerStub(db_path))
    import_file = tmp_path / "items_mixed.txt"
    import_file.write_text(
        (
            "N001|New Item|92.5|WT|10.0\n"
            "U001|Updated Name|95.0|WT|15.0\n"
            "U001|Skip Me|95.0|WT|15.0\n"
            "B001|Bad Purity|101.0|WT|10.0\n"
        ),
        encoding="utf-8",
    )

    settings = _default_import_settings()
    settings["duplicate_mode"] = 1  # UPDATE
    summaries = []
    finished = []
    manager.import_summary_updated.connect(
        lambda summary: summaries.append(dict(summary))
    )
    manager.import_finished.connect(
        lambda success, total, err: finished.append((success, total, err))
    )
    manager.import_from_file(str(import_file), settings)

    assert summaries
    summary = summaries[-1]
    assert summary["inserted"] == 1
    assert summary["updated"] == 2
    assert summary["skipped"] == 0
    assert summary["errors"] == 1
    assert finished[-1][0] == 3
    assert finished[-1][1] == 4
    assert finished[-1][2] in ("", None)


def test_import_emits_skipped_summary_in_skip_mode(qt_app, tmp_path):
    db_path = tmp_path / "import.sqlite"
    _create_items_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
            ("S001", "Existing", 90.0, "WT", 5.0),
        )
        conn.commit()
    finally:
        conn.close()

    manager = ItemImportManager(_DbManagerStub(db_path))
    import_file = tmp_path / "items_skip.txt"
    import_file.write_text("S001|Existing Updated|90.0|WT|8.0\n", encoding="utf-8")

    settings = _default_import_settings()
    settings["duplicate_mode"] = 0  # SKIP
    summaries = []
    finished = []
    manager.import_summary_updated.connect(
        lambda summary: summaries.append(dict(summary))
    )
    manager.import_finished.connect(
        lambda success, total, err: finished.append((success, total, err))
    )
    manager.import_from_file(str(import_file), settings)

    assert summaries
    summary = summaries[-1]
    assert summary["inserted"] == 0
    assert summary["updated"] == 0
    assert summary["skipped"] == 1
    assert summary["errors"] == 0
    assert finished[-1][0] == 1
    assert finished[-1][1] == 1
    assert finished[-1][2] in ("", None)


def test_import_tracks_duplicates_created_within_same_file(qt_app, tmp_path):
    db_path = tmp_path / "import.sqlite"
    _create_items_db(db_path)
    manager = ItemImportManager(_DbManagerStub(db_path))

    import_file = tmp_path / "items_repeated.txt"
    import_file.write_text(
        (
            "N900|New Item|92.5|WT|10.0\n"
            "N900|New Item Updated|93.0|WT|12.0\n"
        ),
        encoding="utf-8",
    )

    settings = _default_import_settings()
    settings["duplicate_mode"] = 1  # UPDATE
    summaries = []
    finished = []
    manager.import_summary_updated.connect(
        lambda summary: summaries.append(dict(summary))
    )
    manager.import_finished.connect(
        lambda success, total, err: finished.append((success, total, err))
    )
    manager.import_from_file(str(import_file), settings)

    assert summaries[-1] == {
        "inserted": 1,
        "updated": 1,
        "skipped": 0,
        "errors": 0,
    }
    assert finished[-1] == (2, 2, "")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT name, purity, wage_rate FROM items WHERE code = ?",
            ("N900",),
        ).fetchone()
    finally:
        conn.close()

    assert row == ("New Item Updated", 93.0, 12.0)
