#!/usr/bin/env python
import json
import re
import urllib.error
import urllib.request
from html import unescape
from typing import Optional

DEFAULT_BASE_URL = "http://www.ddasilver.com/"
TARGET_NAME = "Silver Agra Local Mohar"

SCRAPE_HEADERS = {
    "User-Agent": "SilverEstimate/1.0 (+https://ddasilver.com)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Connection": "close",
}

# Broadcast endpoints used by site UI for exact on-screen numbers.
# The vendor recently migrated the live feed to a new host (13.235.208.189)
# but left the previous endpoint running with stale data. Probe the new host
# first and fall back to the legacy endpoint to remain compatible.
BROADCAST_URLS = (
    "http://13.235.208.189/lmxtrade/winbullliteapi/api/v1/broadcastrates",
    "http://3.109.80.6/lmxtrade/winbullliteapi/api/v1/broadcastrates",
)
BROADCAST_URL = BROADCAST_URLS[0]
BROADCAST_CLIENT = "ddasil"


def fetch_silver_agra_local_mohar_rate(base_url: str = DEFAULT_BASE_URL, timeout: int = 10):
    """
    Fetch the live rate for 'Silver Agra Local Mohar' by scraping the DDASilver homepage.

    Returns a tuple: (rate_int_or_none, metadata_dict)
    - rate is an integer (rounded) or None when the content could not be parsed
    - metadata contains the raw hidden-row fields when available
    """
    url = base_url.rstrip("/") + "/"
    headers = dict(SCRAPE_HEADERS)
    headers.setdefault("Referer", url)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        return None, {}

    return _parse_scraped_rate(html, TARGET_NAME)


def _parse_scraped_rate(html: str, target_name: str):
    """Parse the commodity table markup and extract the rate plus related metadata."""
    row_pattern = re.compile(
        r"<tr[^>]*>\s*<td[^>]*>\s*"
        + re.escape(target_name)
        + r"\s*</td>(?P<body>.*?)</tr>",
        re.IGNORECASE | re.DOTALL,
    )
    row_match = row_pattern.search(html)
    if not row_match:
        return None, {}

    cells_html = row_match.group("body")
    metadata = {}

    for div_match in re.finditer(
        r'<div\s+[^>]*class="([^"]+)"[^>]*>\s*([^<]*)</div>',
        cells_html,
        re.IGNORECASE | re.DOTALL,
    ):
        key = div_match.group(1).strip()
        if not key:
            continue
        value = unescape(div_match.group(2).strip())
        metadata[key] = value

    display_match = re.search(
        r'<div[^>]*class="[^"]*(?:redround|greenround)[^"]*"[^>]*>\s*([^<]*)</div>',
        cells_html,
        re.IGNORECASE | re.DOTALL,
    )
    if display_match:
        display_value = unescape(display_match.group(1).strip())
        if display_value:
            metadata.setdefault("display_rate", display_value)

    metadata["source"] = "scraped"

    def _convert_to_float(raw_val: Optional[str]) -> Optional[float]:
        if raw_val is None:
            return None
        cleaned = raw_val.replace(",", "").strip()
        if cleaned in {"", "-", "--"}:
            return None
        # Strip currency symbols if present
        cleaned = cleaned.lstrip("₹").strip()
        try:
            return float(cleaned)
        except Exception:
            return None

    rate_float = None
    source = None
    sell_rate_val = _convert_to_float(metadata.get("sell_rate"))
    if sell_rate_val is not None:
        rate_float = sell_rate_val
        source = "sell_rate"
        diff_val = _convert_to_float(metadata.get("sell_diff"))
        if diff_val is not None and diff_val != 0:
            rate_float = sell_rate_val - diff_val
            metadata["applied_diff"] = diff_val
            metadata["applied_adjustment"] = "sell_rate - sell_diff"
    if rate_float is None:
        display_val = _convert_to_float(metadata.get("display_rate"))
        if display_val is not None:
            rate_float = display_val
            source = "display_rate"

    if rate_float is None:
        return None, metadata

    decimals = 0
    rate_str = f"{rate_float}"
    if "." in rate_str:
        decimals = len(rate_str.split(".", 1)[1].rstrip("0"))
    if decimals <= 0:
        rate_val = int(round(rate_float))
    else:
        decimals = min(decimals, 4)
        rate_val = round(rate_float, decimals)
    metadata["parsed_decimals"] = decimals
    if source:
        metadata["raw_source"] = source
    return rate_val, metadata

