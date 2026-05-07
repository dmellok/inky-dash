from __future__ import annotations

import hashlib
import threading
import time
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, abort, jsonify, request

from config import Config
from mqtt_bridge import MqttBridge
from renderer import RenderError, render_to_png, render_url_to_png
from state.history import HistoryStore
from state.pages import DraftStore, PageStore

# Per the v2-compatible MQTT contract.
VALID_ROTATIONS = (0, 90, 180, 270)
VALID_SCALES = ("fit", "fill", "stretch", "center")
# 'blurred' is companion-internal only; pre-composed into the PNG and the
# wire bg becomes 'white'. Stage 6's Send page uses this for letterboxed
# image uploads; for dashboards the rendered PNG already fills the panel.
VALID_BGS = ("black", "white", "red", "green", "blue", "yellow", "orange", "blurred")

DEFAULT_OPTIONS: dict[str, Any] = {
    "rotate": 0,
    "scale": "fit",
    "bg": "white",
    "saturation": 0.5,
}


class PushBusy(Exception):
    """Raised when a push is requested while another is still in flight."""


class PushValidationError(Exception):
    """Raised when push options fail the v2 wire-contract validation."""


def _iso_now() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _local_compose_url(config: Config, *, page_id: str | None = None,
                       draft_id: str | None = None) -> str:
    # Loopback URL — the renderer is colocated with the Flask app. The wire URL
    # the Pi reads is a separate `<PUBLIC_BASE_URL>/renders/<file>.png`.
    base = f"http://127.0.0.1:{config.port}"
    if page_id:
        return f"{base}/compose/{page_id}?for_push=1"
    if draft_id:
        return f"{base}/compose/draft/{draft_id}?for_push=1"
    raise ValueError("need page_id or draft_id")


def _validate_options(
    raw: dict[str, Any] | None,
    *,
    panel_portrait: bool = False,
) -> dict[str, Any]:
    # When the configured panel is portrait (height > width) the renderer
    # produces a tall PNG, but the physical Inky panel is mounted in
    # landscape — the listener has to rotate 90° before painting. The user's
    # `rotate` option is treated as an additional offset on top of that base
    # rotation, so the form can stay at 0 by default and just compose with
    # the panel's intrinsic orientation.
    raw_dict = raw or {}
    opts: dict[str, Any] = {**DEFAULT_OPTIONS, **raw_dict}
    rotate = opts["rotate"]
    try:
        rotate = int(rotate)
    except (TypeError, ValueError):
        raise PushValidationError("rotate must be an integer")
    if rotate not in VALID_ROTATIONS:
        raise PushValidationError(
            f"rotate must be one of {VALID_ROTATIONS}, got {rotate}"
        )
    if panel_portrait:
        rotate = (rotate + 90) % 360
    if opts["scale"] not in VALID_SCALES:
        raise PushValidationError(
            f"scale must be one of {VALID_SCALES}, got {opts['scale']!r}"
        )
    if opts["bg"] not in VALID_BGS:
        raise PushValidationError(
            f"bg must be one of {VALID_BGS}, got {opts['bg']!r}"
        )
    try:
        sat = float(opts["saturation"])
    except (TypeError, ValueError):
        raise PushValidationError("saturation must be a number in [0.0, 1.0]")
    if not (0.0 <= sat <= 1.0):
        raise PushValidationError(
            f"saturation must be in [0.0, 1.0], got {sat}"
        )
    return {
        "rotate": rotate,
        "scale": opts["scale"],
        "bg": opts["bg"],
        "saturation": sat,
    }


