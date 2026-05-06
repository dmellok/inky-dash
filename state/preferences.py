"""Lightweight UI preferences store.

Holds non-sensitive global preferences that don't belong in .env (because
they're hot-tunable from admin UIs without restart). Currently just the
default font; add fields here as more are needed.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path


class Preferences:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def get_default_font(self) -> str | None:
        with self._lock:
            v = self._read().get("default_font")
        return v if isinstance(v, str) and v else None

    def set_default_font(self, font_id: str | None) -> None:
        with self._lock:
            data = self._read()
            if font_id:
                data["default_font"] = font_id
            else:
                data.pop("default_font", None)
            self._write(data)

    def get_font_weight(self) -> int:
        """Page-wide font weight applied to body. 400 (Regular) is the
        default — anything else gets emitted as a CSS rule by the composer
        so widgets that don't override font-weight pick it up."""
        with self._lock:
            v = self._read().get("font_weight")
        try:
            n = int(v) if v is not None else 400
        except (TypeError, ValueError):
            return 400
        # CSS weights only allow 100..900 in 100-step increments.
        if n < 100 or n > 900:
            return 400
        return (n // 100) * 100

    def set_font_weight(self, weight: int | None) -> None:
        with self._lock:
            data = self._read()
            if weight in (None, 400):
                data.pop("font_weight", None)
            else:
                data["font_weight"] = int(weight)
            self._write(data)
