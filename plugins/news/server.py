"""RSS / Atom feed reader via feedparser."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import feedparser

CACHE_TTL = 600  # 10 minutes


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    # Cell URL overrides the global default-url setting; either-or is fine.
    url = (options.get("url") or settings.get("default_url") or "").strip()
    count = max(1, min(int(options.get("count", 8) or 8), 30))
    title_override = options.get("title", "")
    user_agent = settings.get("user_agent") or "inky-dash/1.0"

    if not url:
        return {"error": "No feed URL configured (cell option or settings)."}

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(url.encode()).hexdigest()[:16]
    cache = data_dir / f"feed_{cache_key}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    try:
        parsed = feedparser.parse(url, agent=user_agent)
    except Exception as err:
        return {"error": f"{type(err).__name__}: {err}"}

    if parsed.bozo and not parsed.entries:
        return {"error": f"Could not parse feed at {url}"}

    feed_title = title_override or parsed.feed.get("title", url)
    items = []
    for entry in parsed.entries[:count]:
        items.append(
            {
                "title": entry.get("title", "(no title)"),
                "link": entry.get("link", ""),
                "published": entry.get("published", "") or entry.get("updated", ""),
                "summary": entry.get("summary", "")[:200],
            }
        )

    result = {"title": feed_title, "items": items, "fetched_at": int(time.time())}
    cache.write_text(json.dumps(result))
    return result
