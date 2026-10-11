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
    assert toolbar.mode_index() == 0
    assert toolbar.mode_buttons.checkedButton().text() == "Regular"
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


def test_mode_buttons_emit_selection_and_follow_set_mode_index(toolbar, qtbot):
    with qtbot.waitSignal(toolbar.mode_selected) as blocker:
        toolbar.mode_buttons.button(2).click()
    assert blocker.args == [2]

    received = []
    toolbar.mode_selected.connect(received.append)
    toolbar.set_mode_index(1)
    assert toolbar.mode_index() == 1
    assert received == []


def test_card_holds_the_fields_and_leaves_badge_and_mode_switch_to_the_owner(
    toolbar,
):
    layout = toolbar.layout()
    for widget in (
        toolbar.date_edit,
        toolbar.silver_rate_spin,
        toolbar.note_edit,
    ):
        assert layout.indexOf(widget) >= 0
    # The status badge goes beside Save, the mode switch below the card.
    assert layout.indexOf(toolbar.unsaved_badge) < 0
    assert layout.indexOf(toolbar.mode_selector) < 0
    assert [
        label.text()
        for label in (
            toolbar.voucher_label,
            toolbar.date_label,
            toolbar.rate_label,
            toolbar.note_label,
        )
    ] == ["Voucher", "Date", "Rate ₹/g", "Note"]


def test_rate_companion_sits_beside_the_rate_field(toolbar, qtbot):
    from PySide6.QtWidgets import QLabel

    live_rate = QLabel("128.40")
    toolbar.set_rate_companion(live_rate)
    toolbar.resize(320, toolbar.sizeHint().height())
    toolbar.show()
    qtbot.wait(10)

    assert live_rate.parent() is toolbar
    assert live_rate.isVisible()
    assert live_rate.x() > toolbar.silver_rate_spin.geometry().right()


def test_mode_labels_shorten_to_fit_the_switch(toolbar, qtbot):
    selector = toolbar.mode_selector
    toolbar.show()
    selector.show()

    def texts():
        return [button.text() for button in toolbar.mode_buttons.buttons()]

    def assert_no_label_is_clipped():
        for button in toolbar.mode_buttons.buttons():
            assert button.width() >= button.sizeHint().width(), button.text()

    selector.resize(600, 30)
    qtbot.wait(10)
    assert texts() == ["Regular", "Return  Ctrl+R", "Silver Bar  Ctrl+B"]
    assert_no_label_is_clipped()

    # Too narrow for the shortcuts: the switch drops them (they stay in the
    # tooltips) instead of clipping a label or widening the side panel.
    hinted = sum(button.sizeHint().width() for button in toolbar.mode_buttons.buttons())
    selector.resize(hinted - 20, 30)
    qtbot.wait(10)
    assert texts() == ["Regular", "Return", "Silver Bar"]
    assert_no_label_is_clipped()
    assert selector.minimumSizeHint().width() < hinted

    # Narrower still: only then is "Silver Bar" shortened.
    plain = sum(button.sizeHint().width() for button in toolbar.mode_buttons.buttons())
    selector.resize(plain - 10, 30)
    qtbot.wait(10)
    assert texts() == ["Regular", "Return", "Bar"]
