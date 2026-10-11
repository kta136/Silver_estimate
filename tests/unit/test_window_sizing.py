"""Minimum window sizes stay usable without leaving the screen."""

from types import SimpleNamespace

from silverestimate.ui.window_sizing import (
    TITLE_BAR_ALLOWANCE,
    set_usable_minimum_size,
)


class _Window:
    def __init__(self, width, height):
        self._available = SimpleNamespace(width=lambda: width, height=lambda: height)
        self.minimum = None

    def screen(self):
        return SimpleNamespace(availableGeometry=lambda: self._available)

    def setMinimumSize(self, width, height):
        self.minimum = (width, height)


def test_minimum_size_is_used_when_the_screen_has_room():
    window = _Window(1920, 1040)
    set_usable_minimum_size(window, width=1280, height=680)
    assert window.minimum == (1280, 680)


def test_minimum_size_never_exceeds_a_small_screen():
    # 1366x768 with a taskbar: the title bar must still fit above the window.
    window = _Window(1366, 728)
    set_usable_minimum_size(window, width=1280, height=720)
    assert window.minimum == (1280, 728 - TITLE_BAR_ALLOWANCE)

    tiny = _Window(1024, 560)
    set_usable_minimum_size(tiny, width=1280, height=680)
    assert tiny.minimum == (1024, 560 - TITLE_BAR_ALLOWANCE)
