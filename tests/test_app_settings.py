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


def test_get_app_settings_masks_password(client: FlaskClient, tmp_path: Path) -> None:
    # Seed a stored settings file with a password
    store = AppSettingsStore(tmp_path / "data" / "core" / "settings.json")
    store.save(
        AppSettings(
            mqtt=MqttSettings(host="broker", password="hunter2"),
            base_url="http://x",
        )
    )
    body = client.get("/api/app/settings").get_json()
    assert body["mqtt"]["host"] == "broker"
    assert body["mqtt"]["password"] == "•••"


def test_put_app_settings_keeps_password_when_placeholder_sent(
    client: FlaskClient, tmp_path: Path
) -> None:
    store = AppSettingsStore(tmp_path / "data" / "core" / "settings.json")
    store.save(AppSettings(mqtt=MqttSettings(host="b1", password="hunter2")))

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
    store = AppSettingsStore(tmp_path / "data" / "core" / "settings.json")
    store.save(AppSettings(mqtt=MqttSettings(host="b1", password="old")))

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
    store = AppSettingsStore(tmp_path / "data" / "core" / "settings.json")
    store.save(AppSettings(panel=PanelSettings(model="impression_7_3", orientation="portrait")))

    client.put("/api/app/settings", json={"panel": {"orientation": "landscape"}})
    saved = json.loads((tmp_path / "data" / "core" / "settings.json").read_text())
    assert saved["panel"]["model"] == "impression_7_3"
    assert saved["panel"]["orientation"] == "landscape"


def test_put_panel_rejects_unknown_orientation(client: FlaskClient) -> None:
    res = client.put(
        "/api/app/settings", json={"panel": {"orientation": "diagonal"}}
    )
    assert res.status_code == 400
