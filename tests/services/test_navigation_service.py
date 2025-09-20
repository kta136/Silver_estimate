import logging
import sys
import types

from silverestimate.services.navigation_service import NavigationService


class _ActionStub:
    def __init__(self):
        self.checked = False

    def setChecked(self, value):
        self.checked = bool(value)


class _StackStub:
    def __init__(self):
        self.current = None
        self.added = []

    def setCurrentWidget(self, widget):
        self.current = widget

    def addWidget(self, widget):
        self.added.append(widget)


class _MessageBoxRecorder:
    def __init__(self):
        self.calls = []

    def critical(self, *args):
        self.calls.append(args)


def test_show_estimate_switches_widget(monkeypatch):
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.services.navigation_service.QMessageBox",
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

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-nav"))
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
        "silverestimate.services.navigation_service.QMessageBox",
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

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-nav-item"))
    service.show_item_master()

    widget = getattr(main_window, "item_master_widget")
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
        "silverestimate.services.navigation_service.QMessageBox",
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

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-nav-item-fail"))
    service.show_item_master()

    assert message_box.calls
    # Ensure the stack was not updated to a new widget
    assert stack.current is None
