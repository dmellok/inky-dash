"""xkcd widget — fetches the current or a random strip and embeds the comic
image inline as a base64 data URL.

Why inline: Playwright's `wait_until="load"` (and even `networkidle`) routinely
hangs on slow imgs.xkcd.com fetches. Pre-fetching the bytes server-side and
emitting them as `data:` URLs makes the rendered HTML self-contained — the
panel render is reliable.
"""
from __future__ import annotations

import base64
import json
import random
import time
import urllib.request
from typing import Any

INFO_URL = "https://xkcd.com/info.0.json"
INFO_NUM_URL = "https://xkcd.com/{n}/info.0.json"

# Cache the LATEST comic JSON briefly so we don't re-hit xkcd.com on every
# render. The current strip changes ~3× a week, so a short TTL is fine.
_latest_cache: dict[str, Any] = {"data": None, "ts": 0.0}
_LATEST_TTL_S = 60 * 30  # 30 min


def _http_json(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-xkcd"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _http_bytes(url: str, timeout: float = 15.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-xkcd"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _latest() -> dict:
    now = time.time()
    if _latest_cache["data"] and now - _latest_cache["ts"] < _LATEST_TTL_S:
        return _latest_cache["data"]
    data = _http_json(INFO_URL)
    _latest_cache["data"] = data
    _latest_cache["ts"] = now
    return data


def _embed_image(url: str) -> str:
    raw = _http_bytes(url)
    ext = url.rsplit(".", 1)[-1].lower()
    mime = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext, "image/png")
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    mode = options.get("mode") or "current"
    try:
        latest = _latest()
        if mode == "random":
            n = random.randint(1, latest["num"])
            comic = _http_json(INFO_NUM_URL.format(n=n))
        else:
            comic = latest
        return {
            "num": comic["num"],
            "title": comic["title"],
            "alt": comic.get("alt", ""),
            "img": _embed_image(comic["img"]),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
