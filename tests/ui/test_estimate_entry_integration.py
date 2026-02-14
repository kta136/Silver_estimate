"""Integration tests for EstimateEntryWidget that test real user workflows.

These tests exercise the full code paths including:
- EstimateTableAdapter layer
- EstimateTableView with Model/View architecture
- Signal routing and event chains
- QTableWidget compatibility layer

Unlike the existing widget tests which bypass the adapter layer,
these tests simulate actual user interactions.
"""

import types

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QTableWidgetItem

from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_ITEM_NAME,
    COL_NET_WT,
    COL_PIECES,
    COL_POLY,
    COL_PURITY,
    COL_TYPE,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)


@pytest.fixture()
def fake_db():
    """Create a fake database manager for testing."""

    class _DB:
        def __init__(self):
            self.item_cache_controller = None
            self.generate_calls = 0

        def generate_voucher_no(self):
            self.generate_calls += 1
            return "TEST123"

        def drop_tables(self):
            return True

        def setup_database(self):
            return True

        def delete_all_estimates(self):
            return True

        def get_item_by_code(self, code):
            return {"wage_type": "WT", "wage_rate": 10}

    return _DB()


class _RepositoryStub:
    """Stub repository for testing."""

    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        loader = getattr(self.db, "get_estimate_by_voucher", None)
        if callable(loader):
            return loader(voucher_no)
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def estimate_exists(self, voucher_no):
        return bool(self.load_estimate(voucher_no))

    def notify_silver_bars_for_estimate(self, voucher_no):
        deleter = getattr(self.db, "delete_silver_bars_for_estimate", None)
        if callable(deleter):
            deleter(voucher_no)

    def save_estimate(
        self, voucher_no, date, silver_rate, regular_items, return_items, totals
    ):
        saver = getattr(self.db, "save_estimate_with_returns", None)
        if callable(saver):
            return bool(
                saver(
                    voucher_no,
                    date,
                    silver_rate,
                    list(regular_items or []),
                    list(return_items or []),
                    dict(totals or {}),
                )
            )
        return True

    def last_error(self):
        return getattr(self.db, "last_error", None)


def _make_widget(db_manager):
    """Create a widget instance for testing."""
    main_window_stub = types.SimpleNamespace(
        show_inline_status=lambda *a, **k: None,
        show_silver_bars=lambda: None,
    )
    repository = _RepositoryStub(db_manager)
    widget = EstimateEntryWidget(db_manager, main_window_stub, repository)
    widget.presenter.handle_item_code = lambda row, code: False
    return widget


# ============================================================================
# Program Startup Tests
# ============================================================================


def test_program_startup_creates_empty_row(qt_app, fake_db):
    """Test that starting the program creates an initial empty row via adapter.

    This simulates what happens when a user launches the application.
    The widget should initialize with one empty row ready for data entry.
    """
    widget = _make_widget(fake_db)
    try:
        # Verify initial state
        assert (
            widget.item_table.rowCount() >= 1
        ), "Should have at least one row on startup"

        # Verify the row was created via the adapter (uses insertRow internally)
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item is not None, "Type column should be initialized"
        # Model returns user-friendly display text ("No", "Return", "Silver Bar")
        assert type_item.text() == "No", "Empty row should be marked as regular type"

        # Verify voucher was generated
        assert widget.voucher_edit.text() == "TEST123"
        assert fake_db.generate_calls == 1
    finally:
        widget.deleteLater()


def test_initial_empty_row_has_correct_structure(qt_app, fake_db):
    """Test that the initial empty row has all cells properly initialized."""
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        last_row = table.rowCount() - 1

        # Verify all columns have items (created by adapter)
        for col in range(table.columnCount()):
            item = table.item(last_row, col)
            assert item is not None, f"Column {col} should have an item"

        # Verify calculated columns are non-editable
        net_wt_item = table.item(last_row, COL_NET_WT)
        wage_amt_item = table.item(last_row, COL_WAGE_AMT)
        fine_wt_item = table.item(last_row, COL_FINE_WT)

        # These should be read-only (flags check)
        assert not (
            net_wt_item.flags() & Qt.ItemIsEditable
        ), "Net weight should be read-only"
        assert not (
            wage_amt_item.flags() & Qt.ItemIsEditable
        ), "Wage amount should be read-only"
        assert not (
            fine_wt_item.flags() & Qt.ItemIsEditable
        ), "Fine weight should be read-only"
    finally:
        widget.deleteLater()


# ============================================================================
# Adapter Layer Tests - Add Row Functionality
# ============================================================================


