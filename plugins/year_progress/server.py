"""Year progress widget — server-side computation of where in the year we are.

Pure local — no network — but server-side so the rendered snapshot at push
time matches the host's wall clock and timezone.
"""
from __future__ import annotations

from datetime import date, datetime


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    now = datetime.now().astimezone()
    today = now.date()
    year = today.year
    start = date(year, 1, 1)
    end = date(year + 1, 1, 1)
    days_in_year = (end - start).days
    day_of_year = (today - start).days + 1
    days_remaining = days_in_year - day_of_year
    pct = (day_of_year / days_in_year) * 100
    week_of_year = int(today.strftime("%V"))
    quarter = (today.month - 1) // 3 + 1
    month_progress = today.day / _days_in_month(today)
    return {
        "year": year,
        "day_of_year": day_of_year,
        "days_in_year": days_in_year,
        "days_remaining": days_remaining,
        "pct": round(pct, 1),
        "week_of_year": week_of_year,
        "quarter": quarter,
        "month_progress_pct": round(month_progress * 100, 0),
        "month_name": today.strftime("%B"),
        "today_label": today.strftime("%A %-d %B"),
    }


def _days_in_month(d: date) -> int:
    if d.month == 12:
        next_month = date(d.year + 1, 1, 1)
    else:
        next_month = date(d.year, d.month + 1, 1)
    return (next_month - date(d.year, d.month, 1)).days
