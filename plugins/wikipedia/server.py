"""Wikipedia "today's featured article" widget.

Pulls from the Wikimedia REST feed: /api/rest_v1/feed/featured/YYYY/MM/DD.
Returns the day's TFA (Today's Featured Article) — title, extract, and an
optional thumbnail (downloaded and inlined as a data URL so Playwright
doesn't have to re-fetch on every render).
"""
from __future__ import annotations

import base64
import json
import threading
import time
import urllib.request
from datetime import date
from typing import Any


_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http(url: str, timeout: float = 12.0) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Inky-Dash-wikipedia/1.0 (+https://github.com/dmellok/inky-dash)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    lang = (options.get("lang") or "en").strip().lower() or "en"
    show_image = options.get("show_image") is not False
    ttl = int(settings.get("WIKIPEDIA_CACHE_S") or 21600)

    today = date.today()
    cache_key = f"{lang}:{today.isoformat()}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    url = (
        f"https://{lang}.wikipedia.org/api/rest_v1/feed/featured/"
        f"{today.year:04d}/{today.month:02d}/{today.day:02d}"
    )
    try:
        body = json.loads(_http(url))
    except Exception as exc:
        return {"error": f"Wikipedia feed failed: {type(exc).__name__}: {exc}"}

    tfa = body.get("tfa") or {}
    if not tfa:
        # Some language editions don't run TFA every day — fall back to the
        # most-read story so the widget still has something to show.
        most_read = (body.get("mostread") or {}).get("articles") or []
        if most_read:
            tfa = most_read[0]
        else:
            return {"error": "no featured article today"}

    title = tfa.get("titles", {}).get("normalized") or tfa.get("title") or ""
    extract = tfa.get("extract") or ""
    page_url = tfa.get("content_urls", {}).get("desktop", {}).get("page") or ""
    thumb = tfa.get("thumbnail") or {}
    image_url = thumb.get("source") if show_image else None

    image_data_url = None
    if image_url:
        try:
            img_bytes = _http(image_url, timeout=15.0)
            mime = "image/jpeg"
            lower = image_url.lower()
            if lower.endswith(".png"): mime = "image/png"
            elif lower.endswith(".webp"): mime = "image/webp"
            elif lower.endswith(".gif"): mime = "image/gif"
            image_data_url = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
        except Exception:
            image_data_url = None

    out: dict[str, Any] = {
        "title": title,
        "extract": extract,
        "page_url": page_url,
        "image": image_data_url,
        "lang": lang,
        "date_pretty": today.strftime("%A %-d %B %Y"),
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out
