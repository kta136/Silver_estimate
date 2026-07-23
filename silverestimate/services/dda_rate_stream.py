"""Cancellable SSE transport for DDA's public Agra Mohar customer rate."""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Protocol, cast
from urllib.parse import urlencode

from PySide6.QtCore import QObject, Signal

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DDA_RATE_UNIT,
    DDA_SCHEMA_VERSION,
    DdaCurrentRatesClient,
    DdaRateContractError,
    DdaRateSnapshot,
    DdaSnapshotStore,
    utc_now,
)

DDA_RATE_STREAM_URL = "https://ddajewels.com/sse/rates"
RECONNECT_DELAYS = (1.0, 2.0, 4.0, 8.0, 10.0)


class _StreamResponse(Protocol):
    status: int

    def readline(self, limit: int = -1) -> bytes: ...

    def close(self) -> None: ...


StreamOpen = Callable[..., _StreamResponse]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise DdaRateContractError("SSE receipt time must include a timezone.")
    return value.astimezone(timezone.utc)


def _sequence(payload: Mapping[str, Any]) -> int:
    value = payload.get("sequence")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DdaRateContractError("SSE sequence must be a non-negative integer.")
    return value


def _schema(payload: Mapping[str, Any], *, require_view: bool = False) -> None:
    if payload.get("schemaVersion") != DDA_SCHEMA_VERSION:
        raise DdaRateContractError("Unsupported DDA SSE schemaVersion; expected 1.")
    if require_view and payload.get("view") not in {"default", "tv"}:
        raise DdaRateContractError("DDA SSE view must be 'default' or 'tv'.")


def _finite_positive(value: object) -> float:
    from math import isfinite

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DdaRateContractError("SSE finalRate must be a finite positive number.")
    result = float(value)
    if not isfinite(result) or result <= 0:
        raise DdaRateContractError("SSE finalRate must be a finite positive number.")
    return result


def _target_item(items: object, *, unit_required: bool) -> Mapping[str, Any] | None:
    if not isinstance(items, list):
        raise DdaRateContractError("SSE items must be an array.")
    matches = [
        item
        for item in items
        if isinstance(item, Mapping) and item.get("itemId") == DDA_AGRA_MOHAR_ITEM_ID
    ]
    if len(matches) > 1:
        raise DdaRateContractError("SSE payload duplicated the Agra Mohar item ID.")
    if not matches:
        return None
    item = cast(Mapping[str, Any], matches[0])
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
    _schema(payload, require_view=True)
    item = _target_item(payload.get("items"), unit_required=True)
    if item is None:
        raise DdaRateContractError("SSE snapshot omitted the Agra Mohar item ID.")
    timestamp = _utc(received_at)
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=_finite_positive(item.get("finalRate")),
        unit=DDA_RATE_UNIT,
        sequence=_sequence(payload),
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
    _schema(payload, require_view=True)
    sequence = _sequence(payload)
    item = _target_item(payload.get("items"), unit_required=False)
    if item is None:
        return sequence, None
    if previous is None:
        raise DdaRateContractError("SSE rate delta arrived before a snapshot.")
    timestamp = _utc(received_at)
    return sequence, replace(
        previous,
        final_rate=_finite_positive(item.get("finalRate")),
        sequence=sequence,
        received_at=timestamp,
        server_time=timestamp,
        market_state=(
            dict(market_state) if market_state is not None else previous.market_state
        ),
        transport="sse",
    )


