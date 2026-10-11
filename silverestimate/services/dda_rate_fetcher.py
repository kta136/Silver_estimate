"""Validated anonymous client for DDA's public customer-rate snapshot."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from functools import partial
from typing import Any, Literal, cast

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
    QSslSocket,
)

from silverestimate.infrastructure.settings import (
    SettingsKey,
    SettingsStore,
    as_settings_store,
    get_app_settings,
)

DDA_CURRENT_RATES_URL = "https://ddajewels.com/api/v1/rates/current"
DDA_AGRA_MOHAR_ITEM_ID = "cmomws5tw000004i5k5t6yrnw"
DDA_RATE_UNIT = "PER_KG"
DDA_SCHEMA_VERSION = 1
MAX_CURRENT_RATES_BYTES = 2 * 1024 * 1024

RateTransport = Literal["https", "sse", "cache"]


class DdaRateError(RuntimeError):
    """Base error for public DDA transport and contract failures."""


class DdaRateTransportError(DdaRateError):
    """The public HTTPS request could not be completed."""


class DdaRateContractError(DdaRateError):
    """A DDA response did not satisfy the public version-1 contract."""


@dataclass(frozen=True)
class DdaRateSnapshot:
    """Verified customer-facing Agra Mohar rate and stream position."""

    item_id: str
    final_rate: float
    unit: str
    sequence: int
    received_at: datetime
    server_time: datetime
    market_state: Mapping[str, Any] | None
    transport: RateTransport


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def network_manager(parent: QObject) -> QNetworkAccessManager:
    """Create a manager that uses Windows' own TLS, the backend the app ships."""
    if "schannel" in QSslSocket.availableBackends():
        QSslSocket.setActiveBackend("schannel")
    return QNetworkAccessManager(parent)


def rate_request(url: QUrl | str, accept: str) -> QNetworkRequest:
    """Build an anonymous request that always reaches the network."""
    request = QNetworkRequest(QUrl(url))
    request.setRawHeader(b"Accept", accept.encode("ascii"))
    request.setRawHeader(b"User-Agent", b"SilverEstimate/2.0")
    request.setAttribute(
        QNetworkRequest.Attribute.CacheLoadControlAttribute,
        QNetworkRequest.CacheLoadControl.AlwaysNetwork,
    )
    return request


def http_status(reply: QNetworkReply) -> int | None:
    """Return the final HTTP status once the response headers have arrived."""
    status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
    if status is None or 300 <= int(status) < 400:
        return None
    return int(status)


