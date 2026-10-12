import logging
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction

from silverestimate.infrastructure.app_constants import APP_TITLE
from silverestimate.ui.estimate_entry_logic.constants import (
    COL_CODE,
    COL_FINE_WT,
    COL_GROSS,
    COL_NET_WT,
    COL_POLY,
    COL_PURITY,
    COL_WAGE_AMT,
    COL_WAGE_RATE,
)
from silverestimate.ui.main_window import MainWindow


def test_close_stops_recovery_before_closing_database(main_window_fixture):
    context = main_window_fixture
    window, database = context["window"], context["db"]
    events = []
    window.estimate_widget.draft_recovery = SimpleNamespace(
        stop=lambda: events.append(("stop", database.closed)), flush=lambda: None
    )
    window.close()
    assert events == [("stop", False)]
    assert database.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Windows consoles only")
def test_closing_the_window_leaves_the_test_run_its_console(main_window_fixture):
    import ctypes

    # A process with no console reports code page 0. Without a console, each
    # process a later test starts would open a terminal window of its own.
    kernel32 = ctypes.windll.kernel32
    attached = kernel32.GetConsoleCP()

    main_window_fixture["window"].close()

    assert kernel32.GetConsoleCP() == attached


def test_sales_report_navigation_reuses_view_and_stops_reader_before_close(
    main_window_fixture, qtbot, tmp_path, monkeypatch
):
    from PySide6.QtCore import QDate

    from tests.sales_report_support import report_database

    window = main_window_fixture["window"]
    with report_database(tmp_path) as report_db:
        monkeypatch.setattr(
            window.db,
            "open_read_connection",
            report_db.open_read_connection,
            raising=False,
        )
        window.show()
        action = next(
            action
            for action in window.findChildren(QAction)
            if action.text() == "Sales &Reports"
        )
        action.trigger()
        report = window.sales_report_widget
        qtbot.waitUntil(lambda: not report._loading)
        assert window.stack.currentWidget() is report
        assert window._view_sales_report_action.isChecked()
        report.date_from.setDate(QDate(2026, 9, 30))
        report.date_to.setDate(QDate(2026, 10, 31))
        report.refresh()
        qtbot.waitUntil(lambda: not report._loading)
        assert report.total_labels[0].text() == "18.00 g"
        monkeypatch.setattr(
            window.estimate_widget, "open_saved_estimate", lambda voucher: False
        )
        report.voucher_requested.emit("2")
        assert window.stack.currentWidget() is report
        monkeypatch.setattr(
            window.estimate_widget, "open_saved_estimate", lambda voucher: True
        )
        report.voucher_requested.emit("2")
        assert window.stack.currentWidget() is window.estimate_widget
        action.trigger()
        qtbot.waitUntil(lambda: not report._loading)
        assert window.sales_report_widget is report
        assert report.date_from.date() == QDate(2026, 9, 30)
        events = []
        monkeypatch.setattr(
            window.db,
            "close",
            lambda: events.append(report._load_runner._thread.is_alive()),
        )
        window.close()
        assert events == [False]


def test_estimate_actions_dock_in_menu_bar_only_while_estimate_shows(
    main_window_fixture, qtbot, tmp_path, monkeypatch
):
    from tests.sales_report_support import report_database

    window = main_window_fixture["window"]
    estimate = window.estimate_widget
    strip = estimate.command_strip
    menu_bar = window.menuBar()
    with report_database(tmp_path) as report_db:
        monkeypatch.setattr(
            window.db,
            "open_read_connection",
            report_db.open_read_connection,
            raising=False,
        )
        window.show()
        qtbot.waitUntil(strip.isVisible)
        assert menu_bar.cornerWidget(Qt.Corner.TopRightCorner) is strip
        assert estimate.save_button.isVisible()
        assert estimate.unsaved_badge.parent() is strip
        # Nothing is left above the item table.
        assert estimate.layout().indexOf(strip) < 0
        qtbot.waitUntil(
            lambda: estimate.item_table.mapTo(estimate, QPoint(0, 0)).y() <= 6
        )
        assert estimate.toolbar.isVisible()

        window.show_sales_report()
        report = window.sales_report_widget
        qtbot.waitUntil(lambda: not report._loading)
        assert not strip.isVisible()
        assert menu_bar.cornerWidget(Qt.Corner.TopRightCorner) is None

        window.show_estimate()
        qtbot.waitUntil(strip.isVisible)
        assert menu_bar.cornerWidget(Qt.Corner.TopRightCorner) is strip
        window.close()


