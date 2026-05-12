"""Air quality with a 24h hourly trend chart. open-meteo, no API key."""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CACHE_TTL = 1800  # 30 minutes
HOURS = 24


def _band(aqi: float | None) -> str:
    if aqi is None:
        return "unknown"
    if aqi <= 20:
        return "good"
    if aqi <= 40:
        return "fair"
    if aqi <= 60:
        return "moderate"
    if aqi <= 80:
        return "poor"
    if aqi <= 100:
        return "very poor"
    return "extreme"


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    lat = float(options.get("latitude", -37.6494))
    lon = float(options.get("longitude", 145.1004))

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"aqi_trend_{lat:.3f}_{lon:.3f}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        "&current=european_aqi,pm2_5,pm10,nitrogen_dioxide,ozone,"
        "sulphur_dioxide,carbon_monoxide"
        "&hourly=european_aqi"
        f"&past_hours=12&forecast_hours={HOURS - 12}"
        "&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}"}

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    aqis = hourly.get("european_aqi", [])
    points: list[dict[str, Any]] = []
    for i, t in enumerate(times[:HOURS]):
        try:
            ts = datetime.fromisoformat(t)
            label = ts.strftime("%H")
        except ValueError:
            label = ""
        points.append({"ts": t, "label": label, "aqi": aqis[i] if i < len(aqis) else None})

    current = payload.get("current", {})
    aqi_now = current.get("european_aqi")
    result = {
        "current": current,
        "band": _band(aqi_now),
        "points": points,
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
