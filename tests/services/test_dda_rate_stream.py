import json
import time
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from PySide6.QtCore import Signal

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DdaCurrentRatesClient,
    DdaRateContractError,
    DdaRateSnapshot,
)
from silverestimate.services.dda_rate_stream import (
    DdaRateStream,
    SseDecoder,
    apply_sse_rate_event,
    parse_sse_snapshot,
)
from tests.rate_server_support import RateServer, direct_manager

NOW = datetime(2026, 7, 15, 8, 30, tzinfo=timezone.utc)
WAIT_MS = 5000


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


def _current_payload(sequence=10, final_rate=100000):
    return {
        "schemaVersion": 1,
        "view": "default",
        "serverTime": "2026-07-15T08:30:00.000Z",
        "sequence": sequence,
        "items": [
            {
                "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                "unit": "PER_KG",
                "finalRate": final_rate,
            }
        ],
    }


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


class _Store:
    def __init__(self, cached=None):
        self.cached = cached
        self.saved = []

    def save(self, snapshot):
        self.saved.append(snapshot)

    def load(self):
        return self.cached


class _Harness:
    """A stream wired to the loopback server, recording everything it emits."""

    def __init__(self, server, qtbot, *, store=None, **options):
        self.server = server
        self.qtbot = qtbot
        self.store = store or _Store()
        self.delays = []
        self.manager = direct_manager()
        self.client = DdaCurrentRatesClient(
            endpoint=server.current_url,
            manager=self.manager,
            timeout=options.pop("timeout", 2.0),
            now=lambda: NOW,
        )
        self.stream = DdaRateStream(
            current_client=self.client,
            snapshot_store=self.store,
            stream_url=server.stream_url,
            manager=self.manager,
            now=lambda: NOW,
            jitter=lambda delay: self.delays.append(delay) or 0.02,
            **options,
        )
        self.states = []
        self.errors = []
        self.rates = []
        self.stream.connection_state_changed.connect(self.states.append)
        self.stream.stream_error.connect(self.errors.append)
        self.stream.rate_received.connect(self.rates.append)

    def wait(self, condition):
        self.qtbot.waitUntil(condition, timeout=WAIT_MS)

    def wait_state(self, state, count=1):
        self.wait(lambda: self.states.count(state) >= count)

    def start_connected(self, sequence=10):
        """Hydrate at ``sequence`` and return the open, scripted stream."""
        self.server.queue_current(_current_payload(sequence=sequence))
        scripted = self.server.queue_stream()
        self.stream.start()
        self.wait_state("connected")
        return scripted


@pytest.fixture()
def server():
    rate_server = RateServer()
    yield rate_server
    rate_server.close()


@pytest.fixture()
def harness(server, qtbot):
    made = []

    def make(**options):
        made.append(_Harness(server, qtbot, **options))
        return made[-1]

    yield make
    for item in made:
        item.stream.stop()


def _offline_stream(**options):
    return DdaRateStream(snapshot_store=_Store(), now=lambda: NOW, **options)


def test_stream_declares_required_class_level_signals():
    for name in (
        "rate_received",
        "feed_status_received",
        "connection_state_changed",
        "stream_error",
    ):
        assert name in DdaRateStream.__dict__
        assert type(DdaRateStream.__dict__[name]) is type(Signal(object))


def test_stream_request_is_seeded_once_anonymous_and_desktop_surface(qt_app):
    stream = _offline_stream()

    seeded = stream.stream_request(seeded=True)
    unseeded = stream.stream_request(seeded=False)

    assert seeded.url().toString().endswith("?seeded=1&surface=desktop")
    assert unseeded.url().toString().endswith("?surface=desktop")
    headers = {bytes(name).decode().lower() for name in seeded.rawHeaderList()}
    assert "authorization" not in headers
    assert "x-api-key" not in headers
    assert seeded.rawHeader("Accept").data() == b"text/event-stream"


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


