"""Silver Bars is a View-menu screen: built when opened, discarded when left."""

import threading

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QDialog
from shiboken6 import isValid

from silverestimate.persistence.silver_bar_query_repository import (
    SilverBarsSnapshotRepository,
)
from silverestimate.ui.print_manager import PrintManager
from silverestimate.ui.print_preview_output import PrintOutputOutcome, PrintOutputStatus
from silverestimate.ui.silver_bar_history import SilverBarHistoryDialog
from silverestimate.ui.silver_bar_management import SilverBarWidget
from tests.silver_bar_workspace_support import bar_list_count, seed_workspace_db
from tests.ui.test_main_window_interactions import (  # noqa: F401
    main_window_fixture,
)


@pytest.fixture
def screens(main_window_fixture, qtbot, tmp_path):  # noqa: F811
    """The main window, with a real silver bar inventory behind its screens."""
    window = main_window_fixture["window"]
    db = seed_workspace_db(tmp_path)
    window.navigation_controller._db = db
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    yield window, db
    if window.silver_bar_widget is not None:
        window.silver_bar_widget.shutdown()
    db.close()


def _released(widget) -> bool:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return not isValid(widget)


def _menu_actions(window, title):
    menu = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.text().replace("&", "") == title
    )
    return [a for a in menu.actions() if not a.isSeparator() and a.menu() is None]


def test_silver_bars_sits_in_the_view_menu_not_the_tools_menu(screens):
    window, _ = screens

    view = {a.text().replace("&", ""): a for a in _menu_actions(window, "View")}
    tools = [a.text().replace("&", "") for a in _menu_actions(window, "Tools")]

    action = view["Silver Bars"]
    assert action.isCheckable()
    assert action.icon().isNull()
    assert action.shortcut().toString() == "Alt+B"
    assert not any("Silver Bars" in text for text in tools)
    assert list(view) == [
        "Estimate Entry",
        "Item Master",
        "Sales Reports",
        "Silver Bars",
    ]


def test_the_screen_is_built_on_open_and_discarded_on_leaving(screens, qtbot):
    window, _ = screens
    assert window.silver_bar_widget is None
    assert window.stack.count() == 1

    window._view_silver_bars_action.trigger()

    screen = window.silver_bar_widget
    assert isinstance(screen, SilverBarWidget)
    assert window.stack.count() == 2
    assert window.stack.currentWidget() is screen
    assert window._view_silver_bars_action.isChecked()
    qtbot.waitUntil(screen.weight_search_edit.hasFocus)

    window._view_item_master_action.trigger()

    assert window.stack.currentWidget() is window.item_master_widget
    assert window.silver_bar_widget is None
    assert window.stack.indexOf(screen) == -1
    assert screen._load_controller.shutdown_called
    qtbot.waitUntil(lambda: _released(screen))
    # Item Master stays loaded once opened; only Silver Bars is let go.
    assert window.stack.count() == 2

    window._view_silver_bars_action.trigger()
    assert window.silver_bar_widget is not screen
    assert isValid(window.silver_bar_widget)


def test_the_close_button_and_escape_go_back_to_the_estimate(screens, qtbot):
    window, _ = screens
    window.show_silver_bars()
    screen = window.silver_bar_widget

    screen.close_button.click()

    assert window.stack.currentWidget() is window.estimate_widget
    assert window._view_estimate_action.isChecked()
    assert window.silver_bar_widget is None

    window.show_silver_bars()
    screen = window.silver_bar_widget
    qtbot.waitUntil(screen.weight_search_edit.hasFocus)
    for _ in range(4):
        if window.silver_bar_widget is None:
            break
        qtbot.keyClick(screen.weight_search_edit, Qt.Key.Key_Escape)
        qtbot.wait(60)
    assert window.silver_bar_widget is None
    assert window.stack.currentWidget() is window.estimate_widget


