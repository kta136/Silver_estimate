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
