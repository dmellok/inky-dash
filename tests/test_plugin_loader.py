from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.plugin_loader import discover

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "plugin.schema.json"


def _write_plugin(
    folder: Path, manifest: dict[str, Any], *, client_js: str = "export default function(){}"
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "plugin.json").write_text(json.dumps(manifest))
    (folder / "client.js").write_text(client_js)


VALID_MANIFEST: dict[str, Any] = {
    "manifest_version": 1,
    "id": "demo",
    "name": "Demo",
    "version": "0.1.0",
    "kind": "widget",
    "supports": {"sizes": ["xs", "sm", "md", "lg"]},
}


def test_discovers_valid_plugin(tmp_path: Path) -> None:
    _write_plugin(tmp_path / "plugins" / "demo", VALID_MANIFEST)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" in registry.plugins
    assert registry.errors == []
    assert (tmp_path / "data" / "demo").is_dir()


def test_rejects_missing_manifest_version(tmp_path: Path) -> None:
    bad = {**VALID_MANIFEST}
    del bad["manifest_version"]
    _write_plugin(tmp_path / "plugins" / "demo", bad)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" not in registry.plugins
    assert any("manifest_version" in e.message for e in registry.errors)


def test_rejects_unknown_manifest_version(tmp_path: Path) -> None:
    bad = {**VALID_MANIFEST, "manifest_version": 99}
    _write_plugin(tmp_path / "plugins" / "demo", bad)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" not in registry.plugins
    assert any("99" in e.message for e in registry.errors)


def test_rejects_invalid_schema(tmp_path: Path) -> None:
    bad = {**VALID_MANIFEST, "kind": "invalid_kind"}
    _write_plugin(tmp_path / "plugins" / "demo", bad)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" not in registry.plugins
    assert any("kind" in e.message for e in registry.errors)


def test_rejects_id_folder_mismatch(tmp_path: Path) -> None:
    _write_plugin(tmp_path / "plugins" / "wrong_folder", VALID_MANIFEST)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" not in registry.plugins
    assert any("does not match folder name" in e.message for e in registry.errors)


def test_rejects_invalid_json(tmp_path: Path) -> None:
    folder = tmp_path / "plugins" / "demo"
    folder.mkdir(parents=True)
    (folder / "plugin.json").write_text("{ not valid json")
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert "demo" not in registry.plugins
    assert any("invalid JSON" in e.message for e in registry.errors)


def test_skips_hidden_and_underscored_dirs(tmp_path: Path) -> None:
    _write_plugin(tmp_path / "plugins" / "_template", VALID_MANIFEST)
    _write_plugin(tmp_path / "plugins" / ".hidden", VALID_MANIFEST)
    registry = discover(
        tmp_path / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=tmp_path / "data",
    )
    assert registry.plugins == {}
    assert registry.errors == []


def test_cell_option_defaults_merged() -> None:
    from app.plugin_loader import Plugin

    plugin = Plugin(
        id="demo",
        path=Path("/dev/null"),
        manifest={
            **VALID_MANIFEST,
            "cell_options": [
                {"name": "format", "type": "select", "label": "fmt", "default": "24h"},
                {"name": "show_seconds", "type": "boolean", "label": "sec", "default": False},
                {"name": "no_default", "type": "string", "label": "nd"},
            ],
        },
        data_dir=Path("/dev/null"),
    )
    assert plugin.cell_option_defaults() == {"format": "24h", "show_seconds": False}


def test_clock_plugin_loads_from_real_dir() -> None:
    """End-to-end: the bundled clock plugin loads cleanly against the real schema."""
    registry = discover(
        ROOT / "plugins",
        schema_path=SCHEMA_PATH,
        data_root=ROOT / "data" / "_test_plugins",
    )
    assert "clock" in registry.plugins, registry.errors
    assert registry.errors == []
    clock = registry.plugins["clock"]
    assert clock.kind == "widget"
    assert clock.supported_sizes == ["xs", "sm", "md", "lg"]


@pytest.fixture(autouse=True)
def _cleanup_test_data_dir() -> Any:
    yield
    test_dir = ROOT / "data" / "_test_plugins"
    if test_dir.exists():
        import shutil

        shutil.rmtree(test_dir, ignore_errors=True)
