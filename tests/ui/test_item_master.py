import types

from PySide6.QtCore import QItemSelectionModel, Qt

from silverestimate.ui.application_theme import apply_light_application_theme
from silverestimate.ui.item_master import ItemMasterWidget
from tests.smoke.test_full_startup_smoke import _configure_smoke_font


class _StubDbManager:
    def __init__(self):
        self._rows = [
            {
                "code": "ITM001",
                "name": "Ring",
                "tunch": None,
                "purity": 92.5,
                "wage_type": "WT",
                "wage_rate": 10.0,
            },
            {
                "code": "ITM002",
                "name": "Anklet",
                "tunch": "87 + loss",
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
        assert widget._form_panel.minimumWidth() == 280
        assert widget._form_panel.maximumWidth() == 340
        assert widget._item_count_label.minimumWidth() >= 96
        assert "QComboBox QAbstractItemView" in widget.styleSheet()

        target_row = next(
            row
            for row in range(widget.items_model.rowCount())
            if widget.items_model.row_payload(row)["code"] == "ITM002"
        )
        index = widget.items_model.index(target_row, 0)
        widget.items_table.setCurrentIndex(index)
        widget.items_table.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        widget.on_item_selected()

        assert widget.name_edit.text() == "Anklet"
        assert widget.tunch_edit.text() == "87 + loss"
        assert widget.tunch_edit.validator() is None
        # Two decimals, like the table and the estimate screen.
        assert widget.purity_edit.text() == "80.00"
        assert widget.wage_type_combo.currentData() == "PC"
        assert widget.wage_rate_edit.text() == "5.00"
        assert widget.update_button.isHidden() is False
        assert widget.add_button.isHidden() is True
        assert widget.delete_button.isHidden() is False

        widget.clear_form()

        assert widget.code_edit.text() == ""
        assert widget.tunch_edit.text() == ""
        assert widget.update_button.isHidden() is True
        assert widget.delete_button.isEnabled() is False
        # Nothing to delete while a new item is being typed.
        assert widget.delete_button.isHidden() is True
        assert widget.add_button.isHidden() is False
        # Most items are charged per gram, so that is the default.
        assert widget.wage_type_combo.currentData() == "WT"
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


def test_item_master_accepts_numeric_and_text_tunch_above_100(qtbot, monkeypatch):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    saved = []
    monkeypatch.setattr(
        db, "add_item", lambda *args, **kwargs: saved.append((args, kwargs)) or True
    )
    widget.code_edit.setText("HIGH")
    widget.name_edit.setText("High Tunch")
    widget.tunch_edit.setText("125.50% + loss")
    qtbot.keyClicks(widget.purity_edit, "125.50")
    assert widget.purity_edit.text() == "125.50"
    assert widget.purity_edit.hasAcceptableInput()

    widget.add_item()

    assert len(saved) == 1
    assert saved[0][0][2] == 125.5
    assert saved[0][1]["tunch"] == "125.50% + loss"


def test_item_master_explains_a_mistake_beside_the_form(qtbot, monkeypatch):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    widget.show()
    boxes = []
    monkeypatch.setattr(
        "silverestimate.ui.item_master.QMessageBox.warning",
        lambda *args: boxes.append(args),
    )
    try:
        widget.code_edit.setText("NEW01")
        widget.add_item()

        # No message box: the form says what is missing and focuses the field.
        assert boxes == []
        assert widget.form_error_label.isVisible()
        assert widget.form_error_label.text() == "Item name is required."
        assert widget.focusWidget() is widget.name_edit

        widget.name_edit.setText("Ring")
        widget.name_edit.textEdited.emit("Ring")
        assert not widget.form_error_label.isVisible()

        widget.code_edit.setText("ITM002")
        widget.add_item()
        assert "already in use" in widget.form_error_label.text()
        assert "Update" not in widget.form_error_label.text()
        assert widget.focusWidget() is widget.code_edit
    finally:
        # Leave nothing unsaved, so closing the widget asks no question.
        widget._clean_form = widget._form_values()
        widget.deleteLater()


def test_item_master_count_reads_naturally(qtbot):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    try:
        assert widget._item_count_label.text() == "2 items"
        widget.search_edit.setText("ank")
        widget.search_items()
        assert widget._item_count_label.text() == "1 match"
        widget.search_edit.setText("zzzz")
        widget.search_items()
        assert widget._item_count_label.text() == "No matches"
    finally:
        widget.deleteLater()


def test_item_master_delete_names_the_action(qtbot, confirmations):
    db = _StubDbManager()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)
    try:
        widget.items_table.selectRow(0)
        code = widget.code_edit.text()
        confirmations.answer("Cancel")
        widget.delete_item()
        assert confirmations.shown == [f"Delete Item: <b>Delete item {code}?</b>"]
        assert widget.code_edit.text() == code
    finally:
        widget.deleteLater()


def test_item_master_lists_codes_from_a_to_z(qtbot):
    db = _StubDbManager()
    db._rows.reverse()
    widget = ItemMasterWidget(db)
    qtbot.addWidget(widget)

    header = widget.items_table.horizontalHeader()
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == Qt.SortOrder.AscendingOrder
    codes = [
        widget.items_model.row_payload(row)["code"]
        for row in range(widget.items_model.rowCount())
    ]
    assert codes == ["ITM001", "ITM002"]


def test_item_master_marks_the_field_and_keeps_its_buttons_in_place(qtbot):
    widget = ItemMasterWidget(_StubDbManager())
    qtbot.addWidget(widget)
    widget.show()
    try:
        layout = widget._form_panel.layout()
        # What to fix is said above the buttons, so they never move.
        buttons = widget._form_buttons
        assert layout.indexOf(widget.form_error_label) < layout.indexOf(buttons)
        assert layout.indexOf(widget.dirty_label) < layout.indexOf(buttons)
        # Nothing typed yet: no empty line holds the buttons apart.
        assert not widget.dirty_label.isVisible()

        widget.code_edit.setText("NEW01")
        widget.add_item()
        assert widget.name_edit.property("invalid") == "true"
        assert widget.code_edit.property("invalid") == "false"

        widget.name_edit.setText("Ring")
        widget.name_edit.textEdited.emit("Ring")
        assert widget.name_edit.property("invalid") == "false"
        assert widget.dirty_label.isVisible()
    finally:
        widget._clean_form = widget._form_values()
        widget.deleteLater()


def test_item_master_unsaved_prompt_keeps_edits_on_cancel_and_restores_on_discard(
    qtbot, confirmations
):
    widget = ItemMasterWidget(
        _StubDbManager(), types.SimpleNamespace(show_status_message=lambda *_: None)
    )
    qtbot.addWidget(widget)
    widget.items_table.selectRow(0)
    original = widget.name_edit.text()
    original_code = widget.code_edit.text()
    widget.name_edit.setText("Changed")

    confirmations.always("Cancel")
    widget.items_table.selectRow(1)
    assert widget.code_edit.text() == original_code
    assert widget.name_edit.text() == "Changed"
    assert not widget.confirm_discard_edits()
    assert widget.name_edit.text() == "Changed"

    confirmations.always("Discard")
    assert widget.confirm_discard_edits()
    assert widget.name_edit.text() == original
    assert not widget.dirty_label.text()
    assert confirmations.shown[-1].startswith("Unsaved Item Changes")


def test_a_long_item_name_shows_its_start_in_the_form(qtbot):
    long_name = "Very Long Descriptive Jewellery Item Name Number 7 With Extra Words"
    db = _StubDbManager()
    db._rows[0]["name"] = long_name
    main_window = types.SimpleNamespace(show_status_message=lambda *_args: None)
    widget = ItemMasterWidget(db, main_window)
    qtbot.addWidget(widget)
    widget.resize(1280, 640)
    widget.show()
    try:
        index = widget.items_model.index(0, 0)
        widget.items_table.setCurrentIndex(index)
        widget.items_table.selectionModel().select(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect
            | QItemSelectionModel.SelectionFlag.Rows,
        )
        widget.on_item_selected()

        assert widget.name_edit.text() == long_name
        # setText leaves the cursor at the end, so only the tail would show.
        assert widget.name_edit.cursorPosition() == 0
    finally:
        widget.deleteLater()


def test_the_form_fits_a_1280x720_screen_without_scrolling(qtbot, qt_application_state):
    _configure_smoke_font(qt_application_state)
    apply_light_application_theme(qt_application_state)
    widget = ItemMasterWidget(
        _StubDbManager(),
        types.SimpleNamespace(show_status_message=lambda *_args: None),
    )
    qtbot.addWidget(widget)
    # Offscreen the menu bar is inside the window; on Windows it is in the
    # title bar, so this is a little stricter than the real thing.
    widget.resize(1280, 629)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    index = widget.items_model.index(0, 0)
    widget.items_table.setCurrentIndex(index)
    widget.items_table.selectionModel().select(
        index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect
        | QItemSelectionModel.SelectionFlag.Rows,
    )
    widget.on_item_selected()
    qtbot.wait(60)

    form_scroll = widget._form_panel.parentWidget().parentWidget()
    assert not form_scroll.verticalScrollBar().isVisible()
    assert widget.update_button.isVisible()
    assert widget.delete_button.isVisible()
    bottom = widget.delete_button.mapTo(
        widget, widget.delete_button.rect().bottomLeft()
    )
    assert bottom.y() < widget.height()
    # Save and Cancel are one row, so the primary action stays beside Cancel.
    assert widget.update_button.geometry().y() == widget.clear_button.geometry().y()
    assert (
        widget.update_button.geometry().right() < widget.clear_button.geometry().left()
    )
