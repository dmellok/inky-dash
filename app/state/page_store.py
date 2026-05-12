"""Atomic JSON file storage for pages.

Pages live in ``data/core/pages.json`` as a JSON array. The store loads on
demand (so external edits to the file are picked up next read) and writes
atomically via tmp-rename so a crash mid-write can't corrupt the file.

mypy --strict applies via re-export through ``app.state``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.state.page_model import Page

logger = logging.getLogger(__name__)


class PageStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        # Change listeners — invoked after a successful upsert or delete so
        # downstream services (HA discovery) can republish per-page entities.
        # Listener exceptions are logged + swallowed; they can't block a save.
        self._listener_lock = threading.Lock()
        self._listeners: list[Callable[[], None]] = []

    def _load_raw(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text())
        if not isinstance(data, list):
            raise ValueError(f"{self.path} must contain a JSON array of pages")
        return [d for d in data if isinstance(d, dict)]

    def _save_raw(self, raw: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(raw, indent=2, sort_keys=False))
        os.replace(tmp, self.path)

    def all(self) -> list[Page]:
        return [Page.model_validate(d) for d in self._load_raw()]

    def get(self, page_id: str) -> Page | None:
        for record in self._load_raw():
            if record.get("id") == page_id:
                return Page.model_validate(record)
        return None

    def upsert(self, page: Page) -> None:
        raw = self._load_raw()
        # exclude_none keeps optional fields (cell.theme/font) out of JSON when
        # unset, so the saved file matches the schema (which rejects null).
        new_record = page.model_dump(mode="json", exclude_none=True)
        for index, existing in enumerate(raw):
            if existing.get("id") == page.id:
                raw[index] = new_record
                break
        else:
            raw.append(new_record)
        self._save_raw(raw)
        self._notify()

    def delete(self, page_id: str) -> bool:
        raw = self._load_raw()
        kept = [d for d in raw if d.get("id") != page_id]
        if len(kept) == len(raw):
            return False
        self._save_raw(kept)
        self._notify()
        return True

    # -- Change listeners -------------------------------------------------

    def add_listener(self, callback: Callable[[], None]) -> None:
        """Register a function to be called after every page upsert/delete."""
        with self._listener_lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[], None]) -> None:
        with self._listener_lock, contextlib.suppress(ValueError):
            self._listeners.remove(callback)

    def _notify(self) -> None:
        with self._listener_lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb()
            except Exception:  # noqa: BLE001
                logger.exception("PageStore listener %r raised", cb)
