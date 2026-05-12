"""Weather radar — RainViewer rain layer atop a CartoDB basemap.

The server's job is small: fetch RainViewer's frame index (which gives us the
URL path for the most recent radar snapshot) and hand the client everything
it needs to construct a 3×3 tile mosaic centered on the user's lat/lon.

Tile providers used:
- CartoDB (basemaps): https://{a-d}.basemaps.cartocdn.com — free, attribution
  required, no key. Light/dark/voyager styles.
- RainViewer (radar overlay): https://tilecache.rainviewer.com — free, no
  key.

The basemap+radar URL templates are returned with ``{x}`` / ``{y}``
placeholders so the client can fill in offsets without re-trip-ing the
server. Frame index is cached for 5 min.
"""

from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CACHE_TTL = 5 * 60  # RainViewer publishes ~every 10 min, so 5 is fine.

BASEMAP_PATHS = {
    "light": "light_all",
    "dark": "dark_all",
    "voyager": "rastertiles/voyager",
}


def _deg2tile(lat: float, lon: float, zoom: int) -> tuple[int, int]:
    """Standard Slippy Map XYZ tile math."""
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def _frame_index(data_dir: Path) -> dict[str, Any] | None:
    """Latest radar frame from RainViewer. Cached on disk."""
    cache = data_dir / "frames.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    url = "https://api.rainviewer.com/public/weather-maps.json"
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    data_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(payload))
    return payload


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    try:
        lat = float(options.get("lat") or -37.6494)
        lon = float(options.get("lon") or 145.1004)
    except (TypeError, ValueError):
        return {"error": "Invalid lat/lon."}

    try:
        zoom = int(options.get("zoom") or 7)
    except (TypeError, ValueError):
        zoom = 7
    zoom = max(3, min(zoom, 10))

    label = (options.get("label") or "").strip()
    basemap_choice = (options.get("basemap") or "light").lower()

    data_dir = Path(ctx["data_dir"])
    frames = _frame_index(data_dir)
    if frames is None:
        return {"error": "RainViewer is unreachable. Try again shortly."}

    past = (frames.get("radar") or {}).get("past") or []
    if not past:
        return {"error": "No recent radar frames available."}
    latest = past[-1]
    radar_path = latest.get("path", "")
    radar_ts = int(latest.get("time") or 0)
    radar_host = frames.get("host") or "https://tilecache.rainviewer.com"

    tile_x, tile_y = _deg2tile(lat, lon, zoom)

    basemap_path = BASEMAP_PATHS.get(basemap_choice)
    basemap_template = (
        f"https://a.basemaps.cartocdn.com/{basemap_path}/{{z}}/{{x}}/{{y}}.png"
        if basemap_path
        else None
    )
    # ``2`` = "original" colour ramp; ``1_1`` = smooth on, snow on.
    radar_template = (
        f"{radar_host}{radar_path}/256/{{z}}/{{x}}/{{y}}/2/1_1.png"
    )

    return {
        "label": label,
        "lat": lat,
        "lon": lon,
        "zoom": zoom,
        "tile_x": tile_x,
        "tile_y": tile_y,
        "basemap_template": basemap_template,
        "radar_template": radar_template,
        "radar_ts": radar_ts,
        "radar_iso": datetime.fromtimestamp(radar_ts, tz=UTC).isoformat()
        if radar_ts
        else None,
    }
