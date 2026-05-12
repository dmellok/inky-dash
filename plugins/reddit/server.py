"""Reddit widget — fetches the top posts of a subreddit via the public
JSON endpoint.

Reddit lets you append ``.json`` to any subreddit URL and get a structured
listing back without auth: ``https://www.reddit.com/r/<sub>/<sort>.json``.
We respect their rate limiter by caching responses on disk with a
configurable TTL (default 10 min); on a network failure we fall back to
whatever was last cached so the cell never blanks.

A descriptive User-Agent is strongly recommended by Reddit — the default
identifies the project but you can override it under /settings.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_VALID_SORTS = frozenset({"hot", "new", "top", "rising"})
_VALID_TIME_FILTERS = frozenset({"hour", "day", "week", "month", "year", "all"})
_DEFAULT_TTL_MIN = 10
_CACHE_FILENAME_RE_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789-_"


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    sub = (options.get("subreddit") or "popular").strip().lstrip("r/").lower()
    if not sub or not all(c.lower() in _CACHE_FILENAME_RE_CHARS for c in sub):
        return {"error": "Subreddit name has unexpected characters."}

    sort = options.get("sort", "hot")
    if sort not in _VALID_SORTS:
        sort = "hot"
    time_filter = options.get("time_filter", "day")
    if time_filter not in _VALID_TIME_FILTERS:
        time_filter = "day"
    try:
        limit = max(1, min(int(options.get("limit") or 5), 25))
    except (TypeError, ValueError):
        limit = 5
    hide_nsfw = options.get("hide_nsfw", True) is not False

    user_agent = (settings.get("user_agent") or "inky-dash/1.0 (Reddit widget)").strip()
    try:
        ttl_min = max(1, int(settings.get("cache_ttl_minutes") or _DEFAULT_TTL_MIN))
    except (TypeError, ValueError):
        ttl_min = _DEFAULT_TTL_MIN

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"{sub}_{sort}_{time_filter}.json"

    raw = _read_cache(cache, ttl_min)
    if raw is None:
        try:
            raw = _download(sub, sort, time_filter, limit, user_agent)
        except urllib.error.HTTPError as err:
            stale = _read_cache(cache, ttl_min=10_000)
            if stale is not None:
                return _shape(stale, sub, sort, limit, hide_nsfw, note=f"stale (HTTP {err.code})")
            return {"error": _http_error_message(err)}
        except urllib.error.URLError as err:
            stale = _read_cache(cache, ttl_min=10_000)
            if stale is not None:
                return _shape(stale, sub, sort, limit, hide_nsfw, note=f"stale ({err.reason})")
            return {"error": f"Couldn't reach Reddit: {err.reason}"}
        except (json.JSONDecodeError, KeyError) as err:
            return {"error": f"Unexpected response from Reddit: {err}"}
        cache.write_text(json.dumps(raw))
    return _shape(raw, sub, sort, limit, hide_nsfw)


def _download(sub: str, sort: str, time_filter: str, limit: int, user_agent: str) -> dict[str, Any]:
    params: dict[str, str] = {"limit": str(limit)}
    if sort == "top":
        params["t"] = time_filter
    url = (
        f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/{sort}.json"
        f"?{urllib.parse.urlencode(params)}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _http_error_message(err: urllib.error.HTTPError) -> str:
    if err.code == 403:
        # 403 from Reddit usually means a bad / blocked User-Agent.
        return "Reddit returned 403 — try setting a unique User-Agent in /settings."
    if err.code == 404:
        return "Subreddit not found (or quarantined)."
    if err.code == 429:
        return "Rate-limited by Reddit — bump cache TTL in /settings."
    return f"Reddit HTTP {err.code}: {err.reason}"


def _read_cache(cache: Path, ttl_min: int) -> dict[str, Any] | None:
    if not cache.exists():
        return None
    age_min = (time.time() - cache.stat().st_mtime) / 60
    if age_min > ttl_min:
        return None
    try:
        return json.loads(cache.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _shape(
    raw: dict[str, Any],
    sub: str,
    sort: str,
    limit: int,
    hide_nsfw: bool,
    note: str | None = None,
) -> dict[str, Any]:
    """Project Reddit's JSON shape into something the client can render
    without knowing about t2_/t3_ kind prefixes or the listing wrapper."""
    children = (raw.get("data") or {}).get("children") or []
    now = time.time()
    posts: list[dict[str, Any]] = []
    for child in children:
        if child.get("kind") != "t3":  # t3 = link/post
            continue
        d = child.get("data") or {}
        if d.get("stickied"):
            continue  # mod-pinned posts are rarely what the user wants
        if hide_nsfw and d.get("over_18"):
            continue
        thumb = d.get("thumbnail") or ""
        # Reddit returns sentinel strings ("self", "default", "nsfw") when
        # there's no real thumbnail — strip those.
        if not thumb.startswith(("http://", "https://")):
            thumb = ""
        posts.append(
            {
                "title": d.get("title") or "",
                "score": int(d.get("score") or 0),
                "comments": int(d.get("num_comments") or 0),
                "author": d.get("author") or "",
                "subreddit": d.get("subreddit") or sub,
                "domain": d.get("domain") or "",
                "age_seconds": int(now - float(d.get("created_utc") or now)),
                "thumbnail": thumb,
                "is_self": bool(d.get("is_self")),
                "permalink": f"https://www.reddit.com{d.get('permalink', '')}",
            }
        )
        if len(posts) >= limit:
            break
    result: dict[str, Any] = {
        "subreddit": sub,
        "sort": sort,
        "posts": posts,
        "fetched_at": int(now),
    }
    if note:
        result["note"] = note
    return result
