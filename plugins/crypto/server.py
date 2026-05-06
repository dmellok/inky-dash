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


API_URL = "https://api.coingecko.com/api/v3/simple/price"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}

_VALID_VS = {"usd", "eur", "gbp", "aud", "jpy", "cad", "chf", "nzd"}

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
    if vs not in _VALID_VS:
        vs = "usd"

    ttl = int(settings.get("CRYPTO_CACHE_S") or 300)
    cache_key = f"{vs}:{','.join(ids)}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    qs = urllib.parse.urlencode({
        "ids": ",".join(ids),
        "vs_currencies": vs,
        "include_24hr_change": "true",
    })
    try:
        body = _http_json(f"{API_URL}?{qs}")
    except Exception as exc:
        return {"error": f"CoinGecko failed: {type(exc).__name__}: {exc}"}

    rows: list[dict] = []
    for cid in ids:
        item = body.get(cid)
        if not item:
            continue
        price = item.get(vs)
        change = item.get(f"{vs}_24h_change")
        if price is None:
            continue
        try:
            price = float(price)
        except (TypeError, ValueError):
            continue
        try:
            change = float(change) if change is not None else None
        except (TypeError, ValueError):
            change = None
        rows.append({
            "id": cid,
            "label": _LABELS.get(cid, cid).upper() if cid in _LABELS else cid.upper(),
            "value": _fmt_price(price),
            "raw": price,
            "delta_pct": round(change, 2) if change is not None else None,
            "direction": "up" if (change or 0) > 0 else ("down" if (change or 0) < 0 else "flat"),
        })

    out: dict[str, Any] = {
        "vs": vs.upper(),
        "rows": rows,
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out


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
