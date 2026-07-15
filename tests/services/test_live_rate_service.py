import logging
import threading
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

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


class _Worker(QObject):
    rate_received = pyqtSignal(object)
    feed_status_received = pyqtSignal(object)
    connection_state_changed = pyqtSignal(str)
    stream_error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.run_calls = 0
        self.stop_calls = 0
        self.refresh_calls = 0

    def run(self):
        self.run_calls += 1
        self.rate_received.emit(_snapshot())
        self.connection_state_changed.emit("connected")

    def stop(self):
        self.stop_calls += 1

    def request_refresh(self):
        self.refresh_calls += 1


def test_service_starts_one_qthread_worker_and_forwards_signals(qtbot):
    workers = []

    def factory(**_kwargs):
        worker = _Worker()
        workers.append(worker)
        return worker

    service = LiveRateService(
        logger=logging.getLogger("test.live_rate"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        worker_factory=factory,
    )
    received = []
    states = []
    service.rate_updated.connect(received.append)
    service.connection_state_changed.connect(states.append)

    service.start()
    qtbot.waitUntil(lambda: bool(received), timeout=1000)
    service.start()

    assert len(workers) == 1
    assert received[-1].final_rate == 100000
    assert states[-1] == "connected"
    service.stop()
    assert workers[0].stop_calls == 1


def test_manual_refresh_reuses_running_worker(qtbot):
    worker = _Worker()
    service = LiveRateService(
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        worker_factory=lambda **_kwargs: worker,
    )
    service.start()
    qtbot.waitUntil(lambda: worker.run_calls == 1, timeout=1000)

    service.refresh_now()

    assert worker.refresh_calls == 1
    service.stop()


def test_manual_refresh_starts_worker_when_not_running(qtbot):
    worker = _Worker()
    service = LiveRateService(
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        worker_factory=lambda **_kwargs: worker,
    )

    service.refresh_now()
    qtbot.waitUntil(lambda: worker.run_calls == 1, timeout=1000)

    assert worker.refresh_calls == 0
    service.stop()


def test_disabled_setting_prevents_worker_creation():
    calls = []
    service = LiveRateService(
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": False}),
        worker_factory=lambda **kwargs: calls.append(kwargs),
    )

    service.start()
    service.refresh_now()

    assert calls == []


def test_stop_is_idempotent_without_worker():
    service = LiveRateService(
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True})
    )

    service.stop()
    service.stop()


def test_worker_rate_is_delivered_to_qobject_receiver_on_gui_thread(qtbot):
    gui_thread_id = threading.get_ident()
    handled_on = []

    class _Receiver(QObject):
        @pyqtSlot(object)
        def handle(self, _snapshot):
            handled_on.append(threading.get_ident())

    receiver = _Receiver()
    worker = _Worker()
    service = LiveRateService(
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        worker_factory=lambda **_kwargs: worker,
    )
    service.rate_updated.connect(receiver.handle)

    service.start()
    qtbot.waitUntil(lambda: bool(handled_on), timeout=1000)

    assert handled_on == [gui_thread_id]
    service.stop()