class PushManager:
    """Single-flight orchestrator: render → publish → record history."""

    def __init__(
        self,
        config: Config,
        mqtt: MqttBridge,
        history: HistoryStore,
        pages: PageStore,
        drafts: DraftStore,
    ):
        self.config = config
        self.mqtt = mqtt
        self.history = history
        self.pages = pages
        self.drafts = drafts
        self._state_lock = threading.Lock()
        self._render_lock = threading.Lock()
        self._in_flight: dict[str, Any] | None = None
        self._last_completed_at: float | None = None

    def _panel_is_portrait(self) -> bool:
        return self.config.panel_height > self.config.panel_width

    # ---------- introspection ---------------------------------------------

    def state(self) -> dict[str, Any]:
        with self._state_lock:
            now = time.time()
            since = (
                (now - self._last_completed_at)
                if self._last_completed_at is not None
                else None
            )
            return {
                "in_flight": self._in_flight is not None,
                "in_flight_meta": dict(self._in_flight) if self._in_flight else None,
                "last_completed_at": self._last_completed_at,
                "seconds_since_completed": since,
                "lockout_seconds": self.config.refresh_lockout_seconds,
                "in_lockout": (
                    since is not None
                    and since < self.config.refresh_lockout_seconds
                ),
            }

    # ---------- core push --------------------------------------------------

    def push(
        self,
        *,
        source: str,
        target: dict[str, str | None],
        options: dict[str, Any] | None,
        compose_url: str,
        wire_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        opts = _validate_options(options, panel_portrait=self._panel_is_portrait())

        # Single-flight: 409 if a render is already running.
        if not self._render_lock.acquire(blocking=False):
            raise PushBusy("a push is already in progress")

        meta = {
            "source": source,
            "started_at": time.time(),
            **{k: v for k, v in target.items() if v is not None},
        }
        with self._state_lock:
            self._in_flight = meta

        started = time.time()
        render_filename: str | None = None
        try:
            render_filename = self._render(compose_url)
            wire_payload = self._wire_payload(render_filename, opts, wire_overrides)
            info = self.mqtt.publish_update(wire_payload)
            duration = time.time() - started

            history_id = self.history.record(
                ts=_iso_now(),
                source=source,
                page_id=target.get("page_id"),
                draft_id=target.get("draft_id"),
                source_image=target.get("source_image"),
                render_filename=render_filename,
                wire_payload=wire_payload,
                duration_s=duration,
                result="ok",
                publish_rc=int(info.rc),
            )
            return {
                "history_id": history_id,
                "render_filename": render_filename,
                "wire_payload": wire_payload,
                "duration_s": duration,
                "publish_rc": int(info.rc),
            }
        except Exception as exc:
            duration = time.time() - started
            try:
                self.history.record(
                    ts=_iso_now(),
                    source=source,
                    page_id=target.get("page_id"),
                    draft_id=target.get("draft_id"),
                    source_image=target.get("source_image"),
                    render_filename=render_filename or "(failed)",
                    wire_payload={},
                    duration_s=duration,
                    result="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
            raise
        finally:
            with self._state_lock:
                self._in_flight = None
                self._last_completed_at = time.time()
            self._render_lock.release()

    # ---------- webpage push (no compose URL — direct browser nav) --------

    def push_webpage(
        self,
        *,
        url: str,
        extra_wait_ms: int,
        options: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if not (url.startswith("http://") or url.startswith("https://")):
            raise PushValidationError("url must start with http:// or https://")
        opts = _validate_options(options, panel_portrait=self._panel_is_portrait())

        if not self._render_lock.acquire(blocking=False):
            raise PushBusy("a push is already in progress")
        meta = {"source": "webpage", "url": url, "started_at": time.time()}
        with self._state_lock:
            self._in_flight = meta

        started = time.time()
        render_filename: str | None = None
        try:
            render_filename = self._render_url(url, extra_wait_ms=extra_wait_ms)
            wire_payload = self._wire_payload(
                render_filename, opts,
                wire_overrides={"scale": "fit", "bg": "white"},
            )
            info = self.mqtt.publish_update(wire_payload)
            duration = time.time() - started
            history_id = self.history.record(
                ts=_iso_now(),
                source="webpage",
                source_image=url,  # store the original URL for context
                render_filename=render_filename,
                wire_payload=wire_payload,
                duration_s=duration,
                result="ok",
                publish_rc=int(info.rc),
            )
            return {
                "history_id": history_id,
                "render_filename": render_filename,
                "wire_payload": wire_payload,
                "duration_s": duration,
                "publish_rc": int(info.rc),
            }
        except Exception as exc:
            duration = time.time() - started
            try:
                self.history.record(
                    ts=_iso_now(),
                    source="webpage",
                    source_image=url,
                    render_filename=render_filename or "(failed)",
                    wire_payload={},
                    duration_s=duration,
                    result="error",
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                pass
            raise
        finally:
            with self._state_lock:
                self._in_flight = None
                self._last_completed_at = time.time()
            self._render_lock.release()

    def _render_url(self, url: str, *, extra_wait_ms: int) -> str:
        """Direct-URL render (no composer page, no __inkyReady)."""
        import hashlib as _h
        tmp_path = self.config.render_dir / "_pending.png"
        try:
            render_url_to_png(
                url,
                panel_w=self.config.panel_width,
                panel_h=self.config.panel_height,
                output_path=tmp_path,
                extra_wait_ms=extra_wait_ms,
            )
            digest = _h.sha256(tmp_path.read_bytes()).hexdigest()[:12]
            final_name = f"{digest}.png"
            final_path = self.config.render_dir / final_name
            if final_path.exists():
                tmp_path.unlink()
            else:
                tmp_path.replace(final_path)
            return final_name
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    # ---------- replay -----------------------------------------------------

    def replay(self, push_id: int) -> dict[str, Any]:
        record = self.history.get(push_id)
        if record is None:
            raise LookupError(f"no history row {push_id}")
        png_path = self.config.render_dir / record["render_filename"]
        if not png_path.exists():
            raise FileNotFoundError(
                f"render {record['render_filename']} no longer on disk"
            )
        payload = record["wire_payload"]
        info = self.mqtt.publish_update(payload)
        history_id = self.history.record(
            ts=_iso_now(),
            source="replay",
            page_id=record.get("page_id"),
            draft_id=record.get("draft_id"),
            source_image=record.get("source_image"),
            render_filename=record["render_filename"],
            wire_payload=payload,
            duration_s=0.0,
            result="ok",
            publish_rc=int(info.rc),
        )
        return {
            "history_id": history_id,
            "wire_payload": payload,
            "publish_rc": int(info.rc),
        }

    # ---------- internals --------------------------------------------------

    def _render(self, compose_url: str) -> str:
        """Run Playwright, content-hash the PNG, dedupe to <hash>.png."""
        tmp_path = self.config.render_dir / "_pending.png"
        try:
            render_to_png(
                compose_url,
                panel_w=self.config.panel_width,
                panel_h=self.config.panel_height,
                output_path=tmp_path,
            )
            digest = hashlib.sha256(tmp_path.read_bytes()).hexdigest()[:12]
            final_name = f"{digest}.png"
            final_path = self.config.render_dir / final_name
            if final_path.exists():
                tmp_path.unlink()
            else:
                tmp_path.replace(final_path)
            return final_name
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

    def _wire_payload(
        self,
        render_filename: str,
        opts: dict[str, Any],
        wire_overrides: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # wire_overrides forces wire-level scale/bg when the source's compose route
        # has already baked them into the PNG (Send page image uploads). The brief:
        # "bg=blurred ... gets pre-composed into the PNG and the wire bg is white."
        merged = {**opts, **(wire_overrides or {})}
        wire_bg = "white" if merged["bg"] == "blurred" else merged["bg"]
        return {
            "url": f"{self.config.public_base_url}/renders/{render_filename}",
            "rotate": merged["rotate"],
            "scale": merged["scale"],
            "bg": wire_bg,
            "saturation": merged["saturation"],
        }


# ---------- Flask blueprint ---------------------------------------------------


def make_blueprint(manager: PushManager) -> Blueprint:
    bp = Blueprint("push", __name__)

    @bp.post("/api/push/<page_id>")
    def push_page(page_id):
        page = manager.pages.get(page_id)
        if not page:
            abort(404)
        try:
            options = request.get_json(silent=True) or {}
            # Page-level saturation seeds the request options so saved
            # dashboards push with their tuned colour intensity. Caller-
            # supplied saturation (Send page slider, schedule override) still
            # wins because the explicit key in `options` survives the merge.
            if page.saturation is not None and "saturation" not in options:
                options["saturation"] = page.saturation
            return jsonify(
                manager.push(
                    source="page",
                    target={"page_id": page_id},
                    options=options,
                    compose_url=_local_compose_url(manager.config, page_id=page_id),
                )
            )
        except PushBusy as exc:
            return jsonify({"error": str(exc)}), 409
        except PushValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except RenderError as exc:
            return jsonify({"error": f"render failed: {exc}"}), 500
        except Exception as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    @bp.post("/api/push-draft/<draft_id>")
    def push_draft(draft_id):
        if manager.drafts.get(draft_id) is None:
            abort(404)
        try:
            options = request.get_json(silent=True) or {}
            return jsonify(
                manager.push(
                    source="draft",
                    target={"draft_id": draft_id},
                    options=options,
                    compose_url=_local_compose_url(manager.config, draft_id=draft_id),
                )
            )
        except PushBusy as exc:
            return jsonify({"error": str(exc)}), 409
        except PushValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except RenderError as exc:
            return jsonify({"error": f"render failed: {exc}"}), 500
        except Exception as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    @bp.get("/api/push/state")
    def push_state():
        return jsonify(manager.state())

    @bp.get("/api/history")
    def history_list():
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 500))
        return jsonify({"history": manager.history.list(limit=limit)})

    @bp.get("/api/history/<int:push_id>")
    def history_one(push_id):
        h = manager.history.get(push_id)
        if not h:
            abort(404)
        return jsonify(h)

    @bp.post("/api/replay/<int:push_id>")
    def replay(push_id):
        try:
            return jsonify(manager.replay(push_id))
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except FileNotFoundError as exc:
            return jsonify({"error": str(exc)}), 410
        except Exception as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    @bp.delete("/api/history/<int:push_id>")
    def history_delete(push_id):
        filename = manager.history.delete(push_id)
        if filename is None:
            return jsonify({"error": "not found"}), 404
        _unlink_render(manager.config.render_dir, filename)
        return ("", 204)

    @bp.delete("/api/history")
    def history_clear():
        filenames = manager.history.clear()
        for f in filenames:
            _unlink_render(manager.config.render_dir, f)
        return jsonify({"deleted": len(filenames)})

    return bp


def _unlink_render(render_dir, filename: str) -> None:
    """Best-effort unlink of a render PNG. Filename comes from the DB so we
    only allow plain basenames — no traversal."""
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return
    path = render_dir / filename
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
