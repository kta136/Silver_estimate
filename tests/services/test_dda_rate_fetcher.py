import json
from datetime import datetime, timezone

import pytest

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DDA_CURRENT_RATES_URL,
    MAX_CURRENT_RATES_BYTES,
    DdaCurrentRatesClient,
    DdaRateContractError,
    DdaRateTransportError,
    DdaSnapshotStore,
    parse_current_rates,
)
from tests.rate_server_support import RateServer, direct_manager

WAIT_MS = 5000


def _payload(**overrides):
    payload = {
        "schemaVersion": 1,
        "view": "default",
        "serverTime": "2026-07-15T08:30:00.000Z",
        "sequence": 42,
        "items": [
            {
                "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                "name": "A renamed public item",
                "unit": "PER_KG",
                "finalRate": 123456.5,
                "baseRate": 111.0,
                "movementValue": 0,
                "movementDirection": "flat",
            }
        ],
        "feedStatus": {
            "status": None,
            "marketState": {
                "code": "open_live",
                "label": "Market open",
            },
        },
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def server():
    rate_server = RateServer()
    yield rate_server
    rate_server.close()


class _Fetch:
    """A client pointed at the loopback server, recording its one outcome."""

    def __init__(self, server, qtbot, **options):
        self.qtbot = qtbot
        self.manager = direct_manager()
        self.client = DdaCurrentRatesClient(
            endpoint=server.current_url, manager=self.manager, **options
        )
        self.snapshots = []
        self.failures = []
        self.client.snapshot_received.connect(self.snapshots.append)
        self.client.failed.connect(self.failures.append)

    def run(self):
        self.client.fetch()
        self.qtbot.waitUntil(
            lambda: bool(self.snapshots or self.failures), timeout=WAIT_MS
        )
        return self


class _Settings:
    def __init__(self):
        self.values = {}

    def value(self, key, default=None, type=None):  # noqa: A002
        del type
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def sync(self):
        return None


def test_parse_selects_exact_item_id_and_uses_final_rate_not_base_rate():
    payload = _payload()
    payload["items"].insert(
        0,
        {
            "itemId": "different-id",
            "name": "Silver Agra Mohar",
            "unit": "PER_KG",
            "finalRate": 999999,
        },
    )

    snapshot = parse_current_rates(payload)

    assert snapshot.item_id == DDA_AGRA_MOHAR_ITEM_ID
    assert snapshot.final_rate == 123456.5
    assert snapshot.final_rate != 111.0
    assert snapshot.unit == "PER_KG"
    assert snapshot.sequence == 42
    assert snapshot.transport == "https"
    assert snapshot.market_state["code"] == "open_live"


def test_client_is_anonymous_and_uses_only_public_https_endpoint(qt_app):
    class _Captured(Exception):
        pass

    class _Manager:
        def get(self, request):
            self.request = request
            raise _Captured

    manager = _Manager()

    with pytest.raises(_Captured):
        DdaCurrentRatesClient(manager=manager, timeout=3).fetch()

    request = manager.request
    headers = {name.data().decode().lower() for name in request.rawHeaderList()}
    assert request.url().toString() == DDA_CURRENT_RATES_URL
    assert DDA_CURRENT_RATES_URL.startswith("https://")
    assert request.transferTimeout() == 3000
    assert headers == {"accept", "user-agent"}


def test_client_delivers_the_verified_snapshot(server, qtbot):
    server.queue_current(_payload())

    fetch = _Fetch(server, qtbot).run()

    assert fetch.failures == []
    assert fetch.snapshots[0].final_rate == 123456.5
    assert fetch.snapshots[0].transport == "https"
    sent = {name.lower() for name in server.requests[0][1]}
    assert not sent & {"authorization", "x-api-key", "api-key", "cookie"}


def test_client_reports_an_http_error_status(server, qtbot):
    server.queue_current({"error": "down"}, status=502)

    fetch = _Fetch(server, qtbot).run()

    assert fetch.snapshots == []
    assert isinstance(fetch.failures[0], DdaRateTransportError)
    assert "HTTP 502" in str(fetch.failures[0])


def test_client_gives_up_when_the_server_never_answers(server, qtbot):
    fetch = _Fetch(server, qtbot, timeout=0.2).run()

    assert isinstance(fetch.failures[0], DdaRateTransportError)
    assert "no response within 0.2 seconds" in str(fetch.failures[0])


def test_client_rejects_an_oversized_response(server, qtbot):
    server.queue_current(b" " * (MAX_CURRENT_RATES_BYTES + 1))

    fetch = _Fetch(server, qtbot).run()

    assert isinstance(fetch.failures[0], DdaRateContractError)
    assert "too large" in str(fetch.failures[0])


def test_client_rejects_a_response_that_breaks_the_contract(server, qtbot):
    server.queue_current(_payload(schemaVersion=2))

    fetch = _Fetch(server, qtbot).run()

    assert isinstance(fetch.failures[0], DdaRateContractError)


def test_a_cancelled_or_replaced_request_reports_nothing(server, qtbot):
    fetch = _Fetch(server, qtbot)
    fetch.client.fetch()
    qtbot.waitUntil(lambda: bool(server.requests), timeout=WAIT_MS)

    fetch.client.cancel()
    qtbot.wait(100)
    assert fetch.snapshots == fetch.failures == []

    fetch.client.fetch()
    for _abandoned_or_live in range(3):
        server.queue_current(_payload())
    fetch.run()
    qtbot.wait(100)

    assert len(fetch.snapshots) == 1
    assert fetch.failures == []


@pytest.mark.parametrize(
    "payload",
    [
        _payload(schemaVersion=2),
        _payload(view="desktop"),
        _payload(serverTime="not-a-date"),
        _payload(serverTime="2026-07-15T08:30:00"),
        _payload(sequence=-1),
        _payload(items=[]),
        _payload(
            items=[
                {
                    "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                    "unit": "PER_GRAM",
                    "finalRate": 1,
                }
            ]
        ),
        _payload(
            items=[
                {
                    "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                    "unit": "PER_KG",
                    "finalRate": 0,
                }
            ]
        ),
        _payload(
            items=[
                {
                    "itemId": DDA_AGRA_MOHAR_ITEM_ID,
                    "unit": "PER_KG",
                    "finalRate": float("inf"),
                }
            ]
        ),
    ],
)
def test_parse_rejects_invalid_public_contract(payload):
    with pytest.raises(DdaRateContractError):
        parse_current_rates(payload)


def test_parser_ignores_unknown_fields_for_forward_compatibility():
    payload = _payload(futureTopLevel={"enabled": True})
    payload["items"][0]["futureItemField"] = [1, 2, 3]

    assert parse_current_rates(payload).final_rate == 123456.5


def test_snapshot_store_round_trip_marks_snapshot_as_cached():
    settings = _Settings()
    store = DdaSnapshotStore(settings_provider=lambda: settings)
    snapshot = parse_current_rates(
        _payload(),
        received_at=datetime(2026, 7, 15, 8, 31, tzinfo=timezone.utc),
    )

    store.save(snapshot)
    restored = store.load()

    assert restored is not None
    assert restored.transport == "cache"
    assert restored.final_rate == snapshot.final_rate
    assert restored.sequence == snapshot.sequence
    assert restored.server_time == snapshot.server_time


def test_snapshot_store_ignores_wrong_item_id():
    settings = _Settings()
    store = DdaSnapshotStore(settings_provider=lambda: settings)
    snapshot = parse_current_rates(_payload())
    store.save(snapshot)
    cached = json.loads(next(iter(settings.values.values())))
    cached["item_id"] = "wrong"
    settings.values[next(iter(settings.values))] = json.dumps(cached)

    assert store.load() is None
