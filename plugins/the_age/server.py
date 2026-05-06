"""The Age front-page widget.

Scrapes frontpages.com/the-age/, extracts the og:image, then rewrites the
URL to the high-resolution share variant: their CDN serves a smaller
thumbnail at /g/<id>.jpg and the full front page at /share/<id>. Per the
brief: "swap /g/ -> /share/ in the path and strip the .jpg suffix."
"""
from __future__ import annotations

import base64
import re
import threading
import time
import urllib.request
from typing import Any

SOURCE_URL = "https://www.frontpages.com/the-age/"

_OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.I,
)

_lock = threading.Lock()
_cache: dict[str, Any] = {"data": None, "ts": 0.0, "key": None}


def _http_get(url: str, timeout: float = 15.0, *, as_text: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-the_age"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return body.decode("utf-8", errors="replace") if as_text else body


def _share_url(og_image: str) -> str:
    """Translate the og:image thumbnail URL into the high-res share URL.
    Per the v2 quirk: swap '/g/' -> '/share/' and strip the trailing '.jpg'."""
    url = og_image.replace("/g/", "/share/")
    if url.lower().endswith(".jpg"):
        url = url[:-4]
    return url


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    cache_s = int(settings.get("THE_AGE_CACHE_S") or 1800)
    now = time.time()
    with _lock:
        if _cache["data"] and now - _cache["ts"] < cache_s:
            return _cache["data"]
    try:
        html = _http_get(SOURCE_URL, as_text=True)
        m = _OG_IMAGE_RE.search(html)
        if not m:
            return {"error": "og:image meta tag not found on the source page"}
        share_url = _share_url(m.group(1))
        img_bytes = _http_get(share_url, timeout=20.0)
        # The share endpoint returns JPEG even though the path has no extension.
        b64 = base64.b64encode(img_bytes).decode("ascii")
        data = {
            "img": f"data:image/jpeg;base64,{b64}",
            "source": share_url,
        }
        with _lock:
            _cache["data"] = data
            _cache["ts"] = now
        return data
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
