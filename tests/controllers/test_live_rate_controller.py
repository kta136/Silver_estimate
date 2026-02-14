import logging
import types

from PyQt5.QtCore import QObject

from silverestimate.controllers.live_rate_controller import LiveRateController


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _ServiceStub:
    def __init__(self):
        self.rate_updated = _Signal()
        self.start_calls = 0
        self.stop_calls = 0
        self.refresh_calls = 0
        self.raise_on_refresh = False

    def start(self):
        self.start_calls += 1

    def stop(self):
        self.stop_calls += 1

    def refresh_now(self):
        self.refresh_calls += 1
        if self.raise_on_refresh:
            raise RuntimeError("refresh boom")


class _LabelStub:
    def __init__(self, text=""):
        self.visible = True
        self._text = text
        self.tooltip = ""

    def setVisible(self, visible):
        self.visible = bool(visible)

    def setText(self, text):
        self._text = str(text)

    def text(self):
        return self._text

    def setToolTip(self, text):
        self.tooltip = str(text)


class _WidgetStub:
    def __init__(self):
        self.live_rate_label = _LabelStub()
        self.live_rate_value_label = _LabelStub("-")
        self.live_rate_meta_label = _LabelStub("")
        self.refresh_rate_button = _LabelStub()
        self.refresh_calls = 0

    def refresh_silver_rate(self):
        self.refresh_calls += 1


class _SettingsStub:
    def __init__(self, values):
        self.values = dict(values)

    def value(self, key, default=None):
        return self.values.get(key, default)


def _build_controller(
    *, settings, service=None, widget=None, status=None, single_shot=None
):
    service = service or _ServiceStub()
    widget = widget
    status = status if status is not None else []

    def service_factory(**kwargs):
        return service

    controller = LiveRateController(
        parent=QObject(),
        widget_getter=(lambda: widget),
        status_callback=(lambda *args: status.append(args)),
        logger=logging.getLogger("test.live_rate_controller"),
        service_factory=service_factory,
        settings_provider=lambda: _SettingsStub(settings),
        single_shot=(single_shot or (lambda _delay, callback: callback())),
    )
    return controller, service, status


def test_apply_visibility_settings_hides_rate_widgets_when_disabled():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": False},
        widget=widget,
    )

    assert controller.apply_visibility_settings() is False
    assert widget.live_rate_label.visible is False
    assert widget.live_rate_value_label.visible is False
    assert widget.live_rate_meta_label.visible is False
    assert widget.refresh_rate_button.visible is False
    assert widget.live_rate_value_label.text() == "-"
    assert widget.live_rate_meta_label.text() == "Waiting…"


def test_apply_visibility_settings_shows_placeholder_when_enabled():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True},
        widget=widget,
    )

    assert controller.apply_visibility_settings() is True
    assert widget.live_rate_label.visible is True
    assert widget.live_rate_value_label.text() == "."
    assert widget.live_rate_meta_label.text() == "Waiting…"


def test_initialize_starts_service_and_schedules_refresh_when_visible():
    scheduled = []
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True, "rates/auto_refresh_enabled": True},
        widget=_WidgetStub(),
        single_shot=lambda delay, callback: scheduled.append((delay, callback)),
    )

    controller.initialize(initial_refresh_delay_ms=123)

    assert service.start_calls == 1
    assert len(scheduled) == 1
    assert scheduled[0][0] == 123


def test_apply_timer_settings_only_stops_service_when_auto_refresh_disabled():
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True, "rates/auto_refresh_enabled": False},
        widget=_WidgetStub(),
    )

    controller.apply_timer_settings()

    assert service.stop_calls == 1
    assert service.start_calls == 0


def test_refresh_now_triggers_service_refresh_and_status_message():
    controller, service, status = _build_controller(
        settings={"rates/live_enabled": True},
        widget=_WidgetStub(),
    )

    controller.refresh_now()

    assert service.refresh_calls == 1
    assert status[-1] == ("Refreshing live rate.", 1500, "info")


def test_refresh_now_falls_back_to_widget_refresh_when_service_raises():
    widget = _WidgetStub()
    controller, service, status = _build_controller(
        settings={"rates/live_enabled": True},
        widget=widget,
    )
    service.raise_on_refresh = True

    controller.refresh_now()

    assert service.refresh_calls == 1
    assert widget.refresh_calls == 1
    assert status == []


def test_refresh_now_reports_unavailable_when_no_widget_fallback():
    controller, _, status = _build_controller(
        settings={"rates/live_enabled": True},
        widget=types.SimpleNamespace(),
        service=None,
        single_shot=lambda _delay, callback: callback(),
    )

    controller._service_factory = lambda **kwargs: (_ for _ in ()).throw(
        RuntimeError("x")
    )
    controller.refresh_now()

    assert status[-1] == ("Live rate refresh unavailable", 3000, "warning")


def test_update_display_sets_source_tooltip_and_state_on_success():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True},
        widget=widget,
    )

    controller._update_display(50000, 50000, None, True)

    assert widget.live_rate_value_label.text().endswith(" /g")
    assert "Source: Broadcast" in widget.live_rate_value_label.tooltip
    assert "Market open" in widget.live_rate_value_label.tooltip
    assert controller._last_source == "Broadcast"
    assert controller._last_error is None


def test_update_display_handles_missing_rate_and_reports_manual_failure():
    widget = _WidgetStub()
    status = []
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True},
        widget=widget,
        status=status,
    )
    controller._manual_refresh = True

    controller._update_display(None, None, None, False)

    assert widget.live_rate_value_label.text() == "N/A /g"
    assert "Reason: No live rate available" in widget.live_rate_value_label.tooltip
    assert status[-1] == ("Live rate unavailable", 3000, "warning")
    assert controller._last_source is None
    assert controller._last_error == "No live rate available"


def test_shutdown_calls_service_stop_and_swallows_errors():
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True},
        widget=_WidgetStub(),
    )
    controller._service = service
    service.stop = lambda: (_ for _ in ()).throw(RuntimeError("stop boom"))

    controller.shutdown()
