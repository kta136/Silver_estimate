"""Integration tests for EstimateEntryWidget real user workflows."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit

from silverestimate.domain.estimate_models import EstimateLineCategory
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_GROSS,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_RATE,
)


def _begin_inline_edit(qtbot, widget, row: int, column: int) -> QLineEdit:
    table = widget.item_table
    table.setCurrentCell(row, column)
    widget.current_row = row
    widget.current_column = column
    assert table.begin_cell_edit(row, column)
    qtbot.waitUntil(lambda: table.findChild(QLineEdit) is not None, timeout=1000)
    editor = table.findChild(QLineEdit)
    assert editor is not None
    return editor


# ============================================================================
# Adapter Layer Tests - Add Row Functionality
# ============================================================================


def test_adapter_reuses_empty_row_and_preserves_filled_rows(
    make_estimate_widget, qt_app, fake_db
):
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    adapter = widget.table_controller._get_table_adapter()
    table = widget.item_table

    adapter.add_empty_row()
    assert table.rowCount() == 1
    assert table.get_cell_text(0, COL_TYPE) == "Regular"

    adapter.add_empty_row()
    assert table.rowCount() == 1

    table.set_cell_text(0, COL_CODE, "CACHE1")
    adapter.add_empty_row()
    assert table.rowCount() == 2
    assert table.get_cell_text(0, COL_CODE) == "CACHE1"


# ============================================================================
# Adapter Layer Tests - Populate Row
# ============================================================================


def test_adapter_populate_row_pc_restores_one_after_wt_zero(
    make_estimate_widget, qt_app, fake_db
):
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    widget.table_controller._get_table_adapter().populate_row(
        0,
        {
            "code": "wt001",
            "name": "WT Item",
            "purity": 92.5,
            "wage_rate": 10.0,
            "wage_type": "WT",
        },
    )
    table = widget.item_table
    assert table.get_cell_text(0, COL_PIECES) == "0"
    index = table.model().index(0, COL_PIECES)
    assert not (table.model().flags(index) & Qt.ItemFlag.ItemIsEditable)

    widget.table_controller._get_table_adapter().populate_row(
        0,
        {
            "code": "pc001",
            "name": "PC Item",
            "purity": 92.5,
            "wage_rate": 10.0,
            "wage_type": "PC",
        },
    )
    table = widget.item_table
    assert table.get_cell_text(0, COL_PIECES) == "1"
    index = table.model().index(0, COL_PIECES)
    assert bool(table.model().flags(index) & Qt.ItemFlag.ItemIsEditable)


@pytest.mark.parametrize(
    "category",
    [EstimateLineCategory.RETURN, EstimateLineCategory.SILVER_BAR],
)
def test_adapter_populate_row_preserves_existing_row_type(
    make_estimate_widget, qt_app, fake_db, category
):
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    adapter = widget.table_controller._get_table_adapter()
    adapter.add_empty_row()
    table = widget.item_table
    table.set_row_category(0, category)

    adapter.populate_row(
        0,
        {
            "code": "updated",
            "name": "Updated Item Name",
            "purity": 92.5,
            "wage_rate": 10.0,
            "wage_type": "WT",
        },
    )

    assert table.get_cell_text(0, COL_TYPE) == category.display_name()
    assert table.get_row_state(0).category is category


# ============================================================================
# Model/View Architecture Tests
# ============================================================================


def test_cell_text_and_model_updates_round_trip(make_estimate_widget, qt_app, fake_db):
    """Edits through either API remain visible through the other."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()

    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "SYNC123")

    # Verify model was updated
    model = table.get_model()
    index = model.index(0, COL_CODE)
    model_data = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert model_data == "SYNC123", "Model should be updated"
    # Update model directly
    model.setData(index, "DIRECT123", Qt.ItemDataRole.EditRole)

    assert table.get_cell_text(0, COL_CODE) == "DIRECT123"


# ============================================================================
# Table Row Helper Tests
# ============================================================================


def test_append_empty_row_model_first_helper(make_estimate_widget, qt_app, fake_db):
    widget = make_estimate_widget(fake_db)
    table = widget.item_table
    initial_count = table.rowCount()
    table.append_empty_row()
    assert table.rowCount() == initial_count + 1


# ============================================================================
# Focus and Navigation Tests
# ============================================================================


