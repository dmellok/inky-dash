"""Current temp + daily outlook from open-meteo (no API key)."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

CACHE_TTL = 600  # 10 minutes


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    lat = float(options.get("latitude", 51.5074))
    lon = float(options.get("longitude", -0.1278))
    units = options.get("units", "metric")

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"wx_{lat:.3f}_{lon:.3f}_{units}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    temp_unit = "fahrenheit" if units == "imperial" else "celsius"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
        f"&daily=temperature_2m_max,temperature_2m_min,weather_code"
        f"&temperature_unit={temp_unit}"
        f"&timezone=auto&forecast_days=4"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/0.7"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        return {"error": f"{type(err).__name__}: {err}"}

    result = {
        "current": payload.get("current", {}),
        "daily": payload.get("daily", {}),
        "units": units,
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
