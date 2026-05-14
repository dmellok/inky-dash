from __future__ import annotations

import json
from pathlib import Path

from flask.testing import FlaskClient

from app.state import (
    PANEL_MODELS,
    AppSettings,
    AppSettingsStore,
    MqttSettings,
    PanelSettings,
)


def test_app_settings_default(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")
    s = store.load()
    assert s.mqtt.host == ""
    assert s.mqtt.port == 1883
    assert s.base_url == "http://localhost:5555"


def test_app_settings_round_trip(tmp_path: Path) -> None:
    store = AppSettingsStore(tmp_path / "settings.json")
    s = AppSettings(
        mqtt=MqttSettings(host="broker.local", port=8883, username="me", password="secret"),
        base_url="http://192.168.1.10:5555",
    )
    store.save(s)
    loaded = store.load()
    assert loaded.mqtt.host == "broker.local"
    assert loaded.mqtt.password == "secret"
    assert loaded.base_url == "http://192.168.1.10:5555"


def test_corrupt_file_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ not json")
    store = AppSettingsStore(path)
    assert store.load().mqtt.host == ""


def _seed_settings_keeping_auth(tmp_path: Path, **kwargs: object) -> AppSettingsStore:
    """Helper: write app-settings while preserving the auth block the
    test fixture seeded (so the auth gate stays satisfied). Used by the
    handful of tests below that round-trip MQTT/base_url and would
    otherwise overwrite the password hash to "" and bounce to /setup."""
    store = AppSettingsStore(tmp_path / "data" / "core" / "settings.json")
    existing = store.load()
    settings = AppSettings(auth=existing.auth, **kwargs)  # type: ignore[arg-type]
    store.save(settings)
    return store


def test_get_app_settings_masks_password(client: FlaskClient, tmp_path: Path) -> None:
    _seed_settings_keeping_auth(
        tmp_path,
        mqtt=MqttSettings(host="broker", password="hunter2"),
        base_url="http://x",
    )
    body = client.get("/api/app/settings").get_json()
    assert body["mqtt"]["host"] == "broker"
    assert body["mqtt"]["password"] == "•••"


def test_put_app_settings_keeps_password_when_placeholder_sent(
    client: FlaskClient, tmp_path: Path
) -> None:
    _seed_settings_keeping_auth(tmp_path, mqtt=MqttSettings(host="b1", password="hunter2"))

    res = client.put(
        "/api/app/settings",
        json={"mqtt": {"host": "b2", "password": "•••"}},
    )
    assert res.status_code == 200
    saved = json.loads((tmp_path / "data" / "core" / "settings.json").read_text())
    # Password unchanged
    assert saved["mqtt"]["password"] == "hunter2"
    assert saved["mqtt"]["host"] == "b2"


def test_put_app_settings_changes_password_when_provided(
    client: FlaskClient, tmp_path: Path
) -> None:
    _seed_settings_keeping_auth(tmp_path, mqtt=MqttSettings(host="b1", password="old"))

    client.put("/api/app/settings", json={"mqtt": {"password": "new"}})
    saved = json.loads((tmp_path / "data" / "core" / "settings.json").read_text())
    assert saved["mqtt"]["password"] == "new"


def test_put_validation_rejects_bad_port(client: FlaskClient) -> None:
    res = client.put("/api/app/settings", json={"mqtt": {"port": -1}})
    assert res.status_code == 400


def test_put_settings_updates_push_manager_base_url(client: FlaskClient, app: object) -> None:
    client.put(
        "/api/app/settings",
        json={"base_url": "http://10.0.0.5:5555"},
    )
    pm = app.config["PUSH_MANAGER"]  # type: ignore[attr-defined]
    assert pm._base_url == "http://10.0.0.5:5555"


def test_panel_defaults() -> None:
    p = PanelSettings()
    assert p.model == "spectra_6_13_3"
    assert p.orientation == "landscape"
    # Default = landscape (matches panel's native) → no pre-send rotation.
    assert p.rotate_quarters() == 0
    # Composition viewport is the panel's native landscape dims.
    assert p.render_dimensions() == (1600, 1200)


def test_panel_portrait_rotates_quarter_turn() -> None:
    p = PanelSettings(model="impression_7_3", orientation="portrait")
    # CCW (3 ≡ -1 mod 4) so the rotated bytes land right-side-up on the
    # panel's landscape-native pixel grid.
    assert p.rotate_quarters() == 3
    # Portrait composes at swapped dims (short × long).
    assert p.render_dimensions() == (480, 800)


def test_panel_unknown_model_falls_back_to_default() -> None:
    p = PanelSettings(model="nonexistent")
    spec = p.spec()
    assert spec.width == 1600
    assert spec.height == 1200


def test_panel_models_catalog_has_all_impression_skus() -> None:
    expected = {
        "impression_4",
        "impression_5_7",
        "impression_7_3",
        "spectra_6_7_3",
        "spectra_6_13_3",
    }
    assert expected.issubset(set(PANEL_MODELS))


def test_list_panels_endpoint(client: FlaskClient) -> None:
    body = client.get("/api/app/panels").get_json()
    ids = {p["id"] for p in body}
    assert "impression_4" in ids
    assert "spectra_6_13_3" in ids
    one = next(p for p in body if p["id"] == "spectra_6_13_3")
    assert one["width"] == 1600
    assert one["height"] == 1200


def test_put_panel_orientation_updates_push_manager(client: FlaskClient, app: object) -> None:
    client.put(
        "/api/app/settings",
        json={"panel": {"orientation": "portrait"}},
    )
    pm = app.config["PUSH_MANAGER"]  # type: ignore[attr-defined]
    assert pm._rotate_quarters == 3
    # And landscape flips it back.
    client.put(
        "/api/app/settings",
        json={"panel": {"orientation": "landscape"}},
    )
    assert pm._rotate_quarters == 0


def test_put_panel_partial_update_preserves_model(client: FlaskClient, tmp_path: Path) -> None:
    """Sending just orientation must not reset the panel model to default."""
    _seed_settings_keeping_auth(
        tmp_path,
        panel=PanelSettings(model="impression_7_3", orientation="portrait"),
    )

    client.put("/api/app/settings", json={"panel": {"orientation": "landscape"}})
    saved = json.loads((tmp_path / "data" / "core" / "settings.json").read_text())
    assert saved["panel"]["model"] == "impression_7_3"
    assert saved["panel"]["orientation"] == "landscape"


def test_put_panel_rejects_unknown_orientation(client: FlaskClient) -> None:
    res = client.put("/api/app/settings", json={"panel": {"orientation": "diagonal"}})
    assert res.status_code == 400


def test_panel_model_change_resizes_existing_pages(client: FlaskClient, app: object) -> None:
    """Switching panel model rescales every dashboard so it matches the
    new resolution — cells stay in the same proportional spots."""
    # Start: default 13.3" landscape (1600×1200). Demo seeded at full bleed.
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "spectra_6_13_3", "orientation": "landscape"}},
    )
    before = client.get("/api/pages/_demo").get_json()
    assert before["panel"] == {"w": 1600, "h": 1200}
    # Switch to 7.3" landscape (800×480).
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "impression_7_3", "orientation": "landscape"}},
    )
    after = client.get("/api/pages/_demo").get_json()
    assert after["panel"] == {"w": 800, "h": 480}
    # Cells scaled proportionally (full-bleed cell stays full-bleed).
    full_bleed = after["cells"][0]
    assert full_bleed["x"] == 0 and full_bleed["y"] == 0
    assert full_bleed["w"] == 800 and full_bleed["h"] == 480


def test_panel_orientation_and_model_change_in_one_call(client: FlaskClient, app: object) -> None:
    """Combined orientation flip + model swap: rotate, then rescale."""
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "spectra_6_13_3", "orientation": "landscape"}},
    )
    # Demo at 1600×1200 landscape.
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "impression_7_3", "orientation": "portrait"}},
    )
    after = client.get("/api/pages/_demo").get_json()
    # 7.3" portrait is 480×800.
    assert after["panel"] == {"w": 480, "h": 800}
