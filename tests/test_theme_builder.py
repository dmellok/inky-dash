"""Theme builder API tests — POST + DELETE on /api/themes."""

from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient

GOOD_PALETTE = {
    "bg": "#222222",
    "surface": "#333333",
    "surface2": "#444444",
    "fg": "#eeeeee",
    "fgSoft": "#cccccc",
    "muted": "#888888",
    "accent": "#ff8844",
    "accentSoft": "#cc6633",
    "divider": "#555555",
    "danger": "#ff4444",
    "warn": "#ffcc44",
    "ok": "#44ff44",
}


def _theme_body(theme_id: str = "twilight") -> dict:
    return {
        "id": theme_id,
        "name": "Twilight",
        "mode": "dark",
        "palette": dict(GOOD_PALETTE),
    }


def test_create_user_theme_appears_in_listing(client: FlaskClient) -> None:
    res = client.post("/api/themes", json=_theme_body())
    assert res.status_code == 200
    body = res.get_json()
    assert body["id"] == "twilight"
    assert body["is_user"] is True

    listing = client.get("/api/themes").get_json()
    twilight = next((t for t in listing if t["id"] == "twilight"), None)
    assert twilight is not None
    assert twilight["is_user"] is True


def test_create_user_theme_persists_to_user_json(client: FlaskClient, tmp_path: Path) -> None:
    client.post("/api/themes", json=_theme_body("persistent"))
    user_json = tmp_path / "data" / "plugins" / "themes_core" / "user.json"
    assert user_json.exists()
    saved = json.loads(user_json.read_text())
    ids = [t["id"] for t in saved.get("themes", [])]
    assert "persistent" in ids


def test_create_rejects_clash_with_built_in_theme(client: FlaskClient) -> None:
    body = _theme_body("default")  # collides with the bundled default
    res = client.post("/api/themes", json=body)
    assert res.status_code == 409
    assert "built-in" in res.get_json()["error"]


def test_create_rejects_bad_hex_in_palette(client: FlaskClient) -> None:
    bad = _theme_body()
    bad["palette"]["bg"] = "not-a-hex"
    res = client.post("/api/themes", json=bad)
    assert res.status_code == 400


def test_create_rejects_missing_palette_keys(client: FlaskClient) -> None:
    bad = _theme_body()
    del bad["palette"]["accent"]
    res = client.post("/api/themes", json=bad)
    assert res.status_code == 400


def test_delete_user_theme(client: FlaskClient) -> None:
    client.post("/api/themes", json=_theme_body("delete-me"))
    res = client.delete("/api/themes/delete-me")
    assert res.status_code == 204
    listing = client.get("/api/themes").get_json()
    assert all(t["id"] != "delete-me" for t in listing)


def test_delete_built_in_theme_forbidden(client: FlaskClient) -> None:
    res = client.delete("/api/themes/default")
    assert res.status_code == 403


def test_delete_unknown_theme_404(client: FlaskClient) -> None:
    res = client.delete("/api/themes/never-existed")
    assert res.status_code == 404


def test_user_theme_can_be_used_by_a_page(client: FlaskClient) -> None:
    """A page that references a user-created theme should hydrate using its palette."""
    client.post("/api/themes", json=_theme_body("smoke-themed"))
    page = {
        "id": "themed-page",
        "name": "Themed",
        "panel": {"w": 400, "h": 300},
        "theme": "smoke-themed",
        "cells": [{"id": "c", "x": 0, "y": 0, "w": 400, "h": 300, "plugin": "clock"}],
    }
    client.put("/api/pages/themed-page", json=page)
    response = client.get("/compose/themed-page")
    assert response.status_code == 200
    # Twilight bg is #222222
    assert b"#222222" in response.data
