"""Tests for VoucherToolbar component."""

import pytest
from PySide6.QtCore import QDate

from silverestimate.ui.estimate_entry_components.voucher_toolbar import VoucherToolbar


@pytest.fixture
def toolbar(qtbot):
    """Create a fresh VoucherToolbar for testing."""
    widget = VoucherToolbar()
    qtbot.addWidget(widget)
    return widget


def test_initial_state(toolbar):
    """Test that toolbar initializes with default values."""
    assert toolbar.voucher_edit.text() == ""
    assert toolbar.note_edit.text() == ""
    assert not toolbar.note_edit.isHidden()
    assert toolbar.date_edit.date() == QDate.currentDate()
    assert toolbar.unsaved_badge.text() == "● Ready"
    assert toolbar.unsaved_badge.property("dirty") == "false"
    assert toolbar.mode_indicator_label.text() == "Mode: Regular"
    assert toolbar.mode_combo.currentText() == "Regular"
    assert toolbar.layout().indexOf(toolbar.mode_combo) >= 0
    assert toolbar.mode_indicator_label.property("modeState") == "regular"
    assert toolbar.status_message_label.text() == ""


def test_set_voucher_number(toolbar):
    """Test setting voucher number."""
    toolbar.set_voucher_number("EST001")
    assert toolbar.voucher_edit.text() == "EST001"


def test_show_unsaved_badge(toolbar):
    """Test showing/hiding unsaved badge."""
    # Show the toolbar to ensure visibility changes work
    toolbar.show()

    assert toolbar.unsaved_badge.text() == "● Ready"
    assert toolbar.unsaved_badge.property("dirty") == "false"

    toolbar.show_unsaved_badge(True)
    assert toolbar.unsaved_badge.isVisible()
    assert toolbar.unsaved_badge.text() == "● Unsaved"
    assert toolbar.unsaved_badge.property("dirty") == "true"

    toolbar.show_unsaved_badge(False)
    assert toolbar.unsaved_badge.text() == "● Ready"
    assert toolbar.unsaved_badge.property("dirty") == "false"


def test_load_clicked_signal(toolbar):
    """Test that load button emits signal."""
    signal_received = []
    toolbar.load_clicked.connect(lambda: signal_received.append(True))

    toolbar.load_button.click()
    assert len(signal_received) == 1


def test_voucher_number_changed_signal(toolbar):
    """Test that voucher number changes emit signal."""
    values = []
    toolbar.voucher_number_changed.connect(lambda v: values.append(v))

    toolbar.voucher_edit.setText("EST001")
    assert len(values) > 0
    assert values[-1] == "EST001"


def test_date_changed_signal(toolbar):
    """Test that date changes emit signal."""
    dates = []
    toolbar.date_changed.connect(lambda d: dates.append(d))

    test_date = QDate(2024, 1, 15)
    toolbar.date_edit.setDate(test_date)
    assert len(dates) > 0
    assert dates[-1] == test_date


def test_note_changed_signal(toolbar):
    """Test that note changes emit signal."""
    values = []
    toolbar.note_changed.connect(lambda v: values.append(v))

    toolbar.note_edit.setText("Test")
    assert len(values) > 0
    assert values[-1] == "Test"