def _parse_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DdaRateContractError(f"{field} must be an ISO-8601 timestamp.")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise DdaRateContractError(f"{field} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DdaRateContractError(f"{field} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DdaRateContractError(f"{field} must be a non-negative integer.")
    return value


def positive_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DdaRateContractError(f"{field} must be a finite positive number.")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise DdaRateContractError(f"{field} must be a finite positive number.")
    return number


def validate_schema(
    payload: Mapping[str, Any], *, label: str = "DDA", require_view: bool = True
) -> None:
    """Check the schema version and, where the message carries one, the view."""
    if payload.get("schemaVersion") != DDA_SCHEMA_VERSION:
        raise DdaRateContractError(f"Unsupported {label} schemaVersion; expected 1.")
    if require_view and payload.get("view") not in {"default", "tv"}:
        raise DdaRateContractError(f"{label} view must be 'default' or 'tv'.")


def agra_mohar_items(items: object, *, label: str = "DDA") -> list[Mapping[str, Any]]:
    """Return the entries of ``items`` that carry the configured item ID."""
    if not isinstance(items, list):
        raise DdaRateContractError(f"{label} items must be an array.")
    return [
        cast(Mapping[str, Any], item)
        for item in items
        if isinstance(item, Mapping) and item.get("itemId") == DDA_AGRA_MOHAR_ITEM_ID
    ]


def _matching_item(items: object, *, require_unit: bool) -> Mapping[str, Any]:
    matches = agra_mohar_items(items)
    if len(matches) != 1:
        raise DdaRateContractError(
            "DDA response must contain exactly one configured Agra Mohar item ID."
        )
    item = matches[0]
    if require_unit and item.get("unit") != DDA_RATE_UNIT:
        raise DdaRateContractError("Agra Mohar rate unit must be PER_KG.")
    return item


def parse_current_rates(
    payload: bytes | str | Mapping[str, Any],
    *,
    received_at: datetime | None = None,
) -> DdaRateSnapshot:
    """Parse the public response using only the configured item's ``finalRate``."""
    if isinstance(payload, bytes | str):
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DdaRateContractError("DDA response is not valid JSON.") from exc
    else:
        decoded = payload
    if not isinstance(decoded, Mapping):
        raise DdaRateContractError("DDA response must be a JSON object.")
    validate_schema(decoded)
    sequence = nonnegative_int(decoded.get("sequence"), "sequence")
    server_time = _parse_datetime(decoded.get("serverTime"), "serverTime")
    item = _matching_item(decoded.get("items"), require_unit=True)
    final_rate = positive_finite_number(item.get("finalRate"), "finalRate")
    feed_status = decoded.get("feedStatus")
    market_state: Mapping[str, Any] | None = None
    if feed_status is not None:
        if not isinstance(feed_status, Mapping):
            raise DdaRateContractError("feedStatus must be an object.")
        raw_market_state = feed_status.get("marketState")
        if raw_market_state is not None:
            if not isinstance(raw_market_state, Mapping):
                raise DdaRateContractError("feedStatus.marketState must be an object.")
            market_state = dict(raw_market_state)
    return DdaRateSnapshot(
        item_id=DDA_AGRA_MOHAR_ITEM_ID,
        final_rate=final_rate,
        unit=DDA_RATE_UNIT,
        sequence=sequence,
        received_at=(received_at or utc_now()).astimezone(timezone.utc),
        server_time=server_time,
        market_state=market_state,
        transport="https",
    )


class DdaCurrentRatesClient(QObject):
    """Anonymous HTTPS hydration and sequence-reconciliation client."""

    snapshot_received = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        *,
        endpoint: str = DDA_CURRENT_RATES_URL,
        timeout: float = 7.0,
        manager: QNetworkAccessManager | None = None,
        now: Callable[[], datetime] = utc_now,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._endpoint = endpoint
        self._timeout = timeout
        self._manager = manager or network_manager(self)
        self._now = now
        self._reply: QNetworkReply | None = None
        self._oversized = False

    def fetch(self) -> None:
        """Request the public snapshot, replacing any request still in flight."""
        self.cancel()
        request = rate_request(self._endpoint, "application/json")
        request.setTransferTimeout(int(self._timeout * 1000))
        reply = self._manager.get(request)
        self._reply = reply
        self._oversized = False
        reply.downloadProgress.connect(partial(self._limit_size, reply))
        reply.finished.connect(partial(self._finish, reply))

    def cancel(self) -> None:
        """Abandon the request in flight without reporting a result."""
        reply, self._reply = self._reply, None
        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _limit_size(self, reply: QNetworkReply, received: int, _total: int) -> None:
        if reply is self._reply and received > MAX_CURRENT_RATES_BYTES:
            self._oversized = True
            reply.abort()

    def _finish(self, reply: QNetworkReply) -> None:
        if reply is not self._reply:
            return
        self._reply = None
        reply.deleteLater()
        try:
            snapshot = self._read(reply)
        except DdaRateError as exc:
            self.failed.emit(exc)
            return
        self.snapshot_received.emit(snapshot)

    def _read(self, reply: QNetworkReply) -> DdaRateSnapshot:
        if self._oversized:
            raise DdaRateContractError("DDA current-rates response is too large.")
        status = http_status(reply)
        if status is not None and status != 200:
            raise DdaRateTransportError(f"DDA current-rates returned HTTP {status}.")
        error = reply.error()
        if error in (
            QNetworkReply.NetworkError.OperationCanceledError,
            QNetworkReply.NetworkError.TimeoutError,
        ):
            raise DdaRateTransportError(
                "DDA current-rates request failed: no response within "
                f"{self._timeout:g} seconds."
            )
        if error != QNetworkReply.NetworkError.NoError:
            raise DdaRateTransportError(
                f"DDA current-rates request failed: {reply.errorString()}"
            )
        body = bytes(reply.readAll().data())
        if len(body) > MAX_CURRENT_RATES_BYTES:
            raise DdaRateContractError("DDA current-rates response is too large.")
        return parse_current_rates(body, received_at=self._now())


class DdaSnapshotStore:
    """Persist only the last fully verified public snapshot in QSettings."""

    def __init__(
        self,
        *,
        settings_provider: Callable[[], SettingsStore] = get_app_settings,
        logger: logging.Logger | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._logger = logger or logging.getLogger(__name__)

    def save(self, snapshot: DdaRateSnapshot) -> None:
        payload = asdict(snapshot)
        payload["received_at"] = snapshot.received_at.isoformat()
        payload["server_time"] = snapshot.server_time.isoformat()
        payload["market_state"] = (
            dict(snapshot.market_state) if snapshot.market_state is not None else None
        )
        try:
            settings = as_settings_store(self._settings_provider())
            settings.set(
                SettingsKey.RATES_VERIFIED_SNAPSHOT,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )
            settings.sync()
        except Exception as exc:
            self._logger.warning("Could not persist verified DDA snapshot: %s", exc)

    def load(self) -> DdaRateSnapshot | None:
        try:
            raw = as_settings_store(self._settings_provider()).get_text(
                SettingsKey.RATES_VERIFIED_SNAPSHOT,
            )
            decoded = json.loads(str(raw)) if raw else None
            if not isinstance(decoded, Mapping):
                return None
            item_id = decoded.get("item_id")
            if item_id != DDA_AGRA_MOHAR_ITEM_ID:
                raise DdaRateContractError("Cached DDA item ID does not match.")
            if decoded.get("unit") != DDA_RATE_UNIT:
                raise DdaRateContractError("Cached DDA unit does not match.")
            market_state = decoded.get("market_state")
            if market_state is not None and not isinstance(market_state, Mapping):
                raise DdaRateContractError("Cached DDA market state is invalid.")
            return DdaRateSnapshot(
                item_id=DDA_AGRA_MOHAR_ITEM_ID,
                final_rate=positive_finite_number(
                    decoded.get("final_rate"), "cached final_rate"
                ),
                unit=DDA_RATE_UNIT,
                sequence=nonnegative_int(decoded.get("sequence"), "cached sequence"),
                received_at=_parse_datetime(
                    decoded.get("received_at"), "cached received_at"
                ),
                server_time=_parse_datetime(
                    decoded.get("server_time"), "cached server_time"
                ),
                market_state=(
                    dict(market_state) if isinstance(market_state, Mapping) else None
                ),
                transport="cache",
            )
        except Exception as exc:
            self._logger.warning("Ignoring invalid cached DDA snapshot: %s", exc)
            return None


__all__ = [
    "DDA_AGRA_MOHAR_ITEM_ID",
    "DDA_CURRENT_RATES_URL",
    "DDA_RATE_UNIT",
    "DDA_SCHEMA_VERSION",
    "DdaCurrentRatesClient",
    "DdaRateContractError",
    "DdaRateError",
    "DdaRateSnapshot",
    "DdaRateTransportError",
    "DdaSnapshotStore",
    "agra_mohar_items",
    "http_status",
    "network_manager",
    "nonnegative_int",
    "parse_current_rates",
    "positive_finite_number",
    "rate_request",
    "validate_schema",
]
