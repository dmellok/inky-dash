"""Sun clock widget — polar 24-hour ring with daylight + cursor.

Same data source as sun_moon (sunrise-sunset.org) but the visual lives in
a separate widget so dashboards can mix them. Returns the four key times
(dawn / sunrise / sunset / dusk) as fractional hours from midnight in the
host's local timezone — the client maps those to angles on a polar
doughnut chart.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Any


API_URL = "https://api.sunrise-sunset.org/json"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-sun_clock"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _to_local_hours(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()
    return local.hour + local.minute / 60.0 + local.second / 3600.0


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    try:
        lat = float(options.get("lat") or "-37.8136")
        lng = float(options.get("lng") or "144.9631")
    except (TypeError, ValueError):
        return {"error": "lat/lng must be numbers"}
    place = (options.get("place_label") or "Melbourne").strip()

    ttl = int(settings.get("SUN_CLOCK_CACHE_S") or 1800)
    cache_key = f"{lat:.4f},{lng:.4f}:{date.today().isoformat()}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            cached = dict(hit[1])
            cached["place"] = place
            cached["now_hour"] = _now_hour()
            return cached

    qs = urllib.parse.urlencode({"lat": lat, "lng": lng, "formatted": 0, "date": "today"})
    try:
        body = _http_json(f"{API_URL}?{qs}")
    except Exception as exc:
        return {"error": f"sun API failed: {type(exc).__name__}: {exc}"}
    if (body.get("status") or "").upper() != "OK":
        return {"error": f"sun API status: {body.get('status')!r}"}
    r = body.get("results") or {}

    sunrise = _to_local_hours(r.get("sunrise"))
    sunset = _to_local_hours(r.get("sunset"))
    civil_dawn = _to_local_hours(r.get("civil_twilight_begin"))
    civil_dusk = _to_local_hours(r.get("civil_twilight_end"))
    solar_noon = _to_local_hours(r.get("solar_noon"))
    if sunrise is None or sunset is None:
        return {"error": "sun API returned incomplete data"}

    out: dict[str, Any] = {
        "place": place,
        "dawn_h": civil_dawn,
        "sunrise_h": sunrise,
        "noon_h": solar_noon,
        "sunset_h": sunset,
        "dusk_h": civil_dusk,
        "now_hour": _now_hour(),
        "sunrise": _hm(sunrise),
        "sunset": _hm(sunset),
        "day_length": _hm_diff(sunset - sunrise) if sunrise is not None and sunset is not None else "",
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out


def _now_hour() -> float:
    n = datetime.now().astimezone()
    return n.hour + n.minute / 60.0 + n.second / 3600.0


def _hm(hour: float | None) -> str:
    if hour is None:
        return ""
    h = int(hour) % 24
    m = int(round((hour - int(hour)) * 60))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    return f"{h:02d}:{m:02d}"


def _hm_diff(hours: float) -> str:
    h = int(hours)
    m = int(round((hours - h) * 60))
    return f"{h}h {m}m"
