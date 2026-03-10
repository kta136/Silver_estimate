import ssl
import urllib.error

import pytest

from silverestimate.services import dda_rate_fetcher


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fetch_silver_agra_local_mohar_rate_prefers_numeric_display_rate(monkeypatch):
    html = f"""
    <html><body>
      <table>
        <tr>
          <td>{dda_rate_fetcher.TARGET_NAME}</td>
          <td>
            <div class="com_id">47</div>
            <div class="sell_rate">95,000</div>
            <div class="com_display_purity">92.5</div>
            <div class="redround">95,000</div>
          </td>
        </tr>
      </table>
    </body></html>
    """

    def _fake_urlopen(req, timeout=10):  # noqa: ARG001
        return _FakeResponse(html.encode("utf-8"))

    monkeypatch.setattr(dda_rate_fetcher.urllib.request, "urlopen", _fake_urlopen)

    rate, metadata = dda_rate_fetcher.fetch_silver_agra_local_mohar_rate(
        base_url="http://example.test", timeout=5
    )

    assert rate == 95000
    assert metadata["source"] == "scraped"
    assert metadata["raw_source"] == "display_rate"


def test_fetch_silver_agra_local_mohar_rate_returns_none_on_network_failure(
    monkeypatch,
):
    def _raise_urlerror(req, timeout=10):  # noqa: ARG001
        raise urllib.error.URLError("network down")

    monkeypatch.setattr(dda_rate_fetcher.urllib.request, "urlopen", _raise_urlerror)

    rate, metadata = dda_rate_fetcher.fetch_silver_agra_local_mohar_rate(timeout=1)

    assert rate is None
    assert metadata == {}


def test_parse_scraped_rate_falls_back_to_display_rate_when_sell_missing():
    html = f"""
    <tr>
      <td>{dda_rate_fetcher.TARGET_NAME}</td>
      <td>
        <div class="display_rate">48,123.50</div>
        <div class="greenround">48,123.50</div>
      </td>
    </tr>
    """

    rate, metadata = dda_rate_fetcher._parse_scraped_rate(
        html, dda_rate_fetcher.TARGET_NAME
    )

    assert rate == 48123.5
    assert metadata["raw_source"] == "display_rate"
    assert metadata["source"] == "scraped"


def test_parse_scraped_rate_handles_missing_target_row():
    rate, metadata = dda_rate_fetcher._parse_scraped_rate(
        "<html><body>No matching commodity row</body></html>",
        dda_rate_fetcher.TARGET_NAME,
    )

    assert rate is None
    assert metadata == {}


def test_lookup_com_id_for_target_handles_valid_and_invalid_values(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "fetch_silver_agra_local_mohar_rate",
        lambda **kwargs: (50000, {"com_id": "47"}),
    )
    assert dda_rate_fetcher._lookup_com_id_for_target() == 47

    monkeypatch.setattr(
        dda_rate_fetcher,
        "fetch_silver_agra_local_mohar_rate",
        lambda **kwargs: (None, {"com_id": "not-an-int"}),
    )
    assert dda_rate_fetcher._lookup_com_id_for_target() is None


def test_lookup_homepage_broadcast_url_extracts_bcurl(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_HOMEPAGE_BROADCAST_URL",
        None,
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_fetch_url_text",
        lambda url, **kwargs: (
            'var bcurl = "http://live.example/feed";'
            if url == "http://example.test/"
            else ""
        ),
    )

    endpoint = dda_rate_fetcher._lookup_homepage_broadcast_url(
        base_url="http://example.test"
    )

    assert endpoint == "http://live.example/feed"


def test_fetch_broadcast_rate_exact_prefers_homepage_advertised_endpoint(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_HOMEPAGE_BROADCAST_URL",
        None,
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "BROADCAST_URLS",
        (
            "http://stale-one/feed",
            "http://stale-two/feed",
        ),
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_lookup_homepage_broadcast_url",
        lambda **kwargs: "http://homepage-live/feed",
    )

    calls = []

    def _fake_fetch(endpoint, payload, timeout):  # noqa: ARG001
        calls.append(endpoint)
        if endpoint == "http://homepage-live/feed":
            return "3\t47\t0\t0\t52500"
        raise AssertionError(f"unexpected endpoint call: {endpoint}")

    monkeypatch.setattr(dda_rate_fetcher, "_fetch_broadcast_payload", _fake_fetch)

    rate, market_open, info = dda_rate_fetcher.fetch_broadcast_rate_exact()

    assert rate == 52500
    assert market_open is True
    assert info["endpoint"] == "http://homepage-live/feed"
    assert calls == ["http://homepage-live/feed"]


def test_main_prints_scraped_rate(monkeypatch, capsys):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "fetch_silver_agra_local_mohar_rate",
        lambda: (50001, {"source": "scraped"}),
    )
    dda_rate_fetcher._main()
    assert capsys.readouterr().out.strip() == "50001"


