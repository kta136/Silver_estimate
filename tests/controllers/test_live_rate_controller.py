import logging
import types
from datetime import datetime, timezone

from PyQt6.QtCore import QObject

from silverestimate.controllers.live_rate_controller import LiveRateController
from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DdaRateSnapshot,
)


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
        self.feed_status_updated = _Signal()
        self.connection_state_changed = _Signal()
        self.stream_error = _Signal()
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


def _snapshot(*, transport="sse", final_rate=125000):
    now = datetime(2026, 7, 15, 8, 30, tzinfo=timezone.utc)
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=final_rate,
        unit="PER_KG",
        sequence=51,
        received_at=now,
        server_time=now,
        market_state={"code": "open_live", "label": "Market open"},
        transport=transport,
    )


def _build_controller(
    *, settings, service=None, widget=None, status=None, single_shot=None
):
    service = service or _ServiceStub()
    status = status if status is not None else []

    controller = LiveRateController(
        parent=QObject(),
        widget_getter=lambda: widget,
        status_callback=lambda *args: status.append(args),
        logger=logging.getLogger("test.live_rate_controller"),
        service_factory=lambda **_kwargs: service,
        settings_provider=lambda: _SettingsStub(settings),
        single_shot=single_shot or (lambda _delay, callback: callback()),
    )
    return controller, service, status


def test_apply_visibility_settings_hides_rate_widgets_when_disabled():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": False}, widget=widget
    )

    assert controller.apply_visibility_settings() is False
    assert widget.live_rate_value_label.visible is False
    assert widget.live_rate_meta_label.visible is False
    assert widget.refresh_rate_button.visible is False
    assert widget.live_rate_value_label.text() == "-"
    assert widget.live_rate_meta_label.text() == "--:--"


def test_initialize_starts_stream_and_schedules_hydration_refresh():
    scheduled = []
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True, "rates/auto_refresh_enabled": True},
        widget=_WidgetStub(),
        single_shot=lambda delay, callback: scheduled.append((delay, callback)),
    )

    controller.initialize(initial_refresh_delay_ms=123)

    assert service.start_calls == 1
    assert scheduled[0][0] == 123


def test_auto_updates_disabled_stops_service():
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True, "rates/auto_refresh_enabled": False},
        widget=_WidgetStub(),
    )

    controller.apply_timer_settings()

    assert service.stop_calls == 1
    assert service.start_calls == 0


def test_refresh_now_reuses_service_and_reports_status():
    controller, service, status = _build_controller(
        settings={"rates/live_enabled": True}, widget=_WidgetStub()
    )

    controller.refresh_now()

    assert service.refresh_calls == 1
    assert status[-1] == ("Refreshing live rate.", 1500, "info")


def test_refresh_falls_back_to_widget_when_service_raises():
    widget = _WidgetStub()
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=widget
    )
    service.raise_on_refresh = True

    controller.refresh_now()

    assert widget.refresh_calls == 1


def test_refresh_reports_unavailable_without_service_or_widget_fallback():
    controller, _, status = _build_controller(
        settings={"rates/live_enabled": True},
        widget=types.SimpleNamespace(),
    )
    controller._service_factory = lambda **_kwargs: (_ for _ in ()).throw(
        RuntimeError("unavailable")
    )

    controller.refresh_now()

    assert status[-1] == ("Live rate refresh unavailable", 3000, "warning")


def test_display_uses_final_rate_item_id_and_sse_source():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=widget
    )

    controller._handle_connection_state("connected")
    controller._update_display(_snapshot())

    assert widget.live_rate_value_label.text().endswith(" /g")
    assert "Source: DDA SSE" in widget.live_rate_value_label.tooltip
    assert f"Item ID: {DDA_AGRA_MOHAR_ITEM_ID}" in widget.live_rate_value_label.tooltip
    assert "Customer finalRate: 125000 PER_KG" in widget.live_rate_value_label.tooltip
    assert "Market: Market open" in widget.live_rate_value_label.tooltip
    assert len(widget.live_rate_meta_label.text()) == 5
    assert ":" in widget.live_rate_meta_label.text()
    assert controller._last_source == "DDA SSE"


def test_disconnected_state_retains_rate_and_marks_timestamp_stale():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=widget
    )
    controller._update_display(_snapshot(transport="cache"))
    original = widget.live_rate_value_label.text()

    controller._handle_connection_state("offline-stale")

    assert widget.live_rate_value_label.text() == original
    assert widget.live_rate_meta_label.text().endswith("*")
    assert "offline/stale" in widget.live_rate_value_label.tooltip.lower()
    assert "Source: Cached DDA" in widget.live_rate_value_label.tooltip


def test_feed_status_updates_market_label_without_changing_rate():
    widget = _WidgetStub()
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=widget
    )
    controller._update_display(_snapshot())

    controller._handle_feed_status(
        {"marketState": {"code": "closed", "label": "Market closed"}}
    )

    assert "Market: Market closed" in widget.live_rate_value_label.tooltip


def test_manual_success_reports_updated_status():
    widget = _WidgetStub()
    status = []
    controller, _, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=widget, status=status
    )
    controller._manual_refresh = True

    controller._update_display(_snapshot())

    assert status[-1] == ("Live rate updated", 2000, "info")


def test_shutdown_calls_service_stop_and_clears_reference():
    controller, service, _ = _build_controller(
        settings={"rates/live_enabled": True}, widget=_WidgetStub()
    )
    controller._service = service

    controller.shutdown()

    assert service.stop_calls == 1
    assert controller._service is None
