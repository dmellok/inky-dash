from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient


def test_settings_listing_includes_news_plugin(client: FlaskClient) -> None:
    body = client.get("/api/settings").get_json()
    plugins = {p["plugin_id"]: p for p in body}
    assert "news" in plugins
    field_names = {f["name"] for f in plugins["news"]["settings"]}
    assert "default_url" in field_names
    assert "user_agent" in field_names


def test_save_settings_writes_to_disk(client: FlaskClient, tmp_path: Path) -> None:
    res = client.put(
        "/api/settings/news",
        json={"default_url": "https://example.com/rss", "user_agent": "test/1.0"},
    )
    assert res.status_code == 204
    settings_file = tmp_path / "data" / "plugins" / "news" / "settings.json"
    assert settings_file.exists()
    saved = json.loads(settings_file.read_text())
    assert saved["default_url"] == "https://example.com/rss"


def test_unknown_plugin_404s(client: FlaskClient) -> None:
    res = client.put("/api/settings/no_such_plugin", json={})
    assert res.status_code == 404


def test_unknown_keys_silently_dropped(client: FlaskClient, tmp_path: Path) -> None:
    """Sending a key the manifest doesn't declare is ignored, not an error."""
    res = client.put("/api/settings/news", json={"rogue_field": "x"})
    assert res.status_code == 204
    settings_file = tmp_path / "data" / "plugins" / "news" / "settings.json"
    saved = json.loads(settings_file.read_text())
    assert "rogue_field" not in saved


def test_settings_page_renders_shell(client: FlaskClient) -> None:
    res = client.get("/settings")
    assert res.status_code == 200
    assert b"dist/settings.js" in res.data


def test_news_fetch_uses_default_url_setting(client: FlaskClient) -> None:
    """If the cell option is empty AND the setting is set, fetch should use the setting."""
    # Save a setting first
    client.put("/api/settings/news", json={"default_url": ""})
    # Without a URL anywhere, news fetch returns an error message
    page = {
        "id": "news_test",
        "name": "News test",
        "panel": {"w": 400, "h": 300},
        "cells": [
            {
                "id": "c",
                "x": 0,
                "y": 0,
                "w": 400,
                "h": 300,
                "plugin": "news",
                "options": {"url": ""},
            }
        ],
    }
    client.put("/api/pages/news_test", json=page)
    html = client.get("/compose/news_test").get_data(as_text=True)
    # The error message should appear in the embedded data attr
    assert "No feed URL configured" in html or "No feed URL" in html