def test_main_falls_back_to_broadcast_when_scrape_fails(monkeypatch, capsys):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "fetch_silver_agra_local_mohar_rate",
        lambda: (None, {}),
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "fetch_broadcast_rate_exact",
        lambda: (49000, True, {"com_id": 47}),
    )

    dda_rate_fetcher._main()

    out = capsys.readouterr().out
    assert "attempting broadcast" in out
    assert "49000 True {'com_id': 47}" in out


def test_fetch_broadcast_rate_exact_returns_errors_when_all_endpoints_fail(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_lookup_homepage_broadcast_url",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "BROADCAST_URLS",
        ("http://a", "http://b"),
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_fetch_broadcast_payload",
        lambda endpoint, payload, timeout: (_ for _ in ()).throw(
            RuntimeError(f"{endpoint} down")
        ),
    )
    monkeypatch.setattr(dda_rate_fetcher, "_lookup_com_id_for_target", lambda **_: None)

    rate, market_open, info = dda_rate_fetcher.fetch_broadcast_rate_exact()

    assert rate is None
    assert market_open is True
    assert info["com_id"] == 47
    assert len(info["errors"]) == 2


def test_fetch_broadcast_payload_uses_post_request_shape(monkeypatch):
    calls = {}

    def _fake_fetch_url_text(url, **kwargs):
        calls["url"] = url
        calls["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr(dda_rate_fetcher, "_fetch_url_text", _fake_fetch_url_text)

    assert (
        dda_rate_fetcher._fetch_broadcast_payload("http://endpoint", b"{}", 3) == "ok"
    )
    assert calls["url"] == "http://endpoint"
    assert calls["kwargs"]["data"] == b"{}"
    assert calls["kwargs"]["method"] == "POST"
    assert calls["kwargs"]["timeout"] == 3
    assert "Content-Type" in calls["kwargs"]["headers"]


def test_parse_broadcast_payload_tolerates_malformed_rows():
    text = "\n".join(
        [
            "malformed",
            "4\tX\tX\tbad\tworse",
            "3\tbad-cid\t0\t0\t50000",
            "3\t47\t0\t0\tbad-rate",
        ]
    )

    rate, market_open = dda_rate_fetcher._parse_broadcast_payload(
        text, target_com_id=47
    )

    assert rate is None
    assert market_open is True


def test_parse_scraped_rate_handles_empty_keys_and_invalid_numeric_values():
    html = f"""
    <tr>
      <td>{dda_rate_fetcher.TARGET_NAME}</td>
      <td>
        <div class="">ignored</div>
        <div class="sell_rate">-</div>
        <div class="redround">abc</div>
      </td>
    </tr>
    """

    rate, metadata = dda_rate_fetcher._parse_scraped_rate(
        html, dda_rate_fetcher.TARGET_NAME
    )

    assert rate is None
    assert metadata["source"] == "scraped"


def test_parse_scraped_rate_rounds_integer_sell_rate_without_adjustment():
    html = f"""
    <tr>
      <td>{dda_rate_fetcher.TARGET_NAME}</td>
      <td>
        <div class="sell_rate">42000</div>
      </td>
    </tr>
    """

    rate, metadata = dda_rate_fetcher._parse_scraped_rate(
        html, dda_rate_fetcher.TARGET_NAME
    )

    assert rate == 42000
    assert metadata["raw_source"] == "sell_rate"
    assert metadata["parsed_decimals"] == 0


def test_parse_scraped_rate_applies_display_purity_when_display_missing():
    html = f"""
    <tr>
      <td>{dda_rate_fetcher.TARGET_NAME}</td>
      <td>
        <div class="redround">-</div>
        <div class="sell_rate">275569.00</div>
        <div class="com_display_purity">99</div>
      </td>
    </tr>
    """

    rate, metadata = dda_rate_fetcher._parse_scraped_rate(
        html, dda_rate_fetcher.TARGET_NAME
    )

    assert rate == 272814
    assert metadata["raw_source"] == "sell_rate"
    assert metadata["applied_adjustment"] == "sell_rate * display_purity_percent"
    assert metadata["applied_purity_percent"] == 99.0
    assert metadata["parsed_decimals"] == 0


def test_fetch_url_text_returns_body_without_tls_retry(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher.urllib.request,
        "urlopen",
        lambda req, timeout=10: _FakeResponse(b"plain-ok"),
    )

    assert dda_rate_fetcher._fetch_url_text("https://example.test") == "plain-ok"


def test_fetch_url_text_raises_non_tls_urlerror(monkeypatch):
    def _raise_urlerror(req, timeout=10, context=None):  # noqa: ARG001
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(dda_rate_fetcher.urllib.request, "urlopen", _raise_urlerror)

    with pytest.raises(urllib.error.URLError):
        dda_rate_fetcher._fetch_url_text("https://example.test")


def test_dynamic_broadcast_lookup_continues_when_dynamic_fetch_errors(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_lookup_homepage_broadcast_url",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(dda_rate_fetcher, "BROADCAST_URLS", ("http://one",))
    monkeypatch.setattr(dda_rate_fetcher, "_lookup_com_id_for_target", lambda **_: 99)

    calls = {"count": 0}

    def _fake_fetch(endpoint, payload, timeout):  # noqa: ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            return "3\t46\t0\t0\t50000"  # static parse misses target com_id=47
        raise RuntimeError("dynamic fetch failed")

    monkeypatch.setattr(dda_rate_fetcher, "_fetch_broadcast_payload", _fake_fetch)

    rate, market_open, info = dda_rate_fetcher.fetch_broadcast_rate_exact(
        prefer_static_id=True
    )

    assert rate is None
    assert market_open is True
    assert info["com_id"] == 99


def test_fetch_url_text_retries_with_unverified_tls_on_cert_error(monkeypatch):
    calls = []

    cert_err = ssl.SSLCertVerificationError(
        1,
        "certificate verify failed: self-signed certificate",
    )

    def _fake_urlopen(req, timeout=10, context=None):
        calls.append({"url": req.full_url, "timeout": timeout, "context": context})
        if context is None:
            raise urllib.error.URLError(cert_err)
        return _FakeResponse(b"ok")

    monkeypatch.setattr(
        dda_rate_fetcher.urllib.request,
        "urlopen",
        _fake_urlopen,
    )

    text = dda_rate_fetcher._fetch_url_text(
        "https://13.235.208.189/lmxtrade/winbullliteapi/api/v1/broadcastrates",
        timeout=5,
    )

    assert text == "ok"
    assert len(calls) == 2
    assert calls[0]["context"] is None
    assert calls[1]["context"] is not None


def test_fetch_url_text_does_not_retry_for_untrusted_host(monkeypatch):
    cert_err = ssl.SSLCertVerificationError(
        1,
        "certificate verify failed: self-signed certificate",
    )

    def _fake_urlopen(req, timeout=10, context=None):  # noqa: ARG001
        raise urllib.error.URLError(cert_err)

    monkeypatch.setattr(
        dda_rate_fetcher.urllib.request,
        "urlopen",
        _fake_urlopen,
    )

    with pytest.raises(ValueError, match="Blocked request to untrusted endpoint"):
        dda_rate_fetcher._fetch_url_text(
            "https://example.com/path",
            timeout=5,
        )


def test_parse_broadcast_payload_marks_market_closed_and_extracts_rate():
    text = "\n".join(
        [
            "4\t0\t0\t0\t1",
            "3\t47\t0\t0\t50123.9",
        ]
    )

    rate, market_open = dda_rate_fetcher._parse_broadcast_payload(
        text, target_com_id=47
    )

    assert rate == 50123
    assert market_open is False


def test_fetch_broadcast_rate_exact_falls_back_to_secondary_endpoint(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_lookup_homepage_broadcast_url",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "BROADCAST_URLS",
        (
            "http://primary.invalid/feed",
            "http://secondary.valid/feed",
        ),
    )

    def _fake_fetch(endpoint, payload, timeout):
        if endpoint == "http://primary.invalid/feed":
            raise RuntimeError("primary down")
        return "3\t47\t0\t0\t49000"

    monkeypatch.setattr(dda_rate_fetcher, "_fetch_broadcast_payload", _fake_fetch)

    rate, market_open, info = dda_rate_fetcher.fetch_broadcast_rate_exact()

    assert rate == 49000
    assert market_open is True
    assert info["endpoint"] == "http://secondary.valid/feed"
    assert info["com_id"] == 47


def test_fetch_broadcast_rate_exact_uses_dynamic_com_id_when_static_misses(monkeypatch):
    monkeypatch.setattr(
        dda_rate_fetcher,
        "_lookup_homepage_broadcast_url",
        lambda **kwargs: None,
    )
    monkeypatch.setattr(
        dda_rate_fetcher,
        "BROADCAST_URLS",
        ("http://single.endpoint/feed",),
    )
    monkeypatch.setattr(dda_rate_fetcher, "_lookup_com_id_for_target", lambda **_: 99)

    monkeypatch.setattr(
        dda_rate_fetcher,
        "_fetch_broadcast_payload",
        lambda endpoint, payload, timeout: "3\t99\t0\t0\t52500",
    )

    rate, market_open, info = dda_rate_fetcher.fetch_broadcast_rate_exact(
        prefer_static_id=True
    )

    assert rate == 52500
    assert market_open is True
    assert info["com_id"] == 99
