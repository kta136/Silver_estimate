import sqlite3
import types

from PyQt5.QtCore import QItemSelectionModel

from silverestimate.ui.item_master import ItemMasterWidget


class _StubDbManager:
    def __init__(self):
        self._rows = [
            {
                "code": "ITM001",
                "name": "Ring",
                "purity": 92.5,
                "wage_type": "WT",
                "wage_rate": 10.0,
            },
            {
                "code": "ITM002",
                "name": "Anklet",
                "purity": 80.0,
                "wage_type": "PC",
                "wage_rate": 5.0,
            },
        ]
        self.search_calls = []

    def get_all_items(self):
        return list(self._rows)

    def search_items(self, term):
        self.search_calls.append(term)
        normalized = (term or "").strip().lower()
        return [
            row
            for row in self._rows
            if normalized in row["code"].lower() or normalized in row["name"].lower()
        ]

    def get_item_by_code(self, code):
        for row in self._rows:
            if row["code"] == code:
                return dict(row)
        return None

    def add_item(self, *args, **kwargs):
        del args, kwargs
        return True

    def update_item(self, *args, **kwargs):
        del args, kwargs
        return True

    def delete_item(self, *args, **kwargs):
        del args, kwargs
        return True


def test_item_master_selection_populates_form_and_clear_resets(qtbot):
    db = _StubDbManager()
    main_window = types.SimpleNamespace(show_status_message=lambda *_args: None)
    widget = ItemMasterWidget(db, main_window)
    qtbot.addWidget(widget)
    try:
        assert widget.items_model.rowCount() == 2

        target_row = next(
            row
            for row in range(widget.items_model.rowCount())
            if widget.items_model.row_payload(row)["code"] == "ITM002"
        )
        index = widget.items_model.index(target_row, 0)
        widget.items_table.setCurrentIndex(index)
        widget.items_table.selectionModel().select(
            index,
            QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
        )
        widget.on_item_selected()

        assert widget.name_edit.text() == "Anklet"
        assert widget.purity_edit.text() == "80.0"
        assert widget.wage_type_combo.currentText() == "PC"
        assert widget.wage_rate_edit.text() == "5.0"
        assert widget.update_button.isEnabled() is True
        assert widget.add_button.isEnabled() is False

        widget.clear_form()

        assert widget.code_edit.text() == ""
        assert widget.update_button.isEnabled() is False
        assert widget.delete_button.isEnabled() is False
        assert widget.add_button.isEnabled() is True
        assert widget.items_table.selectionModel().hasSelection() is False
    finally:
        widget.deleteLater()


def test_item_master_search_reloads_table_model(qtbot):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    try:
        widget.search_edit.setText("ank")
        widget.search_items()

        assert db.search_calls == ["ank"]
        assert widget.items_model.rowCount() == 1
        assert widget.items_model.row_payload(0)["code"] == "ITM002"
    finally:
        widget.deleteLater()


def test_item_master_async_snapshot_load_populates_rows(qtbot, tmp_path):
    db_path = tmp_path / "items.sqlite"
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE items (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                purity REAL DEFAULT 0,
                wage_type TEXT DEFAULT 'WT',
                wage_rate REAL DEFAULT 0
            )
            """
        )
        conn.executemany(
            "INSERT INTO items (code, name, purity, wage_type, wage_rate) VALUES (?, ?, ?, ?, ?)",
            [
                ("ITM001", "Ring", 92.5, "WT", 10.0),
                ("ITM002", "Anklet", 80.0, "PC", 5.0),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    db = _StubDbManager()
    db.temp_db_path = str(db_path)

    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    try:
        qtbot.waitUntil(lambda: widget.items_model.rowCount() == 2, timeout=2000)
        assert {widget.items_model.row_payload(i)["code"] for i in range(2)} == {
            "ITM001",
            "ITM002",
        }
    finally:
        widget.close()
        widget.deleteLater()


def test_item_master_ignores_stale_async_results(qtbot):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    try:
        original_codes = [
            widget.items_model.row_payload(row)["code"]
            for row in range(widget.items_model.rowCount())
        ]
        widget._load_request_id = 2
        widget._load_request_meta = {1: (0.0, "old"), 2: (0.0, "new")}

        widget._handle_async_load_result(
            1,
            [
                {
                    "code": "OLD001",
                    "name": "Old",
                    "purity": 90.0,
                    "wage_type": "WT",
                    "wage_rate": 10.0,
                }
            ],
        )

        assert [
            widget.items_model.row_payload(row)["code"]
            for row in range(widget.items_model.rowCount())
        ] == original_codes
    finally:
        widget.deleteLater()