def test_the_estimate_keeps_what_was_typed_while_silver_bars_is_open(screens, qtbot):
    window, _ = screens
    window.estimate_widget.note_edit.setText("Customer A")

    window.show_silver_bars()
    window.show_estimate()

    assert window.estimate_widget.note_edit.text() == "Customer A"


def test_ctrl_p_and_f1_reach_the_open_screen_despite_the_menu_shortcuts(
    screens, qtbot, monkeypatch
):
    # File > Print and Help > Keyboard Shortcuts own Ctrl+P and F1 for the whole
    # window; a second shortcut on the same key would leave both dead.
    window, db = screens
    window.show_silver_bars()
    screen = window.silver_bar_widget
    screen.apply_snapshot(db.add_bars_to_list([1, 6]).unwrap())
    list_id = screen.current_list_id
    qtbot.waitUntil(screen.weight_search_edit.hasFocus)
    help_calls = []
    monkeypatch.setattr(
        SilverBarWidget, "show_keyboard_help", lambda self: help_calls.append("help")
    )
    monkeypatch.setattr(
        QDialog, "exec", lambda self: pytest.fail("the app shortcut list opened")
    )
    monkeypatch.setattr(
        PrintManager,
        "quick_print",
        lambda *a: PrintOutputOutcome(PrintOutputStatus.SUCCESS),
    )

    qtbot.keyClick(screen.weight_search_edit, Qt.Key.Key_F1)
    assert help_calls == ["help"]

    qtbot.keyClick(
        screen.weight_search_edit, Qt.Key.Key_P, Qt.KeyboardModifier.ControlModifier
    )
    qtbot.waitUntil(lambda: screen.current_list_id is None)
    assert db.get_silver_bar_list_snapshot(list_id).issued
    assert bar_list_count(db) == 1


def test_alt_b_opens_the_screen_from_any_screen(screens, qtbot):
    window, _ = screens

    qtbot.keyClick(window, Qt.Key.Key_B, Qt.KeyboardModifier.AltModifier)

    assert isinstance(window.silver_bar_widget, SilverBarWidget)
    assert window.stack.currentWidget() is window.silver_bar_widget


def test_a_list_chosen_in_silver_bar_history_opens_in_the_screen(
    screens, qtbot, monkeypatch
):
    window, db = screens
    active = db.add_bars_to_list([2, 3]).unwrap()

    def choose(dialog):
        dialog.selected_list_id = active.list_id
        # Close it as exec() would, which also stops its background loading.
        dialog.done(QDialog.DialogCode.Accepted)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(SilverBarHistoryDialog, "exec", choose)

    window.show_silver_bar_history()

    screen = window.silver_bar_widget
    assert window.stack.currentWidget() is screen
    qtbot.waitUntil(lambda: screen.current_list_id == active.list_id)
    qtbot.waitUntil(lambda: screen.list_bars_model.rowCount() == 2)


def test_closing_the_application_stops_an_open_silver_bars_screen(screens, qtbot):
    window, _ = screens
    window.show_silver_bars()
    screen = window.silver_bar_widget

    window.close()

    assert screen._closed
    assert screen._load_controller.shutdown_called


def test_leaving_while_bars_are_still_loading_stops_the_search_cleanly(
    screens, qtbot, monkeypatch
):
    started, release = threading.Event(), threading.Event()
    original = SilverBarsSnapshotRepository.search_weight_prefix

    def slow(*args, **kwargs):
        started.set()
        release.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(SilverBarsSnapshotRepository, "search_weight_prefix", slow)
    window, _ = screens
    window.show_silver_bars()
    screen = window.silver_bar_widget
    runner = screen._load_controller.search_runner
    qtbot.waitUntil(started.is_set)

    # A cancelled query ends soon after; leaving waits for that, then lets go.
    threading.Timer(0.15, release.set).start()
    window.show_estimate()

    assert window.silver_bar_widget is None
    qtbot.waitUntil(lambda: not runner._thread.is_alive())
    qtbot.waitUntil(lambda: _released(screen))
