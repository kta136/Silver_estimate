import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QDialog

from silverestimate.ui.item_selection_dialog import ItemSelectionDialog


class _FakeDb:
    def __init__(self, items):
        self._items = items

    def get_all_items(self):
        return list(self._items)


@pytest.fixture()
def sample_items():
    return [
        {
            "code": "BAD2",
            "name": "Metal Ring",
            "purity": 75.0,
            "wage_type": "WT",
            "wage_rate": 20.0,
        },
        {
            "code": "AD01",
            "name": "Classic Chain",
            "purity": 91.5,
            "wage_type": "WT",
            "wage_rate": 12.5,
        },
        {
            "code": "ZZ10",
            "name": "Adorn Pendant",
            "purity": 88.0,
            "wage_type": "PC",
            "wage_rate": 3.0,
        },
        {
            "code": "AXAD",
            "name": "Roadline Anklet",
            "purity": 80.0,
            "wage_type": "WT",
            "wage_rate": 9.75,
        },
    ]


def _make_dialog(qt_app, items, term="AD"):
    dialog = ItemSelectionDialog(_FakeDb(items), term)
    dialog.show()
    QTest.qWait(30)
    qt_app.processEvents()
    return dialog


def test_opens_prefilled_and_focuses_search(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="ad")
    try:
        assert dialog.search_edit.text() == "ad"
        assert dialog.search_edit.hasFocus()
    finally:
        dialog.close()
        dialog.deleteLater()


def test_ranking_prefers_prefix_then_contains(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="AD")
    try:
        codes = [dialog.items_table.item(row, 0).text() for row in range(dialog.items_table.rowCount())]
        assert codes == ["AD01", "ZZ10", "AXAD", "BAD2"]
    finally:
        dialog.close()
        dialog.deleteLater()


def test_empty_search_shows_all_sorted_by_code(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="")
    try:
        codes = [dialog.items_table.item(row, 0).text() for row in range(dialog.items_table.rowCount())]
        assert codes == sorted(codes)
        assert dialog.result_count_label.text() == "4 matches"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_no_match_state_is_visible_and_select_disabled(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="NOTHING")
    try:
        assert dialog.items_table.rowCount() == 0
        assert dialog.empty_label.isVisible()
        assert dialog.select_button.isEnabled() is False
    finally:
        dialog.close()
        dialog.deleteLater()


def test_enter_in_search_accepts_first_visible_match(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="AD")
    try:
        dialog.search_edit.setFocus()
        QTest.qWait(10)
        QTest.keyClick(dialog.search_edit, Qt.Key_Return)
        QTest.qWait(10)

        assert dialog.result() == QDialog.Accepted
        picked = dialog.get_selected_item()
        assert picked is not None
        assert picked["code"] == "AD01"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_double_click_accepts_and_returns_payload(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="AD")
    try:
        dialog.items_table.selectRow(1)
        dialog.items_table.itemDoubleClicked.emit(dialog.items_table.item(1, 0))
        QTest.qWait(10)

        assert dialog.result() == QDialog.Accepted
        picked = dialog.get_selected_item()
        assert picked is not None
        assert set(picked.keys()) == {
            "code",
            "name",
            "purity",
            "wage_type",
            "wage_rate",
        }
        assert picked["code"] == "ZZ10"
        assert picked["wage_type"] == "PC"
        assert isinstance(picked["purity"], float)
        assert isinstance(picked["wage_rate"], float)
    finally:
        dialog.close()
        dialog.deleteLater()


def test_selection_updates_detail_panel(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="AD")
    try:
        dialog.items_table.selectRow(2)
        QTest.qWait(10)

        assert dialog.detail_code.text() == "AXAD"
        assert dialog.detail_name.text() == "Roadline Anklet"
        assert dialog.detail_purity.text() == "80.00"
        assert dialog.detail_wage_type.text() == "WT"
        assert dialog.detail_wage_rate.text() == "9.75"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_down_arrow_in_search_moves_focus_to_results(qt_app, sample_items):
    dialog = _make_dialog(qt_app, sample_items, term="AD")
    try:
        dialog.search_edit.setFocus()
        QTest.qWait(10)
        QTest.keyClick(dialog.search_edit, Qt.Key_Down)
        QTest.qWait(10)

        assert dialog.items_table.hasFocus()
        assert dialog.items_table.currentRow() >= 0
    finally:
        dialog.close()
        dialog.deleteLater()
