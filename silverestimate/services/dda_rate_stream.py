"""Event-driven SSE transport for DDA's public Agra Mohar customer rate."""

from __future__ import annotations

import json
import logging
import random
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from functools import partial
from typing import Any

from PySide6.QtCore import QObject, QTimer, QUrl, QUrlQuery, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DDA_RATE_UNIT,
    DdaCurrentRatesClient,
    DdaRateContractError,
    DdaRateSnapshot,
    DdaSnapshotStore,
    agra_mohar_items,
    http_status,
    network_manager,
    nonnegative_int,
    positive_finite_number,
    rate_request,
    utc_now,
    validate_schema,
)

DDA_RATE_STREAM_URL = "https://ddajewels.com/sse/rates"
RECONNECT_DELAYS = (1.0, 2.0, 4.0, 8.0, 10.0)
MAX_SSE_LINE_BYTES = 1024 * 1024

# Why the current-rates endpoint is being asked; each ends up in error text.
HYDRATION = "startup hydration"
MANUAL_REFRESH = "manual refresh"
GAP_RECOVERY = "sequence-gap recovery"
FALLBACK_POLL = "fallback poll"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DdaRateContractError("SSE receipt time must include a timezone.")
    return value.astimezone(timezone.utc)


def _target_item(items: object, *, unit_required: bool) -> Mapping[str, Any] | None:
    matches = agra_mohar_items(items, label="SSE")
    if len(matches) > 1:
        raise DdaRateContractError("SSE payload duplicated the Agra Mohar item ID.")
    if not matches:
        return None
    item = matches[0]
    if unit_required and item.get("unit") != DDA_RATE_UNIT:
        raise DdaRateContractError("SSE Agra Mohar unit must be PER_KG.")
    return item


def parse_sse_snapshot(
    payload: Mapping[str, Any],
    *,
    received_at: datetime,
    market_state: Mapping[str, Any] | None = None,
) -> DdaRateSnapshot:
    """Validate an authoritative snapshot and select only the stable item ID."""
    validate_schema(payload, label="DDA SSE", require_view=True)
    item = _target_item(payload.get("items"), unit_required=True)
    if item is None:
        raise DdaRateContractError("SSE snapshot omitted the Agra Mohar item ID.")
    timestamp = _utc(received_at)
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=positive_finite_number(item.get("finalRate"), "SSE finalRate"),
        unit=DDA_RATE_UNIT,
        sequence=nonnegative_int(payload.get("sequence"), "SSE sequence"),
        received_at=timestamp,
        server_time=timestamp,
        market_state=(dict(market_state) if market_state is not None else None),
        transport="sse",
    )


def apply_sse_rate_event(
    payload: Mapping[str, Any],
    *,
    previous: DdaRateSnapshot | None,
    received_at: datetime,
    market_state: Mapping[str, Any] | None = None,
) -> tuple[int, DdaRateSnapshot | None]:
    """Validate a rate delta and apply it only when its item ID matches."""
    validate_schema(payload, label="DDA SSE", require_view=True)
    sequence = nonnegative_int(payload.get("sequence"), "SSE sequence")
    item = _target_item(payload.get("items"), unit_required=False)
    if item is None:
        return sequence, None
    if previous is None:
        raise DdaRateContractError("SSE rate delta arrived before a snapshot.")
    timestamp = _utc(received_at)
    return sequence, replace(
        previous,
        final_rate=positive_finite_number(item.get("finalRate"), "SSE finalRate"),
        sequence=sequence,
        received_at=timestamp,
        server_time=timestamp,
        market_state=(
            dict(market_state) if market_state is not None else previous.market_state
        ),
        transport="sse",
    )


class SseDecoder:
    """Split a ``text/event-stream`` byte stream into ``(event, data)`` pairs."""

    def __init__(self, on_malformed: Callable[[UnicodeDecodeError], None]) -> None:
        self._on_malformed = on_malformed
        self._buffer = bytearray()
        self._event = "message"
        self._data: list[str] = []

    def push(self, chunk: bytes) -> None:
        self._buffer += chunk

    def next_event(self) -> tuple[str, str] | None:
        """Return the next complete event, or ``None`` until more bytes arrive."""
        while True:
            end = self._buffer.find(b"\n")
            if (len(self._buffer) if end < 0 else end) > MAX_SSE_LINE_BYTES:
                raise DdaRateContractError("DDA SSE line exceeded 1 MiB.")
            if end < 0:
                return None
            raw_line = bytes(self._buffer[:end])
            del self._buffer[: end + 1]
            try:
                line = raw_line.decode("utf-8").rstrip("\r")
            except UnicodeDecodeError as exc:
                self._on_malformed(exc)
                self._event, self._data = "message", []
                continue
            if not line:
                event, data = self._event, self._data
                self._event, self._data = "message", []
                if data:
                    return event, "\n".join(data)
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                self._event = value
            elif field == "data":
                self._data.append(value)