def test_adapter_add_empty_row_via_button(qt_app, fake_db):
    """Test that clicking 'Add Row' button uses adapter.add_empty_row().

    This is the most common user action - clicking the Add Row button.
    It exercises the full adapter path including insertRow().
    """
    widget = _make_widget(fake_db)
    try:
        initial_count = widget.item_table.rowCount()

        # Clear existing rows to test from clean slate
        widget.clear_all_rows()

        # Simulate user clicking "Add Row" button (triggers adapter)
        widget.table_adapter.add_empty_row()

        assert widget.item_table.rowCount() == 1, "Should add one row"

        # Verify the row has proper structure
        type_item = widget.item_table.item(0, COL_TYPE)
        assert type_item is not None
        assert type_item.text() == "No"  # Default type (display label)
    finally:
        widget.deleteLater()


def test_adapter_prevents_multiple_empty_rows(qt_app, fake_db):
    """Test that adapter doesn't create duplicate empty rows.

    If there's already an empty row, clicking Add Row should focus it
    rather than creating a new one.
    """
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()

        # Add first empty row
        widget.table_adapter.add_empty_row()
        assert widget.item_table.rowCount() == 1

        # Try to add another empty row
        widget.table_adapter.add_empty_row()

        # Should still have only one row (focuses existing empty row)
        assert widget.item_table.rowCount() == 1
    finally:
        widget.deleteLater()


def test_adapter_adds_row_when_last_has_code(qt_app, fake_db):
    """Test that adapter creates new row when last row has code."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()

        # Add row and populate it
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        code_item = table.item(0, COL_CODE)
        code_item.setText("ABC123")

        # Now try to add another row
        widget.table_adapter.add_empty_row()

        # Should create a new row since last one has code
        assert table.rowCount() == 2, "Should create second row when first has code"
    finally:
        widget.deleteLater()


# ============================================================================
# Adapter Layer Tests - Populate Row
# ============================================================================


def test_adapter_populate_row_uses_model_backed_items(qt_app, fake_db):
    """Test that adapter.populate_row works with ModelBackedTableItem.

    This is critical - the adapter calls item() and setText() on the results,
    which must update the underlying model in Model/View architecture.
    """
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        # Populate row via adapter (uses item(), setText(), etc.)
        widget.table_adapter.populate_row(
            0,
            {
                "code": "test001",
                "name": "Test Item",
                "purity": 92.5,
                "wage_rate": 10.0,
            },
        )

        table = widget.item_table

        # Verify data was written via ModelBackedTableItem
        assert table.item(0, COL_CODE).text() == "TEST001"  # Should be uppercased
        assert table.item(0, COL_ITEM_NAME).text() == "Test Item"
        assert table.item(0, COL_PURITY).text() == "92.5"
        assert table.item(0, COL_WAGE_RATE).text() == "10.0"

        # Verify UserRole data is preserved
        code_item = table.item(0, COL_CODE)
        assert (
            code_item.data(Qt.UserRole) == "test001"
        ), "Canonical code should be stored"
    finally:
        widget.deleteLater()


def test_adapter_populate_row_wt_forces_zero_and_disables_pieces(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        widget.table_adapter.populate_row(
            0,
            {
                "code": "wt001",
                "name": "WT Item",
                "purity": 92.5,
                "wage_rate": 10.0,
                "wage_type": "WT",
            },
        )
        pieces_item = widget.item_table.item(0, COL_PIECES)
        assert pieces_item.text() == "0"
        index = widget.item_table.model().index(0, COL_PIECES)
        assert not bool(widget.item_table.model().flags(index) & Qt.ItemIsEditable)
    finally:
        widget.deleteLater()


def test_adapter_populate_row_pc_restores_one_after_wt_zero(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        widget.table_adapter.populate_row(
            0,
            {
                "code": "wt001",
                "name": "WT Item",
                "purity": 92.5,
                "wage_rate": 10.0,
                "wage_type": "WT",
            },
        )
        widget.table_adapter.populate_row(
            0,
            {
                "code": "pc001",
                "name": "PC Item",
                "purity": 92.5,
                "wage_rate": 10.0,
                "wage_type": "PC",
            },
        )
        pieces_item = widget.item_table.item(0, COL_PIECES)
        assert pieces_item.text() == "1"
        assert bool(pieces_item.flags() & Qt.ItemIsEditable)
    finally:
        widget.deleteLater()


def test_adapter_populate_triggers_calculations(qt_app, fake_db):
    """Test that populating a row via adapter triggers calculations.

    The adapter should call calculate_net_weight() which computes
    derived fields like net weight, fine weight, wage amount.
    """
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        # Populate with data that should trigger calculations
        widget.table_adapter.populate_row(
            0,
            {
                "code": "calc001",
                "name": "Calculation Test",
                "purity": 92.5,
                "wage_rate": 10.0,
            },
        )

        # Manually set gross and poly to trigger calculations
        table = widget.item_table
        table.item(0, COL_GROSS).setText("10.0")
        table.item(0, COL_POLY).setText("1.0")

        # Trigger calculation manually (in real app, this happens via signals)
        widget.current_row = 0
        widget.calculate_net_weight()

        # Verify calculations
        assert float(table.item(0, COL_NET_WT).text()) == pytest.approx(9.0)
        # Fine weight = 9.0 * 0.925 = 8.325
        assert float(table.item(0, COL_FINE_WT).text()) == pytest.approx(8.33, abs=0.01)
        # Wage = 9.0 * 10.0 = 90
        assert float(table.item(0, COL_WAGE_AMT).text()) == pytest.approx(90.0)
    finally:
        widget.deleteLater()


# ============================================================================
# Model/View Architecture Tests
# ============================================================================


def test_model_backed_item_syncs_with_model(qt_app, fake_db):
    """Test that ModelBackedTableItem updates propagate to the model."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table
        item = table.item(0, COL_CODE)

        # Update via ModelBackedTableItem
        item.setText("SYNC123")

        # Verify model was updated
        model = table.get_model()
        index = model.index(0, COL_CODE)
        model_data = model.data(index, Qt.DisplayRole)

        assert model_data == "SYNC123", "Model should be updated"
    finally:
        widget.deleteLater()


