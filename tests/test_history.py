from __future__ import annotations

from pathlib import Path

from app.state import HistoryStore


def test_empty_returns_no_records(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    assert store.recent() == []


def test_record_then_recent_round_trips(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    new_id = store.record(
        page_id="_demo",
        digest="abc123",
        status="sent",
        duration_s=1.5,
        error=None,
        options={"rotate": 0, "scale": "fit", "bg": "white", "saturation": 0.5},
    )
    assert new_id > 0

    rows = store.recent()
    assert len(rows) == 1
    row = rows[0]
    assert row.page_id == "_demo"
    assert row.digest == "abc123"
    assert row.status == "sent"
    assert row.duration_s == 1.5
    assert row.options["scale"] == "fit"


def test_recent_returns_most_recent_first(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    for i in range(3):
        store.record(
            page_id=f"page-{i}",
            digest=None,
            status="sent",
            duration_s=0.1,
            error=None,
            options={},
        )
    rows = store.recent()
    assert [r.page_id for r in rows] == ["page-2", "page-1", "page-0"]


def test_limit_caps_results(tmp_path: Path) -> None:
    store = HistoryStore(tmp_path / "history.db")
    for i in range(5):
        store.record(
            page_id=f"p{i}",
            digest=None,
            status="sent",
            duration_s=0.0,
            error=None,
            options={},
        )
    assert len(store.recent(limit=2)) == 2
