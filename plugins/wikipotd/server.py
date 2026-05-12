"""Wikimedia Commons Picture of the Day.

Uses the public Wikimedia Feed API
(``api.wikimedia.org/feed/v1/wikipedia/en/featured/YYYY/MM/DD``), which
returns today's featured ``image`` block alongside news/articles. No auth.

Cached for 6 hours — the POTD only changes once a day, but we want a
graceful fallback if the API is briefly unreachable. On error we fall back
to whatever we last successfully fetched.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

CACHE_TTL = 6 * 60 * 60
LOOKBACK_DAYS = 5  # in case today's feed isn't published yet


def _api_request(when: date) -> dict[str, Any]:
    url = (
        f"https://api.wikimedia.org/feed/v1/wikipedia/en/featured/"
        f"{when.year}/{when:%m}/{when:%d}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text: str) -> str:
    """The description.text field sometimes contains inline tags. Strip them
    for plain-text overlay rendering."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _pick_image(feed: dict[str, Any]) -> dict[str, Any] | None:
    img = feed.get("image")
    if not isinstance(img, dict):
        return None
    image_url = ((img.get("image") or {}).get("source")) or (
        (img.get("thumbnail") or {}).get("source")
    )
    if not image_url:
        return None
    return {
        "url": image_url,
        "title": _strip_html((img.get("description") or {}).get("text", "")) or "",
        "artist": _strip_html((img.get("artist") or {}).get("text", "")),
        "credit": _strip_html((img.get("credit") or {}).get("text", "")),
        "license": (img.get("license") or {}).get("type", ""),
    }


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / "potd.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    today = datetime.now(UTC).date()
    last_err: str | None = None
    for offset in range(LOOKBACK_DAYS):
        when = today - timedelta(days=offset)
        try:
            feed = _api_request(when)
        except urllib.error.HTTPError as err:
            # 404 means today's feed isn't published yet — try yesterday.
            if err.code == 404 and offset == 0:
                continue
            last_err = f"HTTP {err.code}: {err.reason}"
            break
        except Exception as err:  # noqa: BLE001
            last_err = f"{type(err).__name__}: {err}"
            break
        pick = _pick_image(feed)
        if pick is not None:
            pick["date"] = when.isoformat()
            pick["fetched_at"] = int(time.time())
            cache.write_text(json.dumps(pick))
            return pick

    # Fall back to whatever we last managed to fetch, if anything.
    if cache.exists():
        try:
            stale = json.loads(cache.read_text())
            stale["stale"] = True
            return stale
        except (json.JSONDecodeError, OSError):
            pass
    return {"error": last_err or "No Wikimedia POTD available.", "url": None}