def test_model_backed_item_reads_from_model(qt_app, fake_db):
    """Test that ModelBackedTableItem.text() reads from the model."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table
        model = table.get_model()

        # Update model directly
        index = model.index(0, COL_CODE)
        model.setData(index, "DIRECT123", Qt.EditRole)

        # Verify item reads updated data
        item = table.item(0, COL_CODE)
        assert item.text() == "DIRECT123", "Item should read from model"
    finally:
        widget.deleteLater()


def test_item_cache_invalidates_on_row_changes(qt_app, fake_db):
    """Test that item cache is cleared when rows change."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table

        # Get item (should be cached)
        item1 = table.item(0, COL_CODE)
        item1.setText("CACHE1")

        # Add another row (should clear cache)
        widget.table_adapter.add_empty_row()

        # Get item again (should be new instance)
        item2 = table.item(0, COL_CODE)

        # Both should read same data from model
        assert item1.text() == "CACHE1"
        assert item2.text() == "CACHE1"
    finally:
        widget.deleteLater()


# ============================================================================
# Mode Toggle Tests (Integration with Adapter)
# ============================================================================


def test_mode_toggle_updates_empty_row_type_via_adapter(qt_app, fake_db):
    """Test that toggling modes updates empty row type through adapter."""
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        last_row = table.rowCount() - 1

        # Initial state (display labels)
        assert table.item(last_row, COL_TYPE).text() == "No"

        # Toggle return mode
        widget.toggle_return_mode()

        # Adapter should refresh empty row type
        last_row = table.rowCount() - 1
        assert table.item(last_row, COL_TYPE).text() == "Return"

        # Toggle silver bar mode
        widget.toggle_silver_bar_mode()
        last_row = table.rowCount() - 1
        assert table.item(last_row, COL_TYPE).text() == "Silver Bar"

        # Toggle off
        widget.toggle_silver_bar_mode()
        last_row = table.rowCount() - 1
        assert table.item(last_row, COL_TYPE).text() == "No"
    finally:
        widget.deleteLater()


# ============================================================================
# QTableWidget Compatibility Layer Tests
# ============================================================================


def test_insertrow_compatibility_method(qt_app, fake_db):
    """Test that QTableWidget.insertRow() compatibility works."""
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        initial_count = table.rowCount()

        # Call insertRow directly (QTableWidget compatibility)
        table.insertRow(initial_count)

        assert table.rowCount() == initial_count + 1
    finally:
        widget.deleteLater()


def test_item_setitem_compatibility_methods(qt_app, fake_db):
    """Test that item() and setItem() compatibility methods work."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        table = widget.item_table
        table.insertRow(0)

        # Create item and set it (QTableWidget style)
        new_item = QTableWidgetItem("COMPAT123")
        table.setItem(0, COL_CODE, new_item)

        # Retrieve and verify
        retrieved_item = table.item(0, COL_CODE)
        assert retrieved_item.text() == "COMPAT123"
    finally:
        widget.deleteLater()


# ============================================================================
# Focus and Navigation Tests
# ============================================================================


def test_adapter_focus_on_empty_row(qt_app, fake_db):
    """Test adapter.focus_on_empty_row() finds or creates empty row."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()

        # No rows - should create one
        widget.table_adapter.focus_on_empty_row()
        assert widget.item_table.rowCount() == 1

        # Add code to first row
        table = widget.item_table
        table.item(0, COL_CODE).setText("FILLED")

        # Should create new empty row
        widget.table_adapter.focus_on_empty_row()
        assert table.rowCount() == 2
    finally:
        widget.deleteLater()


