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


def _make_dialog(qtbot, items, term="AD"):
    dialog = ItemSelectionDialog(_FakeDb(items), term)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)
    return dialog


def test_opens_prefilled_and_focuses_search(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="ad")
    assert dialog.search_edit.text() == "ad"
    qtbot.waitUntil(lambda: dialog.search_edit.hasFocus(), timeout=1000)


def test_ranking_prefers_prefix_then_contains(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    codes = [
        dialog.items_table.item(row, 0).text()
        for row in range(dialog.items_table.rowCount())
    ]
    assert codes == ["AD01", "ZZ10", "AXAD", "BAD2"]


def test_empty_search_shows_all_sorted_by_code(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="")
    codes = [
        dialog.items_table.item(row, 0).text()
        for row in range(dialog.items_table.rowCount())
    ]
    assert codes == sorted(codes)
    assert dialog.result_count_label.text() == "4 matches"


def test_no_match_state_is_visible_and_select_disabled(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="NOTHING")
    assert dialog.items_table.rowCount() == 0
    assert dialog.empty_label.isVisible()
    assert dialog.select_button.isEnabled() is False


def test_enter_in_search_accepts_first_visible_match(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.search_edit.setFocus()
    qtbot.waitUntil(lambda: dialog.search_edit.hasFocus(), timeout=1000)
    QTest.keyClick(dialog.search_edit, Qt.Key_Return)

    qtbot.waitUntil(lambda: dialog.result() == QDialog.Accepted, timeout=1000)
    picked = dialog.get_selected_item()
    assert picked is not None
    assert picked["code"] == "AD01"


def test_double_click_accepts_and_returns_payload(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.items_table.selectRow(1)
    dialog.items_table.itemDoubleClicked.emit(dialog.items_table.item(1, 0))

    qtbot.waitUntil(lambda: dialog.result() == QDialog.Accepted, timeout=1000)
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


def test_selection_updates_detail_panel(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.items_table.selectRow(2)

    qtbot.waitUntil(lambda: dialog.detail_code.text() == "AXAD", timeout=1000)
    assert dialog.detail_name.text() == "Roadline Anklet"
    assert dialog.detail_purity.text() == "80.00"
    assert dialog.detail_wage_type.text() == "WT"
    assert dialog.detail_wage_rate.text() == "9.75"


def test_down_arrow_in_search_moves_focus_to_results(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.search_edit.setFocus()
    qtbot.waitUntil(lambda: dialog.search_edit.hasFocus(), timeout=1000)
    QTest.keyClick(dialog.search_edit, Qt.Key_Down)

    qtbot.waitUntil(
        lambda: dialog.items_table.hasFocus() and dialog.items_table.currentRow() >= 0,
        timeout=1000,
    )
