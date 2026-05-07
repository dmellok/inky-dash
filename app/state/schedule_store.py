"""Atomic JSON file storage for schedules. Same pattern as PageStore."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.state.schedule_model import Schedule


class ScheduleStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [d for d in data if isinstance(d, dict)]

    def _save_raw(self, raw: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(raw, indent=2, default=str))
        os.replace(tmp, self.path)

    def all(self) -> list[Schedule]:
        out: list[Schedule] = []
        for d in self._load_raw():
            try:
                out.append(Schedule.model_validate(d))
            except Exception:
                continue
        return out

    def get(self, schedule_id: str) -> Schedule | None:
        for s in self.all():
            if s.id == schedule_id:
                return s
        return None

    def upsert(self, schedule: Schedule) -> None:
        raw = self._load_raw()
        record = schedule.model_dump(mode="json", exclude_none=True)
        for i, existing in enumerate(raw):
            if existing.get("id") == schedule.id:
                raw[i] = record
                break
        else:
            raw.append(record)
        self._save_raw(raw)

    def delete(self, schedule_id: str) -> bool:
        raw = self._load_raw()
        kept = [d for d in raw if d.get("id") != schedule_id]
        if len(kept) == len(raw):
            return False
        self._save_raw(kept)
        return True
