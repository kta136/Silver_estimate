"""Tests for VoucherToolbar component."""

import pytest
from PyQt5.QtCore import QDate

from silverestimate.ui.estimate_entry_components.voucher_toolbar import VoucherToolbar


@pytest.fixture
def toolbar(qt_app):
    """Create a fresh VoucherToolbar for testing."""
    return VoucherToolbar()


def test_initial_state(toolbar):
    """Test that toolbar initializes with default values."""
    assert toolbar.get_voucher_number() == ""
    assert toolbar.get_note() == ""
    assert toolbar.get_date() == QDate.currentDate()
    assert not toolbar.delete_button.isEnabled()
    assert not toolbar.unsaved_badge.isVisible()


def test_set_voucher_number(toolbar):
    """Test setting voucher number."""
    toolbar.set_voucher_number("EST001")
    assert toolbar.get_voucher_number() == "EST001"
    assert toolbar.voucher_edit.text() == "EST001"


def test_set_date(toolbar):
    """Test setting date."""
    test_date = QDate(2024, 1, 15)
    toolbar.set_date(test_date)
    assert toolbar.get_date() == test_date


def test_set_note(toolbar):
    """Test setting note."""
    toolbar.set_note("Test note")
    assert toolbar.get_note() == "Test note"
    assert toolbar.note_edit.text() == "Test note"


def test_enable_delete(toolbar):
    """Test enabling/disabling delete button."""
    assert not toolbar.delete_button.isEnabled()

    toolbar.enable_delete(True)
    assert toolbar.delete_button.isEnabled()

    toolbar.enable_delete(False)
    assert not toolbar.delete_button.isEnabled()


def test_set_mode_indicator(toolbar):
    """Test setting mode indicator text."""
    toolbar.set_mode_indicator("Mode: Return Items")
    assert toolbar.mode_indicator_label.text() == "Mode: Return Items"


def test_show_unsaved_badge(toolbar):
    """Test showing/hiding unsaved badge."""
    # Show the toolbar to ensure visibility changes work
    toolbar.show()

    assert not toolbar.unsaved_badge.isVisible()

    toolbar.show_unsaved_badge(True)
    assert toolbar.unsaved_badge.isVisible()
    assert toolbar.unsaved_badge.text() == "● Unsaved"

    toolbar.show_unsaved_badge(False)
    assert not toolbar.unsaved_badge.isVisible()


def test_clear_voucher_metadata(toolbar):
    """Test clearing all metadata."""
    # Set some data
    toolbar.set_voucher_number("EST001")
    toolbar.set_note("Test note")
    toolbar.set_date(QDate(2024, 1, 15))
    toolbar.enable_delete(True)
    toolbar.show_unsaved_badge(True)

    # Clear it
    toolbar.clear_voucher_metadata()

    # Verify all cleared
    assert toolbar.get_voucher_number() == ""
    assert toolbar.get_note() == ""
    assert toolbar.get_date() == QDate.currentDate()
    assert not toolbar.delete_button.isEnabled()
    assert not toolbar.unsaved_badge.isVisible()


def test_save_clicked_signal(toolbar):
    """Test that save button emits signal."""
    signal_received = []
    toolbar.save_clicked.connect(lambda: signal_received.append(True))

    toolbar.save_button.click()
    assert len(signal_received) == 1


def test_load_clicked_signal(toolbar):
    """Test that load button emits signal."""
    signal_received = []
    toolbar.load_clicked.connect(lambda: signal_received.append(True))

    toolbar.load_button.click()
    assert len(signal_received) == 1


def test_history_clicked_signal(toolbar):
    """Test that history button emits signal."""
    signal_received = []
    toolbar.history_clicked.connect(lambda: signal_received.append(True))

    toolbar.history_button.click()
    assert len(signal_received) == 1


def test_delete_clicked_signal(toolbar):
    """Test that delete button emits signal when enabled."""
    signal_received = []
    toolbar.delete_clicked.connect(lambda: signal_received.append(True))

    toolbar.enable_delete(True)
    toolbar.delete_button.click()
    assert len(signal_received) == 1


def test_new_clicked_signal(toolbar):
    """Test that new button emits signal."""
    signal_received = []
    toolbar.new_clicked.connect(lambda: signal_received.append(True))

    toolbar.new_button.click()
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
