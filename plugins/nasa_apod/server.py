"""NASA Astronomy Picture of the Day widget.

If today's APOD is a video (per `media_type`), we walk back day-by-day until
we find an image — per the brief: "when payload is video instead of image,
fall back to the previous day's APOD."
"""
from __future__ import annotations

import base64
import json
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from typing import Any

API_URL = "https://api.nasa.gov/planetary/apod"

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
_TTL_S = 60 * 60  # 1h


def _http_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-nasa_apod"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _http_bytes(url: str, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-nasa_apod"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    api_key = (settings.get("NASA_API_KEY") or "").strip() or "DEMO_KEY"

    cache_key = api_key
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _TTL_S:
            data = dict(hit[1])
            if api_key == "DEMO_KEY":
                data["warning"] = "Using DEMO_KEY — set NASA_API_KEY in /settings for higher quota"
            return data

    # Walk back up to 7 days to skip videos. Also tolerates per-day API
    # failures: NASA returns 400 if the requested date is past their latest
    # publication (host clock skew, or APOD not yet published today), so
    # bailing on the first error would mask perfectly good prior days.
    today = date.today()
    apod = None
    last_err: str | None = None
    for offset in range(0, 7):
        params = {"api_key": api_key, "date": (today - timedelta(days=offset)).isoformat()}
        try:
            payload = _http_json(f"{API_URL}?{urllib.parse.urlencode(params)}")
        except Exception as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            continue
        if payload.get("media_type") == "image" and payload.get("url"):
            apod = payload
            break
    if apod is None:
        return {"error": last_err or "no image APOD found in the last 7 days"}

    # Prefer high-resolution image if available, fall back to standard.
    img_url = apod.get("hdurl") or apod.get("url")
    try:
        img_bytes = _http_bytes(img_url)
    except Exception as exc:
        return {"error": f"image fetch failed: {exc}"}
    encoded = base64.b64encode(img_bytes).decode("ascii")
    # Guess MIME from extension; default to JPEG.
    ext = (img_url.rsplit(".", 1)[-1] or "").lower()
    mime = {
        "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    }.get(ext, "image/jpeg")

    data = {
        "img": f"data:{mime};base64,{encoded}",
        "title": apod.get("title") or "",
        "date": apod.get("date") or "",
        "explanation": apod.get("explanation") or "",
        "copyright": apod.get("copyright") or None,
    }
    with _lock:
        _cache[cache_key] = (now, data)
    if api_key == "DEMO_KEY":
        data["warning"] = "Using DEMO_KEY — set NASA_API_KEY in /settings for higher quota"
    return data