def _main():
    rate, meta = fetch_silver_agra_local_mohar_rate()
    if rate is None:
        print("Failed to scrape rate from homepage; attempting broadcast...")
        br, open_, info = fetch_broadcast_rate_exact()
        print(br, open_, info)
    else:
        print(rate)

def _lookup_com_id_for_target(base_url: str = DEFAULT_BASE_URL, timeout: int = 10):
    """Resolve com_id for TARGET_NAME via the scraped metadata."""
    rate, item = fetch_silver_agra_local_mohar_rate(base_url=base_url, timeout=timeout)
    try:
        return int(item.get("com_id")) if item else None
    except Exception:
        return None

def fetch_broadcast_rate_exact(timeout: int = 10, client: str = BROADCAST_CLIENT, target_name: str = TARGET_NAME,
                               base_url: str = DEFAULT_BASE_URL, prefer_static_id: bool = True):
    """
    Fetch the exact on-screen rate via the broadcast endpoint the site uses.

    Returns (rate_or_none, market_open_bool, info_dict)
    - rate: integer if available
    - market_open_bool: False when the broadcast signals market closed/message mode
    - info: auxiliary data (e.g., matched com_id)
    """
    import urllib.request, json

    # Prefer the known com_id (47) to avoid blocking on the website during lookup.
    # Only attempt dynamic lookup if explicitly requested and broadcast parsing fails.
    com_id = 47 if prefer_static_id else (_lookup_com_id_for_target(base_url=base_url, timeout=timeout) or 47)

    payload = json.dumps({"client": client}).encode("utf-8")
    text = None
    endpoint_used = None
    fetch_errors = []
    for endpoint in BROADCAST_URLS:
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "SilverEstimate/1.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            endpoint_used = endpoint
            break
        except Exception as exc:
            fetch_errors.append(repr(exc))
            continue
    if text is None:
        info = {"com_id": com_id}
        if fetch_errors:
            info["errors"] = fetch_errors
        return None, True, info

    rate_val = None
    market_open = True

    lines = text.splitlines()
    for line in lines:
        parts = line.split("\t")
        if not parts or len(parts) < 2:
            continue
        rec_type = parts[0]
        # Market/Message status record
        if rec_type == "4":
            try:
                # parts[3] == 0 => closed; parts[4] == 1 => message mode
                closed_flag = int(parts[3]) == 0
                message_flag = int(parts[4]) == 1
                if closed_flag or message_flag:
                    market_open = False
            except Exception:
                pass
        # Commodity rate record
        if rec_type == "3":
            try:
                cid = int(parts[1])
            except Exception:
                continue
            if cid == com_id:
                # Indexes as per site JS: [3]=buy, [4]=sell
                try:
                    rate_val = int(float(parts[4]))
                except Exception:
                    try:
                        rate_val = int(round(float(parts[4])))
                    except Exception:
                        rate_val = None
    # If not found and we didn't try dynamic lookup, try once more by resolving com_id dynamically
    if rate_val is None and prefer_static_id:
        dyn_id = _lookup_com_id_for_target(base_url=base_url, timeout=timeout)
        if dyn_id and dyn_id != com_id:
            try:
                payload = json.dumps({"client": client}).encode("utf-8")
                req = urllib.request.Request(
                    endpoint_used or BROADCAST_URLS[0],
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "SilverEstimate/1.0"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    text = resp.read().decode("utf-8", errors="replace")
                for line in text.splitlines():
                    parts = line.split("\t")
                    if parts and parts[0] == "3":
                        try:
                            cid = int(parts[1])
                        except Exception:
                            continue
                        if cid == dyn_id:
                            try:
                                rate_val = int(float(parts[4]))
                            except Exception:
                                try:
                                    rate_val = int(round(float(parts[4])))
                                except Exception:
                                    rate_val = None
                            break
            except Exception:
                pass

        com_id = dyn_id or com_id

    info = {"com_id": com_id}
    if endpoint_used:
        info["endpoint"] = endpoint_used
    return rate_val, market_open, info


if __name__ == "__main__":
    _main()
