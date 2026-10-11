"""The brief outcome message shown over the bottom of a window."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from silverestimate.ui.status_toast import StatusToast


def _host(qtbot) -> QWidget:
    host = QWidget()
    qtbot.addWidget(host)
    host.resize(800, 500)
    host.show()
    return host


def test_toast_shows_a_message_at_the_bottom_and_clears_itself(qtbot):
    host = _host(qtbot)
    toast = StatusToast(host)
    assert not toast.isVisible()

    toast.show_message("Estimate '12' saved successfully.", timeout=40)

    assert toast.isVisible()
    assert toast.text() == "Estimate '12' saved successfully."
    # Bottom centre, inside the window.
    assert toast.geometry().bottom() < host.height()
    assert toast.geometry().top() > host.height() // 2
    assert abs(toast.geometry().center().x() - host.width() // 2) <= 2
    # It never blocks the table or buttons underneath.
    assert toast.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    qtbot.waitUntil(lambda: not toast.isVisible(), timeout=1000)
    assert toast.text() == ""


def test_toast_marks_errors_and_follows_the_window_size(qtbot):
    host = _host(qtbot)
    toast = StatusToast(host)

    toast.show_message("Item could not be saved.", timeout=0, level="error")
    assert toast.property("statusLevel") == "error"
    before = toast.geometry()

    host.resize(1000, 640)
    qtbot.waitUntil(lambda: toast.geometry() != before, timeout=1000)
    assert toast.geometry().bottom() < host.height()
    assert abs(toast.geometry().center().x() - host.width() // 2) <= 2

    toast.show_message("")
    assert not toast.isVisible()


def test_the_first_toast_is_tall_enough_under_the_app_theme(
    qtbot, qt_application_state
):
    from silverestimate.ui.application_theme import apply_light_application_theme

    apply_light_application_theme(qt_application_state)
    host = _host(qtbot)
    toast = StatusToast(host)

    toast.show_message("Row 3 deleted. Press Ctrl+Shift+D to undo.", timeout=0)
    first = toast.height()
    toast.show_message("Row 3 deleted. Press Ctrl+Shift+D to undo.", timeout=0)

    # The very first message used to be measured before the theme's font and
    # padding applied, which cut its text in half.
    assert first == toast.height()
    assert first > toast.fontMetrics().height() + 8


def test_long_messages_stay_inside_a_narrow_window(qtbot):
    host = _host(qtbot)
    host.resize(320, 300)
    toast = StatusToast(host)

    toast.show_message("Row 12 deleted. Press Ctrl+Shift+D to undo. " * 3, timeout=0)

    assert toast.geometry().left() >= 0
    assert toast.geometry().right() <= host.width()
    assert toast.geometry().top() >= 0


def test_a_short_message_stays_on_one_line(qtbot):
    host = _host(qtbot)
    toast = StatusToast(host)

    toast.show_message("Row 3 deleted. Press Ctrl+Shift+D to undo.", timeout=0)

    one_line = toast.fontMetrics().height()
    assert toast.height() < 2 * one_line + 20