def test_adapter_focus_on_empty_row(make_estimate_widget, qt_app, fake_db):
    """Test adapter.focus_on_empty_row() finds or creates empty row."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()

    # No rows - should create one
    widget.table_controller._get_table_adapter().focus_on_empty_row()
    assert widget.item_table.rowCount() == 1

    # Add code to first row
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "FILLED")

    # Should create new empty row
    widget.table_controller._get_table_adapter().focus_on_empty_row()
    assert table.rowCount() == 2


# ============================================================================
# Async/Timer Tests (Critical for catching delayed operations)
# ============================================================================


def test_widget_initialization_with_timers(make_estimate_widget, qtbot, fake_db):
    """Test that widget initialization completes including timer-delayed operations.

    This test catches issues with QTimer.singleShot operations like
    force_focus_to_first_cell() which are missed by synchronous tests.
    """
    widget = make_estimate_widget(fake_db)
    widget.show()
    qtbot.waitUntil(lambda: widget.item_table.rowCount() > 0, timeout=1500)
    qtbot.waitUntil(
        lambda: widget.item_table.findChild(QLineEdit) is not None,
        timeout=1500,
    )
    current_index = widget.item_table.currentIndex()
    assert current_index.isValid()
    assert current_index.column() == COL_CODE

    editor = widget.item_table.findChild(QLineEdit)
    assert editor is not None
    qtbot.keyClicks(editor, "AB12")
    assert editor.text() == "AB12"


def test_navigation_target_mapping_is_consistent(make_estimate_widget, qt_app, fake_db):
    """Test cursor navigation mapping helpers for deterministic movement."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    widget.item_table.set_cell_text(0, COL_CODE, "WT001")
    widget.table_controller._get_table_adapter().add_empty_row()
    widget.item_table.set_cell_text(1, COL_CODE, "PC001")
    model = widget.item_table.get_model()
    assert model.set_row_wage_type(0, "WT")
    assert model.set_row_wage_type(1, "PC")

    wt_row = 0
    pc_row = 1

    assert widget.table_controller._next_edit_target(wt_row, COL_WAGE_RATE) == (
        wt_row + 1,
        COL_CODE,
    )
    assert widget.table_controller._previous_edit_target(wt_row + 1, COL_CODE) == (
        wt_row,
        COL_WAGE_RATE,
    )

    row = pc_row
    assert widget.table_controller._next_edit_target(row, COL_CODE) == (
        row,
        COL_GROSS,
    )
    assert widget.table_controller._next_edit_target(row, COL_GROSS) == (
        row,
        COL_POLY,
    )
    assert widget.table_controller._next_edit_target(row, COL_POLY) == (
        row,
        COL_PURITY,
    )
    assert widget.table_controller._next_edit_target(row, COL_PURITY) == (
        row,
        COL_WAGE_RATE,
    )
    assert widget.table_controller._next_edit_target(row, COL_WAGE_RATE) == (
        row,
        COL_PIECES,
    )
    assert widget.table_controller._next_edit_target(row, COL_PIECES) == (
        row + 1,
        COL_CODE,
    )

    assert widget.table_controller._previous_edit_target(row, COL_PIECES) == (
        row,
        COL_WAGE_RATE,
    )
    assert widget.table_controller._previous_edit_target(row, COL_WAGE_RATE) == (
        row,
        COL_PURITY,
    )
    assert widget.table_controller._previous_edit_target(row, COL_PURITY) == (
        row,
        COL_POLY,
    )
    assert widget.table_controller._previous_edit_target(row, COL_POLY) == (
        row,
        COL_GROSS,
    )
    assert widget.table_controller._previous_edit_target(row, COL_GROSS) == (
        row,
        COL_CODE,
    )
    assert widget.table_controller._previous_edit_target(row, COL_CODE) == (
        row - 1,
        COL_WAGE_RATE,
    )
    assert widget.table_controller._previous_edit_target(0, COL_CODE) == (
        0,
        COL_CODE,
    )


def test_table_delegates_signal_navigation_requests(
    make_estimate_widget, qtbot, fake_db
):
    """Delegates should request navigation through explicit signals."""
    widget = make_estimate_widget(fake_db)
    widget.show()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW1")

    table.setCurrentCell(0, COL_GROSS)
    widget.current_row = 0
    widget.current_column = COL_GROSS
    numeric_delegate = table.itemDelegateForColumn(COL_GROSS)
    numeric_delegate.reverse_requested.emit()
    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_CODE
        ),
        timeout=1000,
    )

    table.setCurrentCell(0, COL_CODE)
    widget.current_row = 0
    widget.current_column = COL_CODE
    code_delegate = table.itemDelegateForColumn(COL_CODE)
    code_delegate.advance_requested.emit()
    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_GROSS
        ),
        timeout=1000,
    )


