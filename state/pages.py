from __future__ import annotations

import json
import threading
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

DEFAULT_BG = "#ffffff"
HEADER_HEIGHT_PX = 56  # multi-cell header strip


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float


# 7 fixed layouts — fractional rectangles in [0..1].
# Adding new layouts requires a code edit (deliberate; plugins don't extend this).
LAYOUTS: dict[str, list[Rect]] = {
    "single": [Rect(0.0, 0.0, 1.0, 1.0)],
    "stack_2": [
        Rect(0.0, 0.0, 1.0, 0.5),
        Rect(0.0, 0.5, 1.0, 0.5),
    ],
    "row_2": [
        Rect(0.0, 0.0, 0.5, 1.0),
        Rect(0.5, 0.0, 0.5, 1.0),
    ],
    "stack_3": [
        Rect(0.0, 0.0, 1.0, 1 / 3),
        Rect(0.0, 1 / 3, 1.0, 1 / 3),
        Rect(0.0, 2 / 3, 1.0, 1 / 3),
    ],
    "grid_2x2": [
        Rect(0.0, 0.0, 0.5, 0.5),
        Rect(0.5, 0.0, 0.5, 0.5),
        Rect(0.0, 0.5, 0.5, 0.5),
        Rect(0.5, 0.5, 0.5, 0.5),
    ],
    "hero_top_two_below": [
        Rect(0.0, 0.0, 1.0, 0.6),
        Rect(0.0, 0.6, 0.5, 0.4),
        Rect(0.5, 0.6, 0.5, 0.4),
    ],
    "hero_bottom_two_above": [
        Rect(0.0, 0.0, 0.5, 0.4),
        Rect(0.5, 0.0, 0.5, 0.4),
        Rect(0.0, 0.4, 1.0, 0.6),
    ],
}


def layout_cell_count(layout: str) -> int:
    return len(LAYOUTS.get(layout, LAYOUTS["single"]))


@dataclass
class Cell:
    widget: str
    options: dict[str, Any] = field(default_factory=dict)
    theme: str | None = None

    def to_json(self) -> dict:
        out: dict[str, Any] = {"widget": self.widget}
        if self.options:
            out["options"] = self.options
        if self.theme:
            out["theme"] = self.theme
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Cell":
        return cls(
            widget=data["widget"],
            options=dict(data.get("options") or {}),
            theme=data.get("theme") or None,
        )


@dataclass
class Page:
    id: str
    name: str
    layout: str = "single"
    cells: list[Cell] = field(default_factory=list)
    # Defaults for new pages constructed via Page(...) directly. Pages
    # loaded from JSON go through from_json() which preserves whatever was
    # written to disk (including explicit 0), so existing dashboards are
    # never silently restyled.
    cell_gap: int = 38
    cell_radius: int = 20
    bg_color: str = DEFAULT_BG
    icon: str | None = None
    header_theme: str | None = None
    theme: str | None = None
    font: str | None = None

    def to_json(self) -> dict:
        # Rule 7: omit empty optional fields.
        out: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "layout": self.layout,
            "cells": [c.to_json() for c in self.cells],
        }
        if self.cell_gap:
            out["cell_gap"] = self.cell_gap
        if self.cell_radius:
            out["cell_radius"] = self.cell_radius
        if self.bg_color and self.bg_color.lower() != DEFAULT_BG:
            out["bg_color"] = self.bg_color
        if self.icon:
            out["icon"] = self.icon
        if self.header_theme:
            out["header_theme"] = self.header_theme
        if self.theme:
            out["theme"] = self.theme
        if self.font:
            out["font"] = self.font
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Page":
        if "id" not in data or "name" not in data:
            raise ValueError("page requires id and name")
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            layout=str(data.get("layout") or "single"),
            cells=[Cell.from_json(c) for c in data.get("cells") or []],
            cell_gap=int(data.get("cell_gap") or 0),
            cell_radius=int(data.get("cell_radius") or 0),
            bg_color=str(data.get("bg_color") or DEFAULT_BG),
            icon=data.get("icon") or None,
            header_theme=data.get("header_theme") or None,
            theme=data.get("theme") or None,
            font=data.get("font") or None,
        )


class PageStore:
    """Disk-backed page list at data/pages.json."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._pages: list[Page] = []
        self.reload()

    def reload(self) -> None:
        with self._lock:
            self._pages = []
            if not self.path.exists():
                return
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                return
            for entry in raw.get("pages") or []:
                try:
                    self._pages.append(Page.from_json(entry))
                except Exception:
                    continue

    def _save_locked(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"version": 1, "pages": [p.to_json() for p in self._pages]}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(body, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def list(self) -> list[Page]:
        with self._lock:
            return list(self._pages)

    def get(self, page_id: str) -> Page | None:
        with self._lock:
            for p in self._pages:
                if p.id == page_id:
                    return p
            return None

    def upsert(self, page: Page) -> Page:
        with self._lock:
            for i, p in enumerate(self._pages):
                if p.id == page.id:
                    self._pages[i] = page
                    self._save_locked()
                    return page
            self._pages.append(page)
            self._save_locked()
            return page

    def delete(self, page_id: str) -> bool:
        with self._lock:
            before = len(self._pages)
            self._pages = [p for p in self._pages if p.id != page_id]
            if len(self._pages) == before:
                return False
            self._save_locked()
            return True

    def unique_slug(self, base: str, *, exclude: str | None = None) -> str:
        """Return a slug not already used by another page (optionally excluding one id)."""
        slug = slugify(base) or "page"
        with self._lock:
            taken = {p.id for p in self._pages if p.id != exclude}
        if slug not in taken:
            return slug
        i = 2
        while f"{slug}-{i}" in taken:
            i += 1
        return f"{slug}-{i}"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-")


class DraftStore:
    """In-memory transient drafts for the editor's iframe preview.
    Bounded by max_drafts; oldest evicted first.
    """

    def __init__(self, max_drafts: int = 16):
        self._lock = threading.Lock()
        self._drafts: OrderedDict[str, dict] = OrderedDict()
        self._max = max_drafts

    def put(self, page: dict) -> str:
        draft_id = token_urlsafe(8)
        with self._lock:
            self._drafts[draft_id] = page
            self._drafts.move_to_end(draft_id)
            while len(self._drafts) > self._max:
                self._drafts.popitem(last=False)
        return draft_id

    def get(self, draft_id: str) -> dict | None:
        with self._lock:
            return self._drafts.get(draft_id)