class DdaRateStream(QObject):
    """Hydrate over HTTPS, then keep the rate current from the SSE stream.

    Everything runs on the owner's thread from network and timer signals, so
    :meth:`stop` takes effect at once.
    """

    rate_received = Signal(object)
    feed_status_received = Signal(object)
    connection_state_changed = Signal(str)
    stream_error = Signal(str)

    def __init__(
        self,
        *,
        current_client: DdaCurrentRatesClient | None = None,
        snapshot_store: DdaSnapshotStore | None = None,
        stream_url: str = DDA_RATE_STREAM_URL,
        manager: QNetworkAccessManager | None = None,
        logger: logging.Logger | None = None,
        now: Callable[[], datetime] = utc_now,
        jitter: Callable[[float], float] | None = None,
        stale_after: float = 45.0,
        poll_interval: float = 10.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager or network_manager(self)
        self._current_client = current_client or DdaCurrentRatesClient(
            manager=self._manager, parent=self
        )
        self._current_client.snapshot_received.connect(self._on_current_rates)
        self._current_client.failed.connect(self._on_current_rates_failed)
        self._snapshot_store = snapshot_store or DdaSnapshotStore(logger=logger)
        self._stream_url = stream_url
        self._logger = logger or logging.getLogger(__name__)
        self._now = now
        self._jitter = jitter or (
            lambda delay: delay * random.uniform(0.8, 1.2)  # noqa: S311
        )
        self._stale_after = stale_after
        self._stale_timer = self._timer(stale_after, self._on_stale, single_shot=True)
        self._reconnect_timer = self._timer(0, self._open_stream, single_shot=True)
        self._poll_timer = self._timer(poll_interval, self._poll, single_shot=False)
        self._running = False
        self._fetch_reason: str | None = None
        self._seeded = False
        self._backoff_index = 0
        self._reply: QNetworkReply | None = None
        self._decoder: SseDecoder | None = None
        self._connected = False
        self._event_count = 0
        self._reset = False
        self._failure: str | None = None
        self._last_snapshot: DdaRateSnapshot | None = None
        self._last_sequence: int | None = None
        self._market_state: Mapping[str, Any] | None = None

    def _timer(
        self, seconds: float, slot: Callable[[], None], *, single_shot: bool
    ) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(single_shot)
        timer.setInterval(int(seconds * 1000))
        timer.timeout.connect(slot)
        return timer

    @property
    def last_sequence(self) -> int | None:
        return self._last_sequence

    def start(self) -> None:
        """Hydrate from current rates, then open the stream."""
        if self._running:
            return
        self._running = True
        self._backoff_index = 0
        self._fetch(HYDRATION)

    def request_refresh(self) -> None:
        """Reconcile through current rates now, then reconnect the stream."""
        if not self._running:
            return
        self._reconnect_timer.stop()
        self._close_stream()
        self._fetch(MANUAL_REFRESH)

    def stop(self) -> None:
        """Abort every request and timer; nothing is delivered afterwards."""
        if not self._running:
            return
        self._running = False
        self._fetch_reason = None
        for timer in (self._stale_timer, self._reconnect_timer, self._poll_timer):
            timer.stop()
        self._current_client.cancel()
        self._close_stream()
        self.connection_state_changed.emit("stopped")

    def stream_request(self, *, seeded: bool) -> QNetworkRequest:
        """Build the anonymous stream request; ``seeded`` skips the first snapshot."""
        query = QUrlQuery()
        if seeded:
            query.addQueryItem("seeded", "1")
        query.addQueryItem("surface", "desktop")
        url = QUrl(self._stream_url)
        url.setQuery(query)
        request = rate_request(url, "text/event-stream")
        request.setRawHeader(b"Cache-Control", b"no-cache")
        # Events must arrive as they are sent, not when a compressor flushes.
        request.setRawHeader(b"Accept-Encoding", b"identity")
        return request

    def _fetch(self, reason: str) -> None:
        self._fetch_reason = reason
        self._current_client.fetch()

    def _on_current_rates(self, snapshot: DdaRateSnapshot) -> None:
        reason, self._fetch_reason = self._fetch_reason, None
        if not self._running or reason is None:
            return
        self._accept_snapshot(snapshot, persist=True, authoritative=True)
        if reason == HYDRATION:
            self.connection_state_changed.emit("hydrated")
        if reason in (HYDRATION, MANUAL_REFRESH):
            self._seeded = True
            self._open_stream()
        elif reason == GAP_RECOVERY:
            self._drain()

    def _on_current_rates_failed(self, error: object) -> None:
        reason, self._fetch_reason = self._fetch_reason, None
        if not self._running or reason is None:
            return
        self.stream_error.emit(f"DDA {reason} failed: {error}")
        if reason == HYDRATION:
            cached = self._snapshot_store.load()
            if cached is not None:
                self._accept_snapshot(cached, persist=False, authoritative=True)
                self.connection_state_changed.emit("offline-stale")
            else:
                self.connection_state_changed.emit("disconnected")
        if reason in (HYDRATION, MANUAL_REFRESH):
            self._open_stream()
        elif reason == GAP_RECOVERY:
            self._fail_stream("DDA sequence-gap recovery failed.")

    def _open_stream(self) -> None:
        if not self._running:
            return
        self._reconnect_timer.stop()
        self._close_stream()
        request = self.stream_request(seeded=self._seeded)
        self._seeded = False
        self.connection_state_changed.emit("connecting")
        reply = self._manager.get(request)
        self._reply = reply
        self._decoder = SseDecoder(self._report_malformed_text)
        self._connected = False
        self._event_count = 0
        self._reset = False
        self._failure = None
        reply.metaDataChanged.connect(partial(self._on_stream_headers, reply))
        reply.readyRead.connect(partial(self._on_stream_data, reply))
        reply.finished.connect(partial(self._end_stream, reply))
        self._stale_timer.start()

    def _on_stream_headers(self, reply: QNetworkReply) -> None:
        if reply is not self._reply or self._connected:
            return
        status = http_status(reply)
        if status is None:
            return
        if status != 200:
            self._fail_stream(f"DDA SSE returned HTTP {status}.")
            return
        self._connected = True
        self._poll_timer.stop()
        self.connection_state_changed.emit("connected")

    def _on_stream_data(self, reply: QNetworkReply) -> None:
        self._on_stream_headers(reply)
        decoder = self._decoder
        if reply is not self._reply or decoder is None:
            return
        self._stale_timer.start()
        decoder.push(bytes(reply.readAll().data()))
        self._drain()

    def _drain(self) -> None:
        """Dispatch buffered events until the stream pauses, resets, or ends."""
        reply, decoder = self._reply, self._decoder
        if reply is None or decoder is None:
            return
        try:
            # Events wait in the buffer while a sequence gap is reconciled.
            while self._reply is reply and self._fetch_reason != GAP_RECOVERY:
                event = decoder.next_event()
                if event is None:
                    return
                self._event_count += 1
                if self._dispatch_event(*event):
                    self._reset = True
                    reply.abort()
                    self._end_stream(reply)
        except DdaRateContractError as exc:
            self._fail_stream(str(exc))

    def _report_malformed_text(self, error: UnicodeDecodeError) -> None:
        self.stream_error.emit(f"Malformed DDA SSE UTF-8: {error}")

    def _on_stale(self) -> None:
        self._fail_stream(
            f"DDA SSE socket had no activity for {self._stale_after:g} seconds."
        )

    def _fail_stream(self, message: str) -> None:
        reply = self._reply
        if reply is None:
            return
        self._failure = message
        reply.abort()
        self._end_stream(reply)

    def _end_stream(self, reply: QNetworkReply) -> None:
        if reply is not self._reply:
            return
        self._reply = None
        self._decoder = None
        self._stale_timer.stop()
        reply.deleteLater()
        if self._event_count:
            self._backoff_index = 0
        if self._reset:
            self.connection_state_changed.emit("reconnecting")
            self._open_stream()
            return
        self.connection_state_changed.emit("disconnected")
        self.stream_error.emit(self._failure or self._close_reason(reply))
        delay = self._jitter(RECONNECT_DELAYS[self._backoff_index])
        self._backoff_index = min(self._backoff_index + 1, len(RECONNECT_DELAYS) - 1)
        self._reconnect_timer.start(int(delay * 1000))
        if not self._poll_timer.isActive():
            self._poll_timer.start()

    @staticmethod
    def _close_reason(reply: QNetworkReply) -> str:
        status = http_status(reply)
        if status is not None and status != 200:
            return f"DDA SSE returned HTTP {status}."
        if reply.error() != QNetworkReply.NetworkError.NoError:
            return reply.errorString()
        return "DDA SSE stream ended unexpectedly."

    def _close_stream(self) -> None:
        """Drop the active stream without treating it as a failure."""
        reply, self._reply = self._reply, None
        self._decoder = None
        self._stale_timer.stop()
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _poll(self) -> None:
        """Keep the rate fresh from current rates while the stream is down."""
        if self._running and self._fetch_reason is None:
            self._fetch(FALLBACK_POLL)

    def _dispatch_event(self, event_name: str, raw_data: str) -> bool:
        try:
            payload = json.loads(raw_data)
            if not isinstance(payload, Mapping):
                raise DdaRateContractError("DDA SSE data must be a JSON object.")
            if event_name == "snapshot":
                self._handle_snapshot(payload)
            elif event_name == "rate":
                self._handle_rate(payload)
            elif event_name == "feed-status":
                self._handle_feed_status(payload)
            elif event_name == "heartbeat":
                validate_schema(payload, label="DDA SSE", require_view=False)
            elif event_name == "stream-reset":
                validate_schema(payload, label="DDA SSE", require_view=False)
                if payload.get("reason") != "max_age":
                    raise DdaRateContractError("Unknown DDA stream-reset reason.")
                return True
        except (json.JSONDecodeError, DdaRateContractError) as exc:
            self.stream_error.emit(f"Malformed DDA SSE {event_name} event: {exc}")
        return False

    def _handle_snapshot(self, payload: Mapping[str, Any]) -> None:
        snapshot = parse_sse_snapshot(
            payload,
            received_at=self._now(),
            market_state=self._market_state,
        )
        if self._last_sequence is not None and snapshot.sequence <= self._last_sequence:
            return
        self._accept_snapshot(snapshot, persist=True, authoritative=True)

    def _handle_rate(self, payload: Mapping[str, Any]) -> None:
        validate_schema(payload, label="DDA SSE", require_view=True)
        sequence = nonnegative_int(payload.get("sequence"), "SSE sequence")
        if self._last_sequence is not None and sequence <= self._last_sequence:
            return
        if self._last_sequence is None or sequence != self._last_sequence + 1:
            self._fetch(GAP_RECOVERY)
            return
        sequence, snapshot = apply_sse_rate_event(
            payload,
            previous=self._last_snapshot,
            received_at=self._now(),
            market_state=self._market_state,
        )
        self._last_sequence = sequence
        if snapshot is not None:
            self._accept_snapshot(snapshot, persist=True, authoritative=False)

    def _handle_feed_status(self, payload: Mapping[str, Any]) -> None:
        validate_schema(payload, label="DDA SSE", require_view=False)
        # The server sends a word such as "stale"; only marketState is used.
        status = payload.get("status")
        if status is not None and not isinstance(status, str | Mapping):
            raise DdaRateContractError(
                "DDA feed-status status must be text or an object."
            )
        market_state = payload.get("marketState")
        if market_state is not None and not isinstance(market_state, Mapping):
            raise DdaRateContractError("DDA feed-status marketState must be an object.")
        if isinstance(market_state, Mapping):
            self._market_state = dict(market_state)
        self.feed_status_received.emit(dict(payload))

    def _accept_snapshot(
        self,
        snapshot: DdaRateSnapshot,
        *,
        persist: bool,
        authoritative: bool,
    ) -> None:
        if (
            not authoritative
            and self._last_sequence is not None
            and snapshot.sequence < self._last_sequence
        ):
            return
        self._last_snapshot = snapshot
        self._last_sequence = snapshot.sequence
        if snapshot.market_state is not None:
            self._market_state = dict(snapshot.market_state)
        if persist and snapshot.transport != "cache":
            self._snapshot_store.save(snapshot)
        self.rate_received.emit(snapshot)


__all__ = [
    "DDA_RATE_STREAM_URL",
    "DdaRateStream",
    "SseDecoder",
    "apply_sse_rate_event",
    "parse_sse_snapshot",
]
