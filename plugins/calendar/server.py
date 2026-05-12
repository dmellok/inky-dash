"""Calendar widget — pulls VEVENT entries from an ICS feed and hands the
client an ordered list of upcoming events.

We deliberately don't depend on a heavy ICS library here. The ICS format is
line-based (RFC 5545) and our needs are narrow: parse VEVENT blocks for
SUMMARY / DTSTART / DTEND / LOCATION. Recurring events (RRULE) and TZID
parameters with non-UTC timezones aren't expanded — calendars with simple
non-recurring events work out of the box; for recurring-event support, swap
in the ``icalendar`` package if you need it.

The fetched payload is cached on disk under ``data/plugins/calendar/`` with
a settings-configurable TTL (default 15 min).
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_CACHE_FILENAME = "feed.json"
_DEFAULT_TTL_MIN = 15
_HORIZON_DAYS = 60  # how far ahead we keep events around


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    """Return upcoming events from the configured ICS feed."""
    feed_url = (settings.get("feed_url") or "").strip()
    if not feed_url:
        return {"error": "Set the ICS feed URL in /settings."}

    try:
        ttl_min = max(1, int(settings.get("cache_ttl_minutes") or _DEFAULT_TTL_MIN))
    except (TypeError, ValueError):
        ttl_min = _DEFAULT_TTL_MIN

    try:
        event_count = max(1, min(int(options.get("event_count") or 3), 20))
    except (TypeError, ValueError):
        event_count = 3

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / _CACHE_FILENAME

    # Try the cache before hitting the network.
    cached_events = _read_cache(cache, ttl_min)
    if cached_events is None:
        try:
            ics_text = _download(feed_url)
        except urllib.error.URLError as err:
            # Network failed — fall back to whatever's on disk, if anything.
            stale = _read_cache(cache, ttl_min=10_000)
            if stale is not None:
                return _shape(stale, event_count, note=f"stale (network: {err.reason})")
            return {"error": f"Couldn't fetch ICS feed: {err.reason}"}
        events = _parse_ics(ics_text)
        _write_cache(cache, events)
        cached_events = events

    return _shape(cached_events, event_count)


# ---------------------------------------------------------------------------
# ICS parser — handles the narrow subset of RFC 5545 we actually need.
# ---------------------------------------------------------------------------


def _download(url: str) -> str:
    # ``webcal://`` is the iCal subscription scheme — same payload as
    # https, just a different URI prefix that calendar clients recognise.
    # urllib doesn't know it, so swap it back to https before fetching.
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_ics(text: str) -> list[dict[str, Any]]:
    """Extract VEVENT blocks from an ICS body. Returns dicts with
    ``title``, ``location``, ``start_iso``, ``end_iso``, ``all_day``."""
    # 1. Unfold continuation lines. Per RFC 5545, a line starting with a
    #    space or tab continues the previous logical line.
    raw_lines = text.replace("\r\n", "\n").split("\n")
    logical: list[str] = []
    for raw in raw_lines:
        if raw.startswith((" ", "\t")) and logical:
            logical[-1] += raw[1:]
        else:
            logical.append(raw)

    # 2. Walk VEVENT blocks. We only capture the fields we care about.
    events: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in logical:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                shaped = _shape_event(current)
                if shaped is not None:
                    events.append(shaped)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        # KEY[;PARAM=val;...] — strip params, keep the base key.
        base = key_part.split(";", 1)[0].upper()
        # Detect VALUE=DATE all-day markers in any parameter list.
        value_date = "VALUE=DATE" in key_part.upper()
        if base == "SUMMARY":
            current["summary"] = _unescape(value)
        elif base == "LOCATION":
            current["location"] = _unescape(value)
        elif base == "DTSTART":
            current["dtstart"] = (value, value_date)
        elif base == "DTEND":
            current["dtend"] = (value, value_date)
    return events


def _unescape(value: str) -> str:
    """Reverse RFC 5545 text-value escaping."""
    return (
        value.replace("\\n", "\n")
        .replace("\\N", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _shape_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Project the parsed VEVENT fields into the dict the client expects."""
    dtstart = raw.get("dtstart")
    if not dtstart:
        return None
    start_dt = _parse_ics_dt(*dtstart)
    if start_dt is None:
        return None
    end_dt = None
    if raw.get("dtend"):
        end_dt = _parse_ics_dt(*raw["dtend"])
    all_day = dtstart[1] or (start_dt.hour == 0 and start_dt.minute == 0 and end_dt is None)
    return {
        "title": raw.get("summary") or "(no title)",
        "location": raw.get("location", ""),
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat() if end_dt else None,
        "all_day": all_day,
    }


def _parse_ics_dt(value: str, value_date: bool) -> datetime | None:
    """Parse an ICS DATE or DATE-TIME value to a tz-aware datetime.

    Pure date values (``20261002``) come back as midnight UTC of that day.
    UTC datetimes (``20261002T140000Z``) come back as UTC. Local datetimes
    without a tz attach the host's local tz on a best-effort basis."""
    if not value:
        return None
    try:
        if value_date or (len(value) == 8 and "T" not in value):
            return datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC)
        if value.endswith("Z"):
            return datetime.strptime(value[:-1], "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
        # Floating local-time datetimes — attach the host's tz so they sort.
        return datetime.strptime(value, "%Y%m%dT%H%M%S").astimezone()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Cache + shaping
# ---------------------------------------------------------------------------


def _read_cache(cache: Path, ttl_min: int) -> list[dict[str, Any]] | None:
    if not cache.exists():
        return None
    age_min = (time.time() - cache.stat().st_mtime) / 60
    if age_min > ttl_min:
        return None
    try:
        return json.loads(cache.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(cache: Path, events: list[dict[str, Any]]) -> None:
    cache.write_text(json.dumps(events))


def _shape(
    events: list[dict[str, Any]], event_count: int, note: str | None = None
) -> dict[str, Any]:
    """Filter to upcoming events + take the first N. Client renders the
    month grid itself from today's date; the server just supplies the
    agenda items."""
    now = datetime.now(UTC)
    horizon = now + timedelta(days=_HORIZON_DAYS)
    upcoming: list[dict[str, Any]] = []
    for e in events:
        try:
            start = datetime.fromisoformat(e["start_iso"])
        except (KeyError, ValueError):
            continue
        if start < now - timedelta(hours=12):
            continue  # already finished
        if start > horizon:
            continue  # too far in the future to bother showing
        upcoming.append(e)
    upcoming.sort(key=lambda e: e["start_iso"])
    payload: dict[str, Any] = {"events": upcoming[:event_count]}
    if note:
        payload["note"] = note
    return payload
