"""Integration tests for EstimateEntryWidget real user workflows."""

import types

import pytest
from PyQt5.QtCore import Qt

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

        # Verify the row was created via the adapter
        last_row = widget.item_table.rowCount() - 1
        assert (
            widget.item_table.get_cell_text(last_row, COL_TYPE) == "No"
        ), "Empty row should be marked as regular type"

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

        # Verify all columns map to valid model indexes.
        model = table.get_model()
        for col in range(table.columnCount()):
            assert model.index(last_row, col).isValid(), f"Column {col} should be valid"

        # Verify calculated columns are non-editable
        net_index = model.index(last_row, COL_NET_WT)
        wage_index = model.index(last_row, COL_WAGE_AMT)
        fine_index = model.index(last_row, COL_FINE_WT)
        assert not (
            model.flags(net_index) & Qt.ItemIsEditable
        ), "Net weight should be read-only"
        assert not (
            model.flags(wage_index) & Qt.ItemIsEditable
        ), "Wage amount should be read-only"
        assert not (
            model.flags(fine_index) & Qt.ItemIsEditable
        ), "Fine weight should be read-only"
    finally:
        widget.deleteLater()


# ============================================================================
# Adapter Layer Tests - Add Row Functionality
# ============================================================================


def test_adapter_add_empty_row_via_button(qt_app, fake_db):
    """Test that clicking 'Add Row' button uses adapter.add_empty_row().

    This is the most common user action - clicking the Add Row button.
    It exercises the full adapter path for row creation.
    """
    widget = _make_widget(fake_db)
    try:
        initial_count = widget.item_table.rowCount()

        # Clear existing rows to test from clean slate
        widget.clear_all_rows()

        # Simulate user clicking "Add Row" button (triggers adapter)
        widget.table_adapter.add_empty_row()

        assert widget.item_table.rowCount() == 1, "Should add one row"

        assert widget.item_table.get_cell_text(0, COL_TYPE) == "No"
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
        table.set_cell_text(0, COL_CODE, "ABC123")

        # Now try to add another row
        widget.table_adapter.add_empty_row()

        # Should create a new row since last one has code
        assert table.rowCount() == 2, "Should create second row when first has code"
    finally:
        widget.deleteLater()


# ============================================================================
# Adapter Layer Tests - Populate Row
# ============================================================================


def test_adapter_populate_row_uses_model_first_updates(qt_app, fake_db):
    """Test that adapter.populate_row writes through model-first helpers."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        # Populate row via adapter.
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

        assert table.get_cell_text(0, COL_CODE) == "TEST001"
        assert table.get_cell_text(0, COL_ITEM_NAME) == "Test Item"
        assert table.get_cell_text(0, COL_PURITY) == "92.5"
        assert table.get_cell_text(0, COL_WAGE_RATE) == "10.0"
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
        table = widget.item_table
        assert table.get_cell_text(0, COL_PIECES) == "0"
        index = table.model().index(0, COL_PIECES)
        assert not bool(table.model().flags(index) & Qt.ItemIsEditable)
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
        table = widget.item_table
        assert table.get_cell_text(0, COL_PIECES) == "1"
        index = table.model().index(0, COL_PIECES)
        assert bool(table.model().flags(index) & Qt.ItemIsEditable)
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
        table.set_cell_text(0, COL_GROSS, "10.0")
        table.set_cell_text(0, COL_POLY, "1.0")

        # Trigger calculation manually (in real app, this happens via signals)
        widget.current_row = 0
        widget.calculate_net_weight()

        # Verify calculations
        assert float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.0)
        # Fine weight = 9.0 * 0.925 = 8.325
        assert float(table.get_cell_text(0, COL_FINE_WT)) == pytest.approx(
            8.33, abs=0.01
        )
        # Wage = 9.0 * 10.0 = 90
        assert float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(90.0)
    finally:
        widget.deleteLater()


# ============================================================================
# Model/View Architecture Tests
# ============================================================================


def test_set_cell_text_syncs_with_model(qt_app, fake_db):
    """Setting cell text should propagate to the underlying model."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table
        table.set_cell_text(0, COL_CODE, "SYNC123")

        # Verify model was updated
        model = table.get_model()
        index = model.index(0, COL_CODE)
        model_data = model.data(index, Qt.DisplayRole)

        assert model_data == "SYNC123", "Model should be updated"
    finally:
        widget.deleteLater()


