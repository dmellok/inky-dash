"""Weather widget — Open-Meteo (no API key needed).

Renders current conditions, a 12-hour hourly forecast, and a 4-day daily
forecast. Geocoding caches per location string. The icon set is configurable:

  WEATHER_ICON_SET=meteocons (default) — bundled SVGs in static/icons/
  WEATHER_ICON_SET=phosphor             — Phosphor font icons (monochrome)

Per the brief: "Render `13°C` as `<span>13</span><span class='unit'>°C</span>`
and avoid kerning into the degree symbol — getting this wrong was a v2 bug
we revisited multiple times." The client.js handles that markup.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo WMO codes → (icon_id, label)
WMO_MAP: dict[int, tuple[str, str]] = {
    0:  ("clear",            "Clear sky"),
    1:  ("partly-cloudy",    "Mainly clear"),
    2:  ("partly-cloudy",    "Partly cloudy"),
    3:  ("overcast",         "Overcast"),
    45: ("fog",              "Fog"),
    48: ("fog",              "Depositing rime fog"),
    51: ("drizzle",          "Light drizzle"),
    53: ("drizzle",          "Drizzle"),
    55: ("drizzle",          "Heavy drizzle"),
    56: ("sleet",            "Light freezing drizzle"),
    57: ("sleet",            "Heavy freezing drizzle"),
    61: ("rain",             "Light rain"),
    63: ("rain",             "Rain"),
    65: ("rain",             "Heavy rain"),
    66: ("sleet",            "Light freezing rain"),
    67: ("sleet",            "Freezing rain"),
    71: ("snow",             "Light snow"),
    73: ("snow",             "Snow"),
    75: ("snow",             "Heavy snow"),
    77: ("snow",             "Snow grains"),
    80: ("rain",             "Light showers"),
    81: ("rain",             "Showers"),
    82: ("rain",             "Heavy showers"),
    85: ("snow",             "Light snow showers"),
    86: ("snow",             "Heavy snow showers"),
    95: ("thunderstorms",    "Thunderstorm"),
    96: ("thunderstorms",    "Thunderstorm w/ light hail"),
    99: ("thunderstorms",    "Thunderstorm w/ hail"),
}

# Phosphor mapping (monochrome line icons)
PHOSPHOR_MAP = {
    "clear":            ("ph-sun",            "ph-moon"),
    "partly-cloudy":    ("ph-cloud-sun",      "ph-cloud-moon"),
    "overcast":         ("ph-cloud",          "ph-cloud"),
    "fog":              ("ph-cloud-fog",      "ph-cloud-fog"),
    "drizzle":          ("ph-cloud-rain",     "ph-cloud-rain"),
    "rain":             ("ph-cloud-rain",     "ph-cloud-rain"),
    "sleet":            ("ph-cloud-snow",     "ph-cloud-snow"),
    "snow":             ("ph-snowflake",     "ph-snowflake"),
    "thunderstorms":    ("ph-cloud-lightning","ph-cloud-lightning"),
    "not-available":    ("ph-question",       "ph-question"),
}

# Meteocons base + day/night variant filenames.
# Some icons (drizzle, rain, sleet, snow) don't have day/night variants.
MET_HAS_VARIANT = {"clear", "partly-cloudy", "overcast", "fog", "thunderstorms"}

ICON_DIR = Path(__file__).resolve().parent / "static" / "icons"

_lock = threading.Lock()
_geo_cache: dict[str, dict] = {}
_forecast_cache: dict[str, tuple[float, dict]] = {}  # location -> (ts, data)
_svg_cache: dict[str, str] = {}


def _http_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-weather"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _geocode(location: str) -> dict | None:
    with _lock:
        if location in _geo_cache:
            return _geo_cache[location]
    # Open-Meteo's geocoding API takes a bare city name; users tend to type
    # "Melbourne, AU" (city, country). Split off the country part for the
    # lookup, but use it as a tie-breaker on the result set.
    name = location
    country_hint = None
    if "," in location:
        parts = [p.strip() for p in location.split(",", 1)]
        name = parts[0] or location
        country_hint = (parts[1] if len(parts) > 1 else "").upper()[:2] or None
    params = urllib.parse.urlencode({"name": name, "count": 5})
    try:
        data = _http_json(f"{GEO_URL}?{params}")
        results = data.get("results") or []
        if not results:
            return None
        r = results[0]
        if country_hint:
            for cand in results:
                if (cand.get("country_code") or "").upper() == country_hint:
                    r = cand; break
        info = {
            "lat": r["latitude"],
            "lng": r["longitude"],
            "name": r.get("name") or location,
            "country": r.get("country_code") or "",
            "tz": r.get("timezone") or "auto",
        }
        with _lock:
            _geo_cache[location] = info
        return info
    except Exception:
        return None


def _meteocon(icon_id: str, is_day: bool) -> str:
    """Return inline SVG markup for a meteocon, or an empty string on error."""
    name = icon_id
    if icon_id in MET_HAS_VARIANT:
        name = f"{icon_id}-{'day' if is_day else 'night'}"
    cache_key = name
    with _lock:
        cached = _svg_cache.get(cache_key)
        if cached:
            return cached
    path = ICON_DIR / f"{name}.svg"
    if not path.exists():
        path = ICON_DIR / "not-available.svg"
        cache_key = "not-available"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    with _lock:
        _svg_cache[cache_key] = text
    return text


def _phosphor(icon_id: str, is_day: bool) -> str:
    day, night = PHOSPHOR_MAP.get(icon_id, PHOSPHOR_MAP["not-available"])
    return day if is_day else night


def _ui_meteocon(name: str) -> str:
    """Inline SVG markup for one of the UI/metric meteocons (sunrise,
    sunset, wind, humidity, uv-index, umbrella, thermometer-celsius)."""
    cache_key = f"ui:{name}"
    with _lock:
        cached = _svg_cache.get(cache_key)
        if cached:
            return cached
    path = ICON_DIR / f"{name}.svg"
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    with _lock:
        _svg_cache[cache_key] = text
    return text


def _icon_for(icon_set: str, icon_id: str, is_day: bool) -> dict:
    if icon_set == "phosphor":
        return {"set": "phosphor", "name": _phosphor(icon_id, is_day)}
    return {"set": "meteocons", "svg": _meteocon(icon_id, is_day)}


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    location = (options.get("location") or "Melbourne, AU").strip()
    cache_s = int(settings.get("WEATHER_CACHE_S") or 600)
    icon_set = (settings.get("WEATHER_ICON_SET") or "meteocons").lower()
    if icon_set not in ("meteocons", "phosphor"):
        icon_set = "meteocons"

    cache_key = f"{location}|{icon_set}"
    now = time.time()
    with _lock:
        hit = _forecast_cache.get(cache_key)
        if hit and now - hit[0] < cache_s:
            return hit[1]

    geo = _geocode(location)
    if not geo:
        return {"error": f"could not geocode {location!r}"}

    params = {
        "latitude": geo["lat"],
        "longitude": geo["lng"],
        "current": "temperature_2m,apparent_temperature,is_day,weather_code,relative_humidity_2m,wind_speed_10m,wind_direction_10m,uv_index",
        "hourly": "temperature_2m,weather_code,is_day,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,uv_index_max,precipitation_probability_max",
        "forecast_days": 5,
        "timezone": geo["tz"],
    }
    try:
        forecast = _http_json(f"{FORECAST_URL}?{urllib.parse.urlencode(params)}")
    except Exception as exc:
        return {"error": f"forecast fetch failed: {exc}"}

    cur = forecast.get("current") or {}
    cur_code = int(cur.get("weather_code") or 0)
    cur_id, cur_label = WMO_MAP.get(cur_code, ("not-available", f"WMO {cur_code}"))
    is_day = bool(cur.get("is_day"))

    hourly = forecast.get("hourly") or {}
    h_times = hourly.get("time") or []
    h_temps = hourly.get("temperature_2m") or []
    h_codes = hourly.get("weather_code") or []
    h_isday = hourly.get("is_day") or [1] * len(h_times)
    h_pop = hourly.get("precipitation_probability") or [None] * len(h_times)
    # Find the index of the first hour at-or-after "now" in the location's tz,
    # then take the next 12 entries.
    cur_iso = (cur.get("time") or "").rstrip("Z")
    start = 0
    for i, t in enumerate(h_times):
        if t >= cur_iso:
            start = i; break
    # Show the next ~5 hours: dense enough on a 13.3" portrait panel to read
    # comfortably without crushing each tick column. Was 12; smaller panels
    # could not fit the meteocon icons at a legible size.
    hourly_slice = []
    for i in range(start, min(start + 5, len(h_times))):
        code = int(h_codes[i] or 0)
        icon_id, _ = WMO_MAP.get(code, ("not-available", ""))
        hourly_slice.append({
            "time": h_times[i],
            "temp": float(h_temps[i]) if h_temps[i] is not None else None,
            "icon": _icon_for(icon_set, icon_id, bool(h_isday[i])),
            "pop": h_pop[i] if i < len(h_pop) else None,
        })

    daily = forecast.get("daily") or {}
    d_times = daily.get("time") or []
    d_codes = daily.get("weather_code") or []
    d_max = daily.get("temperature_2m_max") or []
    d_min = daily.get("temperature_2m_min") or []
    d_sunrise = daily.get("sunrise") or []
    d_sunset = daily.get("sunset") or []
    d_uv_max = daily.get("uv_index_max") or []
    d_pop_max = daily.get("precipitation_probability_max") or []
    daily_slice = []
    for i in range(min(4, len(d_times))):
        code = int(d_codes[i] or 0)
        icon_id, _ = WMO_MAP.get(code, ("not-available", ""))
        daily_slice.append({
            "date": d_times[i],
            "max": float(d_max[i]) if d_max[i] is not None else None,
            "min": float(d_min[i]) if d_min[i] is not None else None,
            "icon": _icon_for(icon_set, icon_id, True),  # daily uses day variant
            "pop": d_pop_max[i] if i < len(d_pop_max) else None,
        })

    sunrise = d_sunrise[0] if d_sunrise else None
    sunset = d_sunset[0] if d_sunset else None
    today_uv_max = d_uv_max[0] if d_uv_max else None
    today_pop_max = d_pop_max[0] if d_pop_max else None

    # UI meteocons for the metric grid. We send them along with the data
    # only when icon_set=meteocons; the phosphor track keeps using <i class>.
    if icon_set == "meteocons":
        ui_icons = {
            "sunrise":     _ui_meteocon("sunrise"),
            "sunset":      _ui_meteocon("sunset"),
            "wind":        _ui_meteocon("wind"),
            "humidity":    _ui_meteocon("humidity"),
            "uv":          _ui_meteocon("uv-index"),
            "rain":        _ui_meteocon("umbrella"),
            "thermometer": _ui_meteocon("thermometer-celsius"),
        }
    else:
        ui_icons = {}

    data = {
        "location": geo["name"],
        "country": geo["country"],
        "current": {
            "temp": float(cur.get("temperature_2m")) if cur.get("temperature_2m") is not None else None,
            "feels_like": float(cur.get("apparent_temperature")) if cur.get("apparent_temperature") is not None else None,
            "humidity": cur.get("relative_humidity_2m"),
            "wind_speed": cur.get("wind_speed_10m"),
            "wind_direction": cur.get("wind_direction_10m"),
            "uv_index": cur.get("uv_index"),
            "label": cur_label,
            "icon": _icon_for(icon_set, cur_id, is_day),
            "is_day": is_day,
        },
        "hourly": hourly_slice,
        "daily": daily_slice,
        "sunrise": sunrise,
        "sunset": sunset,
        "uv_index_max": today_uv_max,
        "rain_today": today_pop_max,
        "icon_set": icon_set,
        "ui_icons": ui_icons,
    }
    with _lock:
        _forecast_cache[cache_key] = (now, data)
    return data