def _decode(*chunks):
    malformed = []
    decoder = SseDecoder(malformed.append)
    events = []
    for chunk in chunks:
        decoder.push(chunk)
        while (event := decoder.next_event()) is not None:
            events.append(event)
    return events, malformed


def test_decoder_frames_events_split_across_network_chunks():
    events, malformed = _decode(
        b": keep-alive\nevent: ra",
        b'te\r\ndata: {"a":\r\n',
        b"data:1}\r\n\r\ndata: plain\n",
        b"\nevent: unfinished\ndata: x\n",
    )

    assert events == [("rate", '{"a":\n1}'), ("message", "plain")]
    assert malformed == []


def test_decoder_skips_a_malformed_event_and_keeps_the_next_one():
    events, malformed = _decode(b"event: rate\n\xff\ndata: lost\n\ndata: kept\n\n")

    assert events == [("message", "lost"), ("message", "kept")]
    assert len(malformed) == 1


def test_decoder_rejects_a_line_longer_than_one_mebibyte():
    decoder = SseDecoder(lambda _error: None)
    decoder.push(b"x" * (1024 * 1024 + 1))

    with pytest.raises(DdaRateContractError, match="exceeded"):
        decoder.next_event()


def test_decoder_accepts_a_large_burst_of_short_lines():
    events, _malformed = _decode(b"data: tick\n\n" * 120_000)

    assert len(events) == 120_000


def test_stream_applies_next_sequence_and_ignores_duplicate_or_stale_events(qt_app):
    stream = _offline_stream()
    received = []
    stream.rate_received.connect(received.append)
    stream._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    received.clear()

    stream._handle_rate(_rate_payload(sequence=11, final_rate=250000))
    stream._handle_rate(_rate_payload(sequence=11, final_rate=999999))
    stream._handle_rate(_rate_payload(sequence=9, final_rate=999999))

    assert [snapshot.final_rate for snapshot in received] == [250000]
    assert stream.last_sequence == 11


def test_unrelated_rate_advances_sequence_without_emitting_rate(qt_app):
    stream = _offline_stream()
    received = []
    stream.rate_received.connect(received.append)
    stream._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    received.clear()

    stream._handle_rate(_rate_payload(sequence=11, item_id="unrelated"))

    assert received == []
    assert stream.last_sequence == 11


def test_dispatch_snapshot_feed_validation_and_stale_acceptance(qt_app):
    stream = _offline_stream()
    errors = []
    received = []
    stream.stream_error.connect(errors.append)
    stream.rate_received.connect(received.append)

    assert stream._dispatch_event("snapshot", json.dumps(_snapshot_payload())) is False
    stream._handle_snapshot(_snapshot_payload(sequence=10, final_rate=999999))
    assert len(received) == 1

    for payload in (
        {"schemaVersion": 1, "status": 5},
        {"schemaVersion": 2, "status": "stale"},
        {"schemaVersion": 1, "status": "stale", "marketState": "bad"},
    ):
        with pytest.raises(DdaRateContractError):
            stream._handle_feed_status(payload)

    stream._accept_snapshot(_snapshot(sequence=9), persist=False, authoritative=False)
    assert stream.last_sequence == 11
    assert stream._dispatch_event("unknown", "[]") is False
    assert (
        stream._dispatch_event(
            "stream-reset", json.dumps({"schemaVersion": 1, "reason": "bad"})
        )
        is False
    )
    assert errors


