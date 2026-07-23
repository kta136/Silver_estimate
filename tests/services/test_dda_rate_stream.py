import json
import threading
import time
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import Signal

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DdaRateContractError,
    DdaRateSnapshot,
)
from silverestimate.services.dda_rate_stream import (
    DdaRateStreamWorker,
    apply_sse_rate_event,
    parse_sse_snapshot,
)

NOW = datetime(2026, 7, 15, 8, 30, tzinfo=timezone.utc)


def _snapshot(sequence=10, final_rate=100000, transport="https"):
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=float(final_rate),
        unit="PER_KG",
        sequence=sequence,
        received_at=NOW,
        server_time=NOW,
        market_state={"code": "open_live", "label": "Market open"},
        transport=transport,
    )


def _snapshot_payload(sequence=11, final_rate=101000):
    return {
        "schemaVersion": 1,
        "view": "default",
        "sequence": sequence,
        "items": [
            {
                "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                "name": "Renamed",
                "unit": "PER_KG",
                "finalRate": final_rate,
            }
        ],
    }


def _rate_payload(sequence=11, final_rate=101000, item_id=DDA_AGRA_MOHAR_ITEM_ID):
    return {
        "schemaVersion": 1,
        "view": "default",
        "sequence": sequence,
        "items": [{"itemId": item_id, "finalRate": final_rate}],
    }


class _CurrentClient:
    def __init__(self, snapshots=None, error=None):
        self.snapshots = list(snapshots or [])
        self.error = error
        self.calls = 0

    def fetch_current(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if not self.snapshots:
            raise RuntimeError("no fixture")
        return self.snapshots.pop(0)


class _Store:
    def __init__(self, cached=None):
        self.cached = cached
        self.saved = []

    def save(self, snapshot):
        self.saved.append(snapshot)

    def load(self):
        return self.cached


class _Response:
    status = 200

    def __init__(self, lines=()):
        self.lines = list(lines)
        self.closed = False

    def readline(self, _limit=-1):
        if self.closed or not self.lines:
            return b""
        return self.lines.pop(0)

    def close(self):
        self.closed = True


def _sse(event, payload):
    return [
        f"event: {event}\n".encode(),
        f"data: {json.dumps(payload)}\n".encode(),
        b"\n",
    ]


def test_worker_declares_required_class_level_signals():
    for name in (
        "rate_received",
        "feed_status_received",
        "connection_state_changed",
        "stream_error",
    ):
        assert name in DdaRateStreamWorker.__dict__
        assert type(DdaRateStreamWorker.__dict__[name]) is type(Signal(object))


def test_stream_request_is_seeded_once_anonymous_and_desktop_surface():
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )

    seeded = worker._stream_request(seeded=True)
    unseeded = worker._stream_request(seeded=False)

    assert seeded.full_url.endswith("?seeded=1&surface=desktop")
    assert unseeded.full_url.endswith("?surface=desktop")
    headers = {key.lower(): value for key, value in seeded.header_items()}
    assert "authorization" not in headers
    assert "x-api-key" not in headers


def test_parse_authoritative_snapshot_matches_id_and_uses_final_rate():
    payload = _snapshot_payload()
    payload["items"][0]["baseRate"] = 1
    payload["items"].insert(
        0,
        {
            "itemId": "not-ours",
            "unit": "PER_KG",
            "finalRate": 999999,
        },
    )

    snapshot = parse_sse_snapshot(payload, received_at=NOW)

    assert snapshot.final_rate == 101000
    assert snapshot.item_id == DDA_AGRA_MOHAR_ITEM_ID
    assert snapshot.transport == "sse"


def test_rate_delta_ignores_unrelated_item_but_returns_global_sequence():
    sequence, snapshot = apply_sse_rate_event(
        _rate_payload(item_id="unrelated"),
        previous=_snapshot(),
        received_at=NOW,
    )

    assert sequence == 11
    assert snapshot is None


def test_worker_applies_next_sequence_and_ignores_duplicate_or_stale_events(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
        now=lambda: NOW,
    )
    received = []
    worker.rate_received.connect(received.append)
    worker._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    received.clear()

    worker._handle_rate(_rate_payload(sequence=11, final_rate=250000))
    worker._handle_rate(_rate_payload(sequence=11, final_rate=999999))
    worker._handle_rate(_rate_payload(sequence=9, final_rate=999999))

    assert [snapshot.final_rate for snapshot in received] == [250000]
    assert worker.last_sequence == 11


def test_unrelated_rate_advances_sequence_without_emitting_rate(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
        now=lambda: NOW,
    )
    received = []
    worker.rate_received.connect(received.append)
    worker._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    received.clear()

    worker._handle_rate(_rate_payload(sequence=11, item_id="unrelated"))

    assert received == []
    assert worker.last_sequence == 11