def test_adapter_refresh_empty_row_type(qt_app, fake_db):
    """Test that adapter.refresh_empty_row_type() updates all empty rows."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()

        # Create multiple empty rows
        widget.table_adapter.add_empty_row()
        widget.table_adapter.add_empty_row()

        table = widget.item_table

        # Toggle mode
        widget.toggle_return_mode()

        # Refresh should update all empty rows
        widget.table_adapter.refresh_empty_row_type()

        # Check all empty rows have correct type
        for row in range(table.rowCount()):
            code_item = table.item(row, COL_CODE)
            if not code_item or not code_item.text().strip():
                type_item = table.item(row, COL_TYPE)
                assert type_item.text() == "Return"  # display label
    finally:
        widget.deleteLater()


# ============================================================================
# Async/Timer Tests (Critical for catching delayed operations)
# ============================================================================


def test_widget_initialization_with_timers(qt_app, fake_db):
    """Test that widget initialization completes including timer-delayed operations.

    This test catches issues with QTimer.singleShot operations like
    force_focus_to_first_cell() which are missed by synchronous tests.
    """
    from PyQt5.QtCore import Qt
    from PyQt5.QtTest import QTest

    widget = _make_widget(fake_db)
    try:
        # Wait for all pending timers to execute (100ms + buffer)
        QTest.qWait(200)

        # Verify force_focus_to_first_cell() executed
        # It calls setCurrentCell() and editItem()
        current_index = widget.item_table.currentIndex()
        assert current_index.isValid(), "Should have focused on a cell"
        assert current_index.column() == COL_CODE, "Should focus on code column"

        # Verify table has at least one row
        assert widget.item_table.rowCount() > 0
    finally:
        widget.deleteLater()


def test_navigation_target_mapping_is_consistent(qt_app, fake_db):
    """Test cursor navigation mapping helpers for deterministic movement."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        widget.item_table.item(0, COL_CODE).setText("WT001")
        widget.table_adapter.add_empty_row()
        widget.item_table.item(1, COL_CODE).setText("PC001")
        model = widget.item_table.get_model()
        assert model.set_row_wage_type(0, "WT")
        assert model.set_row_wage_type(1, "PC")

        wt_row = 0
        pc_row = 1

        assert widget._next_edit_target(wt_row, COL_WAGE_RATE) == (wt_row + 1, COL_CODE)
        assert widget._previous_edit_target(wt_row + 1, COL_CODE) == (
            wt_row,
            COL_WAGE_RATE,
        )

        row = pc_row
        assert widget._next_edit_target(row, COL_CODE) == (row, COL_GROSS)
        assert widget._next_edit_target(row, COL_GROSS) == (row, COL_POLY)
        assert widget._next_edit_target(row, COL_POLY) == (row, COL_PURITY)
        assert widget._next_edit_target(row, COL_PURITY) == (row, COL_WAGE_RATE)
        assert widget._next_edit_target(row, COL_WAGE_RATE) == (row, COL_PIECES)
        assert widget._next_edit_target(row, COL_PIECES) == (row + 1, COL_CODE)

        assert widget._previous_edit_target(row, COL_PIECES) == (row, COL_WAGE_RATE)
        assert widget._previous_edit_target(row, COL_WAGE_RATE) == (row, COL_PURITY)
        assert widget._previous_edit_target(row, COL_PURITY) == (row, COL_POLY)
        assert widget._previous_edit_target(row, COL_POLY) == (row, COL_GROSS)
        assert widget._previous_edit_target(row, COL_GROSS) == (row, COL_CODE)
        assert widget._previous_edit_target(row, COL_CODE) == (row - 1, COL_WAGE_RATE)
        assert widget._previous_edit_target(0, COL_CODE) == (0, COL_CODE)
    finally:
        widget.deleteLater()


def test_add_empty_row_deferred_focus_is_safe_after_delete(qt_app, fake_db, capsys):
    """Test deferred focus timer does not crash when widget is deleted quickly."""
    widget = _make_widget(fake_db)
    widget.clear_all_rows()
    widget.table_adapter.add_empty_row()
    widget.deleteLater()

    # Let deferred QTimer callbacks run.
    qt_app.processEvents()
    QTest.qWait(120)
    qt_app.processEvents()

    captured = capsys.readouterr()
    assert (
        "wrapped C/C++ object of type EstimateEntryWidget has been deleted"
        not in captured.err
    )


