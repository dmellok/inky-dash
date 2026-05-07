"""Theme + font extraction by the plugin loader.

Asserts the bundled themes_core / fonts_core plugins load cleanly and that
the registry exposes them under their declared ids. Also exercises the
schema's strict palette validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.plugin_loader import discover

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "plugin.schema.json"


def _bundled_registry(tmp_path: Path):
    return discover(
        ROOT / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path,
    )


def test_themes_core_loads_at_least_12_themes(tmp_path: Path) -> None:
    registry = _bundled_registry(tmp_path)
    assert "themes_core" in registry.plugins
    assert len(registry.themes) >= 12
    assert "default" in registry.themes  # the convention every page falls back to


def test_themes_have_all_12_palette_keys(tmp_path: Path) -> None:
    required = {
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
    registry = _bundled_registry(tmp_path)
    for theme in registry.themes.values():
        assert set(theme.palette.keys()) == required, (
            f"theme {theme.id!r} palette keys {set(theme.palette.keys())!r}"
        )


def test_fonts_core_loads_default_inter(tmp_path: Path) -> None:
    registry = _bundled_registry(tmp_path)
    assert "fonts_core" in registry.plugins
    assert "default" in registry.fonts
    default_font = registry.fonts["default"]
    assert default_font.name == "Inter"
    # files map should resolve to /plugins/fonts_core/files/...
    for url in default_font.files.values():
        assert url.startswith("/plugins/fonts_core/files/")


def test_palette_with_bad_hex_rejected_by_schema(tmp_path: Path) -> None:
    bad_manifest: dict[str, Any] = {
        "manifest_version": 1,
        "id": "broken_themes",
        "name": "Broken",
        "version": "0.1.0",
        "kind": "theme",
        "supports": {"sizes": ["xs", "sm", "md", "lg"]},
        "themes": [
            {
                "id": "broken",
                "name": "Broken",
                "palette": {
                    "bg": "not-a-hex",
                    "surface": "#fff",
                    "surface2": "#ffffff",
                    "fg": "#000000",
                    "fgSoft": "#444444",
                    "muted": "#888888",
                    "accent": "#ff0000",
                    "accentSoft": "#aa0000",
                    "divider": "#dddddd",
                    "danger": "#cc0000",
                    "warn": "#cccc00",
                    "ok": "#00cc00",
                },
            }
        ],
    }
    plugins_dir = tmp_path / "plugins"
    folder = plugins_dir / "broken_themes"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps(bad_manifest))
    (folder / "client.js").write_text("export default function(){}")

    registry = discover(
        plugins_dir,
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "broken_themes" not in registry.plugins
    # jsonschema reports something like: "'not-a-hex' does not match '^#[0-9a-fA-F]{6}$'"
    assert any(
        "not-a-hex" in e.message or "match" in e.message.lower() or "pattern" in e.message.lower()
        for e in registry.errors
    )


def test_palette_missing_keys_rejected(tmp_path: Path) -> None:
    """A palette missing one of the 12 required keys must be rejected."""
    bad_manifest = {
        "manifest_version": 1,
        "id": "incomplete_themes",
        "name": "Incomplete",
        "version": "0.1.0",
        "kind": "theme",
        "supports": {"sizes": ["xs", "sm", "md", "lg"]},
        "themes": [
            {
                "id": "incomplete",
                "name": "Incomplete",
                "palette": {
                    "bg": "#ffffff",
                    "surface": "#ffffff",
                    # missing the other 10 keys
                },
            }
        ],
    }
    plugins_dir = tmp_path / "plugins"
    folder = plugins_dir / "incomplete_themes"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text(json.dumps(bad_manifest))
    (folder / "client.js").write_text("export default function(){}")

    registry = discover(
        plugins_dir,
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "incomplete_themes" not in registry.plugins


def test_admin_themes_route_renders_shell(client: Any) -> None:
    response = client.get("/themes")
    assert response.status_code == 200
    assert b"dist/themes.js" in response.data


def test_api_themes_returns_loaded_themes(client: Any) -> None:
    body = client.get("/api/themes").get_json()
    assert isinstance(body, list)
    ids = {t["id"] for t in body}
    assert "default" in ids
    assert "ember" in ids


def test_api_fonts_returns_loaded_fonts(client: Any) -> None:
    body = client.get("/api/fonts").get_json()
    ids = {f["id"] for f in body}
    assert "default" in ids
    assert "lexend" in ids


@pytest.mark.parametrize(
    "page_field,value",
    [
        ("theme", "ember"),
        ("font", "lora"),
    ],
)
def test_page_can_set_theme_and_font(client: Any, page_field: str, value: str) -> None:
    """The page model accepts theme + font ids; PUT round-trips them."""
    page = {
        "id": "themed",
        "name": "Themed",
        "panel": {"w": 400, "h": 300},
        "cells": [{"id": "c", "x": 0, "y": 0, "w": 400, "h": 300, "plugin": "clock"}],
        page_field: value,
    }
    response = client.put("/api/pages/themed", json=page)
    assert response.status_code == 200
    saved = response.get_json()
    assert saved[page_field] == value


def test_cell_can_override_theme_and_font(client: Any) -> None:
    page = {
        "id": "override",
        "name": "Override",
        "panel": {"w": 400, "h": 300},
        "theme": "default",
        "font": "default",
        "cells": [
            {
                "id": "c",
                "x": 0,
                "y": 0,
                "w": 400,
                "h": 300,
                "plugin": "clock",
                "theme": "ember",
                "font": "lora",
            }
        ],
    }
    response = client.put("/api/pages/override", json=page)
    assert response.status_code == 200
    saved = response.get_json()
    assert saved["cells"][0]["theme"] == "ember"
    assert saved["cells"][0]["font"] == "lora"


def test_compose_includes_resolved_palette_in_cell_data(client: Any) -> None:
    """The compose route serializes the resolved palette as a data attr."""
    response = client.get("/compose/_demo")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "data-theme-palette" in html
    assert "@font-face" in html  # font_face_css is emitted


def test_compose_cell_override_takes_priority(client: Any) -> None:
    page = {
        "id": "override_compose",
        "name": "Override compose",
        "panel": {"w": 400, "h": 300},
        "theme": "default",
        "font": "default",
        "cells": [
            {
                "id": "c",
                "x": 0,
                "y": 0,
                "w": 400,
                "h": 300,
                "plugin": "clock",
                "theme": "ember",
            }
        ],
    }
    client.put("/api/pages/override_compose", json=page)
    response = client.get("/compose/override_compose")
    html = response.get_data(as_text=True)
    # Ember's bg in plugins/themes_core/plugin.json is #1a1612
    assert "#1a1612" in html
