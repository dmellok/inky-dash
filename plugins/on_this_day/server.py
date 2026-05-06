"""On this day widget — Wikipedia "On this day" feed.

Wikimedia REST endpoint:
  https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/{type}/{MM}/{DD}

Where type ∈ {events, births, deaths, holidays, selected, all}. We use
"selected" by default (curated daily highlights), but the user can pick
any of the others. Image for the hero comes from the first event's
linked Wikipedia page thumbnail when available — downloaded and inlined
as a base64 data URL so Playwright doesn't re-fetch on every push.
"""
from __future__ import annotations

import base64
import json
import threading
import time
import urllib.request
from datetime import date
from typing import Any


API_TMPL = "https://api.wikimedia.org/feed/v1/wikipedia/{lang}/onthisday/{kind}/{mm:02d}/{dd:02d}"
_VALID_KIND = {"selected", "events", "births", "deaths", "holidays"}

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}


def _http(url: str, *, want_json: bool, timeout: float = 12.0) -> Any:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Inky-Dash-on_this_day/1.0 (+https://github.com/dmellok/inky-dash)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    return json.loads(data) if want_json else data


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    kind = (options.get("feed") or "selected").strip().lower()
    if kind not in _VALID_KIND:
        kind = "selected"
    lang = (options.get("lang") or "en").strip().lower() or "en"
    show_image = options.get("show_image") is not False

    today = date.today()
    ttl = int(settings.get("OTD_CACHE_S") or 21600)
    cache_key = f"{lang}:{kind}:{today.month:02d}-{today.day:02d}:{int(show_image)}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and (now - hit[0]) < ttl:
            return dict(hit[1])

    url = API_TMPL.format(lang=lang, kind=kind, mm=today.month, dd=today.day)
    try:
        body = _http(url, want_json=True)
    except Exception as exc:
        return {"error": f"Wikipedia OTD failed: {type(exc).__name__}: {exc}"}

    items = body.get(kind) or []
    if not items:
        return {"error": "no entries for today"}

    # Sort events/births/deaths by recency so the hero is the most recent
    # year. Holidays/selected don't have year fields — keep them as-is.
    if kind in ("events", "births", "deaths"):
        items = sorted(items, key=lambda x: x.get("year") or -10_000, reverse=True)

    hero = items[0]
    rest = items[1:6]  # 5 supporting bullets

    # Hero image — use the first associated page's thumbnail.
    image_data_url = None
    pages = hero.get("pages") or []
    if show_image and pages:
        thumb = (pages[0].get("thumbnail") or {}).get("source")
        if thumb:
            try:
                img_bytes = _http(thumb, want_json=False, timeout=15.0)
                mime = "image/jpeg"
                lower = thumb.lower()
                if lower.endswith(".png"):  mime = "image/png"
                elif lower.endswith(".webp"): mime = "image/webp"
                elif lower.endswith(".svg"):  mime = "image/svg+xml"
                image_data_url = f"data:{mime};base64,{base64.b64encode(img_bytes).decode('ascii')}"
            except Exception:
                image_data_url = None

    def _entry(e: dict) -> dict:
        text = (e.get("text") or "").strip()
        return {
            "year": e.get("year"),
            "text": text,
        }

    out: dict[str, Any] = {
        "kind": kind,
        "lang": lang,
        "date_pretty": today.strftime("%-d %B"),
        "hero": _entry(hero),
        "rest": [_entry(e) for e in rest],
        "image": image_data_url,
    }
    with _lock:
        _cache[cache_key] = (now, out)
    return out