def test_estimate_tools_and_shortcut_help_remain_reachable_from_menu(
    main_window_fixture, monkeypatch
):
    window = main_window_fixture["window"]
    estimate = window.estimate_widget
    tools = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.text() == "&Tools"
    )
    assert any(
        action.menu() is estimate.estimate_tools_menu for action in tools.actions()
    )
    assert estimate.command_undo_row_action in estimate.estimate_tools_menu.actions()
    assert estimate.command_settings_action in estimate.estimate_tools_menu.actions()
    shortcut_action = next(
        action
        for action in window.findChildren(QAction)
        if action.text() == "&Keyboard Shortcuts"
    )
    assert shortcut_action.shortcut().toString() == "F1"
    captured = []
    monkeypatch.setattr(
        "silverestimate.ui.shortcuts_dialog.ShortcutsDialog.exec",
        lambda dialog: captured.append((dialog.windowTitle(), dialog.text())),
    )
    shortcut_action.trigger()
    assert captured[0][0] == "Keyboard Shortcuts"
    for shortcut in (
        "Ctrl+N",
        "Ctrl+H",
        "Ctrl+D",
        "Ctrl+Shift+D",
        "Ctrl+R",
        "Ctrl+B",
        "Page Up",
        "F5",
        "Ctrl+E",
        "Alt+E",
        "Alt+I",
        "Alt+R",
        "Alt+B",
    ):
        assert shortcut in captured[0][1]


@dataclass
class FakeDbManager:
    """In-memory stand-in for the real database manager."""

    items: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "RING001": {
                "code": "RING001",
                "name": "Sample Ring",
                "purity": 92.5,
                "wage_rate": 12.0,
                "wage_type": "WT",
            }
        }
    )
    generate_calls: int = 0
    preload_started: bool = False
    closed: bool = False

    def __post_init__(self) -> None:
        self.item_cache_controller = None

    # --- Lifecycle -------------------------------------------------
    def start_preload_item_cache(self) -> None:
        self.preload_started = True

    def close(self) -> None:
        self.closed = True

    # --- Estimate workflow ----------------------------------------
    def generate_voucher_no(self) -> str:
        self.generate_calls += 1
        return f"TST{self.generate_calls:03d}"

    def get_item_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self.items.get(code.strip().upper())

    def get_estimate_by_voucher(self, voucher_no: str) -> Optional[Dict[str, Any]]:
        return None

    def delete_single_estimate(self, voucher_no: str) -> bool:
        return True

    def delete_all_estimates(self) -> bool:
        return True

    def drop_tables(self) -> bool:
        return True

    def setup_database(self) -> bool:
        return True

    @property
    def last_error(self) -> Optional[str]:
        return None


class StubLiveRateController:
    """Lightweight replacement for the live rate controller used in tests."""

    instances: List["StubLiveRateController"] = []

    def __init__(self, *, parent, widget_getter, status_callback, logger=None, **_):
        self.parent = parent
        self.widget_getter = widget_getter
        self.status_callback = status_callback
        self.logger = logger
        self.initialize_called = False
        self.shutdown_called = False
        self.refresh_calls = 0
        self.visibility_calls = 0
        self.timer_calls = 0
        StubLiveRateController.instances.append(self)

    def initialize(self) -> None:
        self.initialize_called = True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def refresh_now(self) -> None:
        self.refresh_calls += 1

    def apply_visibility_settings(self) -> bool:
        self.visibility_calls += 1
        return True

    def apply_timer_settings(self, **_) -> None:
        self.timer_calls += 1


