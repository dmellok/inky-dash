"""Per-plugin settings persistence.

Each plugin's manifest may declare a ``settings`` array of typed fields with
``secret: true`` markers. Values land in
``data/plugins/<plugin_id>/settings.json`` — the same dir the plugin loader
hands the plugin as ``ctx.data_dir``. The composer reads the dict from this
store and passes it to ``server.py fetch()``.

Secrets aren't masked at this layer; that's the API's job (don't leak
``secret: true`` values out of GET /api/settings).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class SettingsStore:
    """Reads/writes per-plugin settings under ``base_dir/<plugin_id>/settings.json``."""

    FILENAME = "settings.json"

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def _path(self, plugin_id: str) -> Path:
        return self.base_dir / plugin_id / self.FILENAME

    def get(self, plugin_id: str) -> dict[str, Any]:
        path = self._path(plugin_id)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def set(self, plugin_id: str, settings: dict[str, Any]) -> None:
        path = self._path(plugin_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(settings, indent=2, sort_keys=True))
        os.replace(tmp, path)

    def merge(self, plugin_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Apply partial updates on top of existing values; returns the merged dict."""
        existing = self.get(plugin_id)
        existing.update(updates)
        self.set(plugin_id, existing)
        return existing
