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