@pytest.fixture
def main_window_fixture(qtbot, qt_app, settings_stub, monkeypatch):
    """Create a MainWindow instance with test doubles injected."""
    previous_quit_on_close = qt_app.quitOnLastWindowClosed()
    qt_app.setQuitOnLastWindowClosed(False)
    StubLiveRateController.instances.clear()
    monkeypatch.setattr("PySide6.QtWidgets.QApplication.quit", lambda self=None: None)
    monkeypatch.setattr(
        "silverestimate.controllers.live_rate_controller.LiveRateController",
        StubLiveRateController,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.apply_taskbar_icon",
        lambda *args, **kwargs: 12345,
    )
    monkeypatch.setattr(
        "silverestimate.infrastructure.windows_integration.destroy_icon_handle",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry.EstimateEntryWidget.confirm_exit",
        lambda self: True,
    )
    monkeypatch.setattr(
        "silverestimate.ui.estimate_entry_table_controller."
        "EstimateEntryTableController._safe_edit_item",
        lambda self, *_: None,
    )

    db = FakeDbManager()
    logger = logging.getLogger("test.mainwindow")
    window = MainWindow(db_manager=db, logger=logger)
    qtbot.addWidget(window)
    live_rate = StubLiveRateController.instances[-1]

    try:
        yield {"window": window, "db": db, "live_rate": live_rate}
    finally:
        if window:
            window.close()
            window.deleteLater()
            qt_app.processEvents()
        qt_app.setQuitOnLastWindowClosed(previous_quit_on_close)
        StubLiveRateController.instances.clear()


@pytest.fixture
def menus_in_title_bar(monkeypatch):
    """Build the window as Windows does, and record its taskbar captions."""
    from silverestimate.ui import title_bar

    captions = []
    monkeypatch.setattr(title_bar, "supported", lambda: True)
    monkeypatch.setattr(
        title_bar, "set_native_caption", lambda _window, text: captions.append(text)
    )
    return captions


def test_menus_in_title_bar_replace_the_window_title(
    menus_in_title_bar, main_window_fixture, qtbot
):
    from silverestimate.ui import title_bar

    captions = menus_in_title_bar
    window = main_window_fixture["window"]
    bar = window.menuBar()

    assert isinstance(bar, title_bar.TitleMenuBar)
    assert window.windowFlags() & Qt.WindowType.ExpandedClientAreaHint
    assert [action.text() for action in bar.actions()][0] == "&File"
    # Qt would draw the title over the menus; the taskbar keeps the name.
    assert window.windowTitle() == title_bar.BLANK_TITLE
    assert window.accessibleName() == APP_TITLE
    assert captions[-1] == APP_TITLE

    window.estimate_widget._set_unsaved(True, force=True)
    assert window.isWindowModified()
    assert captions[-1] == f"{APP_TITLE}*"
    window.estimate_widget._set_unsaved(False, force=True)
    assert not window.isWindowModified()
    assert captions[-1] == APP_TITLE

    # Save, Print and New stop short of the window's own buttons.
    strip = window.estimate_widget.command_strip
    window.show()
    qtbot.waitUntil(strip.isVisible)
    assert bar.cornerWidget(Qt.Corner.TopRightCorner) is strip
    margins = strip.layout().contentsMargins()
    assert margins.right() == 4 + bar.caption_buttons_width()
    assert strip.minimumHeight() == bar.row_height()
    buttons = window.estimate_widget.primary_actions
    buttons_end = buttons.mapTo(bar, buttons.rect().topRight()).x()
    assert buttons_end <= bar.width() - bar.caption_buttons_width()


def test_ordinary_title_bar_keeps_the_strip_at_the_window_edge(
    main_window_fixture, qtbot
):
    from silverestimate.ui.title_bar import TitleMenuBar

    window = main_window_fixture["window"]
    strip = window.estimate_widget.command_strip
    window.show()
    qtbot.waitUntil(strip.isVisible)

    assert not isinstance(window.menuBar(), TitleMenuBar)
    assert strip.layout().contentsMargins().right() == 4
    window.estimate_widget._set_unsaved(True, force=True)
    assert window.isWindowModified()


