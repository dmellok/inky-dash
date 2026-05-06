"""Wind compass widget — open-meteo current wind direction + speed.

No API key. Caches per (lat, lng, units) so two cells looking at the same
spot share the same upstream call.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any


API_URL = "https://api.open-meteo.com/v1/forecast"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}

_API_UNIT = {"kmh": "kmh", "mph": "mph", "ms": "ms", "kn": "kn"}
_UNIT_LABEL = {"kmh": "km/h", "mph": "mph", "ms": "m/s", "kn": "kn"}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-wind"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _cardinal(deg: float) -> str:
    """16-point cardinal name from a 0-360° bearing."""
    pts = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
           "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = int((deg % 360) / 22.5 + 0.5) % 16
    return pts[idx]


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    try:
        lat = float(options.get("lat") or "-37.8136")
        lng = float(options.get("lng") or "144.9631")
    except (TypeError, ValueError):
        return {"error": "lat/lng must be numbers"}
    place = (options.get("place_label") or "Melbourne").strip()
    units = (options.get("units") or "kmh").strip()
    if units not in _API_UNIT:
        units = "kmh"

    ttl = int(settings.get("WIND_CACHE_S") or 600)
    cache_key = f"{lat:.4f},{lng:.4f}:{units}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            cached = dict(hit[1])
            cached["place"] = place
            return cached

    qs = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lng,
        "current": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "wind_speed_unit": _API_UNIT[units],
        "timezone": "auto",
    })
    try:
        body = _http_json(f"{API_URL}?{qs}")
    except Exception as exc:
        return {"error": f"open-meteo failed: {type(exc).__name__}: {exc}"}

    cur = body.get("current") or {}
    speed = cur.get("wind_speed_10m")
    direction = cur.get("wind_direction_10m")
    gust = cur.get("wind_gusts_10m")
    if speed is None or direction is None:
        return {"error": "wind data missing in response"}

    try:
        speed_f = float(speed)
        dir_f = float(direction)
        gust_f = float(gust) if gust is not None else None
    except (TypeError, ValueError):
        return {"error": "wind values not numeric"}

    out: dict[str, Any] = {
        "place": place,
        "speed": round(speed_f, 1),
        "direction_deg": round(dir_f, 0),
        "cardinal": _cardinal(dir_f),
        "gust": round(gust_f, 1) if gust_f is not None else None,
        "unit_label": _UNIT_LABEL[units],
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out
