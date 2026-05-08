"""Hourly-forecast weather widget — open-meteo, no API key.

Returns the current temp + an hourly array (configurable length) so the
client can draw a sparkline. Cached on disk for 10 minutes per
lat/lon/units to stay polite with the public API.
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CACHE_TTL = 600  # 10 minutes


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    lat = float(options.get("latitude", 51.5074))
    lon = float(options.get("longitude", -0.1278))
    units = options.get("units", "metric")
    hours = max(6, min(72, int(options.get("hours", 24) or 24)))

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"wxchart_{lat:.3f}_{lon:.3f}_{units}_{hours}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    temp_unit = "fahrenheit" if units == "imperial" else "celsius"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,weather_code,relative_humidity_2m,wind_speed_10m"
        "&hourly=temperature_2m,precipitation_probability,weather_code"
        f"&temperature_unit={temp_unit}"
        f"&forecast_hours={hours}"
        "&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}"}

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])[:hours]
    temps = hourly.get("temperature_2m", [])[:hours]
    pops = hourly.get("precipitation_probability", [])[:hours]
    codes = hourly.get("weather_code", [])[:hours]

    points: list[dict[str, Any]] = []
    for i, t in enumerate(times):
        try:
            ts = datetime.fromisoformat(t)
            label = ts.strftime("%H")
        except ValueError:
            label = ""
        points.append(
            {
                "ts": t,
                "label": label,
                "temp": temps[i] if i < len(temps) else None,
                "pop": pops[i] if i < len(pops) else None,
                "code": codes[i] if i < len(codes) else None,
            }
        )

    result = {
        "current": payload.get("current", {}),
        "points": points,
        "units": units,
        "hours": hours,
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
