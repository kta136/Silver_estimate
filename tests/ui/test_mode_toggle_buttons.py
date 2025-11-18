"""Tests for mode toggle button functionality (Ctrl+R and Ctrl+B).

This test module verifies:
1. Mode toggle buttons update row types correctly
2. Modes are mutually exclusive (only one active at a time)
3. Keyboard shortcuts work correctly
"""

import types
import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import COL_TYPE


@pytest.fixture
def fake_db():
    """Create a minimal fake database for testing."""
    class _DB:
        def __init__(self):
            self.item_cache_controller = None
            self.generate_calls = 0

        def generate_voucher_no(self):
            self.generate_calls += 1
            return "TEST123"

        def get_item_by_code(self, code):
            return {"wage_type": "WT", "wage_rate": 10}

    return _DB()


class _RepositoryStub:
    """Minimal repository stub for testing."""
    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def estimate_exists(self, voucher_no):
        return False

    def save_estimate(self, *args, **kwargs):
        return True

    def last_error(self):
        return None


def _make_widget(db_manager):
    """Create a widget for testing."""
    main_window_stub = types.SimpleNamespace(
        show_inline_status=lambda *a, **k: None,
        show_silver_bars=lambda: None,
    )
    repository = _RepositoryStub(db_manager)
    widget = EstimateEntryWidget(db_manager, main_window_stub, repository)
    widget.presenter.handle_item_code = lambda row, code: False
    try:
        widget.item_table.cellChanged.disconnect(widget.handle_cell_changed)
    except (TypeError, AttributeError):
        pass
    return widget


def test_return_mode_button_updates_row_type(qt_app, fake_db):
    """Test that clicking Return button (Ctrl+R) updates empty row type."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Verify initial state (regular mode)
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Should start in regular mode"
        assert not widget.return_mode, "Return mode should be off"
        assert not widget.return_toggle_button.isChecked(), "Button should not be checked"

        # Click return button
        widget.return_toggle_button.click()
        QTest.qWait(50)  # Allow signals to process

        # Verify return mode activated
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "return", "Row type should change to 'return'"
        assert widget.return_mode, "Return mode should be on"
        assert widget.return_toggle_button.isChecked(), "Button should be checked"

        # Click again to toggle off
        widget.return_toggle_button.click()
        QTest.qWait(50)

        # Verify back to regular mode
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Row type should be back to 'regular'"
        assert not widget.return_mode, "Return mode should be off"
        assert not widget.return_toggle_button.isChecked(), "Button should not be checked"

    finally:
        widget.deleteLater()


def test_silver_bar_mode_button_updates_row_type(qt_app, fake_db):
    """Test that clicking Silver Bar button (Ctrl+B) updates empty row type."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Verify initial state (regular mode)
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Should start in regular mode"
        assert not widget.silver_bar_mode, "Silver bar mode should be off"
        assert not widget.silver_bar_toggle_button.isChecked(), "Button should not be checked"

        # Click silver bar button
        widget.silver_bar_toggle_button.click()
        QTest.qWait(50)

        # Verify silver bar mode activated
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "silver_bar", "Row type should change to 'silver_bar'"
        assert widget.silver_bar_mode, "Silver bar mode should be on"
        assert widget.silver_bar_toggle_button.isChecked(), "Button should be checked"

        # Click again to toggle off
        widget.silver_bar_toggle_button.click()
        QTest.qWait(50)

        # Verify back to regular mode
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Row type should be back to 'regular'"
        assert not widget.silver_bar_mode, "Silver bar mode should be off"
        assert not widget.silver_bar_toggle_button.isChecked(), "Button should not be checked"

    finally:
        widget.deleteLater()


