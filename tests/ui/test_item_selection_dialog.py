import pytest
from PyQt5.QtCore import QItemSelectionModel, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QDialog

from silverestimate.ui.item_selection_dialog import ItemSelectionDialog


class _FakeDb:
    def __init__(self, items):
        self._items = list(items)
        self.calls = []

    def search_items_for_selection(self, search_term, limit=500):
        self.calls.append((search_term, limit))
        query = (search_term or "").strip().upper()
        if not query:
            rows = sorted(self._items, key=lambda row: str(row["code"]).upper())
        else:
            scored = []
            for row in self._items:
                code = str(row.get("code", "")).upper()
                name = str(row.get("name", "")).upper()
                if code.startswith(query):
                    rank = 0
                elif name.startswith(query):
                    rank = 1
                elif query in code:
                    rank = 2
                elif query in name:
                    rank = 3
                else:
                    continue
                scored.append((rank, code, row))
            scored.sort(key=lambda entry: (entry[0], entry[1]))
            rows = [entry[2] for entry in scored]
        truncated = len(rows) > int(limit)
        return rows[: int(limit)], truncated


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


def _visible_codes(dialog):
    return [
        dialog.items_model.data(dialog.items_model.index(row, 0), Qt.DisplayRole)
        for row in range(dialog.items_model.rowCount())
    ]


def _select_row(dialog, row):
    index = dialog.items_model.index(row, 0)
    dialog.items_table.setCurrentIndex(index)
    dialog.items_table.selectionModel().select(
        index,
        QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
    )


def test_opens_prefilled_and_focuses_search(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="ad")
    assert dialog.search_edit.text() == "ad"
    dialog._focus_search()
    assert dialog.search_edit.selectedText().lower() == "ad"


def test_ranking_prefers_prefix_then_contains(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    codes = _visible_codes(dialog)
    assert codes == ["AD01", "ZZ10", "AXAD", "BAD2"]


def test_empty_search_shows_all_sorted_by_code(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="")
    codes = _visible_codes(dialog)
    assert codes == sorted(codes)
    assert dialog.result_count_label.text() == "4 matches"


def test_no_match_state_is_visible_and_select_disabled(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="NOTHING")
    assert dialog.items_model.rowCount() == 0
    assert dialog.empty_label.isVisible()
    assert dialog.select_button.isEnabled() is False


def test_enter_in_search_accepts_first_visible_match(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.search_edit.setFocus()
    QTest.keyClick(dialog.search_edit, Qt.Key_Return)

    qtbot.waitUntil(lambda: dialog.result() == QDialog.Accepted, timeout=1000)
    picked = dialog.get_selected_item()
    assert picked is not None
    assert picked["code"] == "AD01"


def test_double_click_accepts_and_returns_payload(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    _select_row(dialog, 1)
    dialog.items_table.doubleClicked.emit(dialog.items_model.index(1, 0))

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
    _select_row(dialog, 2)

    qtbot.waitUntil(lambda: dialog.detail_code.text() == "AXAD", timeout=1000)
    assert dialog.detail_name.text() == "Roadline Anklet"
    assert dialog.detail_purity.text() == "80.00"
    assert dialog.detail_wage_type.text() == "WT"
    assert dialog.detail_wage_rate.text() == "9.75"


def test_down_arrow_in_search_moves_focus_to_results(qtbot, sample_items):
    dialog = _make_dialog(qtbot, sample_items, term="AD")
    dialog.search_edit.setFocus()
    QTest.keyClick(dialog.search_edit, Qt.Key_Down)

    qtbot.waitUntil(
        lambda: dialog.items_table.currentIndex().row() >= 0,
        timeout=1000,
    )


def test_fast_search_provider_limits_visible_rows(qtbot):
    items = [
        {
            "code": f"C{i:04d}",
            "name": f"Item {i:04d}",
            "purity": 90.0,
            "wage_type": "WT",
            "wage_rate": 10.0,
        }
        for i in range(520)
    ]
    db = _FakeDb(items)
    dialog = ItemSelectionDialog(db, "")
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitUntil(lambda: dialog.isVisible(), timeout=1000)

    assert dialog.items_model.rowCount() == 500
    assert dialog.result_count_label.text() == "500+ matches"
    assert "Showing top 500 matches" in dialog.hint_label.text()
    assert db.calls


def test_requires_selection_search_provider():
    class _MissingSearchDb:
        pass

    with pytest.raises(AttributeError):
        ItemSelectionDialog(_MissingSearchDb(), "")
