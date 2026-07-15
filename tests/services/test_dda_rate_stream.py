import json
import threading
import time
from datetime import datetime, timezone

from PyQt6.QtCore import pyqtSignal

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
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


def test_worker_declares_required_class_level_pyqt_signals():
    for name in (
        "rate_received",
        "feed_status_received",
        "connection_state_changed",
        "stream_error",
    ):
        assert name in DdaRateStreamWorker.__dict__
        assert type(DdaRateStreamWorker.__dict__[name]) is type(pyqtSignal(object))


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
