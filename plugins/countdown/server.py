"""Countdown widget — days/hours until a target date.

The server resolves the target string and computes the delta against the
host's wall clock. Renders an explicit "elapsed" sentinel when the target
is in the past so the client can swap to a "since" view without parsing
dates client-side.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta


_TODAY_RE = re.compile(r"^today(?:([+-])(\d+)d)?$", re.IGNORECASE)


def _parse_target(raw: str) -> datetime | None:
    s = (raw or "").strip()
    if not s:
        return None
    # "today" / "today+7d" / "today-3d" sentinel — resolved against the
    # host's local clock at fetch time. Lets the manifest provide a
    # sensible relative default that doesn't go stale.
    m = _TODAY_RE.match(s)
    if m:
        sign, days = m.group(1), m.group(2)
        offset = (1 if sign == "+" else -1) * int(days) if (sign and days) else 0
        return (datetime.now() + timedelta(days=offset)).astimezone().replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
    # Accept YYYY-MM-DD (treat as midnight local) and full ISO datetimes
    # with optional timezone. fromisoformat handles both since 3.11.
    try:
        if "T" not in s:
            s = f"{s}T00:00:00"
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    label = (options.get("label") or "Until").strip()
    # Falls back to "today+7d" if the cell hasn't been configured — keeps
    # newly-added cells from showing an error before the user picks a date.
    target = _parse_target(options.get("target") or "today+7d")
    if target is None:
        return {"error": "could not parse target date"}

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
