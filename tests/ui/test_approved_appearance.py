"""Behavioral checks for the approved presentation changes."""

import sqlite3
import types

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox, QTableView

from silverestimate.infrastructure.settings import SettingsKey, get_app_settings
from silverestimate.persistence.items_repository import fetch_item_catalog_page
from silverestimate.ui.estimate_deletion_dialog import confirm_estimate_deletion
from silverestimate.ui.item_master import ItemMasterWidget
from silverestimate.ui.models.silver_bar_table_models import (
    AvailableSilverBarsTableModel,
)
from silverestimate.ui.selection_check_header import SelectionCheckHeader
from silverestimate.ui.settings_dialog import SettingsDialog
from tests.ui.test_item_master import _StubDbManager
from tests.ui.test_settings_dialog import _make_main_window


def test_deletion_escape_cancels_and_the_action_caption_fits(qtbot, qt_app):
    def cancel():
        dialog = qt_app.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        button = dialog.button(QMessageBox.StandardButton.Yes)
        assert (
            button.fontMetrics().horizontalAdvance(button.text()) < button.width() - 20
        )
        assert dialog.defaultButton() is dialog.button(
            QMessageBox.StandardButton.Cancel
        )
        qtbot.keyClick(dialog, Qt.Key.Key_Escape)

    QTimer.singleShot(0, cancel)
    assert not confirm_estimate_deletion(None, "100")


def test_checkbox_selection_uses_the_transfer_selection_model(qtbot):
    table = QTableView()
    qtbot.addWidget(table)
    model = AvailableSilverBarsTableModel(table)
    model.set_rows([{"bar_id": 1}, {"bar_id": 2}])
    table.setModel(model)
    header = SelectionCheckHeader(table)
    header._toggle(1)
    assert [index.row() for index in table.selectionModel().selectedRows()] == [1]
    header._toggle(1)
    assert not table.selectionModel().hasSelection()
    table.selectRow(0)
    assert table.selectionModel().isRowSelected(0)


def test_catalog_cancel_keeps_edits_and_discard_restores_record(qtbot, monkeypatch):
    catalog = ItemMasterWidget(
        _StubDbManager(), types.SimpleNamespace(show_status_message=lambda *_: None)
    )
    qtbot.addWidget(catalog)
    catalog.items_table.selectRow(0)
    original = catalog.name_edit.text()
    original_code = catalog.code_edit.text()
    catalog.name_edit.setText("Changed name")
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Cancel
    )
    catalog.items_table.selectRow(1)
    assert catalog.code_edit.text() == original_code
    assert catalog.name_edit.text() == "Changed name"
    assert not catalog.confirm_discard_edits()
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Discard
    )
    assert catalog.confirm_discard_edits()
    assert catalog.name_edit.text() == original
    assert not catalog.dirty_label.text()


def test_tunch_search_retains_keyset_pagination():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE items(code, name, tunch, purity, wage_type, wage_rate)"
    )
    connection.executemany(
        "INSERT INTO items VALUES(?, 'Ring', '92.5 + loss', 92.5, 'WT', 10)",
        [("A",), ("B",)],
    )
    first = fetch_item_catalog_page(connection.cursor(), "loss", limit=1)
    second = fetch_item_catalog_page(
        connection.cursor(), "loss", limit=1, page_cursor=first.next_cursor
    )
    assert first.total == 2 and [row["code"] for row in first.items] == ["A"]
    assert [row["code"] for row in second.items] == ["B"]
    assert second.next_cursor is None
    connection.close()


def test_preview_changes_are_staged_and_footer_buttons_work(
    qtbot, settings_stub, monkeypatch
):
    estimate = types.SimpleNamespace(
        apply_table_font_size=lambda _: True,
        apply_breakdown_font_size=lambda _: True,
        apply_final_calc_font_size=lambda _: True,
        apply_totals_position=lambda _: True,
    )
    dialog = SettingsDialog(_make_main_window(estimate))
    qtbot.addWidget(dialog)
    dialog.resize(1366, 768)
    dialog.show()
    settings = get_app_settings()
    before = settings.get_int(SettingsKey.UI_TABLE_FONT_SIZE, 11)
    page = dialog.appearance_page
    page.table_font_size_spin.setValue(13)
    page.density_combo.setCurrentIndex(1)
    page.alternating_checkbox.setChecked(False)
    assert page.preview_table.font().pointSize() == 13
    assert not page.preview_table.alternatingRowColors()
    assert settings.get_int(SettingsKey.UI_TABLE_FONT_SIZE, 11) == before
    calls = []
    monkeypatch.setattr(dialog, "apply_settings", lambda: calls.append("saved") or True)
    save = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    cancel = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
    apply = dialog.buttonBox.button(QDialogButtonBox.StandardButton.Apply)
    assert (
        cancel.mapTo(dialog, cancel.rect().topLeft()).x()
        < apply.mapTo(dialog, apply.rect().topLeft()).x()
        < save.mapTo(dialog, save.rect().topLeft()).x()
    )
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert calls == ["saved"]
    assert dialog.result() == dialog.DialogCode.Accepted
