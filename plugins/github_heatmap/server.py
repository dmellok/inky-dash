"""GitHub contributions heatmap.

Uses the public ``github-contributions-api.jogruber.de`` proxy which mirrors
the GitHub user profile heatmap as JSON. No auth needed, light rate limits.

Cached for 30 min so the panel can re-render without re-hitting the API.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

CACHE_TTL = 30 * 60


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    username = (options.get("username") or "").strip()
    if not username:
        return {"error": "Set a GitHub username in the cell options."}

    range_opt = options.get("range") or "year"
    days = {"year": 371, "6mo": 26 * 7, "3mo": 13 * 7}.get(range_opt, 371)

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / f"{username.lower()}.json"

    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            cached = json.loads(cache.read_text())
            return _slice(cached, days, range_opt, username)
        except (json.JSONDecodeError, OSError):
            pass

    url = (
        "https://github-contributions-api.jogruber.de/v4/"
        f"{urllib.parse.quote(username)}?y=last"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # 404 → user doesn't exist. Surface a clear message.
        if err.code == 404:
            return {"error": f"GitHub user {username!r} not found."}
        return {"error": f"HTTP {err.code}: {err.reason}"}
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}"}

    cache.write_text(json.dumps(payload))
    return _slice(payload, days, range_opt, username)


def _slice(
    payload: dict[str, Any], days: int, range_opt: str, username: str
) -> dict[str, Any]:
    """Return only the last ``days`` of contributions plus derived stats:
    current streak, longest streak, busiest day, active-day count, average."""
    raw = payload.get("contributions") or []
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    sliced = [
        c
        for c in raw
        if isinstance(c, dict) and c.get("date") and c["date"] >= cutoff.isoformat()
    ]
    total = sum(int(c.get("count", 0) or 0) for c in sliced)
    return {
        "username": username,
        "range": range_opt,
        "total": total,
        "contributions": sliced,
        "last_year_total": (payload.get("total") or {}).get("lastYear"),
        "stats": _compute_stats(sliced),
    }


def _compute_stats(contribs: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive headline stats from a chronological list of daily contributions.

    - current_streak: consecutive days ending today (or yesterday, if today
      hasn't recorded a commit yet) that have ≥1 contribution.
    - longest_streak: max run of consecutive ≥1 days in the window.
    - best_day: {date, count} for the busiest day.
    - active_days: count of days with ≥1 contribution.
    - avg_per_day: total / total days in window (over both active and quiet days).
    - busiest_weekday: which weekday accumulates the most commits across the window.
    """
    if not contribs:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "best_day": None,
            "active_days": 0,
            "avg_per_day": 0.0,
            "busiest_weekday": None,
        }

    chronological = sorted(contribs, key=lambda c: c["date"])
    counts = [int(c.get("count", 0) or 0) for c in chronological]
    dates = [c["date"] for c in chronological]

    # Longest streak (any window).
    longest = 0
    run = 0
    for c in counts:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)

    # Current streak: walk backwards from the most recent day. Skip today if
    # it's 0 — common case is "haven't committed yet today, streak is still alive
    # from yesterday". If yesterday is also 0, streak ends.
    current = 0
    today_iso = datetime.now(UTC).date().isoformat()
    rev_counts = list(reversed(counts))
    rev_dates = list(reversed(dates))
    started = False
    for i, c in enumerate(rev_counts):
        if not started:
            # Tolerate today being empty as long as yesterday isn't.
            if c == 0 and rev_dates[i] == today_iso:
                continue
            started = True
        if c > 0:
            current += 1
        else:
            break

    # Busiest day.
    max_idx = max(range(len(counts)), key=lambda i: counts[i])
    best_day = (
        {"date": dates[max_idx], "count": counts[max_idx]}
        if counts[max_idx] > 0
        else None
    )

    active_days = sum(1 for c in counts if c > 0)
    avg = sum(counts) / len(counts) if counts else 0.0

    # Busiest weekday — Mon..Sun aggregation.
    weekday_totals = [0] * 7
    weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d, c in zip(dates, counts, strict=False):
        try:
            wd = datetime.fromisoformat(d).weekday()
        except ValueError:
            continue
        weekday_totals[wd] += c
    busiest_wd = (
        weekday_names[max(range(7), key=lambda i: weekday_totals[i])]
        if any(weekday_totals)
        else None
    )

    return {
        "current_streak": current,
        "longest_streak": longest,
        "best_day": best_day,
        "active_days": active_days,
        "avg_per_day": round(avg, 1),
        "busiest_weekday": busiest_wd,
    }
