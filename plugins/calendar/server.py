"""Calendar widget — pulls events from an iCal feed (HTTP or webcal://).

Uses `icalendar` for parsing and `recurring-ical-events` to expand recurrences
within the lookahead window. Per the brief, never leaves the cell blank: if
both 'today' and 'upcoming' are empty, the response includes the next event
past the lookahead window so the cell still says something useful.
"""
from __future__ import annotations

import threading
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}  # (feed_url, lookahead) -> (ts, data)
_CACHE_S = 5 * 60  # 5 min — feeds change rarely


def _http_get(url: str, timeout: float = 15.0) -> bytes:
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://"):]
    req = urllib.request.Request(url, headers={"User-Agent": "Inky-Dash-calendar"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _to_utc(d) -> datetime:
    """Coerce a date or datetime to a tz-aware UTC datetime."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    # Plain date — treat as midnight UTC.
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _summarise_event(ev) -> dict:
    """Build the JSON-ready dict the client renders."""
    summary = str(ev.get("SUMMARY") or "(untitled)")
    location = str(ev.get("LOCATION") or "") or None
    dtstart = ev.decoded("DTSTART") if ev.get("DTSTART") else None
    dtend = ev.decoded("DTEND") if ev.get("DTEND") else None
    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)
    return {
        "summary": summary,
        "location": location,
        "all_day": bool(all_day),
        "start": _to_utc(dtstart).isoformat() if dtstart else None,
        "end": _to_utc(dtend).isoformat() if dtend else None,
    }


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    feed_url = (options.get("feed_url") or "").strip()
    if not feed_url:
        return {"error": "no iCal feed_url set"}
    try:
        lookahead = int(options.get("lookahead_days") or 14)
    except (TypeError, ValueError):
        lookahead = 14

    cache_key = f"{feed_url}|{lookahead}"
    now = time.time()
    with _lock:
        hit = _cache.get(cache_key)
        if hit and now - hit[0] < _CACHE_S:
            return hit[1]

    try:
        import icalendar
        import recurring_ical_events
    except ImportError as exc:
        return {"error": f"calendar deps missing: {exc}"}
    try:
        raw = _http_get(feed_url)
        cal = icalendar.Calendar.from_ical(raw)
    except Exception as exc:
        return {"error": f"feed fetch/parse failed: {exc}"}

    today = datetime.now(tz=timezone.utc).date()
    end_window = today + timedelta(days=lookahead)
    try:
        events = recurring_ical_events.of(cal).between(today, end_window)
    except Exception as exc:
        return {"error": f"recurrence expansion failed: {exc}"}

    today_list, upcoming_list = [], []
    for ev in events:
        info = _summarise_event(ev)
        if not info["start"]:
            continue
        start_d = datetime.fromisoformat(info["start"]).date()
        if start_d == today:
            today_list.append(info)
        elif today < start_d <= end_window:
            upcoming_list.append(info)
    today_list.sort(key=lambda x: x["start"])
    upcoming_list.sort(key=lambda x: x["start"])

    next_after_window = None
    if not today_list and not upcoming_list:
        # Look further out, up to a year, so the cell never says nothing.
        try:
            far = recurring_ical_events.of(cal).between(end_window, today + timedelta(days=365))
            future = sorted(
                (_summarise_event(e) for e in far if e.get("DTSTART")),
                key=lambda x: x.get("start") or "",
            )
            next_after_window = future[0] if future else None
        except Exception:
            pass

    data = {
        "today": today_list,
        "upcoming": upcoming_list,
        "next_after_window": next_after_window,
        "lookahead_days": lookahead,
    }
    with _lock:
        _cache[cache_key] = (now, data)
    return data
