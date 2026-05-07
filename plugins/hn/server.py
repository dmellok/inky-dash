"""Hacker News stories via the public Firebase API. No key required."""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

CACHE_TTL = 600  # 10 minutes
ALLOWED_FEEDS = frozenset({"topstories", "newstories", "beststories", "askstories", "showstories"})


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/0.7"})
    with urllib.request.urlopen(req, timeout=8) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    feed = options.get("feed", "topstories")
    if feed not in ALLOWED_FEEDS:
        feed = "topstories"
    count = max(1, min(int(options.get("count", 10) or 10), 30))

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"hn_{feed}_{count}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    try:
        ids = _fetch_json(f"https://hacker-news.firebaseio.com/v0/{feed}.json")[:count]
        items: list[dict[str, Any]] = [{} for _ in ids]
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(
                    _fetch_json, f"https://hacker-news.firebaseio.com/v0/item/{i}.json"
                ): idx
                for idx, i in enumerate(ids)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    items[idx] = fut.result()
                except Exception:
                    items[idx] = {}
    except Exception as err:
        return {"error": f"{type(err).__name__}: {err}"}

    result = {
        "stories": [
            {
                "id": s.get("id"),
                "title": s.get("title", ""),
                "score": s.get("score", 0),
                "by": s.get("by", ""),
                "url": s.get("url", ""),
                "comments": s.get("descendants", 0),
            }
            for s in items
            if s
        ],
        "feed": feed,
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result
