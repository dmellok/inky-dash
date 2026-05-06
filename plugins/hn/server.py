"""Hacker News widget — top / new / best / ask / show stories.

Uses the public Firebase HN API (no auth required). Story IDs come from
`<feed>stories.json`; each story is fetched individually but only N times
per render — N is the user-configured count. Per-feed cache so different
cells don't compete on the same upstream call.
"""
from __future__ import annotations

import json
import threading
import time
import urllib.parse
import urllib.request
from typing import Any


_FEED_URLS = {
    "top":  "https://hacker-news.firebaseio.com/v0/topstories.json",
    "new":  "https://hacker-news.firebaseio.com/v0/newstories.json",
    "best": "https://hacker-news.firebaseio.com/v0/beststories.json",
    "ask":  "https://hacker-news.firebaseio.com/v0/askstories.json",
    "show": "https://hacker-news.firebaseio.com/v0/showstories.json",
}
_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"

_lock = threading.Lock()
_cache: dict[str, tuple[float, list[dict]]] = {}


def _http_json(url: str, timeout: float = 10.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-hn"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _domain(url: str | None) -> str:
    if not url:
        return ""
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    feed = (options.get("feed") or "top").strip().lower()
    if feed not in _FEED_URLS:
        feed = "top"
    try:
        count = int(options.get("count") or 5)
    except (TypeError, ValueError):
        count = 5
    count = max(1, min(count, 20))

    ttl = int(settings.get("HN_CACHE_S") or 600)
    cache_key = f"{feed}:{count}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return {"feed": feed, "stories": list(hit[1])}

    try:
        ids = _http_json(_FEED_URLS[feed])
    except Exception as exc:
        return {"error": f"HN feed failed: {type(exc).__name__}: {exc}"}
    if not isinstance(ids, list):
        return {"error": "HN feed returned unexpected payload"}

    stories: list[dict] = []
    for sid in ids[:count]:
        try:
            item = _http_json(_ITEM_URL.format(int(sid)))
        except Exception:
            continue
        if not isinstance(item, dict) or item.get("type") != "story":
            continue
        url = item.get("url") or f"https://news.ycombinator.com/item?id={sid}"
        stories.append({
            "id": int(sid),
            "title": item.get("title") or "",
            "score": int(item.get("score") or 0),
            "comments": int(item.get("descendants") or 0),
            "author": item.get("by") or "",
            "url": url,
            "domain": _domain(item.get("url")),
            "self": "url" not in item,  # Ask HN / Show HN with no external link
        })
        if len(stories) >= count:
            break

    with _lock:
        _cache[cache_key] = (now, stories)
    return {"feed": feed, "stories": stories}
