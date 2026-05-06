"""Tide chart widget — open-meteo marine sea-level height through the day.

No key. open-meteo marine returns hourly sea_level_height_msl in metres
referenced to mean sea level — the curve oscillates around 0 with peaks
at high tide and troughs at low tide. Server identifies the four (or
six, in mixed semidiurnal regions) extrema and ships them alongside the
24h series so the client can label highs/lows and place a "now" cursor.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime
from typing import Any


API_URL = "https://marine-api.open-meteo.com/v1/marine"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-tide"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _extrema(values: list[float], times: list[str]) -> list[dict]:
    """Naive local-extrema detector — every interior point that's higher
    (or lower) than both neighbours. Endpoints handled separately so the
    first/last hour can still flag a peak when the dataset cuts the
    cycle."""
    out: list[dict] = []
    n = len(values)
    if n < 3:
        return out
    for i in range(1, n - 1):
        v = values[i]
        if v is None:
            continue
        prev_v = values[i - 1]
        next_v = values[i + 1]
        if prev_v is None or next_v is None:
            continue
        if v > prev_v and v > next_v:
            out.append({"kind": "high", "t": times[i], "v": round(float(v), 2), "idx": i})
        elif v < prev_v and v < next_v:
            out.append({"kind": "low",  "t": times[i], "v": round(float(v), 2), "idx": i})
    return out


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    try:
        lat = float(options.get("lat") or "-37.85")
        lng = float(options.get("lng") or "144.96")
    except (TypeError, ValueError):
        return {"error": "lat/lng must be numbers"}
    place = (options.get("place_label") or "").strip()

    ttl = int(settings.get("TIDE_CACHE_S") or 1800)
    cache_key = f"{lat:.4f},{lng:.4f}:{date.today().isoformat()}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            cached = dict(hit[1])
            cached["place"] = place
            cached["now_iso"] = datetime.now().astimezone().isoformat(timespec="minutes")
            return cached

    qs = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lng,
        "hourly": "sea_level_height_msl",
        "timezone": "auto",
        "forecast_days": 1,
    })
    try:
        body = _http_json(f"{API_URL}?{qs}")
    except Exception as exc:
        return {"error": f"marine API failed: {type(exc).__name__}: {exc}"}

    hh = body.get("hourly") or {}
    times = hh.get("time") or []
    vals = hh.get("sea_level_height_msl") or []
    if not times or not vals or len(times) != len(vals):
        return {"error": "marine API returned incomplete data"}

    series = []
    for t, v in zip(times, vals):
        if v is None:
            continue
        try:
            series.append({"t": t, "v": round(float(v), 3)})
        except (TypeError, ValueError):
            pass
    if len(series) < 4:
        return {"error": "not enough tide samples for today"}

    extrema = _extrema(
        [s["v"] for s in series],
        [s["t"] for s in series],
    )
    # Min/max for chart scaling. Pad the y-range a touch so the line
    # doesn't kiss the top/bottom edge.
    all_vals = [s["v"] for s in series]
    y_min = min(all_vals)
    y_max = max(all_vals)
    pad = max(0.05, (y_max - y_min) * 0.12)

    return {
        "place": place,
        "series": series,
        "extrema": extrema,
        "y_min": round(y_min - pad, 2),
        "y_max": round(y_max + pad, 2),
        "now_iso": datetime.now().astimezone().isoformat(timespec="minutes"),
    }
