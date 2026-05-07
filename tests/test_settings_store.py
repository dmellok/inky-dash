from __future__ import annotations

from pathlib import Path

from app.state import SettingsStore


def test_empty_returns_dict(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    assert store.get("anything") == {}


def test_set_then_get_round_trips(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("news", {"default_url": "https://example.com/feed"})
    assert store.get("news") == {"default_url": "https://example.com/feed"}


def test_merge_keeps_unrelated_keys(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("news", {"default_url": "u1", "user_agent": "ua"})
    merged = store.merge("news", {"default_url": "u2"})
    assert merged == {"default_url": "u2", "user_agent": "ua"}
    assert store.get("news") == {"default_url": "u2", "user_agent": "ua"}


def test_atomic_write_no_tmp_left_behind(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path)
    store.set("news", {"k": "v"})
    expected = tmp_path / "news" / "settings.json"
    assert expected.exists()
    assert not expected.with_suffix(".json.tmp").exists()


def test_corrupt_file_returns_empty(tmp_path: Path) -> None:
    """Hand-edited or partially-written file shouldn't crash the loader."""
    path = tmp_path / "news" / "settings.json"
    path.parent.mkdir(parents=True)
    path.write_text("{ this is not json")
    store = SettingsStore(tmp_path)
    assert store.get("news") == {}
