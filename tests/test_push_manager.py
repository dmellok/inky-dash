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
    """Replace the renderer with a no-op returning fake bytes. Quantizing
    moved to the panel listener — the push pipeline only renders + (maybe)
    rotates now."""
    monkeypatch.setattr(push_module, "render_to_png", lambda req: FAKE_PNG)


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


def test_set_rotate_quarters_normalises_modulo_four(tmp_path: Path) -> None:
    manager, *_ = _make_manager(tmp_path)
    manager.set_rotate_quarters(5)
    assert manager._rotate_quarters == 1
    manager.set_rotate_quarters(-1)
    assert manager._rotate_quarters == 3
    manager.set_rotate_quarters(0)
    assert manager._rotate_quarters == 0


def test_landscape_rotation_actually_rotates_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: when rotate_quarters=1, the on-disk artifact has swapped dims."""
    import io

    from PIL import Image

    # Real renderer/quantizer would be slow; use a real (small, asymmetric) PNG
    # so the rotation can actually be observed dimensionally.
    src = Image.new("RGB", (40, 10), (200, 50, 50))
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    fake_render = buf.getvalue()
    monkeypatch.setattr(push_module, "render_to_png", lambda req: fake_render)

    bridge = FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=tmp_path / "renders",
        base_url="http://test:5555",
        rotate_quarters=1,
    )
    result = manager.push("_demo")
    assert result.status == "sent"
    artifact = tmp_path / "renders" / f"{result.digest}.png"
    out = Image.open(io.BytesIO(artifact.read_bytes()))
    assert out.size == (10, 40)  # rotated 90° from 40×10


def test_lru_eviction_drops_oldest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counter = [0]

    def unique_render(req: object) -> bytes:
        counter[0] += 1
        # Each render must produce different bytes so the SHA digests
        # differ → LRU has distinct artifacts to evict.
        return FAKE_PNG + f":{counter[0]}".encode()

    monkeypatch.setattr(push_module, "render_to_png", unique_render)

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
        # Disable the identical-push debounce so this LRU test can fire
        # five distinct synthetic renders back-to-back. The debounce is
        # exercised by its own dedicated test.
        debounce_seconds=0,
    )

    for _ in range(5):
        manager.push("_demo")
        time.sleep(0.01)  # ensure mtime ordering on coarse-grained filesystems

    surviving = sorted(renders.glob("*.png"))
    assert len(surviving) == 3


def test_identical_push_within_debounce_returns_busy(tmp_path: Path, fake_render: None) -> None:
    """Five rapid pushes of the same page collapse to one — the rest get
    ``status="busy"`` with a debounce error. Guards against runaway clients
    (e.g. a cross-tab Send race producing 5 pushes in 41 s)."""
    bridge = FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=tmp_path / "renders",
        base_url="http://test:5555",
        debounce_seconds=5,
    )
    results = [manager.push("_demo") for _ in range(5)]
    statuses = [r.status for r in results]
    assert statuses.count("sent") == 1
    assert statuses.count("busy") == 4
    # Only one MQTT publish ever happened.
    assert len(bridge.published) == 1


def test_debounce_lets_different_pages_through(tmp_path: Path, fake_render: None) -> None:
    """Debounce keys off page_id + options, so pushing page A then page B
    in quick succession should not block page B."""
    bridge = FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    page_store.upsert(
        Page(
            id="_other",
            name="Other",
            panel=Panel(w=400, h=300),
            cells=[Cell(id="c", x=0, y=0, w=400, h=300, plugin="clock")],
        )
    )
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=tmp_path / "renders",
        base_url="http://test:5555",
        debounce_seconds=5,
    )
    a = manager.push("_demo")
    b = manager.push("_other")
    assert a.status == "sent"
    assert b.status == "sent"


def test_debounce_window_expires(tmp_path: Path, fake_render: None) -> None:
    """After the window elapses, the same push goes through again."""
    bridge = FakeBridge()
    history = HistoryStore(tmp_path / "history.db")
    page_store = PageStore(tmp_path / "pages.json")
    _seed_demo(page_store)
    manager = PushManager(
        bridge=bridge,
        history=history,
        page_store=page_store,
        renders_dir=tmp_path / "renders",
        base_url="http://test:5555",
        debounce_seconds=0.05,
    )
    first = manager.push("_demo")
    blocked = manager.push("_demo")
    time.sleep(0.08)
    third = manager.push("_demo")
    assert first.status == "sent"
    assert blocked.status == "busy"
    assert third.status == "sent"
