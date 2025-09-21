import logging
import sys
import types

from PyQt5.QtWidgets import QDialog

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

def test_show_silver_bars_lazy_creation(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.services.navigation_service.QMessageBox",
        message_box,
    )

    created = {}
    load_calls = []

    class _SilverBarDialog:
        def __init__(self, db, main_window):
            created["db"] = db
            created["main_window"] = main_window

        def load_available_bars(self):
            load_calls.append("available")

        def load_bars_in_selected_list(self):
            load_calls.append("selected")

    module = types.SimpleNamespace(SilverBarDialog=_SilverBarDialog)
    monkeypatch.setitem(sys.modules, "silverestimate.ui.silver_bar_management", module)

    main_window = types.SimpleNamespace(
        db=object(),
        nav_silver_action=_ActionStub(),
        _menu_silver_action=_ActionStub(),
        _view_silver_bars_action=_ActionStub(),
    )

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-silver"))
    service.show_silver_bars()

    widget = getattr(main_window, "silver_bar_widget")
    assert widget is not None
    assert stack.current is widget
    assert widget in stack.added
    assert created["db"] is main_window.db
    assert load_calls == ["available", "selected"]
    assert message_box.calls == []


def test_show_silver_bars_requires_database(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.services.navigation_service.QMessageBox",
        message_box,
    )

    main_window = types.SimpleNamespace(
        nav_silver_action=_ActionStub(),
        _menu_silver_action=_ActionStub(),
        _view_silver_bars_action=_ActionStub(),
    )

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-silver-db"))
    service.db = None

    service.show_silver_bars()

    assert message_box.calls


def test_show_estimate_history_loads_selected_voucher(monkeypatch):
    stack = _StackStub()
    message_box = _MessageBoxRecorder()
    monkeypatch.setattr(
        "silverestimate.services.navigation_service.QMessageBox",
        message_box,
    )

    voucher_calls = []

    class _Voucher:
        def setText(self, value):
            voucher_calls.append(value)

    load_calls = []

    class _EstimateWidget:
        def __init__(self):
            self.voucher_edit = _Voucher()

        def safe_load_estimate(self):
            load_calls.append("safe")

    estimate_widget = _EstimateWidget()

    main_window = types.SimpleNamespace(
        estimate_widget=estimate_widget,
    )

    class _HistoryDialog:
        def __init__(self, db, main_window_ref, parent):
            self.selected_voucher = "V123"

        def exec_(self):
            return QDialog.Accepted

    monkeypatch.setitem(
        sys.modules,
        "silverestimate.ui.estimate_history",
        types.SimpleNamespace(EstimateHistoryDialog=_HistoryDialog),
    )

    service = NavigationService(main_window, stack, logger=logging.getLogger("test-history"))
    show_calls = []
    service.show_estimate = lambda: show_calls.append("show")

    service.show_estimate_history()

    assert voucher_calls == ["V123"]
    assert load_calls == ["safe"]
    assert show_calls == ["show"]
    assert message_box.calls == []
