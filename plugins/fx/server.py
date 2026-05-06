"""FX rates widget — ECB rates via frankfurter.dev (no key, no auth).

Pulls today's rates plus the most recent prior weekday (frankfurter
auto-rolls weekend dates to the prior Friday) so we can compute a 1-day
delta for the green/red arrow.

frankfurter only covers major fiat currencies — for crypto, use the
crypto plugin which is wired against CoinGecko.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any


API_URL = "https://api.frankfurter.dev/v1"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-fx"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _normalize_codes(raw: str) -> list[str]:
    """Comma- or space-separated → list of upper-case 3-letter codes."""
    out: list[str] = []
    seen: set[str] = set()
    for piece in (raw or "").replace(" ", ",").split(","):
        code = piece.strip().upper()
        if not code or code in seen:
            continue
        if len(code) == 3 and code.isalpha():
            out.append(code)
            seen.add(code)
    return out


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    base = (options.get("base") or "USD").strip().upper()
    if not (len(base) == 3 and base.isalpha()):
        return {"error": "base currency must be a 3-letter code (e.g. USD)"}
    symbols = _normalize_codes(options.get("symbols") or "EUR,GBP,AUD,JPY")
    if not symbols:
        return {"error": "set at least one watchlist currency"}
    # Defensive cap so a runaway list doesn't hammer the API.
    symbols = symbols[:8]

    ttl = int(settings.get("FX_CACHE_S") or 1800)
    cache_key = f"{base}:{','.join(symbols)}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    qs = urllib.parse.urlencode({"base": base, "symbols": ",".join(symbols)})
    try:
        latest = _http_json(f"{API_URL}/latest?{qs}")
    except Exception as exc:
        return {"error": f"FX feed failed: {type(exc).__name__}: {exc}"}

    today = latest.get("date") or date.today().isoformat()
    # Day-before for the delta. frankfurter rolls weekends to prior Friday
    # automatically, so a literal subtraction works without weekday math.
    prev_date = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    try:
        prev = _http_json(f"{API_URL}/{prev_date}?{qs}")
    except Exception:
        prev = {"rates": {}}

    rows = []
    latest_rates = latest.get("rates") or {}
    prev_rates = prev.get("rates") or {}
    for code in symbols:
        v = latest_rates.get(code)
        p = prev_rates.get(code)
        if v is None:
            continue
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        delta_pct = None
        if p is not None:
            try:
                p = float(p)
                if p > 0:
                    delta_pct = round((v - p) / p * 100, 2)
            except (TypeError, ValueError):
                delta_pct = None
        rows.append({
            "code": code,
            "value": _fmt_rate(v),
            "raw": v,
            "delta_pct": delta_pct,
            "direction": "up" if (delta_pct or 0) > 0 else ("down" if (delta_pct or 0) < 0 else "flat"),
        })

    out: dict[str, Any] = {
        "base": base,
        "as_of": today,
        "as_of_prev": prev.get("date") or prev_date,
        "rows": rows,
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out


def _fmt_rate(v: float) -> str:
    """Auto-precision: tiny rates need more decimals, huge ones fewer."""
    if v >= 100:
        return f"{v:,.2f}"
    if v >= 1:
        return f"{v:,.4f}".rstrip("0").rstrip(".")
    return f"{v:.6f}".rstrip("0").rstrip(".")
