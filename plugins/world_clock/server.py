"""World clock widget — N timezones in a horizontal strip with day/night
bars and a "now" cursor on each track.

Timezone names are IANA strings (zoneinfo). Special token "Local" maps to
the host's local zone. Optional "label@tz" syntax overrides the displayed
label so users can show "NY" instead of "America/New_York".
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo, available_timezones


# Day window — kept simple: 06:00-18:00 = "day", everything else "night".
# Locale-true sunrise/sunset would need a per-zone solar calc; this is the
# pragmatic 90% approximation for a glanceable widget.
_DAY_START = 6.0
_DAY_END = 18.0


def _parse_zones(raw: str) -> list[tuple[str, str]]:
    """[(label, tz)] pairs. Label defaults to the city name from the tz id."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    valid = available_timezones()
    for piece in (raw or "").split(","):
        s = piece.strip()
        if not s:
            continue
        if s.lower() == "local":
            label, tz = "Local", "local"
        elif "@" in s:
            label, tz = s.split("@", 1)
            label = label.strip()
            tz = tz.strip()
        else:
            tz = s
            label = s.split("/")[-1].replace("_", " ")
        if tz != "local" and tz not in valid:
            continue
        key = f"{label}|{tz}"
        if key in seen:
            continue
        seen.add(key)
        out.append((label, tz))
    return out[:6]  # cap so a runaway list can't fill the panel


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    pairs = _parse_zones(options.get("zones") or "Local")
    if not pairs:
        return {"error": "set at least one IANA timezone"}
    fmt = (options.get("format") or "24h").strip()
    if fmt not in ("12h", "24h"):
        fmt = "24h"

    rows: list[dict[str, Any]] = []
    for label, tz in pairs:
        if tz == "local":
            now = datetime.now().astimezone()
        else:
            try:
                now = datetime.now(ZoneInfo(tz))
            except Exception:
                continue
        hour_fraction = now.hour + now.minute / 60.0 + now.second / 3600.0
        # 12h vs 24h string formatted server-side so the panel render is
        # stable and matches whatever locale convention the user picked.
        if fmt == "12h":
            h = now.hour % 12 or 12
            t = f"{h}:{now.minute:02d}"
            ampm = "AM" if now.hour < 12 else "PM"
        else:
            t = f"{now.hour:02d}:{now.minute:02d}"
            ampm = ""
        offset = now.utcoffset()
        offset_h = int(offset.total_seconds() // 3600) if offset is not None else 0
        offset_m = int((abs(offset.total_seconds()) % 3600) // 60) if offset is not None else 0
        offset_sign = "+" if offset_h >= 0 else "-"
        offset_label = f"UTC{offset_sign}{abs(offset_h):02d}:{offset_m:02d}"
        rows.append({
            "label": label,
            "tz": tz,
            "time": t,
            "ampm": ampm,
            "is_day": _DAY_START <= hour_fraction < _DAY_END,
            "hour_fraction": round(hour_fraction, 3),
            "weekday": now.strftime("%a"),
            "date": now.strftime("%-d %b"),
            "offset": offset_label,
        })

    return {"rows": rows, "format": fmt, "day_start": _DAY_START, "day_end": _DAY_END}
