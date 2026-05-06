"""News widget — RSS/Atom feed via `feedparser`.

When `cycle=true`, advances a per-feed cursor on each push (NOT preview) so
the highlighted item rotates across panel updates. Cursor lives in
data/news_cycle.json.
"""
from __future__ import annotations

import json
import threading
import time
from html import unescape
from pathlib import Path
from typing import Any

from flask import current_app

_lock = threading.Lock()
_cache: dict[str, tuple[float, list]] = {}
_CACHE_S = 5 * 60


def _cycle_path() -> Path:
    return current_app.config["INKY"].data_dir / "news_cycle.json"


def _load_cursors() -> dict[str, int]:
    p = _cycle_path()
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return {k: int(v) for k, v in d.items() if isinstance(v, int)}
    except Exception:
        return {}


def _save_cursors(cursors: dict[str, int]) -> None:
    p = _cycle_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(cursors, indent=2), encoding="utf-8")
    tmp.replace(p)


def _strip_html(text: str) -> str:
    """Crude HTML strip — feedparser sometimes returns rich markup."""
    if not text:
        return ""
    # Remove tags, collapse whitespace, decode entities.
    import re
    out = re.sub(r"<[^>]+>", " ", text)
    out = unescape(out)
    out = re.sub(r"\s+", " ", out).strip()
    return out


def _summarise(item, max_chars: int = 120) -> str:
    summary = item.get("summary") or item.get("description") or ""
    out = _strip_html(summary)
    if len(out) > max_chars:
        out = out[: max_chars - 1].rstrip() + "…"
    return out


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    feed_url = (options.get("feed_url") or "").strip()
    if not feed_url:
        return {"error": "no feed_url set"}
    try:
        max_items = max(1, min(20, int(options.get("max_items") or 5)))
    except (TypeError, ValueError):
        max_items = 5
    cycle = bool(options.get("cycle"))

    with _lock:
        hit = _cache.get(feed_url)
        if hit and time.time() - hit[0] < _CACHE_S:
            entries = hit[1]
        else:
            try:
                import feedparser
            except ImportError as exc:
                return {"error": f"feedparser missing: {exc}"}
            try:
                parsed = feedparser.parse(feed_url)
                if parsed.bozo and not parsed.entries:
                    return {"error": f"feed parse failed: {parsed.bozo_exception}"}
                entries = parsed.entries or []
            except Exception as exc:
                return {"error": f"fetch failed: {exc}"}
            _cache[feed_url] = (time.time(), entries)

    if not entries:
        return {"error": "feed has no entries"}

    items = []
    for e in entries[:max_items]:
        items.append({
            "title": _strip_html(e.get("title") or "(untitled)")[:200],
            "author": (e.get("author") or "").strip()[:80] or None,
            "summary": _summarise(e),
            "published": e.get("published") or e.get("updated") or None,
        })

    highlighted = 0
    if cycle and not preview:
        with _lock:
            cursors = _load_cursors()
            highlighted = (cursors.get(feed_url, -1) + 1) % len(items)
            cursors[feed_url] = highlighted
            _save_cursors(cursors)
    elif cycle:
        # Preview: peek the cursor without advancing.
        with _lock:
            cursors = _load_cursors()
            highlighted = (cursors.get(feed_url, -1) + 1) % len(items)

    return {"items": items, "highlighted_index": highlighted}
