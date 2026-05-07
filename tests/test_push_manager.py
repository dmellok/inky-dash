"""PushManager unit tests.

Exercise the manager directly with fake renderer/quantizer/bridge so tests
are fast (no Chromium, no broker) and deterministic.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from app import push as push_module
from app.push import VALID_BGS, VALID_ROTATIONS, PushManager, PushOptions
from app.state import HistoryStore, Page, PageStore, Panel
from app.state.page_model import Cell

from ._helpers import FakeBridge

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def fake_render(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the renderer/quantizer with no-op functions returning fake bytes."""
    monkeypatch.setattr(push_module, "render_to_png", lambda req: b"raw" + FAKE_PNG)
    monkeypatch.setattr(
        push_module, "quantize_to_png", lambda src, *, dither: FAKE_PNG + dither.encode()
    )


def _seed_demo(page_store: PageStore) -> None:
    page_store.upsert(
        Page(
            id="_demo",
            name="Demo",
            panel=Panel(w=400, h=300),
            cells=[Cell(id="c", x=0, y=0, w=400, h=300, plugin="clock")],
        )
    )


def _make_manager(
    tmp_path: Path, bridge: FakeBridge | None = None
) -> tuple[PushManager, FakeBridge, HistoryStore, PageStore, Path]:
    bridge = bridge or FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    renders = tmp_path / "renders"
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=renders,
        base_url="http://test:5555",
    )
    return manager, bridge, history, page_store, renders


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rotate": 45},
        {"scale": "weird"},
        {"bg": "purple"},
        {"saturation": -0.1},
        {"saturation": 1.5},
    ],
)
def test_push_options_rejects_invalid(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        PushOptions(**kwargs)  # type: ignore[arg-type]


def test_push_options_defaults_match_brief() -> None:
    opts = PushOptions()
    assert opts.rotate == 0
    assert opts.scale == "fit"
    assert opts.bg == "white"
    assert opts.saturation == 0.5
    assert 0 in VALID_ROTATIONS
    assert "white" in VALID_BGS


def test_successful_push_publishes_correct_payload(tmp_path: Path, fake_render: None) -> None:
    manager, bridge, history, _, renders = _make_manager(tmp_path)
    result = manager.push("_demo")

    assert result.status == "sent"
    assert result.digest is not None
    assert result.url == f"http://test:5555/renders/{result.digest}.png"

    assert len(bridge.published) == 1
    pub = bridge.published[0]
    assert pub["topic"] == "inky/update"
    assert pub["qos"] == 1
    assert pub["retain"] is False
    payload = json.loads(pub["payload"])
    assert payload == {
        "url": result.url,
        "rotate": 0,
        "scale": "fit",
        "bg": "white",
        "saturation": 0.5,
    }

    artifact = renders / f"{result.digest}.png"
    assert artifact.exists()

    rows = history.recent()
    assert len(rows) == 1
    assert rows[0].status == "sent"
    assert rows[0].digest == result.digest


def test_unknown_page_returns_not_found_and_records_history(
    tmp_path: Path, fake_render: None
) -> None:
    manager, bridge, history, _, _ = _make_manager(tmp_path)
    result = manager.push("does-not-exist")
    assert result.status == "not_found"
    assert bridge.published == []
    assert history.recent()[0].status == "not_found"


def test_bridge_failure_records_failed(tmp_path: Path, fake_render: None) -> None:
    bridge = FakeBridge(raise_on_publish=RuntimeError("broker down"))
    manager, _, history, _, _ = _make_manager(tmp_path, bridge=bridge)
    result = manager.push("_demo")
    assert result.status == "failed"
    assert "broker down" in (result.error or "")
    assert history.recent()[0].status == "failed"


def test_concurrent_push_returns_busy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the push lock from inside fake_render to simulate a long-running push,
    then dispatch a second push from another thread; it should return busy."""
    started = threading.Event()
    release = threading.Event()

    def slow_render(req: object) -> bytes:
        started.set()
        release.wait(timeout=2)
        return b"raw"

    monkeypatch.setattr(push_module, "render_to_png", slow_render)
    monkeypatch.setattr(push_module, "quantize_to_png", lambda src, *, dither: FAKE_PNG)

    manager, _, _, _, _ = _make_manager(tmp_path)

    first_result: list[object] = []

    def first() -> None:
        first_result.append(manager.push("_demo"))

    t = threading.Thread(target=first)
    t.start()
    assert started.wait(timeout=2)

    second = manager.push("_demo")
    assert second.status == "busy"

    release.set()
    t.join(timeout=3)
    assert getattr(first_result[0], "status", None) == "sent"


def test_lru_eviction_drops_oldest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = [0]

    def unique_quantize(src: object, *, dither: str) -> bytes:
        counter[0] += 1
        return FAKE_PNG + f":{counter[0]}".encode()

    monkeypatch.setattr(push_module, "render_to_png", lambda req: FAKE_PNG)
    monkeypatch.setattr(push_module, "quantize_to_png", unique_quantize)

    bridge = FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    renders = tmp_path / "renders"
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=renders,
        base_url="http://test:5555",
        renders_cap=3,
    )

    for _ in range(5):
        manager.push("_demo")
        time.sleep(0.01)  # ensure mtime ordering on coarse-grained filesystems

    surviving = sorted(renders.glob("*.png"))
    assert len(surviving) == 3