def test_feed_status_as_the_server_sends_it_updates_the_market_state(qt_app):
    """The shape recorded from the public stream on 11 October 2026."""
    stream = _offline_stream()
    errors = []
    statuses = []
    received = []
    stream.stream_error.connect(errors.append)
    stream.feed_status_received.connect(statuses.append)
    stream.rate_received.connect(received.append)
    stream._accept_snapshot(_snapshot(), persist=False, authoritative=True)
    session = {"phase": "closed", "isOpen": False, "reason": "weekend"}
    payload = {
        "schemaVersion": 1,
        "authority": {"site": "hostinger", "generation": "ac220db1"},
        "status": "stale",
        "marketSession": session,
        "marketState": {
            "code": "closed",
            "severity": "info",
            "reason": "market_closed",
            "label": "MCX closed",
            "marketSession": session,
        },
    }

    stream._dispatch_event("feed-status", json.dumps(payload))
    stream._dispatch_event("source", json.dumps({"schemaVersion": 1, "sources": []}))
    stream._handle_rate(_rate_payload(sequence=11))

    assert errors == []
    assert statuses[0]["marketState"]["label"] == "MCX closed"
    assert received[-1].market_state["label"] == "MCX closed"


def test_start_hydrates_then_uses_a_seeded_stream_and_an_unseeded_one_after_reset(
    server, harness
):
    run = harness()
    first = run.start_connected()
    second = server.queue_stream()

    first.send_event("stream-reset", {"schemaVersion": 1, "reason": "max_age"})
    run.wait_state("connected", 2)

    streams = server.paths("/sse/rates")
    assert "seeded=1" in streams[0]
    assert "seeded=1" not in streams[1]
    assert run.states[:4] == ["hydrated", "connecting", "connected", "reconnecting"]
    assert run.errors == []
    assert run.store.saved == [replace(_snapshot(), market_state=None)]
    second.close()


def test_stream_events_reach_listeners_in_order(server, harness):
    run = harness()
    statuses = []
    run.stream.feed_status_received.connect(statuses.append)
    scripted = run.start_connected(sequence=10)

    scripted.send_event("heartbeat", {"schemaVersion": 1})
    scripted.send_event(
        "feed-status",
        {
            "schemaVersion": 1,
            "status": "stale",
            "marketState": {"code": "closed", "label": "Market closed"},
        },
    )
    scripted.send_event("rate", {"schemaVersion": 99})
    scripted.send_event("rate", _rate_payload(sequence=11, final_rate=111000))
    run.wait(lambda: run.stream.last_sequence == 11)

    assert statuses[-1]["marketState"]["code"] == "closed"
    assert run.rates[-1].final_rate == 111000
    assert run.rates[-1].transport == "sse"
    assert run.rates[-1].market_state == {"code": "closed", "label": "Market closed"}
    assert any("Malformed DDA SSE rate event" in error for error in run.errors)


def test_hydration_failure_shows_the_cached_rate_as_stale_and_still_connects(
    server, harness
):
    cached = _snapshot(transport="cache")
    run = harness(store=_Store(cached=cached))
    server.queue_current({"error": "down"}, status=503)
    scripted = server.queue_stream()

    run.stream.start()
    run.wait_state("connected")

    assert run.rates == [cached]
    assert run.states[:2] == ["offline-stale", "connecting"]
    assert "startup hydration failed" in run.errors[0]
    assert "HTTP 503" in run.errors[0]
    assert "seeded=1" not in server.paths("/sse/rates")[0]
    scripted.close()


def test_a_dropped_stream_backs_off_polls_current_rates_and_reconnects(server, harness):
    run = harness(poll_interval=0.05)
    first = run.start_connected(sequence=10)
    server.queue_current(_current_payload(sequence=12, final_rate=120000))

    first.close()
    run.wait(lambda: run.stream.last_sequence == 12)
    second = server.queue_stream()
    run.wait_state("connected", 2)

    assert run.errors[0] == "DDA SSE stream ended unexpectedly."
    assert "HTTP 503" in run.errors[1]
    assert run.delays[:2] == [1.0, 2.0]
    assert run.states.count("disconnected") >= 2
    assert run.rates[-1].final_rate == 120000
    second.close()