def test_mode_toggles_are_mutually_exclusive(qt_app, fake_db):
    """Test that enabling one mode disables the other (mutual exclusion)."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Activate return mode
        widget.return_toggle_button.click()
        QTest.qWait(50)

        assert widget.return_mode, "Return mode should be on"
        assert widget.return_toggle_button.isChecked()
        assert not widget.silver_bar_mode, "Silver bar mode should be off"
        assert not widget.silver_bar_toggle_button.isChecked()

        # Now activate silver bar mode - should deactivate return mode
        widget.silver_bar_toggle_button.click()
        QTest.qWait(50)

        assert not widget.return_mode, "Return mode should be OFF (mutual exclusion)"
        assert not widget.return_toggle_button.isChecked(), "Return button should be unchecked"
        assert widget.silver_bar_mode, "Silver bar mode should be on"
        assert widget.silver_bar_toggle_button.isChecked(), "Silver bar button should be checked"

        # Verify row type is silver_bar
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "silver_bar", "Row should be silver_bar type"

        # Now activate return mode - should deactivate silver bar mode
        widget.return_toggle_button.click()
        QTest.qWait(50)

        assert widget.return_mode, "Return mode should be on"
        assert widget.return_toggle_button.isChecked(), "Return button should be checked"
        assert not widget.silver_bar_mode, "Silver bar mode should be OFF (mutual exclusion)"
        assert not widget.silver_bar_toggle_button.isChecked(), "Silver bar button should be unchecked"

        # Verify row type is return
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "return", "Row should be return type"

    finally:
        widget.deleteLater()


def test_ctrl_r_keyboard_shortcut_toggles_return_mode(qt_app, fake_db):
    """Test that Ctrl+R keyboard shortcut toggles return mode."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Verify initial state
        assert not widget.return_mode, "Should start in regular mode"

        # Press Ctrl+R
        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        QTest.qWait(50)

        # Verify return mode activated
        assert widget.return_mode, "Ctrl+R should activate return mode"
        assert widget.return_toggle_button.isChecked(), "Button should reflect state"

        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "return", "Row type should be 'return'"

        # Press Ctrl+R again
        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        QTest.qWait(50)

        # Verify back to regular mode
        assert not widget.return_mode, "Ctrl+R should toggle off return mode"
        assert not widget.return_toggle_button.isChecked(), "Button should reflect state"

        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Row type should be 'regular'"

    finally:
        widget.deleteLater()


def test_ctrl_b_keyboard_shortcut_toggles_silver_bar_mode(qt_app, fake_db):
    """Test that Ctrl+B keyboard shortcut toggles silver bar mode."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Verify initial state
        assert not widget.silver_bar_mode, "Should start in regular mode"

        # Press Ctrl+B
        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        QTest.qWait(50)

        # Verify silver bar mode activated
        assert widget.silver_bar_mode, "Ctrl+B should activate silver bar mode"
        assert widget.silver_bar_toggle_button.isChecked(), "Button should reflect state"

        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "silver_bar", "Row type should be 'silver_bar'"

        # Press Ctrl+B again
        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        QTest.qWait(50)

        # Verify back to regular mode
        assert not widget.silver_bar_mode, "Ctrl+B should toggle off silver bar mode"
        assert not widget.silver_bar_toggle_button.isChecked(), "Button should reflect state"

        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "regular", "Row type should be 'regular'"

    finally:
        widget.deleteLater()


def test_keyboard_shortcuts_respect_mutual_exclusion(qt_app, fake_db):
    """Test that keyboard shortcuts also enforce mutual exclusion."""
    widget = _make_widget(fake_db)
    try:
        # Wait for initialization timers
        QTest.qWait(200)

        # Activate return mode with Ctrl+R
        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        QTest.qWait(50)

        assert widget.return_mode, "Return mode should be on"
        assert not widget.silver_bar_mode, "Silver bar mode should be off"

        # Activate silver bar mode with Ctrl+B - should deactivate return mode
        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        QTest.qWait(50)

        assert not widget.return_mode, "Return mode should be OFF (mutual exclusion)"
        assert not widget.return_toggle_button.isChecked()
        assert widget.silver_bar_mode, "Silver bar mode should be on"
        assert widget.silver_bar_toggle_button.isChecked()

        # Verify row type
        last_row = widget.item_table.rowCount() - 1
        type_item = widget.item_table.item(last_row, COL_TYPE)
        assert type_item.text() == "silver_bar"

    finally:
        widget.deleteLater()
