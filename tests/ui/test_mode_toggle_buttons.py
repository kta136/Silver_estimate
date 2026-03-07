"""Tests for mode toggle button functionality (Ctrl+R and Ctrl+B)."""

import types

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from silverestimate.ui.estimate_entry import EstimateEntryWidget
from silverestimate.ui.estimate_entry_logic import COL_TYPE


@pytest.fixture
def fake_db():
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
    def __init__(self, db):
        self.db = db

    def generate_voucher_no(self):
        return self.db.generate_voucher_no()

    def load_estimate(self, voucher_no):
        return None

    def fetch_item(self, code):
        return self.db.get_item_by_code(code)

    def save_estimate(self, *args, **kwargs):
        return True

    def last_error(self):
        return None


def _make_widget(db_manager):
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


def _wait_for_initialized(qtbot, widget):
    qtbot.waitUntil(lambda: widget.item_table.rowCount() > 0, timeout=2000)


def test_return_mode_button_updates_row_type(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)

        last_row = widget.item_table.rowCount() - 1
        assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "No"
        assert not widget.return_mode
        assert not widget.return_toggle_button.isChecked()

        widget.return_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                widget.return_mode
                and widget.return_toggle_button.isChecked()
                and widget.mode_indicator_label.text() == "Mode: Return Items"
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Return"
            ),
            timeout=1000,
        )

        widget.return_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                (not widget.return_mode)
                and (not widget.return_toggle_button.isChecked())
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "No"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_silver_bar_mode_button_updates_row_type(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)

        last_row = widget.item_table.rowCount() - 1
        assert widget.item_table.get_cell_text(last_row, COL_TYPE) == "No"
        assert not widget.silver_bar_mode
        assert not widget.silver_bar_toggle_button.isChecked()

        widget.silver_bar_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                widget.silver_bar_mode
                and widget.silver_bar_toggle_button.isChecked()
                and widget.mode_indicator_label.text() == "Mode: Silver Bars"
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Silver Bar"
            ),
            timeout=1000,
        )

        widget.silver_bar_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                (not widget.silver_bar_mode)
                and (not widget.silver_bar_toggle_button.isChecked())
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "No"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_mode_toggles_are_mutually_exclusive(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)

        widget.return_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                widget.return_mode
                and widget.return_toggle_button.isChecked()
                and (not widget.silver_bar_mode)
                and (not widget.silver_bar_toggle_button.isChecked())
            ),
            timeout=1000,
        )

        widget.silver_bar_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                (not widget.return_mode)
                and (not widget.return_toggle_button.isChecked())
                and widget.silver_bar_mode
                and widget.silver_bar_toggle_button.isChecked()
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Silver Bar"
            ),
            timeout=1000,
        )

        widget.return_toggle_button.click()
        qtbot.waitUntil(
            lambda: (
                widget.return_mode
                and widget.return_toggle_button.isChecked()
                and (not widget.silver_bar_mode)
                and (not widget.silver_bar_toggle_button.isChecked())
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Return"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_ctrl_r_keyboard_shortcut_toggles_return_mode(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)
        assert not widget.return_mode

        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: (
                widget.return_mode
                and widget.return_toggle_button.isChecked()
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Return"
            ),
            timeout=1000,
        )

        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: (
                (not widget.return_mode)
                and (not widget.return_toggle_button.isChecked())
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "No"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_ctrl_b_keyboard_shortcut_toggles_silver_bar_mode(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)
        assert not widget.silver_bar_mode

        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: (
                widget.silver_bar_mode
                and widget.silver_bar_toggle_button.isChecked()
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Silver Bar"
            ),
            timeout=1000,
        )

        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: (
                (not widget.silver_bar_mode)
                and (not widget.silver_bar_toggle_button.isChecked())
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "No"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()


def test_keyboard_shortcuts_respect_mutual_exclusion(qtbot, fake_db):
    widget = _make_widget(fake_db)
    try:
        _wait_for_initialized(qtbot, widget)

        QTest.keyClick(widget, Qt.Key_R, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: widget.return_mode and (not widget.silver_bar_mode), timeout=1000
        )

        QTest.keyClick(widget, Qt.Key_B, Qt.ControlModifier)
        qtbot.waitUntil(
            lambda: (
                (not widget.return_mode)
                and (not widget.return_toggle_button.isChecked())
                and widget.silver_bar_mode
                and widget.silver_bar_toggle_button.isChecked()
                and widget.item_table.get_cell_text(
                    widget.item_table.rowCount() - 1, COL_TYPE
                )
                == "Silver Bar"
            ),
            timeout=1000,
        )
    finally:
        widget.deleteLater()
