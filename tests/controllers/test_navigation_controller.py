import logging
import sys
import types

from silverestimate.controllers.navigation_controller import NavigationController


def _navigation(main_window, stack, logger_name):
    main_window.stack = stack
    return NavigationController(
        main_window=main_window,
        commands=None,
        logger=logging.getLogger(logger_name),
    )


class _ActionStub:
    def __init__(self):
        self.checked = False

    def setChecked(self, value):
        self.checked = bool(value)


class _StackStub:
    def __init__(self):
        self.current = None
        self.added = []
        self.removed = []

    def setCurrentWidget(self, widget):
        self.current = widget

    def currentWidget(self):
        return self.current

    def addWidget(self, widget):
        self.added.append(widget)

    def removeWidget(self, widget):
        self.removed.append(widget)


class _MessageBoxRecorder:
    def __init__(self):
        self.calls = []

    def critical(self, *args):
        self.calls.append(args)


def test_show_estimate_switches_widget(monkeypatch):
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        message_box,
    )

    stack = _StackStub()
    estimate_widget = object()
    main_window = types.SimpleNamespace(
        estimate_widget=estimate_widget,
        nav_estimate_action=_ActionStub(),
        _menu_estimate_action=_ActionStub(),
        _view_estimate_action=_ActionStub(),
    )

    service = _navigation(main_window, stack, "test-nav")
    service.show_estimate()

    assert stack.current is estimate_widget
    assert main_window.nav_estimate_action.checked is True
    assert main_window._menu_estimate_action.checked is True
    assert main_window._view_estimate_action.checked is True
    assert message_box.calls == []


def test_show_item_master_lazy_creation(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        message_box,
    )

    created = {}

    class _ItemMasterWidget:
        def __init__(self, db, main_window):
            created["db"] = db
            created["main_window"] = main_window

    monkeypatch.setitem(
        sys.modules,
        "silverestimate.ui.item_master",
        types.SimpleNamespace(ItemMasterWidget=_ItemMasterWidget),
    )

    main_window = types.SimpleNamespace(
        db=object(),
        nav_item_master_action=_ActionStub(),
        _menu_item_master_action=_ActionStub(),
        _view_item_master_action=_ActionStub(),
    )

    service = _navigation(main_window, stack, "test-nav-item")
    service.show_item_master()

    widget = main_window.item_master_widget
    assert widget is not None
    assert created["db"] is main_window.db
    assert created["main_window"] is main_window
    assert stack.current is widget
    assert widget in stack.added
    assert main_window.nav_item_master_action.checked is True
    assert message_box.calls == []


def test_show_item_master_failure_shows_message(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        message_box,
    )

    class _BrokenWidget:
        def __init__(self, db, main_window):  # noqa: ARG002
            raise RuntimeError("boom")

    monkeypatch.setitem(
        sys.modules,
        "silverestimate.ui.item_master",
        types.SimpleNamespace(ItemMasterWidget=_BrokenWidget),
    )

    main_window = types.SimpleNamespace(
        db=object(),
        nav_item_master_action=_ActionStub(),
        _menu_item_master_action=_ActionStub(),
        _view_item_master_action=_ActionStub(),
    )

    service = _navigation(main_window, stack, "test-nav-item-fail")
    service.show_item_master()

    assert message_box.calls
    # Ensure the stack was not updated to a new widget
    assert stack.current is None


class _SignalStub:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self):
        for callback in list(self.callbacks):
            callback()


class _SilverBarsStub:
    """Stands in for the real screen and records how it is built and released."""

    instances = []

    def __init__(self, db, main_window):
        self.db = db
        self.main_window = main_window
        self.close_requested = _SignalStub()
        self.busy = False
        self.events = []
        type(self).instances.append(self)

    def can_close(self):
        return not self.busy

    def shutdown(self):
        self.events.append("shutdown")

    def deleteLater(self):
        self.events.append("deleteLater")

    def print_selected_list(self):
        self.events.append("print")

    def show_keyboard_help(self):
        self.events.append("help")


def _silver_bars_setup(monkeypatch):
    _SilverBarsStub.instances = []
    module = types.SimpleNamespace(SilverBarWidget=_SilverBarsStub)
    monkeypatch.setitem(sys.modules, "silverestimate.ui.silver_bar_management", module)
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        _MessageBoxRecorder(),
    )
    stack = _StackStub()
    estimate = object()
    main_window = types.SimpleNamespace(
        db=object(),
        estimate_widget=estimate,
        silver_bar_widget=None,
        _view_estimate_action=_ActionStub(),
        _view_silver_bars_action=_ActionStub(),
    )
    commands = types.SimpleNamespace(printed=[])
    commands.print_estimate = lambda: commands.printed.append("estimate")
    service = _navigation(main_window, stack, "test-silver")
    service._commands = commands
    return service, main_window, stack, estimate, commands


def test_silver_bars_are_built_only_when_opened(monkeypatch):
    service, main_window, stack, estimate, _ = _silver_bars_setup(monkeypatch)
    service.show_estimate()

    # Nothing of the screen exists until the user asks for it.
    assert _SilverBarsStub.instances == []
    assert main_window.silver_bar_widget is None

    service.show_silver_bars()

    (screen,) = _SilverBarsStub.instances
    assert screen.db is main_window.db
    assert screen.main_window is main_window
    assert main_window.silver_bar_widget is screen
    assert stack.added == [screen]
    assert stack.current is screen
    assert main_window._view_silver_bars_action.checked is True

    # Opening it again shows the same screen; it is not built twice.
    service.show_silver_bars()
    assert len(_SilverBarsStub.instances) == 1
    assert stack.added == [screen]


def test_silver_bars_cannot_be_left_while_a_print_is_under_way(monkeypatch):
    service, main_window, stack, estimate, _ = _silver_bars_setup(monkeypatch)
    service.show_silver_bars()
    (screen,) = _SilverBarsStub.instances
    screen.busy = True

    service.show_estimate()

    assert stack.current is screen
    assert main_window.silver_bar_widget is screen
    assert screen.events == []

    screen.busy = False
    service.show_estimate()
    assert stack.current is estimate
    assert screen.events == ["shutdown", "deleteLater"]


def test_print_and_help_go_to_the_open_silver_bars_screen(monkeypatch):
    service, main_window, stack, estimate, commands = _silver_bars_setup(monkeypatch)

    # On any other screen File > Print still prints the estimate.
    service.show_estimate()
    service.print_open_screen()
    assert commands.printed == ["estimate"]

    service.show_silver_bars()
    (screen,) = _SilverBarsStub.instances
    service.print_open_screen()
    service.show_keyboard_shortcuts()

    assert commands.printed == ["estimate"]
    assert screen.events == ["print", "help"]


def test_show_silver_bars_requires_database(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        message_box,
    )

    main_window = types.SimpleNamespace(_view_silver_bars_action=_ActionStub())

    service = _navigation(main_window, stack, "test-silver-db")
    service._db = None

    service.show_silver_bars()

    assert message_box.calls


def test_show_estimate_history_loads_selected_voucher(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.controllers.navigation_controller.QMessageBox",
        message_box,
    )

    class _EstimateWidget:
        def __init__(self):
            self.calls = []

        def show_history(self):
            self.calls.append("history")

    estimate_widget = _EstimateWidget()

    main_window = types.SimpleNamespace(
        estimate_widget=estimate_widget,
    )

    service = _navigation(main_window, stack, "test-history")
    show_calls = []
    service.show_estimate = lambda: show_calls.append("show")

    service.show_estimate_history()

    assert estimate_widget.calls == ["history"]
    assert show_calls == ["show"]
    assert message_box.calls == []