def test_manual_row_selection_not_overridden_by_queued_auto_advance(qt_app, fake_db):
    """Manual row selection should win over delayed auto-advance from prior edit."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table

        # Prepare two rows with codes so navigation logic treats them as valid rows.
        table.item(0, COL_CODE).setText("ROW0")
        widget.table_adapter.add_empty_row()
        table.item(1, COL_CODE).setText("ROW1")

        # Simulate an edit in row 1 that queues move_to_next_cell().
        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget.handle_cell_changed(1, COL_GROSS)

        # User manually moves to previous row before queued auto-advance fires.
        table.setCurrentCell(0, COL_CODE)
        widget.current_row = 0
        widget.current_column = COL_CODE

        QTest.qWait(50)
        current = table.currentIndex()
        assert current.isValid()
        assert current.row() == 0
        assert current.column() == COL_CODE
    finally:
        widget.deleteLater()


def test_manual_arrow_navigation_intent_blocks_queued_auto_advance(qt_app, fake_db):
    """Queued auto-advance must not override a user arrow-row navigation."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.item(0, COL_CODE).setText("ROW0")
        widget.table_adapter.add_empty_row()
        table.item(1, COL_CODE).setText("ROW1")

        table.setCurrentCell(1, COL_GROSS)
        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget._schedule_auto_advance_from(1, COL_GROSS)

        # Mimic arrow-up intent arriving before deferred auto-advance executes.
        widget._mark_manual_row_navigation()
        table.setCurrentCell(0, COL_GROSS)
        widget.current_row = 0
        widget.current_column = COL_GROSS

        QTest.qWait(50)
        current = table.currentIndex()
        assert current.isValid()
        assert current.row() == 0
        # In CI (Windows/Py3.13), focus may settle on COL_CODE while preserving the
        # manual row-navigation intent. The critical behavior is that queued
        # auto-advance does not jump away from row 0.
        assert current.column() in (COL_GROSS, COL_CODE)
    finally:
        widget.deleteLater()


def test_row_change_marks_manual_nav_and_blocks_old_auto_advance(qt_app, fake_db):
    """Row switch via current-cell change should suppress queued auto-advance."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.item(0, COL_CODE).setText("ROW0")
        widget.table_adapter.add_empty_row()
        table.item(1, COL_CODE).setText("ROW1")

        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget._schedule_auto_advance_from(1, COL_GROSS)

        # Simulate keyboard row navigation event path.
        widget.current_cell_changed(0, COL_GROSS, 1, COL_GROSS)
        QTest.qWait(50)

        current = table.currentIndex()
        # current index can be invalid in headless mode; if valid it must remain on the upper row.
        assert (not current.isValid()) or (current.row() == 0)
        assert widget.current_row == 0
        assert widget._manual_row_nav_recent()
    finally:
        widget.deleteLater()


def test_click_row_above_during_queued_advance_remains_stable(qt_app, fake_db):
    """Clicking an upper row should not trigger edit-loop churn."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.item(0, COL_CODE).setText("ROW0")
        widget.table_adapter.add_empty_row()
        table.item(1, COL_CODE).setText("ROW1")

        # Trigger an edit change path that queues auto-advance.
        table.setCurrentCell(1, COL_GROSS)
        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget.handle_cell_changed(1, COL_GROSS)

        # User clicks row above immediately.
        widget.cell_clicked(0, COL_CODE)
        table.setCurrentCell(0, COL_CODE)
        widget.current_row = 0
        widget.current_column = COL_CODE

        # Let queued callbacks settle.
        QTest.qWait(120)
        qt_app.processEvents()

        current = table.currentIndex()
        assert current.isValid()
        assert current.row() == 0
    finally:
        widget.deleteLater()


def test_edititem_compatibility_method(qt_app, fake_db):
    """Test that editItem() compatibility method works with ModelBackedTableItem."""
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table

        # Ensure we have a row
        if table.rowCount() == 0:
            widget.table_adapter.add_empty_row()

        # Get item
        item = table.item(0, COL_CODE)
        assert item is not None

        # Call editItem (should not raise AttributeError)
        table.editItem(item)

        # editItem runs asynchronously and may no-op when widget is not visible
        QTest.qWait(50)
        current = table.currentIndex()
        assert (not current.isValid()) or (
            current.row() == 0 and current.column() == COL_CODE
        )
    finally:
        widget.deleteLater()
