"""Habits widget — GitHub-style contribution grid for a single habit.

State lives in `data/habits.json` — one entry per habit, each storing a
sorted list of YYYY-MM-DD date strings on which the habit was checked.
The admin page lets the user create habits and toggle today (or any past
day). The widget renders the last ~26 weeks as a 7×N grid, current week
on the right.

Schema (data/habits.json):
  {
    "habit_id": {
      "id": "habit_id",
      "name": "Daily walk",
      "icon": "ph-footprints",
      "color": "accent",            // "accent" | "ok" | "warn" | "danger"
      "dates": ["2026-05-01", ...]
    },
    ...
  }
"""
from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, render_template, request


_lock = threading.Lock()
_VALID_COLOR = {"accent", "ok", "warn", "danger"}
_PHOSPHOR_RE = re.compile(r"^ph-[a-z0-9-]+$")


def _path() -> Path:
    return current_app.config["INKY"].data_dir / "habits.json"


def _load() -> dict[str, dict]:
    p = _path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(habits: dict[str, dict]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(habits, indent=2), encoding="utf-8")
    tmp.replace(p)


def _normalize(habit: dict) -> dict:
    """Drop bad date strings, sort, dedupe — keeps the file tidy on save."""
    seen: set[str] = set()
    out: list[str] = []
    for d in habit.get("dates") or []:
        if not isinstance(d, str):
            continue
        try:
            date.fromisoformat(d)
        except ValueError:
            continue
        if d in seen:
            continue
        seen.add(d)
        out.append(d)
    out.sort()
    habit["dates"] = out
    if habit.get("color") not in _VALID_COLOR:
        habit["color"] = "accent"
    if not _PHOSPHOR_RE.match(str(habit.get("icon") or "")):
        habit["icon"] = "ph-check-square"
    return habit


# ---------- choice provider ----------------------------------------------


def choices(name: str):
    if name != "habits":
        return []
    with _lock:
        habits = _load()
    return [
        {"value": hid, "label": h.get("name") or hid}
        for hid, h in habits.items()
    ]


# ---------- widget fetch -------------------------------------------------


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    hid = (options.get("habit") or "").strip()
    if not hid:
        return {"error": "no habit selected — pick one in the cell options"}
    with _lock:
        habits = _load()
        habit = habits.get(hid)
    if not habit:
        return {"error": f"habit '{hid}' not found"}

    today = date.today()
    # Build a 26-week window ending on today's week. Week column 0 = oldest.
    weeks = 26
    # Find the Monday of the oldest week we want to show.
    today_iso_mon = today - timedelta(days=today.weekday())
    start_mon = today_iso_mon - timedelta(weeks=weeks - 1)
    dates_set = set(habit.get("dates") or [])
    grid: list[list[dict]] = []  # grid[col=week][row=dow]
    for w in range(weeks):
        col_start = start_mon + timedelta(weeks=w)
        column: list[dict] = []
        for dow in range(7):
            day = col_start + timedelta(days=dow)
            in_future = day > today
            done = day.isoformat() in dates_set
            column.append({
                "iso": day.isoformat(),
                "done": done,
                "future": in_future,
            })
        grid.append(column)

    # Current streak — count back from today through consecutive days.
    streak = 0
    cur = today
    while cur.isoformat() in dates_set:
        streak += 1
        cur -= timedelta(days=1)
    # Best streak across whole history.
    best = 0
    run = 0
    prev_day: date | None = None
    for d_str in habit.get("dates") or []:
        try:
            day = date.fromisoformat(d_str)
        except ValueError:
            continue
        if prev_day is not None and (day - prev_day).days == 1:
            run += 1
        else:
            run = 1
        best = max(best, run)
        prev_day = day

    last_30 = [d for d in habit.get("dates") or [] if d >= (today - timedelta(days=30)).isoformat()]
    return {
        "id": habit.get("id") or hid,
        "name": habit.get("name") or hid,
        "icon": habit.get("icon") or "ph-check-square",
        "color": habit.get("color") or "accent",
        "grid": grid,
        "today_iso": today.isoformat(),
        "streak": streak,
        "best": best,
        "last_30": len(last_30),
        "total": len(habit.get("dates") or []),
        "weeks": weeks,
    }


# ---------- admin blueprint ----------------------------------------------


def blueprint():
    bp = Blueprint("habits", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        return render_template("habits/admin.html")

    @bp.get("/api/habits")
    def api_list():
        with _lock:
            habits = _load()
        out = []
        today = date.today()
        for hid, h in habits.items():
            dates_set = set(h.get("dates") or [])
            streak = 0
            cur = today
            while cur.isoformat() in dates_set:
                streak += 1
                cur -= timedelta(days=1)
            out.append({
                "id": hid,
                "name": h.get("name", hid),
                "icon": h.get("icon", "ph-check-square"),
                "color": h.get("color", "accent"),
                "today_done": today.isoformat() in dates_set,
                "streak": streak,
                "total": len(dates_set),
            })
        return jsonify({"habits": out})

    @bp.post("/api/habits")
    def api_create():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        icon = (body.get("icon") or "ph-check-square").strip()
        if not _PHOSPHOR_RE.match(icon):
            return jsonify({"error": "icon must be a Phosphor name like ph-check-square"}), 400
        color = (body.get("color") or "accent").strip()
        if color not in _VALID_COLOR:
            return jsonify({"error": f"color must be one of {sorted(_VALID_COLOR)}"}), 400
        with _lock:
            habits = _load()
            hid = body.get("id") or uuid.uuid4().hex[:8]
            habits[hid] = _normalize({
                "id": hid,
                "name": name,
                "icon": icon,
                "color": color,
                "dates": [],
            })
            _save(habits)
        return jsonify(habits[hid]), 201

    @bp.put("/api/habits/<hid>")
    def api_update(hid):
        body = request.get_json(silent=True) or {}
        with _lock:
            habits = _load()
            if hid not in habits:
                abort(404)
            habit = habits[hid]
            if "name" in body:
                name = (body["name"] or "").strip()
                if not name:
                    return jsonify({"error": "name cannot be empty"}), 400
                habit["name"] = name
            if "icon" in body and _PHOSPHOR_RE.match(body["icon"] or ""):
                habit["icon"] = body["icon"]
            if "color" in body and body["color"] in _VALID_COLOR:
                habit["color"] = body["color"]
            habits[hid] = _normalize(habit)
            _save(habits)
        return jsonify(habits[hid])

    @bp.delete("/api/habits/<hid>")
    def api_delete(hid):
        with _lock:
            habits = _load()
            if hid not in habits:
                abort(404)
            del habits[hid]
            _save(habits)
        return ("", 204)

    @bp.post("/api/habits/<hid>/toggle")
    def api_toggle(hid):
        body = request.get_json(silent=True) or {}
        day = (body.get("date") or date.today().isoformat()).strip()
        try:
            date.fromisoformat(day)
        except ValueError:
            return jsonify({"error": "date must be YYYY-MM-DD"}), 400
        with _lock:
            habits = _load()
            if hid not in habits:
                abort(404)
            habit = habits[hid]
            dates = list(habit.get("dates") or [])
            if day in dates:
                dates.remove(day)
                done = False
            else:
                dates.append(day)
                done = True
            habit["dates"] = dates
            habits[hid] = _normalize(habit)
            _save(habits)
        return jsonify({"id": hid, "date": day, "done": done})

    return bp
