import json
from datetime import datetime, timezone

import pytest

from silverestimate.services.dda_rate_fetcher import (
    DDA_AGRA_MOHAR_ITEM_ID,
    DDA_CURRENT_RATES_URL,
    DdaCurrentRatesClient,
    DdaRateContractError,
    DdaSnapshotStore,
    parse_current_rates,
)


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


class _Response:
    status = 200

    def __init__(self, body):
        self.body = body

    def read(self, amount=-1):
        return self.body[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


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


def test_client_is_anonymous_and_uses_only_public_https_endpoint():
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = {
            key.lower(): value for key, value in request.header_items()
        }
        captured["timeout"] = timeout
        return _Response(json.dumps(_payload()).encode())

    snapshot = DdaCurrentRatesClient(opener=opener, timeout=3).fetch_current()

    assert snapshot.final_rate == 123456.5
    assert captured["url"] == DDA_CURRENT_RATES_URL
    assert captured["timeout"] == 3
    assert "authorization" not in captured["headers"]
    assert "x-api-key" not in captured["headers"]
    assert "api-key" not in captured["headers"]


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