def test_events_received_restart_the_backoff(server, harness):
    run = harness()
    first = run.start_connected()
    first.close()
    run.wait(lambda: len(run.delays) >= 2)
    second = server.queue_stream()
    run.wait_state("connected", 2)
    reconnects = len(run.delays)

    second.send_event("heartbeat", {"schemaVersion": 1})
    second.close()
    run.wait(lambda: len(run.delays) > reconnects)

    assert run.delays[reconnects] == 1.0


def test_sequence_gap_reconciles_once_and_resumes_buffered_events(server, harness):
    run = harness()
    scripted = run.start_connected(sequence=10)
    requests_before = len(server.paths("/api/"))
    server.queue_current(_current_payload(sequence=15, final_rate=155000))

    scripted.send(
        b"".join(
            f"event: rate\ndata: {json.dumps(payload)}\n\n".encode()
            for payload in (
                _rate_payload(sequence=13, final_rate=130000),
                _rate_payload(sequence=14, final_rate=140000),
                _rate_payload(sequence=16, final_rate=160000),
            )
        )
    )
    run.wait(lambda: run.stream.last_sequence == 16)

    assert len(server.paths("/api/")) == requests_before + 1
    assert [rate.final_rate for rate in run.rates[1:]] == [155000, 160000]
    assert run.states.count("connected") == 1
    assert run.errors == []


def test_failed_gap_recovery_drops_the_stream_and_reconnects(server, harness):
    run = harness()
    scripted = run.start_connected(sequence=10)
    server.queue_current({"error": "down"}, status=500)

    scripted.send_event("rate", _rate_payload(sequence=13))
    run.wait_state("disconnected")

    assert "sequence-gap recovery failed: " in run.errors[0]
    assert run.errors[1] == "DDA sequence-gap recovery failed."
    assert run.stream.last_sequence == 10


def test_manual_refresh_reconciles_then_reconnects_seeded(server, harness):
    run = harness()
    run.start_connected(sequence=10)
    server.queue_current(_current_payload(sequence=20, final_rate=200000))
    second = server.queue_stream()

    run.stream.request_refresh()
    run.wait_state("connected", 2)

    assert run.stream.last_sequence == 20
    assert run.rates[-1].final_rate == 200000
    assert "seeded=1" in server.paths("/sse/rates")[1]
    assert "disconnected" not in run.states
    assert run.errors == []
    second.close()


def test_a_silent_stream_is_dropped_as_stale(server, harness):
    run = harness(stale_after=0.3)
    run.start_connected()

    run.wait_state("disconnected")

    assert run.errors[0] == "DDA SSE socket had no activity for 0.3 seconds."


def test_an_http_error_from_the_stream_is_reported_with_its_status(server, harness):
    run = harness()
    server.queue_current(_current_payload())

    run.stream.start()
    run.wait_state("disconnected")

    assert run.errors[0] == "DDA SSE returned HTTP 503."
    assert "connected" not in run.states


def test_stop_is_immediate_while_a_request_has_no_answer(server, harness):
    run = harness(timeout=30.0)
    run.stream.start()
    run.wait(lambda: bool(server.paths("/api/")))

    started = time.perf_counter()
    run.stream.stop()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.5
    assert run.states == ["stopped"]
    run.qtbot.wait(100)
    assert run.states == ["stopped"]
    assert run.errors == []


def test_nothing_is_delivered_after_stop(server, harness):
    run = harness()
    scripted = run.start_connected(sequence=10)

    run.stream.stop()
    scripted.send_event("rate", _rate_payload(sequence=11))
    scripted.close()
    run.qtbot.wait(150)

    assert run.states[-1] == "stopped"
    assert len(run.rates) == 1
    assert run.errors == []
    run.stream.stop()
    assert run.states.count("stopped") == 1


def test_stream_can_be_restarted_after_stop(server, harness):
    run = harness()
    run.start_connected(sequence=10)
    run.stream.stop()
    server.queue_current(_current_payload(sequence=30, final_rate=300000))
    server.queue_stream()

    run.stream.start()
    run.wait_state("connected", 2)

    assert run.stream.last_sequence == 30
