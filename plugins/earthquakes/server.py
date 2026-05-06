"""Earthquakes widget — recent quakes from the USGS GeoJSON feeds.

Feeds documented at:
  https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php

No API key, no auth. Server caches per-feed so two cells on the same
feed share a single upstream call.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any


_VALID_FEEDS = {
    "significant_day", "significant_week",
    "4.5_day", "4.5_week",
    "2.5_day", "all_hour",
}
_FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{}.geojson"

_lock = threading.Lock()
_cache: dict[str, tuple[float, list[dict]]] = {}


def _http_json(url: str, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-earthquakes"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _quake_severity(mag: float) -> str:
    """Map magnitude to a coarse severity bucket the client styles by."""
    if mag is None:
        return "minor"
    if mag >= 7.0: return "major"
    if mag >= 6.0: return "strong"
    if mag >= 5.0: return "moderate"
    if mag >= 4.0: return "light"
    return "minor"


def _ago(epoch_ms: int, now: float) -> str:
    delta = now - (epoch_ms / 1000)
    if delta < 60:    return f"{int(delta)}s ago"
    if delta < 3600:  return f"{int(delta // 60)}m ago"
    if delta < 86400: return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    feed = (options.get("feed") or "4.5_day").strip()
    if feed not in _VALID_FEEDS:
        feed = "4.5_day"
    try:
        count = int(options.get("count") or 5)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 20))

    ttl = int(settings.get("EARTHQUAKES_CACHE_S") or 600)
    cache_key = f"{feed}:{count}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return {"feed": feed, "quakes": list(hit[1])}

    try:
        body = _http_json(_FEED_URL.format(feed))
    except Exception as exc:
        return {"error": f"USGS feed failed: {type(exc).__name__}: {exc}"}

    features = body.get("features") or []
    quakes: list[dict] = []
    # Largest magnitude first within the time window — that's the "headline"
    # ordering for a glance dashboard.
    sortable = []
    for f in features:
        props = f.get("properties") or {}
        mag = props.get("mag")
        if mag is None:
            continue
        sortable.append((float(mag), f))
    sortable.sort(key=lambda x: x[0], reverse=True)

    max_mag = sortable[0][0] if sortable else 0.0
    for mag, f in sortable[:count]:
        props = f.get("properties") or {}
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None, None]
        depth = coords[2] if len(coords) >= 3 else None
        eq_time_ms = int(props.get("time") or 0)
        quakes.append({
            "id": f.get("id") or "",
            "mag": round(float(mag), 1),
            "place": props.get("place") or "",
            "depth_km": round(float(depth), 1) if depth is not None else None,
            "tsunami": bool(props.get("tsunami")),
            "url": props.get("url") or "",
            "time_iso": datetime.fromtimestamp(eq_time_ms / 1000, tz=timezone.utc).isoformat(),
            "ago": _ago(eq_time_ms, now),
            "severity": _quake_severity(float(mag)),
        })

    with _lock:
        _cache[cache_key] = (now, quakes)
    return {
        "feed": feed,
        "feed_label": _FEED_LABEL.get(feed, feed),
        "quakes": quakes,
        "max_mag": round(max_mag, 1),
        "count": len(features),
    }


_FEED_LABEL = {
    "significant_day":  "SIGNIFICANT · DAY",
    "significant_week": "SIGNIFICANT · WEEK",
    "4.5_day":          "M4.5+ · DAY",
    "4.5_week":         "M4.5+ · WEEK",
    "2.5_day":          "M2.5+ · DAY",
    "all_hour":         "ALL · HOUR",
}
