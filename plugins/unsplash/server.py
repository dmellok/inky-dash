"""Unsplash random-photo widget.

Calls api.unsplash.com/photos/random with the user's access key. Rotation
cadence is whatever schedule the user attached to the dashboard — every
scheduled fire triggers a render which (after the brief in-process cache
expires) fetches a fresh photo. A short TTL prevents the burst of
fetches that happens within a single push pipeline (composer → headless
screenshot → quantized preview) from each hitting the API independently.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

API_BASE = "https://api.unsplash.com"

# Long enough to deduplicate a single push pipeline's compose + screenshot +
# panel-paint preview hits, short enough that a 1-minute scheduler still
# gets a fresh photo every fire.
CACHE_TTL = 30


def _cache_key(options: dict[str, Any]) -> str:
    """Hash the filter options so two cells with different queries get
    independent caches but two with identical filters share one (saves API
    quota)."""
    payload = json.dumps(
        {
            "q": options.get("query", "").strip().lower(),
            "c": options.get("collections", "").strip(),
            "u": options.get("username", "").strip().lower(),
            "o": options.get("orientation", "any"),
        },
        sort_keys=True,
    ).encode()
    return hashlib.sha1(payload).hexdigest()[:12]


def _request(url: str, headers: dict[str, str]) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _track_download(download_endpoint: str, headers: dict[str, str]) -> None:
    """Unsplash API guidelines (the "trigger download" requirement) — fire
    GET on ``links.download_location`` so the photographer's stats reflect
    the use. Best-effort; never fails the render if it fails."""
    try:
        req = urllib.request.Request(download_endpoint, headers=headers)
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception:  # noqa: BLE001
        pass


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    access_key = (settings.get("access_key") or "").strip()
    if not access_key:
        return {
            "error": "Set your Unsplash Access Key in Settings → Plugins → Unsplash.",
            "url": None,
        }

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"unsplash_{_cache_key(options)}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    params: dict[str, str] = {}
    query = options.get("query", "").strip()
    if query:
        params["query"] = query
    collections = options.get("collections", "").strip()
    if collections:
        params["collections"] = collections
    username = options.get("username", "").strip()
    if username:
        params["username"] = username
    orientation = options.get("orientation", "any")
    if orientation in {"landscape", "portrait", "squarish"}:
        params["orientation"] = orientation
    params["content_filter"] = "high"  # safer-by-default

    url = f"{API_BASE}/photos/random"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
        "User-Agent": "inky-dash/1.0",
    }

    try:
        photo = _request(url, headers)
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")[:200]
        return {"error": f"HTTP {err.code}: {body}", "url": None}
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}", "url": None}

    # The /random endpoint can return a list with `count`, but with our
    # default it returns a single object.
    if isinstance(photo, list):
        if not photo:
            return {"error": "Unsplash returned no photos for those filters.", "url": None}
        photo = photo[0]

    image_url = (
        photo.get("urls", {}).get("regular")
        or photo.get("urls", {}).get("full")
        or photo.get("urls", {}).get("raw")
    )
    if not image_url:
        return {"error": "Unsplash response had no image URL.", "url": None}

    download_endpoint = photo.get("links", {}).get("download_location")
    if download_endpoint:
        _track_download(download_endpoint, headers)

    user = photo.get("user") or {}
    result = {
        "url": image_url,
        "alt": (photo.get("alt_description") or photo.get("description") or "").strip(),
        "credit_name": (user.get("name") or "").strip(),
        "credit_username": (user.get("username") or "").strip(),
        "html_link": photo.get("links", {}).get("html", ""),
        "color": photo.get("color"),
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
