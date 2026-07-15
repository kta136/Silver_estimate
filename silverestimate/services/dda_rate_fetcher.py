"""Validated anonymous client for DDA's public customer-rate snapshot."""

from __future__ import annotations

import json
import logging
import math
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Any, Literal, Protocol, cast

from silverestimate.infrastructure.settings import SettingsStore, get_app_settings

DDA_CURRENT_RATES_URL = "https://ddajewels.com/api/v1/rates/current"
DDA_AGRA_MOHAR_ITEM_ID = "cmomws5tw000004i5k5t6yrnw"
DDA_RATE_UNIT = "PER_KG"
DDA_SCHEMA_VERSION = 1
MAX_CURRENT_RATES_BYTES = 2 * 1024 * 1024
SNAPSHOT_SETTINGS_KEY = "rates/dda_last_verified_snapshot"

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

    def as_cached(self) -> DdaRateSnapshot:
        return replace(self, transport="cache")


class _HttpResponse(Protocol):
    status: int

    def read(self, amount: int = -1) -> bytes: ...

    def __enter__(self) -> _HttpResponse: ...

    def __exit__(self, *args: object) -> object: ...


HttpOpen = Callable[..., _HttpResponse]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DdaRateContractError(f"{field} must be a non-negative integer.")
    return value


def _positive_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DdaRateContractError(f"{field} must be a finite positive number.")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise DdaRateContractError(f"{field} must be a finite positive number.")
    return number


def _validate_schema_and_view(payload: Mapping[str, Any]) -> None:
    if payload.get("schemaVersion") != DDA_SCHEMA_VERSION:
        raise DdaRateContractError("Unsupported DDA schemaVersion; expected 1.")
    if payload.get("view") not in {"default", "tv"}:
        raise DdaRateContractError("DDA view must be 'default' or 'tv'.")


def _matching_item(items: object, *, require_unit: bool) -> Mapping[str, Any]:
    if not isinstance(items, list):
        raise DdaRateContractError("DDA items must be an array.")
    matches = [
        item
        for item in items
        if isinstance(item, Mapping) and item.get("itemId") == DDA_AGRA_MOHAR_ITEM_ID
    ]
    if len(matches) != 1:
        raise DdaRateContractError(
            "DDA response must contain exactly one configured Agra Mohar item ID."
        )
    item = cast(Mapping[str, Any], matches[0])
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
    _validate_schema_and_view(decoded)
    sequence = _nonnegative_int(decoded.get("sequence"), "sequence")
    server_time = _parse_datetime(decoded.get("serverTime"), "serverTime")
    item = _matching_item(decoded.get("items"), require_unit=True)
    final_rate = _positive_finite_number(item.get("finalRate"), "finalRate")
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


class DdaCurrentRatesClient:
    """Anonymous HTTPS hydration and sequence-reconciliation client."""

    def __init__(
        self,
        *,
        endpoint: str = DDA_CURRENT_RATES_URL,
        timeout: float = 7.0,
        opener: HttpOpen = urllib.request.urlopen,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._opener = opener
        self._now = now

    def fetch_current(self) -> DdaRateSnapshot:
        """Fetch the public snapshot without API-key or authorization headers."""
        request = urllib.request.Request(
            self._endpoint,
            headers={
                "Accept": "application/json",
                "User-Agent": "SilverEstimate/2.0",
            },
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                status = int(getattr(response, "status", 200))
                if status != 200:
                    raise DdaRateTransportError(
                        f"DDA current-rates returned HTTP {status}."
                    )
                body = response.read(MAX_CURRENT_RATES_BYTES + 1)
        except DdaRateError:
            raise
        except Exception as exc:
            raise DdaRateTransportError(
                f"DDA current-rates request failed: {exc}"
            ) from exc
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
            settings = self._settings_provider()
            settings.setValue(
                SNAPSHOT_SETTINGS_KEY,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
            )
            settings.sync()
        except Exception as exc:
            self._logger.warning("Could not persist verified DDA snapshot: %s", exc)

    def load(self) -> DdaRateSnapshot | None:
        try:
            raw = self._settings_provider().value(SNAPSHOT_SETTINGS_KEY, "")
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
                final_rate=_positive_finite_number(
                    decoded.get("final_rate"), "cached final_rate"
                ),
                unit=DDA_RATE_UNIT,
                sequence=_nonnegative_int(decoded.get("sequence"), "cached sequence"),
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
    "parse_current_rates",
]
