import logging

from silverestimate.services.live_rate_service import LiveRateService


class _SettingsStub:
    def __init__(self, values=None):
        self._values = dict(values or {})

    def value(self, key, default=None, type=None):  # noqa: A002 - Qt-like API
        value = self._values.get(key, default)
        if type is bool:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.strip().lower() in {"1", "true", "yes", "on"}
            return bool(value)
        return value


class _ImmediateThread:
    def __init__(self, target=None, daemon=None):
        self._target = target
        self.daemon = daemon
        self._alive = False

    def start(self):
        self._alive = True
        try:
            if self._target:
                self._target()
        finally:
            self._alive = False

    def is_alive(self):
        return self._alive

    def join(self, timeout=None):
        return None


class _HoldingThread:
    def __init__(self, target=None, daemon=None):
        self._target = target
        self.daemon = daemon
        self.started = False

    def start(self):
        self.started = True

    def run(self):
        if self._target:
            self._target()


def test_live_rate_service_emits_broadcast(qt_app):
    service = LiveRateService(
        logger=logging.getLogger("test_live_rate"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
        broadcast_fetcher=lambda timeout=5: (50000, True, None),
        api_fetcher=lambda timeout=5: (47000, None),
    )

    captured = {}

    def _capture(brate, api_rate, is_open):
        captured["args"] = (brate, api_rate, is_open)

    service.rate_updated.connect(_capture)
    service.refresh_now()

    assert captured["args"] == (50000, None, True)
    assert service._rate_fetch_in_progress is False


def test_live_rate_service_uses_fallback_when_broadcast_fails(qt_app):
    service = LiveRateService(
        logger=logging.getLogger("test_live_rate_fallback"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
        broadcast_fetcher=lambda timeout=5: (_ for _ in ()).throw(RuntimeError("down")),
        api_fetcher=lambda timeout=5: (45500, None),
    )

    captured = {}

    def _capture(brate, api_rate, is_open):
        captured["args"] = (brate, api_rate, is_open)

    service.rate_updated.connect(_capture)
    service.refresh_now()

    assert captured["args"] == (None, 45500, True)
    assert service._rate_fetch_in_progress is False


def test_live_rate_service_skips_reentrant_refresh(qt_app):
    created_threads = []

    def _thread_factory(**kwargs):
        thread = _HoldingThread(**kwargs)
        created_threads.append(thread)
        return thread

    service = LiveRateService(
        logger=logging.getLogger("test_live_rate_reentrant"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        thread_factory=_thread_factory,
        broadcast_fetcher=lambda timeout=5: (50000, True, None),
        api_fetcher=lambda timeout=5: (47000, None),
    )

    service.refresh_now()
    service.refresh_now()

    assert len(created_threads) == 1
    assert service._rate_fetch_in_progress is True

    created_threads[0].run()
    assert service._rate_fetch_in_progress is False


def test_live_rate_service_handles_fallback_failure(qt_app):
    service = LiveRateService(
        logger=logging.getLogger("test_live_rate_fallback_failure"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": True}),
        thread_factory=lambda **kwargs: _ImmediateThread(**kwargs),
        broadcast_fetcher=lambda timeout=5: (_ for _ in ()).throw(RuntimeError("boom")),
        api_fetcher=lambda timeout=5: (_ for _ in ()).throw(RuntimeError("api boom")),
    )

    captured = {}

    def _capture(brate, api_rate, is_open):
        captured["args"] = (brate, api_rate, is_open)

    service.rate_updated.connect(_capture)
    service.refresh_now()

    assert captured["args"] == (None, None, True)
    assert service._rate_fetch_in_progress is False


def test_live_rate_service_start_uses_min_interval_and_honors_auto_flag(qt_app):
    settings_values = {
        "rates/refresh_interval_sec": 1,
        "rates/auto_refresh_enabled": True,
        "rates/live_enabled": True,
    }
    service = LiveRateService(
        logger=logging.getLogger("test_live_rate_start"),
        settings_provider=lambda: _SettingsStub(settings_values),
    )

    service.start()
    assert service._timer is not None
    assert service._timer.interval() == 5000
    assert service._timer.isActive() is True

    settings_values["rates/auto_refresh_enabled"] = False
    service.start()
    assert service._timer.isActive() is False


def test_live_rate_service_refresh_respects_live_enabled_setting(qt_app):
    thread_calls = {"count": 0}

    def _thread_factory(**kwargs):
        thread_calls["count"] += 1
        return _ImmediateThread(**kwargs)

    service = LiveRateService(
        logger=logging.getLogger("test_live_rate_disabled"),
        settings_provider=lambda: _SettingsStub({"rates/live_enabled": False}),
        thread_factory=_thread_factory,
        broadcast_fetcher=lambda timeout=5: (50000, True, None),
        api_fetcher=lambda timeout=5: (47000, None),
    )

    service.refresh_now()

    assert thread_calls["count"] == 0
    assert service._rate_fetch_in_progress is False