def test_main_window_startup_sets_up_estimate_view(main_window_fixture, qt_app, qtbot):
    context = main_window_fixture
    window = context["window"]
    db = context["db"]
    live_rate = context["live_rate"]

    # Main view should be present and active.
    assert window.stack.currentWidget() is window.estimate_widget
    assert window.stack.count() == 1
    assert window.windowTitle() == f"{APP_TITLE}[*]"

    # Startup side effects.
    assert db.generate_calls == 1  # Voucher generated for initial form.
    assert db.preload_started is False
    assert live_rate.initialize_called is True

    # Main navigation wired (menu action created by controller).
    assert hasattr(window, "_menu_estimate_action")
    assert window._menu_estimate_action is not None
    # Screens carry a mark for the open one, so they have no icon to hide it.
    assert window._menu_estimate_action.isCheckable()
    assert window._menu_estimate_action.isChecked()
    assert window._menu_estimate_action.icon().isNull()
    assert not window.refresh_rate_action.icon().isNull()
    # Every destination appears in exactly one menu.
    labels = [
        action.text().split("	")[0].replace("&", "")
        for menu_action in window.menuBar().actions()
        for action in menu_action.menu().actions()
        if not action.isSeparator() and action.menu() is None
    ]
    assert len(labels) == len(set(labels)), labels
    assert [a.text() for a in window.menuBar().actions()] == [
        "&File",
        "&View",
        "&Tools",
        "Hi&story",
        "&Help",
    ]
    file_actions = {action.text(): action for action in window.findChildren(QAction)}
    assert file_actions["&Save"].shortcutContext() == Qt.ShortcutContext.WindowShortcut
    assert file_actions["&Print"].shortcutContext() == Qt.ShortcutContext.WindowShortcut

    widget = window.estimate_widget
    assert not widget.save_button.icon().isNull()
    assert not widget.print_button.icon().isNull()
    assert not widget.clear_button.icon().isNull()
    # The side panel's buttons are text only.
    for button in (
        widget.delete_row_button,
        widget.history_button,
        widget.last_balance_button,
        widget.silver_bars_button,
        widget.delete_estimate_button,
    ):
        assert button.icon().isNull()

    assert widget.save_button.text() == "Save  Ctrl+S"
    assert widget.print_button.text() == "Print"
    assert widget.clear_button.text() == "New"
    assert widget.delete_row_button.text() == "Delete Row"
    assert widget.return_toggle_button.text() == ""
    assert widget.silver_bar_toggle_button.text() == ""
    assert widget.history_button.text() == "History  Ctrl+H"
    assert widget.last_balance_button.text() == "Last Balance"
    assert widget.silver_bars_button.text() == "Silver Bars"
    assert widget.delete_estimate_button.text() == "Delete Estimate"

    assert widget.save_button.accessibleName() == "Save"
    assert widget.print_button.accessibleName() == "Print"
    assert widget.clear_button.accessibleName() == "New"
    assert widget.delete_row_button.accessibleName() == "Delete Row"
    assert widget.return_toggle_button.accessibleName() == "Return"
    assert widget.silver_bar_toggle_button.accessibleName() == "Bar Mode"
    assert widget.last_balance_button.accessibleName() == "Balance"
    assert widget.history_button.accessibleName() == "History"
    assert widget.silver_bars_button.accessibleName() == "Bar List"
    assert widget.delete_estimate_button.accessibleName() == "Delete Estimate"

    # Public helpers delegate to controller.
    window.reconfigure_rate_visibility_from_settings()
    assert live_rate.visibility_calls == 1

    window.reconfigure_rate_timer_from_settings()
    assert live_rate.timer_calls == 1

    # Closing should invoke live-rate shutdown and database close.
    window.close()
    qtbot.waitUntil(lambda: live_rate.shutdown_called is True, timeout=1000)
    qtbot.waitUntil(lambda: db.closed is True, timeout=1000)


