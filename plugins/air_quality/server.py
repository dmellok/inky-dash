"""Air quality widget — current AQI + pollutant breakdown.

Backed by open-meteo's air-quality endpoint (https://open-meteo.com/en/
docs/air-quality-api) — no key, no auth, generous rate limits. We pull
the "current" hour for AQI + the standard pollutants and bucket the AQI
into a category that the client styles by.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any


API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-air_quality"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _us_aqi_category(aqi: float) -> tuple[str, str]:
    """Return (label, severity) per the EPA's standard 6-band AQI scale."""
    if aqi is None:    return ("—", "unknown")
    if aqi <= 50:      return ("Good", "good")
    if aqi <= 100:     return ("Moderate", "moderate")
    if aqi <= 150:     return ("Unhealthy for sensitive", "sensitive")
    if aqi <= 200:     return ("Unhealthy", "unhealthy")
    if aqi <= 300:     return ("Very unhealthy", "very_unhealthy")
    return ("Hazardous", "hazardous")


def _european_aqi_category(aqi: float) -> tuple[str, str]:
    """Return (label, severity) per the European Environment Agency scale."""
    if aqi is None:    return ("—", "unknown")
    if aqi <= 20:      return ("Good", "good")
    if aqi <= 40:      return ("Fair", "moderate")
    if aqi <= 60:      return ("Moderate", "sensitive")
    if aqi <= 80:      return ("Poor", "unhealthy")
    if aqi <= 100:     return ("Very poor", "very_unhealthy")
    return ("Extremely poor", "hazardous")


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    # Same defaults as sun_moon — Melbourne, since the manifest defaults
    # don't auto-merge into options at fetch time.
    try:
        lat = float(options.get("lat") or "-37.8136")
        lng = float(options.get("lng") or "144.9631")
    except (TypeError, ValueError):
        return {"error": "lat/lng must be numbers"}
    place = (options.get("place_label") or "Melbourne").strip()
    scale = (options.get("scale") or "us").strip()
    if scale not in ("us", "european"):
        scale = "us"

    ttl = int(settings.get("AIR_QUALITY_CACHE_S") or 1800)
    cache_key = f"{lat:.4f},{lng:.4f}:{scale}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    aqi_field = "us_aqi" if scale == "us" else "european_aqi"
    params = urllib.parse.urlencode({
        "latitude": lat,
        "longitude": lng,
        "current": ",".join([
            aqi_field, "pm10", "pm2_5", "ozone", "nitrogen_dioxide",
            "sulphur_dioxide", "carbon_monoxide",
        ]),
        "timezone": "auto",
    })
    try:
        body = _http_json(f"{API_URL}?{params}")
    except Exception as exc:
        return {"error": f"air-quality API failed: {type(exc).__name__}: {exc}"}

    cur = body.get("current") or {}
    aqi_raw = cur.get(aqi_field)
    aqi = round(float(aqi_raw)) if aqi_raw is not None else None

    if scale == "us":
        label, severity = _us_aqi_category(aqi)
        scale_max = 500
    else:
        label, severity = _european_aqi_category(aqi)
        scale_max = 100

    def _val(key: str) -> float | None:
        v = cur.get(key)
        try:
            return round(float(v), 1) if v is not None else None
        except (TypeError, ValueError):
            return None

    out: dict[str, Any] = {
        "place": place,
        "scale": scale,
        "aqi": aqi,
        "scale_max": scale_max,
        "category": label,
        "severity": severity,
        "pollutants": [
            {"k": "PM2.5", "v": _val("pm2_5"),           "u": "µg/m³"},
            {"k": "PM10",  "v": _val("pm10"),            "u": "µg/m³"},
            {"k": "O₃",    "v": _val("ozone"),           "u": "µg/m³"},
            {"k": "NO₂",   "v": _val("nitrogen_dioxide"),"u": "µg/m³"},
            {"k": "SO₂",   "v": _val("sulphur_dioxide"), "u": "µg/m³"},
            {"k": "CO",    "v": _val("carbon_monoxide"), "u": "µg/m³"},
        ],
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out