class DdaRateStreamWorker(QObject):
    """Hydrate over HTTPS, then maintain the rate through a blocking SSE stream."""

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
        opener: StreamOpen = urllib.request.urlopen,
        logger: logging.Logger | None = None,
        now: Callable[[], datetime] = utc_now,
        monotonic: Callable[[], float] = time.monotonic,
        jitter: Callable[[float], float] | None = None,
        stale_after: float = 45.0,
        poll_interval: float = 10.0,
    ) -> None:
        super().__init__()
        self._current_client = current_client or DdaCurrentRatesClient()
        self._snapshot_store = snapshot_store or DdaSnapshotStore(logger=logger)
        self._stream_url = stream_url
        self._opener = opener
        self._logger = logger or logging.getLogger(__name__)
        self._now = now
        self._monotonic = monotonic
        self._jitter = jitter or (
            lambda delay: delay * random.uniform(0.8, 1.2)  # noqa: S311
        )
        self._stale_after = stale_after
        self._poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._refresh_event = threading.Event()
        self._response_lock = threading.Lock()
        self._active_response: _StreamResponse | None = None
        self._last_snapshot: DdaRateSnapshot | None = None
        self._last_sequence: int | None = None
        self._market_state: Mapping[str, Any] | None = None

    @property
    def last_sequence(self) -> int | None:
        return self._last_sequence

    def request_refresh(self) -> None:
        """Wake the loop and force an anonymous current-rates reconciliation."""
        self._refresh_event.set()
        self._close_active_response()

    def stop(self) -> None:
        """Cooperatively stop and close the active response to unblock reads."""
        self._stop_event.set()
        self._refresh_event.set()
        self._close_active_response()

    def run(self) -> None:
        """Run in a dedicated ``QThread`` until :meth:`stop` is called."""
        seeded = self._hydrate_initial()
        backoff_index = 0
        next_poll_at = self._monotonic() + self._poll_interval
        while not self._stop_event.is_set():
            if self._refresh_event.is_set():
                self._refresh_event.clear()
                seeded = self._reconcile_current("manual refresh") or seeded
                if self._stop_event.is_set():
                    break
            try:
                self.connection_state_changed.emit("connecting")
                event_count, reset = self._connect_and_consume(seeded=seeded)
                seeded = False
                if event_count:
                    backoff_index = 0
                if self._stop_event.is_set():
                    break
                if reset:
                    self.connection_state_changed.emit("reconnecting")
                    continue
                raise ConnectionError("DDA SSE stream ended unexpectedly.")
            except Exception as exc:
                self._clear_active_response()
                if self._stop_event.is_set():
                    break
                if self._refresh_event.is_set():
                    continue
                self.connection_state_changed.emit("disconnected")
                self.stream_error.emit(str(exc))
                delay = self._jitter(RECONNECT_DELAYS[backoff_index])
                backoff_index = min(backoff_index + 1, len(RECONNECT_DELAYS) - 1)
                next_poll_at = self._wait_disconnected(delay, next_poll_at)
        self._close_active_response()
        self.connection_state_changed.emit("stopped")

    def _hydrate_initial(self) -> bool:
        try:
            snapshot = self._current_client.fetch_current()
        except Exception as exc:
            self.stream_error.emit(f"DDA startup hydration failed: {exc}")
            cached = self._snapshot_store.load()
            if cached is not None:
                self._accept_snapshot(cached, persist=False, authoritative=True)
                self.connection_state_changed.emit("offline-stale")
            else:
                self.connection_state_changed.emit("disconnected")
            return False
        self._accept_snapshot(snapshot, persist=True, authoritative=True)
        self.connection_state_changed.emit("hydrated")
        return True

    def _reconcile_current(self, reason: str) -> bool:
        try:
            snapshot = self._current_client.fetch_current()
        except Exception as exc:
            self.stream_error.emit(f"DDA {reason} failed: {exc}")
            return False
        self._accept_snapshot(snapshot, persist=True, authoritative=True)
        return True

    def _stream_request(self, *, seeded: bool) -> urllib.request.Request:
        query: list[tuple[str, str]] = []
        if seeded:
            query.append(("seeded", "1"))
        query.append(("surface", "desktop"))
        return urllib.request.Request(
            f"{self._stream_url}?{urlencode(query)}",
            headers={
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache",
                "User-Agent": "SilverEstimate/2.0",
            },
            method="GET",
        )

    def _connect_and_consume(self, *, seeded: bool) -> tuple[int, bool]:
        request = self._stream_request(seeded=seeded)
        response = self._opener(request, timeout=self._stale_after)
        if int(getattr(response, "status", 200)) != 200:
            response.close()
            raise ConnectionError(
                f"DDA SSE returned HTTP {getattr(response, 'status', 'unknown')}."
            )
        with self._response_lock:
            self._active_response = response
        self.connection_state_changed.emit("connected")
        try:
            return self._consume_response(response)
        finally:
            try:
                response.close()
            finally:
                self._clear_active_response(response)

    def _consume_response(self, response: _StreamResponse) -> tuple[int, bool]:
        event_name = "message"
        data_lines: list[str] = []
        event_count = 0
        last_activity = self._monotonic()
        while not self._stop_event.is_set():
            raw_line = response.readline(1024 * 1024 + 1)
            now = self._monotonic()
            if now - last_activity > self._stale_after:
                raise TimeoutError("DDA SSE socket had no activity for 45 seconds.")
            if not raw_line:
                return event_count, False
            if len(raw_line) > 1024 * 1024:
                raise DdaRateContractError("DDA SSE line exceeded 1 MiB.")
            last_activity = now
            try:
                line = raw_line.decode("utf-8").rstrip("\r\n")
            except UnicodeDecodeError as exc:
                self.stream_error.emit(f"Malformed DDA SSE UTF-8: {exc}")
                event_name, data_lines = "message", []
                continue
            if not line:
                if data_lines:
                    reset = self._dispatch_event(event_name, "\n".join(data_lines))
                    event_count += 1
                    if reset:
                        return event_count, True
                event_name, data_lines = "message", []
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value[1:] if value.startswith(" ") else value
            if field == "event":
                event_name = value
            elif field == "data":
                data_lines.append(value)
        return event_count, False

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
                _schema(payload)
            elif event_name == "stream-reset":
                _schema(payload)
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
        _schema(payload, require_view=True)
        sequence = _sequence(payload)
        if self._last_sequence is not None and sequence <= self._last_sequence:
            return
        if self._last_sequence is None or sequence != self._last_sequence + 1:
            if not self._reconcile_current("sequence-gap recovery"):
                raise ConnectionError("DDA sequence-gap recovery failed.")
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
        _schema(payload)
        status = payload.get("status")
        if not isinstance(status, Mapping):
            raise DdaRateContractError("DDA feed-status status must be an object.")
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

    def _wait_disconnected(self, delay: float, next_poll_at: float) -> float:
        deadline = self._monotonic() + max(0.0, delay)
        while not self._stop_event.is_set():
            now = self._monotonic()
            if self._refresh_event.is_set():
                return next_poll_at
            if now >= next_poll_at:
                self._reconcile_current("10-second fallback poll")
                next_poll_at = self._monotonic() + self._poll_interval
            if now >= deadline:
                return next_poll_at
            self._stop_event.wait(min(0.25, deadline - now, next_poll_at - now))
        return next_poll_at

    def _close_active_response(self) -> None:
        with self._response_lock:
            response = self._active_response
            self._active_response = None
        if response is not None:
            try:
                response.close()
            except Exception as exc:
                self._logger.debug("Failed to close DDA SSE response: %s", exc)

    def _clear_active_response(self, expected: _StreamResponse | None = None) -> None:
        with self._response_lock:
            if expected is None or self._active_response is expected:
                self._active_response = None


__all__ = [
    "DDA_RATE_STREAM_URL",
    "DdaRateStreamWorker",
    "apply_sse_rate_event",
    "parse_sse_snapshot",
]