def test_deferred_runtime_starts_after_lightweight_shell_paints(
    main_window_fixture, qt_app, qtbot
):
    db = FakeDbManager()
    window = MainWindow(
        db_manager=db,
        logger=logging.getLogger("test.mainwindow.deferred"),
        defer_runtime=True,
    )
    qtbot.addWidget(window)
    try:
        assert window.stack.currentWidget().objectName() == "StartupShell"
        assert not hasattr(window, "estimate_widget")
        assert window._loading_progress.minimum() == 0
        assert window._loading_progress.maximum() == 0

        window.show()
        qtbot.waitUntil(lambda: window._runtime_initialized, timeout=3000)

        assert window.stack.currentWidget() is window.estimate_widget
        assert window.stack.count() == 1
        assert db.generate_calls == 1
        assert window._runtime_services_initialized is False
        qtbot.waitUntil(
            lambda: window._runtime_services_initialized,
            timeout=3000,
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_user_entry_updates_totals_and_save_snapshot(main_window_fixture, qtbot):
    context = main_window_fixture
    window = context["window"]
    db = context["db"]

    widget = window.estimate_widget
    table = widget.item_table

    qtbot.waitUntil(lambda: table.rowCount() > 0, timeout=1500)

    # Simulate entering an item code the way the presenter expects.
    assert widget.presenter.handle_item_code(0, "RING001") is True
    qtbot.waitUntil(
        lambda: table.get_cell_text(0, COL_CODE).strip().upper() == "RING001",
        timeout=1500,
    )

    # Populate user-editable values.
    widget.current_row = 0
    table.set_cell_text(0, COL_GROSS, "10")
    table.set_cell_text(0, COL_POLY, "0.5")
    table.set_cell_text(0, COL_PURITY, "92.5")
    table.set_cell_text(0, COL_WAGE_RATE, "12")

    # Trigger chained calculations (net, fine, wage, totals).
    widget.totals_controller.calculate_net_weight()
    widget.totals_controller.calculate_totals()
    qtbot.waitUntil(
        lambda: table.get_cell_text(0, COL_WAGE_AMT).strip() not in {"", "0", "0.0"},
        timeout=1500,
    )

    # Row cells reflect calculated values.
    assert float(table.get_cell_text(0, COL_NET_WT)) == pytest.approx(9.5, rel=1e-3)
    assert float(table.get_cell_text(0, COL_FINE_WT)) == pytest.approx(8.79, rel=1e-3)
    assert float(table.get_cell_text(0, COL_WAGE_AMT)) == pytest.approx(114.0)

    # Totals panel displays computed aggregates.
    assert float(widget.overall_gross_label.text()) == pytest.approx(10.0)
    assert float(widget.overall_poly_label.text()) == pytest.approx(0.5)
    assert float(widget.total_net_label.text()) == pytest.approx(9.5)
    assert float(widget.total_fine_label.text()) == pytest.approx(8.79, rel=1e-3)
    assert float(widget.net_fine_label.text()) == pytest.approx(8.79, rel=1e-3)

    # The save snapshot captures the active row for downstream workflows.
    snapshot = widget.workflow_controller._capture_snapshot()
    active_rows = [row for row in snapshot.rows if not row.is_empty()]
    assert len(active_rows) == 1
    row_state = active_rows[0]
    assert row_state.code == "RING001"
    assert row_state.gross == pytest.approx(10.0)
    assert row_state.poly == pytest.approx(0.5)
    assert row_state.net_weight == pytest.approx(9.5)
    assert row_state.fine_weight == pytest.approx(8.7875, rel=1e-3)

    # No extra voucher generation during interactions.
    assert db.generate_calls == 1


def test_saved_and_deleted_outcomes_are_shown_in_a_toast(main_window_fixture, qtbot):
    window = main_window_fixture["window"]
    window.show()
    qtbot.waitUntil(window.isVisible)

    window.estimate_widget._notify("Estimate '7' saved successfully.", 5000)

    toast = window.status_toast
    assert toast.isVisible()
    assert toast.text() == "Estimate '7' saved successfully."
    # Routine progress is not turned into a toast.
    window.estimate_widget._status("Preparing print preview...", 2000)
    assert toast.text() == "Estimate '7' saved successfully."
    window.close()


def test_a_toast_does_not_follow_the_user_to_another_screen(main_window_fixture, qtbot):
    window = main_window_fixture["window"]
    window.show()
    qtbot.waitUntil(window.isVisible)

    window.estimate_widget._notify("Row 3 deleted.", 5000)
    assert window.status_toast.isVisible()

    window.stack.currentChanged.emit(window.stack.currentIndex())
    assert not window.status_toast.isVisible()
    window.close()
