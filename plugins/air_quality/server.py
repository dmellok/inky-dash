"""Air quality from open-meteo (no API key)."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any

CACHE_TTL = 1800  # 30 minutes


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    lat = float(options.get("latitude", 51.5074))
    lon = float(options.get("longitude", -0.1278))

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"aq_{lat:.3f}_{lon:.3f}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        "&current=european_aqi,pm2_5,pm10,nitrogen_dioxide,ozone"
        "&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/0.7"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        return {"error": f"{type(err).__name__}: {err}"}

    current = payload.get("current", {})
    result = {
        "aqi": current.get("european_aqi"),
        "pm2_5": current.get("pm2_5"),
        "pm10": current.get("pm10"),
        "no2": current.get("nitrogen_dioxide"),
        "o3": current.get("ozone"),
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
