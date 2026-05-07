from __future__ import annotations

from pathlib import Path

from app.state import Cell, Page, PageStore, Panel


def _make_page(page_id: str, name: str = "X") -> Page:
    return Page(
        id=page_id,
        name=name,
        panel=Panel(w=1600, h=1200),
        cells=[Cell(id="c1", x=0, y=0, w=1600, h=1200, plugin="clock")],
    )


def test_empty_store_returns_no_pages(tmp_path: Path) -> None:
    store = PageStore(tmp_path / "pages.json")
    assert store.all() == []
    assert store.get("anything") is None


def test_upsert_creates_then_updates(tmp_path: Path) -> None:
    path = tmp_path / "pages.json"
    store = PageStore(path)

    store.upsert(_make_page("a", "First"))
    assert [p.id for p in store.all()] == ["a"]
    assert store.get("a").name == "First"

    store.upsert(_make_page("a", "Renamed"))
    assert [p.id for p in store.all()] == ["a"]
    assert store.get("a").name == "Renamed"

    store.upsert(_make_page("b", "B"))
    assert [p.id for p in store.all()] == ["a", "b"]


def test_delete(tmp_path: Path) -> None:
    store = PageStore(tmp_path / "pages.json")
    store.upsert(_make_page("a"))
    store.upsert(_make_page("b"))

    assert store.delete("a") is True
    assert [p.id for p in store.all()] == ["b"]
    assert store.delete("a") is False  # already gone


def test_atomic_write_no_tmp_left_behind(tmp_path: Path) -> None:
    path = tmp_path / "pages.json"
    store = PageStore(path)
    store.upsert(_make_page("a"))
    assert path.exists()
    assert not (tmp_path / "pages.json.tmp").exists()