def test_add_empty_row_deferred_focus_is_safe_after_delete(
    make_estimate_widget, qt_app, fake_db, capsys
):
    """Test deferred focus timer does not crash when widget is deleted quickly."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    widget.close()
    qt_app.sendPostedEvents()
    qt_app.processEvents()

    captured = capsys.readouterr()
    assert (
        "wrapped C/C++ object of type EstimateEntryWidget has been deleted"
        not in captured.err
    )


def test_manual_row_selection_not_overridden_by_queued_auto_advance(
    make_estimate_widget, qtbot, fake_db
):
    """Manual row selection should win over delayed auto-advance from prior edit."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table

    # Prepare two rows with codes so navigation logic treats them as valid rows.
    table.set_cell_text(0, COL_CODE, "ROW0")
    widget.table_controller._get_table_adapter().add_empty_row()
    table.set_cell_text(1, COL_CODE, "ROW1")

    # Simulate an edit in row 1 that queues move_to_next_cell().
    widget.current_row = 1
    widget.current_column = COL_GROSS
    widget.table_controller.handle_cell_changed(1, COL_GROSS)

    # User manually moves to previous row before queued auto-advance fires.
    table.setCurrentCell(0, COL_CODE)
    widget.current_row = 0
    widget.current_column = COL_CODE

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_CODE
        ),
        timeout=1000,
    )


def test_manual_arrow_navigation_intent_blocks_queued_auto_advance(
    make_estimate_widget, qtbot, fake_db
):
    """Queued auto-advance must not override a user arrow-row navigation."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW0")
    widget.table_controller._get_table_adapter().add_empty_row()
    table.set_cell_text(1, COL_CODE, "ROW1")

    table.setCurrentCell(1, COL_GROSS)
    widget.current_row = 1
    widget.current_column = COL_GROSS
    widget.table_controller._schedule_auto_advance_from(1, COL_GROSS)

    # Mimic arrow-up intent arriving before deferred auto-advance executes.
    widget.table_controller._mark_manual_row_navigation()
    table.setCurrentCell(0, COL_GROSS)
    widget.current_row = 0
    widget.current_column = COL_GROSS

    qtbot.waitUntil(
        lambda: table.currentIndex().isValid() and table.currentIndex().row() == 0,
        timeout=1000,
    )
    current = table.currentIndex()
    # In CI (Windows/Py3.13), focus may settle on COL_CODE while preserving the
    # manual row-navigation intent. The critical behavior is that queued
    # auto-advance does not jump away from row 0.
    assert current.column() in (COL_GROSS, COL_CODE)


def test_row_change_marks_manual_nav_and_blocks_old_auto_advance(
    make_estimate_widget, qtbot, fake_db
):
    """Row switch via current-cell change should suppress queued auto-advance."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW0")
    widget.table_controller._get_table_adapter().add_empty_row()
    table.set_cell_text(1, COL_CODE, "ROW1")

    widget.current_row = 1
    widget.current_column = COL_GROSS
    widget.table_controller._schedule_auto_advance_from(1, COL_GROSS)

    # Simulate keyboard row navigation event path.
    widget.table_controller.current_cell_changed(0, COL_GROSS, 1, COL_GROSS)
    qtbot.waitUntil(
        lambda: (
            widget.current_row == 0 and widget.table_controller._manual_row_nav_recent()
        ),
        timeout=1000,
    )

    current = table.currentIndex()
    # current index can be invalid in headless mode; if valid it must remain on the upper row.
    assert (not current.isValid()) or (current.row() == 0)
    assert widget.current_row == 0
    assert widget.table_controller._manual_row_nav_recent()


def test_click_row_above_during_queued_advance_remains_stable(
    make_estimate_widget, qtbot, fake_db
):
    """Clicking an upper row should not trigger edit-loop churn."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW0")
    widget.table_controller._get_table_adapter().add_empty_row()
    table.set_cell_text(1, COL_CODE, "ROW1")

    # Trigger an edit change path that queues auto-advance.
    table.setCurrentCell(1, COL_GROSS)
    widget.current_row = 1
    widget.current_column = COL_GROSS
    widget.table_controller.handle_cell_changed(1, COL_GROSS)

    # User clicks row above immediately.
    widget.table_controller.cell_clicked(0, COL_CODE)
    table.setCurrentCell(0, COL_CODE)
    widget.current_row = 0
    widget.current_column = COL_CODE

    qtbot.waitUntil(
        lambda: table.currentIndex().isValid() and table.currentIndex().row() == 0,
        timeout=1500,
    )


def test_revisiting_row_with_same_code_preserves_manual_overrides(
    make_estimate_widget, qtbot, fake_db
):
    """Unchanged code commit must not reapply item-master defaults."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table

    lookup_calls = []
    master_item = {
        "code": "ITM1",
        "name": "Item Master Name",
        "purity": 91.6,
        "wage_rate": 10.0,
        "wage_type": "WT",
    }

    def _handle_item_code(row, code):
        lookup_calls.append((row, code))
        widget.populate_row(row, master_item)
        return True

    widget.presenter.handle_item_code = _handle_item_code

    # Initial lookup/populate from item master.
    table.set_cell_text(0, COL_CODE, "ITM1")
    qtbot.waitUntil(lambda: len(lookup_calls) >= 1, timeout=1000)
    initial_lookup_count = len(lookup_calls)

    # User manually overrides row values.
    table.set_cell_text(0, COL_PURITY, "95.5")
    table.set_cell_text(0, COL_WAGE_RATE, "22.0")
    assert table.get_cell_text(0, COL_PURITY) == "95.50"
    assert table.get_cell_text(0, COL_WAGE_RATE) == "22.00"

    # Revisit/commit same code value. Should be treated as no-op.
    code_index = table.get_model().index(0, COL_CODE)
    assert table.get_model().setData(code_index, "ITM1", Qt.ItemDataRole.EditRole)
    qtbot.wait(40)

    assert len(lookup_calls) == initial_lookup_count
    assert table.get_cell_text(0, COL_PURITY) == "95.50"
    assert table.get_cell_text(0, COL_WAGE_RATE) == "22.00"


