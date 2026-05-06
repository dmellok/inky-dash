"""Moon calendar widget — full-month grid with the moon phase per day.

Phases computed locally from a known reference new moon:
  2000-01-06 18:14 UTC, synodic period 29.53058867 days.
That's accurate to within a few hours over decades — plenty for a
calendar where each cell only needs to know "what does this day's moon
look like".
"""
from __future__ import annotations

import math
from calendar import monthrange
from datetime import date, datetime, timezone
from typing import Any


_MOON_REF = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
_MOON_PERIOD = 29.53058867
_PHASES = ["New", "Waxing crescent", "First quarter", "Waxing gibbous",
           "Full", "Waning gibbous", "Last quarter", "Waning crescent"]


def _phase_for(d: date) -> dict:
    """Phase index 0..7, illumination % 0..100, fraction 0..1."""
    midday = datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
    days = (midday - _MOON_REF).total_seconds() / 86400.0
    age = days % _MOON_PERIOD
    fraction = age / _MOON_PERIOD
    idx = int((fraction * 8 + 0.5)) % 8
    illumination = (1 - math.cos(2 * math.pi * fraction)) / 2 * 100
    return {
        "idx": idx,
        "name": _PHASES[idx],
        "illumination": round(illumination, 0),
        "fraction": round(fraction, 4),
        "waxing": fraction < 0.5,
    }


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    today = date.today()
    year = today.year
    month = today.month
    first_dow = date(year, month, 1).weekday()  # Monday=0
    days_in_month = monthrange(year, month)[1]

    # Build a 6-week grid: leading blanks → days → trailing blanks. 42 cells
    # is the standard "always-fits" calendar layout regardless of which day
    # of the week the month starts on.
    cells: list[dict | None] = [None] * first_dow
    for d in range(1, days_in_month + 1):
        day = date(year, month, d)
        phase = _phase_for(day)
        cells.append({
            "day": d,
            "iso": day.isoformat(),
            "weekday": day.weekday(),
            "is_today": day == today,
            "is_weekend": day.weekday() >= 5,
            **phase,
        })
    while len(cells) < 42:
        cells.append(None)

    # Today summary for the header chip.
    today_phase = _phase_for(today)

    return {
        "year": year,
        "month": month,
        "month_name": today.strftime("%B"),
        "today_iso": today.isoformat(),
        "today_phase": today_phase,
        "cells": cells,
        "weekday_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    }