def test_sequence_gap_reconciles_once_through_current_rates(qt_app):
    current = _CurrentClient([_snapshot(sequence=15, final_rate=155000)])
    worker = DdaRateStreamWorker(
        current_client=current,
        snapshot_store=_Store(),
        now=lambda: NOW,
    )
    received = []
    worker.rate_received.connect(received.append)
    worker._accept_snapshot(_snapshot(sequence=10), persist=False, authoritative=True)
    received.clear()

    worker._handle_rate(_rate_payload(sequence=13, final_rate=130000))

    assert current.calls == 1
    assert worker.last_sequence == 15
    assert received[-1].final_rate == 155000


def test_feed_status_heartbeat_and_stream_reset_are_consumed(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )
    statuses = []
    worker.feed_status_received.connect(statuses.append)
    lines = []
    lines += _sse("heartbeat", {"schemaVersion": 1})
    lines += _sse(
        "feed-status",
        {
            "schemaVersion": 1,
            "status": {"connected": True},
            "marketState": {"code": "closed", "label": "Market closed"},
        },
    )
    lines += _sse("stream-reset", {"schemaVersion": 1, "reason": "max_age"})

    count, reset = worker._consume_response(_Response(lines))

    assert count == 3
    assert reset is True
    assert statuses[-1]["marketState"]["code"] == "closed"


def test_malformed_event_reports_error_and_next_event_still_applies(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
        now=lambda: NOW,
    )
    worker._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    errors = []
    received = []
    worker.stream_error.connect(errors.append)
    worker.rate_received.connect(received.append)
    received.clear()
    lines = _sse("rate", {"schemaVersion": 99})
    lines += _sse("rate", _rate_payload(sequence=11, final_rate=111000))

    worker._consume_response(_Response(lines))

    assert errors
    assert received[-1].final_rate == 111000


def test_initial_hydration_failure_emits_persisted_snapshot_as_offline_stale(qt_app):
    cached = _snapshot(transport="cache")
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(error=RuntimeError("offline")),
        snapshot_store=_Store(cached=cached),
    )
    received = []
    states = []
    worker.rate_received.connect(received.append)
    worker.connection_state_changed.connect(states.append)

    assert worker._hydrate_initial() is False

    assert received == [cached]
    assert states[-1] == "offline-stale"


def test_stop_sets_event_and_closes_active_response():
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )
    response = _Response()
    worker._active_response = response

    worker.stop()

    assert worker._stop_event.is_set()
    assert response.closed is True


def test_disconnected_wait_polls_current_rates_every_ten_seconds(qt_app):
    current = _CurrentClient([_snapshot(sequence=11)])
    worker = DdaRateStreamWorker(
        current_client=current,
        snapshot_store=_Store(),
        poll_interval=0.01,
        jitter=lambda value: value,
    )

    worker._wait_disconnected(0.025, time.monotonic() + 0.005)

    assert current.calls >= 1


def test_stop_unblocks_a_blocking_sse_read():
    class BlockingResponse(_Response):
        def __init__(self):
            super().__init__()
            self.release = threading.Event()

        def readline(self, _limit=-1):
            self.release.wait(2)
            return b""

        def close(self):
            super().close()
            self.release.set()

    response = BlockingResponse()
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )
    worker._active_response = response
    thread = threading.Thread(target=lambda: worker._consume_response(response))
    thread.start()

    worker.stop()
    thread.join(1)

    assert not thread.is_alive()


@pytest.mark.parametrize(
    ("payload", "received_at", "message"),
    [
        (_snapshot_payload(), datetime(2026, 7, 15), "timezone"),
        ({**_snapshot_payload(), "sequence": True}, NOW, "sequence"),
        ({**_snapshot_payload(), "view": "unknown"}, NOW, "view"),
        ({**_snapshot_payload(), "items": {}}, NOW, "array"),
        (
            {
                **_snapshot_payload(),
                "items": _snapshot_payload()["items"] * 2,
            },
            NOW,
            "duplicated",
        ),
        (
            {
                **_snapshot_payload(),
                "items": [{**_snapshot_payload()["items"][0], "unit": "PER_GM"}],
            },
            NOW,
            "PER_KG",
        ),
        ({**_snapshot_payload(), "items": []}, NOW, "omitted"),
        (
            {
                **_snapshot_payload(),
                "items": [{**_snapshot_payload()["items"][0], "finalRate": 0}],
            },
            NOW,
            "finite positive",
        ),
        (
            {
                **_snapshot_payload(),
                "items": [
                    {**_snapshot_payload()["items"][0], "finalRate": float("nan")}
                ],
            },
            NOW,
            "finite positive",
        ),
    ],
)
def test_snapshot_contract_rejects_invalid_payloads(payload, received_at, message):
    with pytest.raises(DdaRateContractError, match=message):
        parse_sse_snapshot(payload, received_at=received_at)


def test_rate_delta_rejects_matching_item_before_snapshot():
    with pytest.raises(DdaRateContractError, match="before a snapshot"):
        apply_sse_rate_event(_rate_payload(), previous=None, received_at=NOW)


