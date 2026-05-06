from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any

from state.pages import slugify

VALID_KINDS = ("one_shot", "interval")
DEFAULT_COLOR = "#b85a3f"  # warm terracotta — overridable per schedule


@dataclass
class Schedule:
    id: str
    name: str
    kind: str
    target: dict[str, Any]
    enabled: bool = True
    color: str = DEFAULT_COLOR
    options: dict[str, Any] = field(default_factory=dict)

    # one_shot
    at: str | None = None  # ISO8601 local datetime, e.g. "2026-05-10T14:30:00"

    # interval
    every_minutes: int = 15
    start_time: str = "08:00"
    end_time: str = "20:00"
    days_of_week: list[int] = field(default_factory=list)  # ISO weekdays (Mon=0); empty = all days

    # state
    last_fired_at: str | None = None
    last_result: str | None = None  # "ok" | "error"
    last_error: str | None = None

    def to_json(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "target": self.target,
            "color": self.color,
        }
        if not self.enabled:
            out["enabled"] = False
        if self.options:
            out["options"] = self.options
        if self.kind == "one_shot":
            if self.at:
                out["at"] = self.at
        else:
            out["every_minutes"] = self.every_minutes
            out["start_time"] = self.start_time
            out["end_time"] = self.end_time
            if self.days_of_week:
                out["days_of_week"] = self.days_of_week
        if self.last_fired_at:
            out["last_fired_at"] = self.last_fired_at
        if self.last_result:
            out["last_result"] = self.last_result
        if self.last_error:
            out["last_error"] = self.last_error
        return out

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Schedule":
        if "id" not in data or "name" not in data:
            raise ValueError("schedule requires id and name")
        kind = data.get("kind", "interval")
        if kind not in VALID_KINDS:
            raise ValueError(f"kind must be one of {VALID_KINDS}, got {kind!r}")
        target = data.get("target") or {}
        if not isinstance(target, dict) or target.get("type") != "page" or not target.get("page_id"):
            raise ValueError("target must be {type:'page', page_id:'...'}")
        normalized_at: str | None = None
        if kind == "one_shot":
            at = data.get("at")
            if at:
                normalized_at = _normalize_at(at)
        else:
            for f in ("start_time", "end_time"):
                v = data.get(f, cls.__dataclass_fields__[f].default)
                _parse_hm(v)
            try:
                em = int(data.get("every_minutes", 15))
            except (TypeError, ValueError):
                raise ValueError("every_minutes must be an integer")
            if em <= 0:
                raise ValueError("every_minutes must be > 0")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            kind=kind,
            target=dict(target),
            enabled=bool(data.get("enabled", True)),
            color=str(data.get("color") or DEFAULT_COLOR),
            options=dict(data.get("options") or {}),
            at=normalized_at,
            every_minutes=int(data.get("every_minutes") or 15),
            start_time=str(data.get("start_time") or "08:00"),
            end_time=str(data.get("end_time") or "20:00"),
            days_of_week=list(data.get("days_of_week") or []),
            last_fired_at=data.get("last_fired_at") or None,
            last_result=data.get("last_result") or None,
            last_error=data.get("last_error") or None,
        )


def _parse_hm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


def _normalize_at(at: str) -> str:
    """Coerce a one-shot `at` value to HH:MM.

    The original v3 stored ISO datetimes like `2026-05-10T18:00:00`. The
    semantics changed to "fires daily at HH:MM" — only the time-of-day
    matters. We accept either form and normalize.
    """
    s = str(at).strip()
    if "T" in s:
        s = s.split("T", 1)[1]
    # Take the first 5 chars (HH:MM); strip any trailing seconds/timezone.
    hm = s[:5]
    h_str, _, m_str = hm.partition(":")
    h, m = int(h_str), int(m_str)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"at must be HH:MM, got {at!r}")
    return f"{h:02d}:{m:02d}"


class SchedulesStore:
    """Disk-backed schedule list at data/schedules.json."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._items: list[Schedule] = []
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self._items = []
            if not self.path.exists():
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return
            for entry in raw.get("schedules") or []:
                try:
                    self._items.append(Schedule.from_json(entry))
                except Exception:
                    continue

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"version": 1, "schedules": [s.to_json() for s in self._items]}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[Schedule]:
        with self._lock:
            return list(self._items)

    def get(self, sid: str) -> Schedule | None:
        with self._lock:
            for s in self._items:
                if s.id == sid:
                    return s
            return None

    def upsert(self, s: Schedule) -> Schedule:
        with self._lock:
            for i, existing in enumerate(self._items):
                if existing.id == s.id:
                    # Preserve last-fire state when callers don't supply it.
                    if not s.last_fired_at and existing.last_fired_at:
                        s.last_fired_at = existing.last_fired_at
                        s.last_result = existing.last_result
                        s.last_error = existing.last_error
                    self._items[i] = s
                    self._save_locked()
                    return s
            self._items.append(s)
            self._save_locked()
            return s

    def delete(self, sid: str) -> bool:
        with self._lock:
            before = len(self._items)
            self._items = [s for s in self._items if s.id != sid]
            if len(self._items) == before:
                return False
            self._save_locked()
            return True

    def reorder(self, ids: list[str]) -> None:
        """Reorder the schedule list to match the given id sequence.

        Schedules earlier in the list have priority — when several are due in
        the same scheduler tick the topmost one fires and the rest defer. Any
        ids not present in `_items` are dropped silently; any existing items
        absent from `ids` are appended at the end so a stale UI submission
        can't accidentally lose schedules.
        """
        with self._lock:
            by_id = {s.id: s for s in self._items}
            seen: set[str] = set()
            new_list: list[Schedule] = []
            for sid in ids:
                if sid in by_id and sid not in seen:
                    new_list.append(by_id[sid])
                    seen.add(sid)
            for s in self._items:
                if s.id not in seen:
                    new_list.append(s)
            self._items = new_list
            self._save_locked()

    def update_state(
        self,
        sid: str,
        *,
        last_fired_at: str | None = None,
        last_result: str | None = None,
        last_error: str | None = None,
    ) -> None:
        with self._lock:
            for s in self._items:
                if s.id == sid:
                    s.last_fired_at = last_fired_at
                    s.last_result = last_result
                    s.last_error = last_error
                    self._save_locked()
                    return

    def unique_slug(self, base: str, *, exclude: str | None = None) -> str:
        slug = slugify(base) or "schedule"
        with self._lock:
            taken = {s.id for s in self._items if s.id != exclude}
        if slug not in taken:
            return slug
        i = 2
        while f"{slug}-{i}" in taken:
            i += 1
        return f"{slug}-{i}"
