import logging

from silverestimate.services.live_rate_service import LiveRateService


def _patch_thread_to_run_inline(monkeypatch):
    class _ImmediateThread:
        def __init__(self, target=None, daemon=None):
            self._target = target

        def start(self):
            if self._target:
                self._target()

    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.threading.Thread",
        _ImmediateThread,
    )


def test_live_rate_service_emits_broadcast(qt_app, monkeypatch, settings_stub):
    _patch_thread_to_run_inline(monkeypatch)
    settings_stub().setValue("rates/live_enabled", True)

    service = LiveRateService(logger=logging.getLogger("test_live_rate"))

    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.fetch_broadcast_rate_exact",
        lambda timeout=5: (50000, True, None),
    )
    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.fetch_silver_agra_local_mohar_rate",
        lambda timeout=5: (47000, None),
    )

    captured = {}

    def _capture(brate, api_rate, is_open):
        captured["args"] = (brate, api_rate, is_open)

    service.rate_updated.connect(_capture)
    service.refresh_now()

    assert captured["args"] == (50000, None, True)
    assert service._rate_fetch_in_progress is False


def test_live_rate_service_uses_fallback_when_broadcast_fails(qt_app, monkeypatch, settings_stub):
    _patch_thread_to_run_inline(monkeypatch)
    settings_stub().setValue("rates/live_enabled", True)

    service = LiveRateService(logger=logging.getLogger("test_live_rate_fallback"))

    def _fail_fetch(timeout=5):  # noqa: ARG001 - signature parity for monkeypatch
        raise RuntimeError("broadcast down")

    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.fetch_broadcast_rate_exact",
        _fail_fetch,
    )
    monkeypatch.setattr(
        "silverestimate.services.live_rate_service.fetch_silver_agra_local_mohar_rate",
        lambda timeout=5: (45500, None),
    )

    captured = {}

    def _capture(brate, api_rate, is_open):
        captured["args"] = (brate, api_rate, is_open)

    service.rate_updated.connect(_capture)
    service.refresh_now()

    assert captured["args"] == (None, 45500, True)
    assert service._rate_fetch_in_progress is False
