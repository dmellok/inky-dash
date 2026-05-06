from __future__ import annotations

import json
import threading
from pathlib import Path


class WidgetSettings:
    """Persisted enable/disable state for plugins, keyed by plugin id.

    File format:
      {
        "plugin_id": { "enabled": false },
        ...
      }

    Plugins not present in the file are treated as enabled by default.
    """

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def load_state(self) -> dict[str, bool]:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return {
            k: bool(v.get("enabled", True))
            for k, v in (data or {}).items()
            if isinstance(v, dict)
        }

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        with self._lock:
            data: dict = {}
            if self.path.exists():
                try:
                    data = json.loads(self.path.read_text(encoding="utf-8")) or {}
                except Exception:
                    data = {}
            entry = data.get(plugin_id) if isinstance(data.get(plugin_id), dict) else {}
            entry["enabled"] = enabled
            data[plugin_id] = entry
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp.replace(self.path)