# ============================================================================
# Keyboard Editing Regression Tests
# ============================================================================


def test_unchanged_purity_commit_still_advances_cursor(
    make_estimate_widget, qtbot, fake_db
):
    """Committing unchanged purity should still advance to wage-rate column."""
    widget = make_estimate_widget(fake_db)
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table

    table.set_cell_text(0, COL_CODE, "ROW1")
    table.set_cell_text(0, COL_PURITY, "91.6")

    table.setCurrentCell(0, COL_PURITY)
    widget.current_row = 0
    widget.current_column = COL_PURITY

    purity_index = table.get_model().index(0, COL_PURITY)
    assert table.get_model().setData(purity_index, 91.6, Qt.ItemDataRole.EditRole)

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_WAGE_RATE
        ),
        timeout=1000,
    )


def test_unchanged_code_enter_advances_to_gross_without_relookup(
    make_estimate_widget, qtbot, fake_db
):
    """Pressing Enter on an unchanged code should still advance the cursor."""
    widget = make_estimate_widget(fake_db)
    widget.show()
    lookup_calls = []

    def _handle_item_code(row, code):
        lookup_calls.append((row, code))
        return False

    widget.presenter.handle_item_code = _handle_item_code

    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW1")
    qtbot.waitUntil(lambda: len(lookup_calls) == 1, timeout=1000)
    initial_lookup_count = len(lookup_calls)

    editor = _begin_inline_edit(qtbot, widget, 0, COL_CODE)
    QTest.keyClick(editor, Qt.Key.Key_Return)

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_GROSS
        ),
        timeout=1000,
    )
    assert len(lookup_calls) == initial_lookup_count


def test_unchanged_code_tab_advances_to_gross_without_relookup(
    make_estimate_widget, qtbot, fake_db
):
    """Pressing Tab on an unchanged code should keep the same no-relookup behavior."""
    widget = make_estimate_widget(fake_db)
    widget.show()
    lookup_calls = []

    def _handle_item_code(row, code):
        lookup_calls.append((row, code))
        return False

    widget.presenter.handle_item_code = _handle_item_code

    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW1")
    qtbot.waitUntil(lambda: len(lookup_calls) == 1, timeout=1000)
    initial_lookup_count = len(lookup_calls)

    editor = _begin_inline_edit(qtbot, widget, 0, COL_CODE)
    QTest.keyClick(editor, Qt.Key.Key_Tab)

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_GROSS
        ),
        timeout=1000,
    )
    assert len(lookup_calls) == initial_lookup_count


def test_empty_gross_enter_commits_zero_and_advances_to_poly(
    make_estimate_widget, qtbot, fake_db
):
    """Enter on an empty gross editor should still preserve row progression."""
    widget = make_estimate_widget(fake_db)
    widget.show()
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW1")

    editor = _begin_inline_edit(qtbot, widget, 0, COL_GROSS)
    editor.clear()
    QTest.keyClick(editor, Qt.Key.Key_Return)

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_POLY
        ),
        timeout=1000,
    )
    assert table.get_cell_text(0, COL_GROSS) == "0.00"


def test_empty_gross_backspace_moves_to_code_column(
    make_estimate_widget, qtbot, fake_db
):
    """Backspace on an empty gross editor should navigate back to code."""
    widget = make_estimate_widget(fake_db)
    widget.show()
    widget.table_controller.clear_all_rows()
    widget.table_controller._get_table_adapter().add_empty_row()
    table = widget.item_table
    table.set_cell_text(0, COL_CODE, "ROW1")

    editor = _begin_inline_edit(qtbot, widget, 0, COL_GROSS)
    editor.clear()
    QTest.keyClick(editor, Qt.Key.Key_Backspace)

    qtbot.waitUntil(
        lambda: (
            table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_CODE
        ),
        timeout=1000,
    )
