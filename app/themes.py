"""User-created theme persistence + validation.

Themes shipped with the ``themes_core`` plugin live in its ``plugin.json``;
themes the user creates from the /themes page live in
``data/plugins/themes_core/user.json`` (same shape as the manifest's themes
array). The plugin loader reads both at startup.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

REQUIRED_PALETTE_KEYS: frozenset[str] = frozenset(
    {
        "bg",
        "surface",
        "surface2",
        "fg",
        "fgSoft",
        "muted",
        "accent",
        "accentSoft",
        "divider",
        "danger",
        "warn",
        "ok",
    }
)
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class UserTheme(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    mode: Literal["light", "dark"] | None = None
    palette: dict[str, str]

    @field_validator("palette")
    @classmethod
    def _validate_palette(cls, value: dict[str, str]) -> dict[str, str]:
        keys = set(value.keys())
        missing = REQUIRED_PALETTE_KEYS - keys
        extra = keys - REQUIRED_PALETTE_KEYS
        if missing or extra:
            problems: list[str] = []
            if missing:
                problems.append(f"missing: {sorted(missing)}")
            if extra:
                problems.append(f"unexpected: {sorted(extra)}")
            raise ValueError(f"palette key set wrong — {'; '.join(problems)}")
        for key, color in value.items():
            if not _HEX_RE.match(color):
                raise ValueError(f"palette[{key}] must be #rrggbb, got {color!r}")
        return value


class UserThemeStore:
    """Atomic JSON-backed store of user-created themes."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[UserTheme]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return []
        raw_list = data.get("themes", []) if isinstance(data, dict) else []
        out: list[UserTheme] = []
        for raw in raw_list:
            try:
                out.append(UserTheme.model_validate(raw))
            except Exception:
                # Skip malformed entries silently — better than crashing the loader.
                continue
        return out

    def save(self, themes: list[UserTheme]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "themes": [t.model_dump(mode="json", exclude_none=True) for t in themes]
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2))
        os.replace(tmp, self.path)

    def upsert(self, theme: UserTheme) -> None:
        existing = self.load()
        existing = [t for t in existing if t.id != theme.id]
        existing.append(theme)
        self.save(existing)

    def remove(self, theme_id: str) -> bool:
        existing = self.load()
        kept = [t for t in existing if t.id != theme_id]
        if len(kept) == len(existing):
            return False
        self.save(kept)
        return True