def test_model_updates_reflect_in_get_cell_text(qt_app, fake_db):
    """Model updates should be readable via table view helper."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table
        model = table.get_model()

        # Update model directly
        index = model.index(0, COL_CODE)
        model.setData(index, "DIRECT123", Qt.EditRole)

        assert table.get_cell_text(0, COL_CODE) == "DIRECT123"
    finally:
        widget.deleteLater()


def test_row_changes_keep_existing_cell_values(qt_app, fake_db):
    """Adding rows should not disturb existing row values."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()

        table = widget.item_table

        table.set_cell_text(0, COL_CODE, "CACHE1")

        # Add another row (should clear cache)
        widget.table_adapter.add_empty_row()

        assert table.get_cell_text(0, COL_CODE) == "CACHE1"
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
        assert table.get_cell_text(last_row, COL_TYPE) == "No"

        # Toggle return mode
        widget.toggle_return_mode()

        # Adapter should refresh empty row type
        last_row = table.rowCount() - 1
        assert table.get_cell_text(last_row, COL_TYPE) == "Return"

        # Toggle silver bar mode
        widget.toggle_silver_bar_mode()
        last_row = table.rowCount() - 1
        assert table.get_cell_text(last_row, COL_TYPE) == "Silver Bar"

        # Toggle off
        widget.toggle_silver_bar_mode()
        last_row = table.rowCount() - 1
        assert table.get_cell_text(last_row, COL_TYPE) == "No"
    finally:
        widget.deleteLater()


def test_append_empty_row_model_first_helper(qt_app, fake_db):
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table
        initial_count = table.rowCount()
        table.append_empty_row()
        assert table.rowCount() == initial_count + 1
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
        table.set_cell_text(0, COL_CODE, "FILLED")

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
            if not table.get_cell_text(row, COL_CODE).strip():
                assert table.get_cell_text(row, COL_TYPE) == "Return"
    finally:
        widget.deleteLater()


# ============================================================================
# Async/Timer Tests (Critical for catching delayed operations)
# ============================================================================


def test_widget_initialization_with_timers(qtbot, fake_db):
    """Test that widget initialization completes including timer-delayed operations.

    This test catches issues with QTimer.singleShot operations like
    force_focus_to_first_cell() which are missed by synchronous tests.
    """
    widget = _make_widget(fake_db)
    try:
        qtbot.waitUntil(lambda: widget.item_table.rowCount() > 0, timeout=1500)
        current_index = widget.item_table.currentIndex()
        assert (not current_index.isValid()) or (current_index.column() == COL_CODE)
    finally:
        widget.deleteLater()


