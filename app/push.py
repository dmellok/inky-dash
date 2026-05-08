"""Single-flight push pipeline: render → quantize → write artifact → publish.

The MQTT wire format is frozen (v4-brief §"MQTT contract"). This module
constructs valid payloads, persists each render as a content-addressed PNG
under ``data/core/renders/``, and records every attempt in the history.

Concurrency: one push at a time. Concurrent attempts return ``status="busy"``
rather than queuing — keeps the model simple and the UI honest about what's
happening.

mypy --strict applies to this module per v4-brief §6.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.mqtt_bridge import MqttBridge
from app.quantizer import DitherMode, rotate_png
from app.renderer import RenderRequest, render_to_png
from app.state.history import HistoryStore
from app.state.page_store import PageStore

logger = logging.getLogger(__name__)


VALID_ROTATIONS: frozenset[int] = frozenset({0, 90, 180, 270})
VALID_SCALES: frozenset[str] = frozenset({"fit", "fill", "stretch", "center"})
VALID_BGS: frozenset[str] = frozenset(
    {"black", "white", "red", "green", "blue", "yellow", "orange"}
)
VALID_DITHERS: frozenset[str] = frozenset({"floyd-steinberg", "none"})


@dataclass(frozen=True)
class PushOptions:
    rotate: int = 0
    scale: str = "fit"
    bg: str = "white"
    saturation: float = 0.5

    def __post_init__(self) -> None:
        if self.rotate not in VALID_ROTATIONS:
            raise ValueError(
                f"rotate must be one of {sorted(VALID_ROTATIONS)}, got {self.rotate!r}"
            )
        if self.scale not in VALID_SCALES:
            raise ValueError(f"scale must be one of {sorted(VALID_SCALES)}, got {self.scale!r}")
        if self.bg not in VALID_BGS:
            raise ValueError(f"bg must be one of {sorted(VALID_BGS)}, got {self.bg!r}")
        if not 0.0 <= self.saturation <= 1.0:
            raise ValueError(f"saturation must be in [0.0, 1.0], got {self.saturation!r}")


@dataclass(frozen=True)
class PushResult:
    status: Literal["sent", "busy", "failed", "not_found"]
    digest: str | None = None
    url: str | None = None
    duration_s: float = 0.0
    error: str | None = None
    history_id: int | None = None
    options: dict[str, float | int | str] = field(default_factory=dict)


class PushManager:
    def __init__(
        self,
        *,
        bridge: MqttBridge,
        history: HistoryStore,
        page_store: PageStore,
        renders_dir: Path,
        base_url: str,
        topic: str = "inky/update",
        renders_cap: int = 500,
        rotate_quarters: int = 0,
    ) -> None:
        self._bridge = bridge
        self._history = history
        self._page_store = page_store
        self._renders_dir = renders_dir
        self._renders_dir.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")
        self._topic = topic
        self._renders_cap = renders_cap
        self._rotate_quarters = rotate_quarters % 4
        self._lock = threading.Lock()

    def push(
        self,
        page_id: str,
        *,
        options: PushOptions | None = None,
        dither: DitherMode = "floyd-steinberg",
    ) -> PushResult:
        opts = options or PushOptions()
        if dither not in VALID_DITHERS:
            raise ValueError(f"dither must be one of {sorted(VALID_DITHERS)}, got {dither!r}")

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            return self._push_locked(page_id, opts, dither)
        finally:
            self._lock.release()

    def _push_locked(self, page_id: str, opts: PushOptions, dither: DitherMode) -> PushResult:
        started = time.monotonic()
        page = self._page_store.get(page_id)
        if page is None:
            history_id = self._history.record(
                page_id=page_id,
                digest=None,
                status="not_found",
                duration_s=0.0,
                error="page not found",
                options=asdict(opts),
            )
            return PushResult(
                status="not_found",
                error="page not found",
                history_id=history_id,
                options=asdict(opts),
            )

        compose_url = f"{self._base_url}/compose/{page_id}?for_push=1"
        try:
            raw = render_to_png(
                RenderRequest(
                    url=compose_url,
                    viewport_w=page.panel.w,
                    viewport_h=page.panel.h,
                )
            )
            # Wire format: full-color render, post-rotation. The panel
            # listener owns gamut quantization (it knows the actual ink
            # primaries for its hardware). Dither argument is preserved on
            # the API for backward-compat but is a no-op for the bytes —
            # the listener decides how to dither.
            quantized = rotate_png(raw, quarters=self._rotate_quarters)
        except Exception as err:  # noqa: BLE001 — surface any renderer failure
            duration = time.monotonic() - started
            history_id = self._history.record(
                page_id=page_id,
                digest=None,
                status="failed",
                duration_s=duration,
                error=f"render: {err}",
                options=asdict(opts),
            )
            return PushResult(
                status="failed",
                error=f"render: {err}",
                duration_s=duration,
                history_id=history_id,
                options=asdict(opts),
            )

        digest = hashlib.sha256(quantized).hexdigest()[:16]
        artifact = self._renders_dir / f"{digest}.png"
        if not artifact.exists():
            artifact.write_bytes(quantized)
        else:
            # Bump mtime so LRU treats this as freshly used.
            artifact.touch()
        self._evict_lru()

        public_url = f"{self._base_url}/renders/{digest}.png"
        payload = {
            "url": public_url,
            "rotate": opts.rotate,
            "scale": opts.scale,
            "bg": opts.bg,
            "saturation": opts.saturation,
        }
        try:
            self._bridge.publish(
                self._topic, json.dumps(payload).encode("utf-8"), qos=1, retain=False
            )
        except Exception as err:  # noqa: BLE001 — broker failures vary
            duration = time.monotonic() - started
            history_id = self._history.record(
                page_id=page_id,
                digest=digest,
                status="failed",
                duration_s=duration,
                error=f"mqtt: {err}",
                options=asdict(opts),
                payload=payload,
                topic=self._topic,
            )
            return PushResult(
                status="failed",
                digest=digest,
                url=public_url,
                error=f"mqtt: {err}",
                duration_s=duration,
                history_id=history_id,
                options=asdict(opts),
            )

        duration = time.monotonic() - started
        history_id = self._history.record(
            page_id=page_id,
            digest=digest,
            status="sent",
            duration_s=duration,
            error=None,
            options=asdict(opts),
            payload=payload,
            topic=self._topic,
        )
        return PushResult(
            status="sent",
            digest=digest,
            url=public_url,
            duration_s=duration,
            history_id=history_id,
            options=asdict(opts),
        )

    def _evict_lru(self) -> None:
        files = sorted(
            self._renders_dir.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for stale in files[self._renders_cap :]:
            try:
                stale.unlink()
            except OSError as err:
                logger.warning("Could not evict %s: %s", stale, err)

    # -- Hot-swap hooks for the /settings page --------------------------------

    def set_bridge(self, bridge: MqttBridge) -> None:
        """Replace the MQTT bridge atomically. Old bridge is disconnected."""
        with self._lock:
            previous, self._bridge = self._bridge, bridge
        if previous is not bridge:
            try:
                previous.disconnect()
            except Exception as err:  # noqa: BLE001
                logger.warning("Old bridge disconnect failed: %s", err)

    def set_base_url(self, base_url: str) -> None:
        with self._lock:
            self._base_url = base_url.rstrip("/")

    def set_topic(self, topic: str) -> None:
        with self._lock:
            self._topic = topic

    def set_rotate_quarters(self, quarters: int) -> None:
        """Set the pre-publish rotation. ``quarters`` is mod-4 number of 90° turns."""
        with self._lock:
            self._rotate_quarters = quarters % 4

    # ------------------------------------------------------------------
    # Send-page entry points: arbitrary image bytes / arbitrary URL render.
    # Same single-flight lock + history pipeline; bypass page lookup.
    # ------------------------------------------------------------------

    def push_image(
        self,
        image_bytes: bytes,
        *,
        source_label: str = "image",
        options: PushOptions | None = None,
        dither: DitherMode = "floyd-steinberg",
    ) -> PushResult:
        """Quantize raw image bytes (any format Pillow understands), publish."""
        opts = options or PushOptions()
        if dither not in VALID_DITHERS:
            raise ValueError(f"dither must be one of {sorted(VALID_DITHERS)}, got {dither!r}")

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            return self._push_bytes_locked(image_bytes, source_label, opts, dither)
        finally:
            self._lock.release()

    def push_webpage(
        self,
        url: str,
        *,
        viewport_w: int = 1600,
        viewport_h: int = 1200,
        options: PushOptions | None = None,
        dither: DitherMode = "floyd-steinberg",
    ) -> PushResult:
        """Screenshot any URL with the renderer, then quantize + publish."""
        opts = options or PushOptions()
        if dither not in VALID_DITHERS:
            raise ValueError(f"dither must be one of {sorted(VALID_DITHERS)}, got {dither!r}")

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            started = time.monotonic()
            try:
                raw = render_to_png(
                    RenderRequest(url=url, viewport_w=viewport_w, viewport_h=viewport_h)
                )
            except Exception as err:  # noqa: BLE001
                duration = time.monotonic() - started
                history_id = self._history.record(
                    page_id=f"webpage:{url[:80]}",
                    digest=None,
                    status="failed",
                    duration_s=duration,
                    error=f"render: {err}",
                    options=asdict(opts),
                )
                return PushResult(
                    status="failed",
                    error=f"render: {err}",
                    duration_s=duration,
                    history_id=history_id,
                    options=asdict(opts),
                )
            return self._push_bytes_locked(raw, f"webpage:{url[:80]}", opts, dither)
        finally:
            self._lock.release()

    def _push_bytes_locked(
        self,
        image_bytes: bytes,
        source_label: str,
        opts: PushOptions,
        dither: DitherMode,
    ) -> PushResult:
        """Shared tail end of push_image / push_webpage: rotate → store → publish.

        We send the full-color image bytes through; the panel listener owns
        gamut quantization. ``dither`` is kept on the API surface for
        backward compat but no longer transforms the bytes here.
        """
        started = time.monotonic()
        try:
            quantized = rotate_png(image_bytes, quarters=self._rotate_quarters)
        except Exception as err:  # noqa: BLE001
            duration = time.monotonic() - started
            history_id = self._history.record(
                page_id=source_label,
                digest=None,
                status="failed",
                duration_s=duration,
                error=f"rotate: {err}",
                options=asdict(opts),
            )
            return PushResult(
                status="failed",
                error=f"rotate: {err}",
                duration_s=duration,
                history_id=history_id,
                options=asdict(opts),
            )

        digest = hashlib.sha256(quantized).hexdigest()[:16]
        artifact = self._renders_dir / f"{digest}.png"
        if not artifact.exists():
            artifact.write_bytes(quantized)
        else:
            artifact.touch()
        self._evict_lru()

        public_url = f"{self._base_url}/renders/{digest}.png"
        payload = {
            "url": public_url,
            "rotate": opts.rotate,
            "scale": opts.scale,
            "bg": opts.bg,
            "saturation": opts.saturation,
        }
        try:
            self._bridge.publish(
                self._topic, json.dumps(payload).encode("utf-8"), qos=1, retain=False
            )
        except Exception as err:  # noqa: BLE001
            duration = time.monotonic() - started
            history_id = self._history.record(
                page_id=source_label,
                digest=digest,
                status="failed",
                duration_s=duration,
                error=f"mqtt: {err}",
                options=asdict(opts),
                payload=payload,
                topic=self._topic,
            )
            return PushResult(
                status="failed",
                digest=digest,
                url=public_url,
                error=f"mqtt: {err}",
                duration_s=duration,
                history_id=history_id,
                options=asdict(opts),
            )

        duration = time.monotonic() - started
        history_id = self._history.record(
            page_id=source_label,
            digest=digest,
            status="sent",
            duration_s=duration,
            error=None,
            options=asdict(opts),
            payload=payload,
            topic=self._topic,
        )
        return PushResult(
            status="sent",
            digest=digest,
            url=public_url,
            duration_s=duration,
            history_id=history_id,
            options=asdict(opts),
        )
