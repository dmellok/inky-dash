"""Countdown widget — days/hours until a target date.

The server resolves the target string and computes the delta against the
host's wall clock. Renders an explicit "elapsed" sentinel when the target
is in the past so the client can swap to a "since" view without parsing
dates client-side.
"""
from __future__ import annotations

from datetime import datetime, timedelta


def _parse_target(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    # Accept YYYY-MM-DD (treat as midnight local) and full ISO datetimes
    # with optional timezone. fromisoformat handles both since 3.11.
    try:
        if "T" not in s:
            s = f"{s}T00:00:00"
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    # Naive datetimes get the local timezone so the math against
    # datetime.now().astimezone() is apples-to-apples.
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    label = (options.get("label") or "Until").strip()
    target = _parse_target(options.get("target") or "")
    if target is None:
        return {"error": "set a target date in the cell options (YYYY-MM-DD)"}

    now = datetime.now().astimezone()
    delta = target - now
    elapsed = delta.total_seconds() < 0
    if elapsed:
        delta = -delta

    days = delta.days
    seconds = delta.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    return {
        "label": label,
        "target_iso": target.isoformat(timespec="minutes"),
        "target_pretty": target.strftime("%-d %B %Y"),
        "days": days,
        "hours": hours,
        "minutes": minutes,
        "elapsed": elapsed,
        # Total in seconds — handy for fine-grained ticking in preview mode.
        "total_seconds": int(delta.total_seconds()) * (-1 if elapsed else 1),
    }
