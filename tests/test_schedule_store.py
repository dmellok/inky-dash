from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.state import Schedule, ScheduleStore


def _make(id_: str = "a", **kwargs) -> Schedule:
    base: dict = {
        "id": id_,
        "name": id_.title(),
        "page_id": "_demo",
        "type": "interval",
        "interval_minutes": 30,
    }
    base.update(kwargs)
    return Schedule.model_validate(base)


def test_empty_store(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json")
    assert store.all() == []
    assert store.get("anything") is None


def test_upsert_creates_then_updates(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json")
    store.upsert(_make("a", name="First"))
    assert store.get("a").name == "First"
    store.upsert(_make("a", name="Renamed"))
    assert [s.id for s in store.all()] == ["a"]
    assert store.get("a").name == "Renamed"


def test_oneshot_round_trip(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json")
    fires_at = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
    store.upsert(
        Schedule.model_validate(
            {
                "id": "once",
                "name": "Once",
                "page_id": "_demo",
                "type": "oneshot",
                "fires_at": fires_at,
            }
        )
    )
    loaded = store.get("once")
    assert loaded is not None
    assert loaded.type == "oneshot"
    assert loaded.fires_at == fires_at


def test_delete(tmp_path: Path) -> None:
    store = ScheduleStore(tmp_path / "schedules.json")
    store.upsert(_make("a"))
    assert store.delete("a") is True
    assert store.delete("a") is False
    assert store.all() == []


def test_malformed_entries_skipped(tmp_path: Path) -> None:
    """If user hand-edits the JSON and breaks one entry, others survive."""
    path = tmp_path / "schedules.json"
    path.write_text(
        '[{"id": "good", "name": "Good", "page_id": "_demo", '
        '"type": "interval", "interval_minutes": 60}, '
        '{"id": "bad", "type": "interval"}]'
    )
    store = ScheduleStore(path)
    ids = [s.id for s in store.all()]
    assert ids == ["good"]
