"""Crypto prices widget — CoinGecko's free /simple/price endpoint.

No key, no auth. CoinGecko rate-limits to ~30 requests/minute on the
public endpoint, so we cache aggressively (5 min default) and aggregate
all watchlist coins into a single API call.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any


SIMPLE_URL = "https://api.coingecko.com/api/v3/simple/price"
MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}

# CoinGecko accepts ~50+ vs_currencies (the full ISO fiat set plus btc /
# eth / sats / etc). Rather than maintain a list manually, we accept any
# 2-5 character alphabetic token — anything CoinGecko doesn't recognise
# comes back as an empty payload and surfaces as "no rates returned".
import re as _re
_VS_RE = _re.compile(r"^[a-z]{2,5}$")

# Common ticker → CoinGecko id shorthand. Lets the user type "btc" instead
# of "bitcoin" without surprising anyone who already knows the canonical id.
_ALIASES = {
    "btc": "bitcoin",
    "eth": "ethereum",
    "sol": "solana",
    "ada": "cardano",
    "doge": "dogecoin",
    "dot": "polkadot",
    "xrp": "ripple",
    "ltc": "litecoin",
    "matic": "matic-network",
    "link": "chainlink",
    "avax": "avalanche-2",
}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-crypto"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _normalize_ids(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for piece in (raw or "").replace(" ", ",").split(","):
        token = piece.strip().lower()
        if not token:
            continue
        cid = _ALIASES.get(token, token)
        if cid in seen:
            continue
        out.append(cid)
        seen.add(cid)
    return out


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    ids = _normalize_ids(options.get("ids") or "bitcoin,ethereum,solana")
    if not ids:
        return {"error": "set at least one coin id"}
    ids = ids[:8]
    vs = (options.get("vs") or "usd").strip().lower()
    if not _VS_RE.match(vs):
        vs = "usd"
    sparkline = options.get("sparkline") is not False  # default true

    ttl = int(settings.get("CRYPTO_CACHE_S") or 300)
    cache_key = f"{vs}:{int(sparkline)}:{','.join(ids)}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    # When the sparkline option is on we use /coins/markets which returns
    # a 7-day price array per coin in a single call. Without sparklines we
    # stick to /simple/price (lighter, plays nicer with rate limits).
    rows: list[dict] = []
    try:
        if sparkline:
            qs = urllib.parse.urlencode({
                "vs_currency": vs,
                "ids": ",".join(ids),
                "sparkline": "true",
                "price_change_percentage": "24h",
            })
            body = _http_json(f"{MARKETS_URL}?{qs}")
            by_id = {item.get("id"): item for item in body if isinstance(item, dict)}
            for cid in ids:
                item = by_id.get(cid)
                if not item:
                    continue
                price = item.get("current_price")
                change = item.get("price_change_percentage_24h")
                spark = ((item.get("sparkline_in_7d") or {}).get("price")) or []
                if price is None:
                    continue
                rows.append(_row(cid, float(price), change, _decimate_spark(spark, 32)))
        else:
            qs = urllib.parse.urlencode({
                "ids": ",".join(ids),
                "vs_currencies": vs,
                "include_24hr_change": "true",
            })
            body = _http_json(f"{SIMPLE_URL}?{qs}")
            for cid in ids:
                item = body.get(cid) or {}
                price = item.get(vs)
                if price is None:
                    continue
                rows.append(_row(cid, float(price), item.get(f"{vs}_24h_change"), None))
    except Exception as exc:
        return {"error": f"CoinGecko failed: {type(exc).__name__}: {exc}"}

    out: dict[str, Any] = {
        "vs": vs.upper(),
        "rows": rows,
        "sparkline": sparkline,
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out


def _row(cid: str, price: float, change_raw, spark: list[float] | None) -> dict:
    try:
        change = float(change_raw) if change_raw is not None else None
    except (TypeError, ValueError):
        change = None
    return {
        "id": cid,
        "label": _LABELS.get(cid, cid).upper() if cid in _LABELS else cid.upper(),
        "value": _fmt_price(price),
        "raw": price,
        "delta_pct": round(change, 2) if change is not None else None,
        "direction": "up" if (change or 0) > 0 else ("down" if (change or 0) < 0 else "flat"),
        "spark": spark,
    }


def _decimate_spark(points: list[float], target: int) -> list[float]:
    """Sparkline returns ~168 hourly points. Cards render fine at ~32, so
    we downsample with a simple stride to keep payloads tiny + the chart
    snappy without losing the shape."""
    if not points:
        return []
    if len(points) <= target:
        return [round(float(p), 6) for p in points if p is not None]
    stride = max(1, len(points) // target)
    out = [float(points[i]) for i in range(0, len(points), stride) if points[i] is not None]
    return [round(p, 6) for p in out[:target]]


def _fmt_price(v: float) -> str:
    """Auto-precision: BTC reads as $81,287; SHIB-style reads as 0.0000123."""
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.2f}"
    if v >= 0.01:
        return f"{v:.4f}".rstrip("0").rstrip(".")
    return f"{v:.8f}".rstrip("0").rstrip(".")


# Symbol abbreviations — only the popular ones; anything else falls back
# to the raw CoinGecko id in upper-case which is still readable.
_LABELS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "cardano": "ADA",
    "dogecoin": "DOGE",
    "polkadot": "DOT",
    "ripple": "XRP",
    "litecoin": "LTC",
    "matic-network": "MATIC",
    "chainlink": "LINK",
    "avalanche-2": "AVAX",
}
