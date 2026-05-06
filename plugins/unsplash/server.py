"""Unsplash widget — random image by query and/or collection.

Per the brief: "cache the chosen image's URL across the preview→push render
boundary so you don't get two different images in preview vs. panel." We
cache by (query, collection_id) for a short TTL — long enough that the
editor's draft preview and the subsequent push pick up the same photo.
"""
from __future__ import annotations

import base64
import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://api.unsplash.com"
_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}  # key -> (ts, {url, embedded})
_TTL_S = 30  # preview→push window


def _http(url: str, headers: dict, *, timeout: float = 15.0, as_text: bool = False):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return body.decode("utf-8", errors="replace") if as_text else body


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    access_key = (settings.get("UNSPLASH_ACCESS_KEY") or "").strip()
    if not access_key:
        return {"error": "UNSPLASH_ACCESS_KEY is required (set it in /settings)"}

    query = (options.get("query") or "").strip()
    collection_id = (options.get("collection_id") or "").strip()
    cache_key = f"{query}|{collection_id}"

    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _TTL_S:
            return hit[1]

    params = {"orientation": "landscape" if panel_w >= panel_h else "portrait"}
    if query:
        params["query"] = query
    if collection_id:
        params["collections"] = collection_id

    headers = {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": "Inky-Dash-unsplash",
    }
    try:
        body = _http(
            f"{API_BASE}/photos/random?{urllib.parse.urlencode(params)}",
            headers, as_text=True,
        )
        photo = json.loads(body)
    except Exception as exc:
        return {"error": f"Unsplash API failed: {exc}"}

    urls = photo.get("urls") or {}
    img_url = urls.get("regular") or urls.get("full") or urls.get("small")
    if not img_url:
        return {"error": "no image URL in API response"}

    # Pull the image bytes server-side and embed inline so Playwright doesn't
    # block on imgs.unsplash.com during the push render.
    try:
        img_bytes = _http(img_url, {"User-Agent": "Inky-Dash-unsplash"}, timeout=30.0)
    except Exception as exc:
        return {"error": f"image fetch failed: {exc}"}

    encoded = base64.b64encode(img_bytes).decode("ascii")
    data = {
        "img": f"data:image/jpeg;base64,{encoded}",
        "credit": (photo.get("user") or {}).get("name") or "Unsplash",
        "credit_url": ((photo.get("user") or {}).get("links") or {}).get("html"),
        "alt_description": photo.get("alt_description") or "",
    }
    with _lock:
        _cache[cache_key] = (now, data)
    return data
