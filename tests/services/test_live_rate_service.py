import logging
from datetime import datetime, timezone

from PySide6.QtCore import QObject, Signal

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DdaRateSnapshot,
)
from silverestimate.services.live_rate_service import LiveRateService


class _SettingsStub:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def value(self, key, default=None, type=None):  # noqa: A002
        value = self._values.get(key, default)
        return bool(value) if type is bool else value


def _snapshot():
    now = datetime(2026, 7, 15, tzinfo=timezone.utc)
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=100000,
        unit="PER_KG",
        sequence=1,
        received_at=now,
        server_time=now,
        market_state=None,
        transport="https",
    )


class _Stream(QObject):
    rate_received = Signal(object)
    feed_status_received = Signal(object)
    connection_state_changed = Signal(str)
    stream_error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_calls = 0
        self.stop_calls = 0
        self.refresh_calls = 0

    def start(self):
        self.start_calls += 1
        self.rate_received.emit(_snapshot())
        self.connection_state_changed.emit("connected")

    def stop(self):
        self.stop_calls += 1
        self.connection_state_changed.emit("stopped")

    def request_refresh(self):
        self.refresh_calls += 1


def _service(streams, enabled=True):
    def factory(**kwargs):
        streams.append(_Stream(parent=kwargs["parent"]))
        return streams[-1]

    return LiveRateService(
        logger=logging.getLogger("test.live_rate"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": enabled}),
        stream_factory=factory,
    )


def test_service_starts_one_stream_and_forwards_signals(qt_app):
    streams = []
    service = _service(streams)
    received = []
    states = []
    service.rate_updated.connect(received.append)
    service.connection_state_changed.connect(states.append)

    service.start()
    service.start()

    assert len(streams) == 1
    assert streams[0].parent() is service
    assert received[-1].final_rate == 100000
    assert states == ["connected"]
    service.stop()
    assert streams[0].stop_calls == 1


def test_stop_takes_effect_before_it_returns(qt_app):
    streams = []
    service = _service(streams)
    states = []
    received = []
    service.connection_state_changed.connect(states.append)
    service.rate_updated.connect(received.append)
    service.start()

    service.stop()
    streams[0].rate_received.emit(_snapshot())
    streams[0].connection_state_changed.emit("connected")

    assert states == ["connected", "stopped"]
    assert len(received) == 1


def test_a_stopped_service_starts_a_fresh_stream(qt_app):
    streams = []
    service = _service(streams)
    service.start()
    service.stop()

    service.start()

    assert len(streams) == 2
    assert streams[1].start_calls == 1
    service.stop()


def test_manual_refresh_reuses_the_running_stream(qt_app):
    streams = []
    service = _service(streams)
    service.start()

    service.refresh_now()

    assert len(streams) == 1
    assert streams[0].refresh_calls == 1
    service.stop()


def test_manual_refresh_starts_a_stream_when_none_is_running(qt_app):
    streams = []
    service = _service(streams)

    service.refresh_now()

    assert streams[0].start_calls == 1
    assert streams[0].refresh_calls == 0
    service.stop()


def test_disabled_setting_prevents_stream_creation(qt_app):
    streams = []
    service = _service(streams, enabled=False)

    service.start()
    service.refresh_now()

    assert streams == []


def test_stop_is_idempotent_without_a_stream(qt_app):
    service = _service([])

    service.stop()
    service.stop()
