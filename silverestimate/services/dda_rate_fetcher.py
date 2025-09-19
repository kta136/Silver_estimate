#!/usr/bin/env python
import json
import urllib.request
import urllib.error

API_PATH = "index.php/C_booking/get_commodity_data"
DEFAULT_BASE_URL = "http://www.ddasilver.com/"
TARGET_NAME = "Silver Agra Local Mohar"

# Broadcast endpoint used by site UI for exact on-screen numbers
BROADCAST_URL = "http://3.109.80.6/lmxtrade/winbullliteapi/api/v1/broadcastrates"
BROADCAST_CLIENT = "ddasil"


def fetch_silver_agra_local_mohar_rate(base_url: str = DEFAULT_BASE_URL, timeout: int = 10):
    """
    Fetch the live rate for 'Silver Agra Local Mohar' from DDASilver.

    Returns a tuple: (rate_int_or_none, metadata_dict)
    - rate is an integer (rounded according to allowed decimals), or None on failure
    - metadata contains the raw item record when available
    """
    url = base_url.rstrip("/") + "/" + API_PATH
    req = urllib.request.Request(url, headers={
        "User-Agent": "SilverEstimate/1.0 (+https://ddasilver.com)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Expect JSON response
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None, {}

    try:
        commodities = data.get("commodity", {}).get("commoditydetails", [])
        for item in commodities:
            # Defensive: names can differ in case
            if str(item.get("com_name", "")).strip().lower() == TARGET_NAME.lower():
                raw_rate = item.get("sell_rate")
                allowed_decimals = item.get("allowed_decimals", "0")
                try:
                    decimals = int(str(allowed_decimals))
                except Exception:
                    decimals = 0

                rate_float = float(raw_rate) if raw_rate is not None else None
                if rate_float is None:
                    return None, item

                # Round according to allowed_decimals and cast to int if 0 decimals
                if decimals <= 0:
                    rate_val = int(round(rate_float))
                else:
                    # Keep decimals as integer value e.g., 123.45 -> 12345 when decimals=2?
                    # For our UI (QDoubleSpinBox), we only need a numeric value.
                    # Return the float rounded to 'decimals'; caller can format.
                    rate_val = round(rate_float, decimals)
                return rate_val, item
        return None, {}
    except Exception:
        return None, {}

def _main():
    rate, meta = fetch_silver_agra_local_mohar_rate()
    if rate is None:
        print("Failed to fetch rate from commodity API; attempting broadcast…")
        br, open_, info = fetch_broadcast_rate_exact()
        print(br, open_, info)
    else:
        print(rate)

def _lookup_com_id_for_target(base_url: str = DEFAULT_BASE_URL, timeout: int = 10):
    """Resolve com_id for TARGET_NAME via the commodity API."""
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
    req = urllib.request.Request(
        BROADCAST_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "SilverEstimate/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None, True, {"com_id": com_id}

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
                    BROADCAST_URL,
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

    return rate_val, market_open, {"com_id": com_id}


if __name__ == "__main__":
    _main()