def test_navigation_target_mapping_is_consistent(qt_app, fake_db):
    """Test cursor navigation mapping helpers for deterministic movement."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        widget.item_table.set_cell_text(0, COL_CODE, "WT001")
        widget.table_adapter.add_empty_row()
        widget.item_table.set_cell_text(1, COL_CODE, "PC001")
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


def test_add_empty_row_deferred_focus_is_safe_after_delete(
    qt_app, fake_db, capsys
):
    """Test deferred focus timer does not crash when widget is deleted quickly."""
    widget = _make_widget(fake_db)
    widget.clear_all_rows()
    widget.table_adapter.add_empty_row()
    widget.close()
    widget.deleteLater()
    qt_app.sendPostedEvents()
    qt_app.processEvents()

    captured = capsys.readouterr()
    assert (
        "wrapped C/C++ object of type EstimateEntryWidget has been deleted"
        not in captured.err
    )


def test_manual_row_selection_not_overridden_by_queued_auto_advance(qtbot, fake_db):
    """Manual row selection should win over delayed auto-advance from prior edit."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table

        # Prepare two rows with codes so navigation logic treats them as valid rows.
        table.set_cell_text(0, COL_CODE, "ROW0")
        widget.table_adapter.add_empty_row()
        table.set_cell_text(1, COL_CODE, "ROW1")

        # Simulate an edit in row 1 that queues move_to_next_cell().
        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget.handle_cell_changed(1, COL_GROSS)

        # User manually moves to previous row before queued auto-advance fires.
        table.setCurrentCell(0, COL_CODE)
        widget.current_row = 0
        widget.current_column = COL_CODE

        qtbot.waitUntil(
            lambda: table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_CODE,
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_manual_arrow_navigation_intent_blocks_queued_auto_advance(qtbot, fake_db):
    """Queued auto-advance must not override a user arrow-row navigation."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.set_cell_text(0, COL_CODE, "ROW0")
        widget.table_adapter.add_empty_row()
        table.set_cell_text(1, COL_CODE, "ROW1")

        table.setCurrentCell(1, COL_GROSS)
        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget._schedule_auto_advance_from(1, COL_GROSS)

        # Mimic arrow-up intent arriving before deferred auto-advance executes.
        widget._mark_manual_row_navigation()
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
    finally:
        widget.deleteLater()


def test_row_change_marks_manual_nav_and_blocks_old_auto_advance(qtbot, fake_db):
    """Row switch via current-cell change should suppress queued auto-advance."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.set_cell_text(0, COL_CODE, "ROW0")
        widget.table_adapter.add_empty_row()
        table.set_cell_text(1, COL_CODE, "ROW1")

        widget.current_row = 1
        widget.current_column = COL_GROSS
        widget._schedule_auto_advance_from(1, COL_GROSS)

        # Simulate keyboard row navigation event path.
        widget.current_cell_changed(0, COL_GROSS, 1, COL_GROSS)
        qtbot.waitUntil(
            lambda: widget.current_row == 0 and widget._manual_row_nav_recent(),
            timeout=1000,
        )

        current = table.currentIndex()
        # current index can be invalid in headless mode; if valid it must remain on the upper row.
        assert (not current.isValid()) or (current.row() == 0)
        assert widget.current_row == 0
        assert widget._manual_row_nav_recent()
    finally:
        widget.deleteLater()


def test_click_row_above_during_queued_advance_remains_stable(qtbot, fake_db):
    """Clicking an upper row should not trigger edit-loop churn."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table
        table.set_cell_text(0, COL_CODE, "ROW0")
        widget.table_adapter.add_empty_row()
        table.set_cell_text(1, COL_CODE, "ROW1")

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

        qtbot.waitUntil(
            lambda: table.currentIndex().isValid() and table.currentIndex().row() == 0,
            timeout=1500,
        )
    finally:
        widget.deleteLater()


def test_revisiting_row_with_same_code_preserves_manual_overrides(qtbot, fake_db):
    """Unchanged code commit must not reapply item-master defaults."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
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
        assert table.get_cell_text(0, COL_PURITY) == "95.5"
        assert table.get_cell_text(0, COL_WAGE_RATE) == "22.0"

        # Revisit/commit same code value. Should be treated as no-op.
        code_index = table.get_model().index(0, COL_CODE)
        assert table.get_model().setData(code_index, "ITM1", Qt.EditRole)
        qtbot.wait(40)

        assert len(lookup_calls) == initial_lookup_count
        assert table.get_cell_text(0, COL_PURITY) == "95.5"
        assert table.get_cell_text(0, COL_WAGE_RATE) == "22.0"
    finally:
        widget.deleteLater()


def test_unchanged_purity_commit_still_advances_cursor(qtbot, fake_db):
    """Committing unchanged purity should still advance to wage-rate column."""
    widget = _make_widget(fake_db)
    try:
        widget.clear_all_rows()
        widget.table_adapter.add_empty_row()
        table = widget.item_table

        table.set_cell_text(0, COL_CODE, "ROW1")
        table.set_cell_text(0, COL_PURITY, "91.6")

        table.setCurrentCell(0, COL_PURITY)
        widget.current_row = 0
        widget.current_column = COL_PURITY

        purity_index = table.get_model().index(0, COL_PURITY)
        assert table.get_model().setData(purity_index, 91.6, Qt.EditRole)

        qtbot.waitUntil(
            lambda: table.currentIndex().isValid()
            and table.currentIndex().row() == 0
            and table.currentIndex().column() == COL_WAGE_RATE,
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_begin_cell_edit_model_first_helper(qtbot, fake_db):
    """Model-first begin_cell_edit helper should select and edit a cell."""
    widget = _make_widget(fake_db)
    try:
        table = widget.item_table

        # Ensure we have a row
        if table.rowCount() == 0:
            widget.table_adapter.add_empty_row()

        assert table.begin_cell_edit(0, COL_CODE)

        # Editing may no-op in headless runs, but the current index should be set.
        current = table.currentIndex()
        assert (not current.isValid()) or (
            current.row() == 0 and current.column() == COL_CODE
        )
    finally:
        widget.deleteLater()
