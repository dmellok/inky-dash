"""Sun & Moon widget — sunrise / sunset times and moon phase.

Sunrise / sunset times come from sunrise-sunset.org (no API key, daily
results in UTC; we convert to the host's local timezone). Moon phase is
computed locally from a known reference new moon — accurate to within a
few hours, more than enough for a glanceable widget.
"""
from __future__ import annotations

import json
import math
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any


_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}

API_URL = "https://api.sunrise-sunset.org/json"
# Standard reference new moon used widely in moon-phase calculators:
#   2000-01-06 18:14 UTC. Synodic period 29.53058867 days.
_MOON_REF = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_MOON_PERIOD = 29.53058867

_PHASE_NAMES = [
    ("New moon",         "ph-circle"),
    ("Waxing crescent",  "ph-moon"),
    ("First quarter",    "ph-moon"),
    ("Waxing gibbous",   "ph-moon"),
    ("Full moon",        "ph-circle-fill"),
    ("Waning gibbous",   "ph-moon"),
    ("Last quarter",     "ph-moon"),
    ("Waning crescent",  "ph-moon"),
]


def _moon_phase(now: datetime) -> dict[str, Any]:
    """Return phase index, name, illumination percentage."""
    now_utc = now.astimezone(timezone.utc)
    days = (now_utc - _MOON_REF).total_seconds() / 86400.0
    age = days % _MOON_PERIOD
    fraction = age / _MOON_PERIOD  # 0..1 around the cycle
    # 8 named bins: shift by half a bin so e.g. "Full" is centered on day 14.75.
    idx = int((fraction * 8 + 0.5)) % 8
    name, icon = _PHASE_NAMES[idx]
    # Illumination follows roughly cos(2π·fraction) inverted; expressed 0..100.
    illumination = round((1 - math.cos(2 * math.pi * fraction)) / 2 * 100)
    return {
        "phase_index": idx,
        "phase_name": name,
        "icon": icon,
        "illumination_pct": illumination,
        "age_days": round(age, 1),
        "waxing": fraction < 0.5,
    }


def _http_json(url: str, timeout: float = 12.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-sun_moon"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _parse_iso_utc(s: str) -> datetime | None:
    # API gives "YYYY-MM-DDTHH:MM:SS+00:00". datetime.fromisoformat handles it.
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    try:
        lat = float(options.get("lat") or settings.get("SUN_MOON_LAT") or 0)
        lng = float(options.get("lng") or settings.get("SUN_MOON_LNG") or 0)
    except (TypeError, ValueError):
        return {"error": "lat/lng must be numbers"}
    if lat == 0 and lng == 0:
        return {"error": "set latitude / longitude in the cell options"}

    place = (options.get("place_label") or "").strip()
    cache_key = f"{lat:.4f},{lng:.4f}:{date.today().isoformat()}"
    ttl = int(settings.get("SUN_MOON_CACHE_S") or 1800)

    now = datetime.now().astimezone()
    moon = _moon_phase(now)

    with _lock:
        hit = _cache.get(cache_key)
        if hit and (time.time() - hit[0]) < ttl:
            cached = dict(hit[1])
            cached["moon"] = moon
            cached["place"] = place
            return cached

    params = urllib.parse.urlencode({
        "lat": lat,
        "lng": lng,
        "formatted": 0,  # ISO timestamps in UTC
        "date": "today",
    })
    try:
        body = _http_json(f"{API_URL}?{params}")
    except Exception as exc:
        return {"error": f"sun API failed: {type(exc).__name__}: {exc}"}
    if (body.get("status") or "").upper() != "OK":
        return {"error": f"sun API status: {body.get('status')!r}"}

    r = body.get("results") or {}
    sunrise = _parse_iso_utc(r.get("sunrise") or "")
    sunset = _parse_iso_utc(r.get("sunset") or "")
    civil_dawn = _parse_iso_utc(r.get("civil_twilight_begin") or "")
    civil_dusk = _parse_iso_utc(r.get("civil_twilight_end") or "")
    solar_noon = _parse_iso_utc(r.get("solar_noon") or "")
    if not sunrise or not sunset:
        return {"error": "sun API returned incomplete data"}

    def hm_local(dt: datetime | None) -> str:
        return dt.astimezone().strftime("%H:%M") if dt else ""

    daylight_seconds = int(r.get("day_length") or 0)
    daylight_hours = daylight_seconds // 3600
    daylight_minutes = (daylight_seconds % 3600) // 60

    out: dict[str, Any] = {
        "place": place,
        "sunrise": hm_local(sunrise),
        "sunset": hm_local(sunset),
        "dawn": hm_local(civil_dawn),
        "dusk": hm_local(civil_dusk),
        "solar_noon": hm_local(solar_noon),
        "day_length": f"{daylight_hours}h {daylight_minutes}m",
        "moon": moon,
    }
    with _lock:
        _cache[cache_key] = (time.time(), {
            k: v for k, v in out.items() if k not in ("moon", "place")
        })
    return out
