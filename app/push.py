"""Single-flight push pipeline: render → quantize → write artifact → publish.

The MQTT wire format is frozen (byte-for-byte identical to v3, see docs/architecture.md). This module
constructs valid payloads, persists each render as a content-addressed PNG
under ``data/core/renders/``, and records every attempt in the history.

Concurrency: one push at a time. Concurrent attempts return ``status="busy"``
rather than queuing — keeps the model simple and the UI honest about what's
happening.

mypy --strict applies to this module — see pyproject.toml.
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
from app.quantizer import DitherMode, apply_underscan, rotate_png
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
        underscan: int = 0,
        debounce_seconds: float = 5.0,
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
        self._underscan = max(0, underscan)
        self._lock = threading.Lock()
        # Debounce: reject a *successful* push that's identical to one we
        # just published, within this short window. Guards against runaway
        # clients (cross-tab double-fires, sticky keys, replay storms).
        # Keyed by a request signature; cleared when a fresh push lands.
        self._debounce_lock = threading.Lock()
        self._recent_pushes: dict[str, float] = {}
        self._debounce_seconds: float = debounce_seconds

    # -- Debounce helpers --------------------------------------------------
    #
    # The signature is whatever fully identifies "the same push": source
    # type, target, and options. Two clicks that produce the same signature
    # within ``_debounce_seconds`` collapse to one published frame.

    @staticmethod
    def _signature(kind: str, target: str, opts: PushOptions) -> str:
        payload = json.dumps(asdict(opts), sort_keys=True)
        return f"{kind}:{target}:{payload}"

    def _allow_push(self, signature: str) -> bool:
        if self._debounce_seconds <= 0:
            return True
        with self._debounce_lock:
            now = time.monotonic()
            # Cheap GC: drop any entries that have aged out by 2× the window.
            stale_cutoff = now - self._debounce_seconds * 2
            stale = [k for k, ts in self._recent_pushes.items() if ts < stale_cutoff]
            for k in stale:
                del self._recent_pushes[k]
            last = self._recent_pushes.get(signature)
            return last is None or (now - last) >= self._debounce_seconds

    def _record_push(self, signature: str) -> None:
        with self._debounce_lock:
            self._recent_pushes[signature] = time.monotonic()

    def _busy_duplicate(self, opts: PushOptions) -> PushResult:
        return PushResult(
            status="busy",
            error=(f"identical push fired in the last {self._debounce_seconds:.0f}s — ignored"),
            options=asdict(opts),
        )

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

        signature = self._signature("page", page_id, opts)
        if not self._allow_push(signature):
            return self._busy_duplicate(opts)

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            result = self._push_locked(page_id, opts, dither)
            if result.status == "sent":
                self._record_push(signature)
            return result
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
            inset = apply_underscan(raw, underscan=self._underscan)
            quantized = rotate_png(inset, quarters=self._rotate_quarters)
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

    def set_underscan(self, underscan: int) -> None:
        """Set the per-edge inset (px) applied to every published frame."""
        with self._lock:
            self._underscan = max(0, underscan)

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

        # Hash the bytes so two uploads of the same image collapse, but two
        # different uploads from the same source don't.
        signature = self._signature(
            "image", f"{source_label}#{hashlib.sha256(image_bytes).hexdigest()[:16]}", opts
        )
        if not self._allow_push(signature):
            return self._busy_duplicate(opts)

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            result = self._push_bytes_locked(image_bytes, source_label, opts, dither)
            if result.status == "sent":
                self._record_push(signature)
            return result
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

        signature = self._signature("webpage", url, opts)
        if not self._allow_push(signature):
            return self._busy_duplicate(opts)

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
            result = self._push_bytes_locked(raw, f"webpage:{url[:80]}", opts, dither)
            if result.status == "sent":
                self._record_push(signature)
            return result
        finally:
            self._lock.release()

    def republish(self, history_id: int) -> PushResult:
        """Re-publish a previously-rendered artifact straight from the renders
        dir — no re-render, no re-quantize. Looks up the existing history row
        for its digest + options, then publishes the stored PNG. Records a new
        history row tagged with the original ``page_id`` so the Send-page list
        keeps grouping resends with their source."""
        record = self._history.get(history_id)
        if record is None:
            return PushResult(status="not_found", error="history record not found")
        if not record.digest:
            return PushResult(
                status="failed",
                error="record has no digest — original push never produced a render",
                history_id=history_id,
            )
        try:
            opts = PushOptions(
                rotate=int(record.options.get("rotate", 0)),
                scale=str(record.options.get("scale", "fit")),
                bg=str(record.options.get("bg", "white")),
                saturation=float(record.options.get("saturation", 0.5)),
            )
        except (TypeError, ValueError) as err:
            return PushResult(
                status="failed",
                error=f"options: {err}",
                history_id=history_id,
            )

        artifact = self._renders_dir / f"{record.digest}.png"
        if not artifact.exists():
            return PushResult(
                status="failed",
                digest=record.digest,
                error="render artifact has been evicted from disk",
                options=asdict(opts),
            )

        signature = self._signature("republish", record.digest, opts)
        if not self._allow_push(signature):
            return self._busy_duplicate(opts)

        if not self._lock.acquire(blocking=False):
            return PushResult(
                status="busy",
                error="another push is already in flight",
                options=asdict(opts),
            )
        try:
            started = time.monotonic()
            artifact.touch()  # bump LRU mtime
            public_url = f"{self._base_url}/renders/{record.digest}.png"
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
                new_id = self._history.record(
                    page_id=record.page_id,
                    digest=record.digest,
                    status="failed",
                    duration_s=duration,
                    error=f"mqtt: {err}",
                    options=asdict(opts),
                    payload=payload,
                    topic=self._topic,
                )
                return PushResult(
                    status="failed",
                    digest=record.digest,
                    url=public_url,
                    error=f"mqtt: {err}",
                    duration_s=duration,
                    history_id=new_id,
                    options=asdict(opts),
                )
            duration = time.monotonic() - started
            new_id = self._history.record(
                page_id=record.page_id,
                digest=record.digest,
                status="sent",
                duration_s=duration,
                error=None,
                options=asdict(opts),
                payload=payload,
                topic=self._topic,
            )
            self._record_push(signature)
            return PushResult(
                status="sent",
                digest=record.digest,
                url=public_url,
                duration_s=duration,
                history_id=new_id,
                options=asdict(opts),
            )
        finally:
            self._lock.release()

    def delete_history(self, history_id: int) -> bool:
        """Delete a history row and, if no other rows still reference its
        render, remove the PNG too. Returns True if the row was deleted."""
        record = self._history.get(history_id)
        if record is None:
            return False
        ok = self._history.delete(history_id)
        if ok and record.digest and not self._history.digest_in_use(record.digest):
            artifact = self._renders_dir / f"{record.digest}.png"
            try:
                artifact.unlink(missing_ok=True)
            except OSError as err:
                logger.warning("Could not delete render %s: %s", artifact, err)
        return ok

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
            inset = apply_underscan(image_bytes, underscan=self._underscan)
            quantized = rotate_png(inset, quarters=self._rotate_quarters)
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
