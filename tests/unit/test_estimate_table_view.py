"""Tests for EstimateTableView component."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMenu

from silverestimate.domain.estimate_entry import EstimateEntryRowState
from silverestimate.ui.estimate_entry_components import (
    estimate_table_view as view_module,
)
from silverestimate.ui.estimate_entry_components.estimate_table_view import (
    EstimateTableView,
)
from silverestimate.ui.estimate_entry_logic.constants import COL_GROSS


@pytest.fixture
def table_view(qtbot):
    """Create a fresh EstimateTableView for testing."""
    widget = EstimateTableView()
    qtbot.addWidget(widget)
    return widget


def test_initial_state(table_view):
    """Test that table view initializes correctly."""
    model = table_view.get_model()
    assert model is not None
    assert model.rowCount() == 0
    assert model.columnCount() == 11


def test_row_helpers_delegate_to_the_model(table_view):
    """The row helpers pass straight through; the model tests cover the rules."""
    model = table_view.get_model()

    assert table_view.add_row() == 0
    assert table_view.add_row(EstimateEntryRowState(code="A", name="Item A")) == 1
    assert model.rowCount() == 2
    assert table_view.get_row(1).name == "Item A"

    assert table_view.set_row(0, EstimateEntryRowState(code="UPDATED", gross=500.0))
    assert [row.code for row in table_view.get_all_rows()] == ["UPDATED", "A"]

    assert table_view.delete_row(0) is True
    assert [row.code for row in table_view.get_all_rows()] == ["A"]

    table_view.set_all_rows(
        [EstimateEntryRowState(code=code) for code in ("X", "Y", "Z")]
    )
    assert [row.code for row in table_view.get_all_rows()] == ["X", "Y", "Z"]

    table_view.clear_rows()
    assert model.rowCount() == 0


def test_set_current_cell(table_view):
    """Test focusing on a specific cell."""
    table_view.add_row()
    table_view.setCurrentCell(0, 0)

    assert table_view.get_current_row() == 0
    assert table_view.currentIndex().column() == 0


def test_display_and_edit_accessors_use_different_roles(table_view):
    table_view.add_row(EstimateEntryRowState(gross=1234567.5))

    assert table_view.get_cell_text(0, COL_GROSS) == "12,34,567.50"
    assert table_view.get_cell_display_text(0, COL_GROSS) == "12,34,567.50"
    assert table_view.get_cell_edit_value(0, COL_GROSS) == 1234567.5
    assert table_view.get_cell_edit_text(0, COL_GROSS) == "1234567.5"


def test_get_current_row_when_empty(table_view):
    """Test getting current row when no row is selected."""
    assert table_view.get_current_row() == -1


def test_row_deleted_signal(table_view):
    """Test that row deletion emits signal."""
    table_view.add_row()
    table_view.add_row()

    deleted_rows = []
    table_view.row_deleted.connect(lambda r: deleted_rows.append(r))

    # Select first row and trigger delete
    table_view.selectRow(0)
    table_view._delete_current_row()

    assert len(deleted_rows) == 1
    assert deleted_rows[0] == 0


def test_cell_edited_signal(table_view):
    """Test that cell edits emit signal."""
    table_view.add_row()

    edits = []
    table_view.cell_edited.connect(lambda r, c: edits.append((r, c)))

    # Edit a cell through the model
    model = table_view.get_model()
    index = model.index(0, 0)
    model.setData(index, "TEST", 2)  # Qt.ItemDataRole.EditRole = 2

    assert len(edits) > 0
    assert edits[0] == (0, 0)


def test_page_keys_navigate_visible_rows_even_from_cell_editor(qtbot, table_view):
    for row in range(30):
        table_view.add_row(
            EstimateEntryRowState(code=f"ROW{row:02d}", name=f"Item {row}")
        )
    table_view.resize(640, 180)
    qtbot.addWidget(table_view)
    table_view.show()
    table_view.setCurrentIndex(table_view.model().index(0, 0))
    table_view.edit(table_view.currentIndex())
    qtbot.waitUntil(lambda: table_view.focusWidget() is not None)

    QTest.keyClick(
        table_view.focusWidget(),
        Qt.Key.Key_PageDown,
        Qt.KeyboardModifier.NoModifier,
    )

    assert table_view.currentIndex().row() >= 3

    QTest.keyClick(
        table_view.focusWidget(),
        Qt.Key.Key_PageUp,
        Qt.KeyboardModifier.NoModifier,
    )

    assert table_view.currentIndex().row() == 0


def test_context_menu_actions_have_icons(table_view, monkeypatch):
    captured = {}

    class _CapturingMenu(QMenu):
        def exec(self, *_args, **_kwargs):
            captured["actions"] = [
                (action.text(), action.icon()) for action in self.actions()
            ]

    monkeypatch.setattr(view_module, "QMenu", _CapturingMenu)

    table_view._show_context_menu(table_view.rect().center())

    # The names and shortcuts match the More menu and the menu bar.
    assert [text for text, _icon in captured["actions"] if text] == [
        "Delete Current Row\tCtrl+D",
        "Estimate History...\tCtrl+H",
        "Reset Column Layout",
    ]
    for text, icon in captured["actions"]:
        if text:
            assert not icon.isNull(), text


def test_selection_palette_matches_active_and_inactive_states(table_view):
    palette = table_view.palette()

    assert palette.color(QPalette.ColorRole.Highlight).name() == "#e0f2f3"
    assert palette.color(QPalette.ColorRole.HighlightedText).name() == "#0f172a"
    assert (
        palette.color(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Highlight).name()
        == "#e0f2f3"
    )
    assert (
        palette.color(
            QPalette.ColorGroup.Inactive, QPalette.ColorRole.HighlightedText
        ).name()
        == "#0f172a"
    )