def test_run_hydrates_uses_seeded_stream_then_unseeded_reset(qt_app):
    current = _CurrentClient([_snapshot()])
    store = _Store()
    requests = []
    responses = [
        _Response(_sse("stream-reset", {"schemaVersion": 1, "reason": "max_age"})),
        _Response(),
    ]
    worker = None

    def opener(request, **_kwargs):
        requests.append(request.full_url)
        response = responses.pop(0)
        if not responses:
            assert worker is not None
            worker.stop()
        return response

    worker = DdaRateStreamWorker(
        current_client=current,
        snapshot_store=store,
        opener=opener,
        now=lambda: NOW,
    )
    states = []
    worker.connection_state_changed.connect(states.append)

    worker.run()

    assert "seeded=1" in requests[0]
    assert "seeded=1" not in requests[1]
    assert "reconnecting" in states
    assert states[-1] == "stopped"
    assert store.saved == [_snapshot()]


def test_run_reconnect_failure_uses_backoff_and_stops(qt_app):
    delays = []
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient([_snapshot()]),
        snapshot_store=_Store(),
        opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(ConnectionError("down")),
        jitter=lambda delay: delays.append(delay) or delay,
    )
    errors = []
    states = []
    worker.stream_error.connect(errors.append)
    worker.connection_state_changed.connect(states.append)

    def stop_during_wait(_delay, next_poll_at):
        worker.stop()
        return next_poll_at

    worker._wait_disconnected = stop_during_wait
    worker.run()

    assert delays == [1.0]
    assert errors[-1] == "down"
    assert "disconnected" in states
    assert states[-1] == "stopped"


def test_run_processes_manual_refresh_before_connecting(qt_app):
    current = _CurrentClient([_snapshot(sequence=1), _snapshot(sequence=2)])
    worker = None

    def opener(*_args, **_kwargs):
        assert worker is not None
        worker.stop()
        return _Response()

    worker = DdaRateStreamWorker(
        current_client=current,
        snapshot_store=_Store(),
        opener=opener,
    )
    worker._refresh_event.set()

    worker.run()

    assert current.calls == 2
    assert worker.last_sequence == 2


def test_connect_consume_closes_response_and_rejects_http_error(qt_app):
    response = _Response(_sse("heartbeat", {"schemaVersion": 1}))
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
        opener=lambda *_args, **_kwargs: response,
    )

    assert worker._connect_and_consume(seeded=True) == (1, False)
    assert response.closed is True
    assert worker._active_response is None

    bad_response = _Response()
    bad_response.status = 503
    worker._opener = lambda *_args, **_kwargs: bad_response
    with pytest.raises(ConnectionError, match="HTTP 503"):
        worker._connect_and_consume(seeded=False)
    assert bad_response.closed is True


def test_response_parser_detects_stale_oversized_and_invalid_utf8(qt_app):
    moments = iter([0.0, 46.0])
    stale_worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
        monotonic=lambda: next(moments),
    )
    with pytest.raises(TimeoutError, match="no activity"):
        stale_worker._consume_response(_Response([b": heartbeat\n"]))

    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )
    with pytest.raises(DdaRateContractError, match="exceeded"):
        worker._consume_response(_Response([b"x" * (1024 * 1024 + 1)]))

    errors = []
    worker.stream_error.connect(errors.append)
    count, reset = worker._consume_response(
        _Response([b"\xff\n", *_sse("heartbeat", {"schemaVersion": 1})])
    )
    assert (count, reset) == (1, False)
    assert "UTF-8" in errors[-1]


def test_dispatch_snapshot_feed_validation_and_stale_acceptance(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(error=RuntimeError("gap offline")),
        snapshot_store=_Store(),
        now=lambda: NOW,
    )
    errors = []
    received = []
    worker.stream_error.connect(errors.append)
    worker.rate_received.connect(received.append)

    assert worker._dispatch_event("snapshot", json.dumps(_snapshot_payload())) is False
    worker._handle_snapshot(_snapshot_payload(sequence=10, final_rate=999999))
    assert len(received) == 1
    with pytest.raises(ConnectionError, match="recovery failed"):
        worker._handle_rate(_rate_payload(sequence=13))

    for payload in (
        {"schemaVersion": 1, "status": "bad"},
        {"schemaVersion": 1, "status": {}, "marketState": "bad"},
    ):
        with pytest.raises(DdaRateContractError):
            worker._handle_feed_status(payload)

    worker._accept_snapshot(_snapshot(sequence=9), persist=False, authoritative=False)
    assert worker.last_sequence == 11
    assert worker._dispatch_event("unknown", "[]") is False
    assert (
        worker._dispatch_event(
            "stream-reset", json.dumps({"schemaVersion": 1, "reason": "bad"})
        )
        is False
    )
    assert errors


def test_refresh_wait_and_response_cleanup_edges(qt_app):
    worker = DdaRateStreamWorker(
        current_client=_CurrentClient(),
        snapshot_store=_Store(),
    )
    response = _Response()
    worker._active_response = response
    worker.request_refresh()
    assert response.closed is True
    assert worker._wait_disconnected(1, 123.0) == 123.0

    class CloseFailure(_Response):
        def close(self):
            raise RuntimeError("close failed")

    active = CloseFailure()
    other = _Response()
    worker._active_response = active
    worker._clear_active_response(other)
    assert worker._active_response is active
    worker._close_active_response()
    assert worker._active_response is None
