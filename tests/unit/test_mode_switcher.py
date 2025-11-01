"""Tests for ModeSwitcher component."""

import pytest

from silverestimate.ui.estimate_entry_components.mode_switcher import ModeSwitcher


@pytest.fixture
def switcher(qt_app):
    """Create a fresh ModeSwitcher for testing."""
    return ModeSwitcher()


def test_initial_state(switcher):
    """Test that switcher initializes with both modes off."""
    assert not switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()
    assert not switcher.return_toggle_button.isChecked()
    assert not switcher.silver_bar_toggle_button.isChecked()


def test_set_return_mode(switcher):
    """Test setting return mode."""
    switcher.set_return_mode(True)
    assert switcher.get_return_mode()
    assert switcher.return_toggle_button.isChecked()

    switcher.set_return_mode(False)
    assert not switcher.get_return_mode()
    assert not switcher.return_toggle_button.isChecked()


def test_set_silver_bar_mode(switcher):
    """Test setting silver bar mode."""
    switcher.set_silver_bar_mode(True)
    assert switcher.get_silver_bar_mode()
    assert switcher.silver_bar_toggle_button.isChecked()

    switcher.set_silver_bar_mode(False)
    assert not switcher.get_silver_bar_mode()
    assert not switcher.silver_bar_toggle_button.isChecked()


def test_mutual_exclusivity_return_first(switcher):
    """Test that enabling return mode disables silver bar mode."""
    # Enable silver bar mode first
    switcher.set_silver_bar_mode(True)
    assert switcher.get_silver_bar_mode()
    assert not switcher.get_return_mode()

    # Now enable return mode
    switcher.set_return_mode(True)

    # Return mode should be on, silver bar should be off
    assert switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()


def test_mutual_exclusivity_silver_bar_first(switcher):
    """Test that enabling silver bar mode disables return mode."""
    # Enable return mode first
    switcher.set_return_mode(True)
    assert switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()

    # Now enable silver bar mode
    switcher.set_silver_bar_mode(True)

    # Silver bar mode should be on, return should be off
    assert switcher.get_silver_bar_mode()
    assert not switcher.get_return_mode()


def test_reset_modes(switcher):
    """Test resetting both modes."""
    # Enable both (though they're mutually exclusive)
    switcher.set_return_mode(True)
    switcher.set_silver_bar_mode(True)

    # Reset
    switcher.reset_modes()

    # Both should be off
    assert not switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()


def test_return_mode_toggled_signal(switcher):
    """Test that return mode toggle emits signal."""
    states = []
    switcher.return_mode_toggled.connect(lambda s: states.append(s))

    switcher.return_toggle_button.setChecked(True)
    assert len(states) > 0
    assert states[-1] is True

    switcher.return_toggle_button.setChecked(False)
    assert states[-1] is False


def test_silver_bar_mode_toggled_signal(switcher):
    """Test that silver bar mode toggle emits signal."""
    states = []
    switcher.silver_bar_mode_toggled.connect(lambda s: states.append(s))

    switcher.silver_bar_toggle_button.setChecked(True)
    assert len(states) > 0
    assert states[-1] is True

    switcher.silver_bar_toggle_button.setChecked(False)
    assert states[-1] is False


def test_toggle_return_mode_programmatically(switcher):
    """Test toggling return mode via internal method."""
    assert not switcher.get_return_mode()

    switcher._toggle_return_mode()
    assert switcher.get_return_mode()

    switcher._toggle_return_mode()
    assert not switcher.get_return_mode()


def test_toggle_silver_bar_mode_programmatically(switcher):
    """Test toggling silver bar mode via internal method."""
    assert not switcher.get_silver_bar_mode()

    switcher._toggle_silver_bar_mode()
    assert switcher.get_silver_bar_mode()

    switcher._toggle_silver_bar_mode()
    assert not switcher.get_silver_bar_mode()


def test_button_click_triggers_toggle(switcher):
    """Test that clicking buttons toggles modes."""
    assert not switcher.get_return_mode()

    switcher.return_toggle_button.click()
    assert switcher.get_return_mode()

    switcher.return_toggle_button.click()
    assert not switcher.get_return_mode()


def test_mutual_exclusivity_via_button_clicks(switcher):
    """Test mutual exclusivity when clicking buttons."""
    # Click return mode button
    switcher.return_toggle_button.click()
    assert switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()

    # Click silver bar button
    switcher.silver_bar_toggle_button.click()
    assert not switcher.get_return_mode()
    assert switcher.get_silver_bar_mode()

    # Click return mode button again
    switcher.return_toggle_button.click()
    assert switcher.get_return_mode()
    assert not switcher.get_silver_bar_mode()
