"""Admin UI blueprint: editor, design-system demo, and the JSON API the editor talks to.

The editor and components-demo entry points are bundled by esbuild into
``static/dist/{editor,components-demo}.js``. The Jinja templates here just
render the shell HTML and load that bundle.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, jsonify, render_template, request, url_for
from pydantic import ValidationError
from werkzeug.wrappers import Response

from app.mqtt_bridge import MqttBridge
from app.plugin_loader import PluginRegistry
from app.push import PushManager, PushOptions
from app.quantizer import DitherMode, quantize_to_png
from app.renderer import RenderRequest, render_to_png
from app.scheduler import Scheduler
from app.state import HistoryStore, Page, PageStore, Schedule, ScheduleStore

_VALID_DITHER_MODES: frozenset[str] = frozenset({"floyd-steinberg", "none"})

bp = Blueprint("admin", __name__)


def _store() -> PageStore:
    store: PageStore = current_app.config["PAGE_STORE"]
    return store


def _registry() -> PluginRegistry:
    registry: PluginRegistry = current_app.config["PLUGIN_REGISTRY"]
    return registry


@bp.get("/_components")
def components_demo() -> str:
    return render_template("components_demo.html")


@bp.get("/editor")
def editor_index() -> str:
    return render_template("editor.html", page_id=None)


@bp.get("/editor/<page_id>")
def editor(page_id: str) -> str:
    return render_template("editor.html", page_id=page_id)


@bp.get("/api/pages")
def api_list_pages() -> Response:
    return jsonify([p.model_dump(mode="json", exclude_none=True) for p in _store().all()])


@bp.get("/api/pages/<page_id>")
def api_get_page(page_id: str) -> Response:
    page = _store().get(page_id)
    if page is None:
        abort(404)
    return jsonify(page.model_dump(mode="json", exclude_none=True))


@bp.put("/api/pages/<page_id>")
def api_save_page(page_id: str) -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    if body.get("id") != page_id:
        return jsonify({"error": "page id in body must match URL"}), 400
    try:
        page = Page.model_validate(body)
    except ValidationError as err:
        return jsonify({"error": "validation", "details": err.errors()}), 400
    _store().upsert(page)
    return jsonify(page.model_dump(mode="json", exclude_none=True))


@bp.delete("/api/pages/<page_id>")
def api_delete_page(page_id: str) -> tuple[str, int]:
    return ("", 204) if _store().delete(page_id) else ("", 404)


@bp.get("/api/themes")
def api_list_themes() -> Response:
    themes = [
        {
            "id": t.id,
            "name": t.name,
            "mode": t.mode,
            "palette": t.palette,
            "plugin_id": t.plugin_id,
            "is_user": t.is_user,
        }
        for t in _registry().themes.values()
    ]
    return jsonify(themes)


@bp.post("/api/themes")
def api_create_theme() -> tuple[Response, int] | Response:
    """Create or replace a user theme. Saved to themes_core's data dir."""
    from app.plugin_loader import Theme
    from app.themes import UserTheme, UserThemeStore

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    try:
        ut = UserTheme.model_validate(body)
    except ValidationError as err:
        details = [
            {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in err.errors()
        ]
        return jsonify({"error": "validation", "details": details}), 400

    registry = _registry()
    existing = registry.themes.get(ut.id)
    if existing is not None and not existing.is_user:
        return (
            jsonify({"error": f"id {ut.id!r} clashes with a built-in theme"}),
            409,
        )

    plugin = registry.plugins.get("themes_core")
    if plugin is None:
        return jsonify({"error": "themes_core plugin not loaded"}), 500
    UserThemeStore(plugin.data_dir / "user.json").upsert(ut)

    new_theme = Theme(
        id=ut.id,
        name=ut.name,
        mode=ut.mode or "",
        palette=dict(ut.palette),
        plugin_id="themes_core",
        is_user=True,
    )
    registry.themes[ut.id] = new_theme
    return jsonify(
        {
            "id": new_theme.id,
            "name": new_theme.name,
            "mode": new_theme.mode,
            "palette": new_theme.palette,
            "plugin_id": new_theme.plugin_id,
            "is_user": True,
        }
    )


@bp.delete("/api/themes/<theme_id>")
def api_delete_theme(theme_id: str) -> tuple[Response, int] | tuple[str, int]:
    from app.themes import UserThemeStore

    registry = _registry()
    theme = registry.themes.get(theme_id)
    if theme is None:
        return ("", 404)
    if not theme.is_user:
        return jsonify({"error": "cannot delete a built-in theme"}), 403

    plugin = registry.plugins.get("themes_core")
    if plugin is None:
        return jsonify({"error": "themes_core plugin not loaded"}), 500
    UserThemeStore(plugin.data_dir / "user.json").remove(theme_id)
    del registry.themes[theme_id]
    return ("", 204)


@bp.get("/api/fonts")
def api_list_fonts() -> Response:
    fonts = [
        {
            "id": f.id,
            "name": f.name,
            "category": f.category,
            "weights": list(f.weights),
            "files": f.files,
            "plugin_id": f.plugin_id,
        }
        for f in _registry().fonts.values()
    ]
    return jsonify(fonts)


@bp.get("/themes")
def themes_page() -> str:
    return render_template("themes.html")


@bp.get("/api/widgets")
def api_list_widgets() -> Response:
    """Loaded widget plugins, in the shape the editor needs to populate dropdowns."""
    widgets: list[dict[str, Any]] = [
        {
            "id": p.id,
            "name": p.name,
            "supported_sizes": p.supported_sizes,
            "cell_options": p.manifest.get("cell_options", []),
        }
        for p in _registry().widgets()
    ]
    return jsonify(widgets)


def _render_page_png(page_id: str) -> tuple[bytes, int, int]:
    """Render the page at panel resolution, return (png_bytes, panel_w, panel_h)."""
    page = _store().get(page_id)
    if page is None:
        abort(404)
    compose_url = url_for("composer.compose", page_id=page_id, for_push=1, _external=True)
    raw = render_to_png(
        RenderRequest(
            url=compose_url,
            viewport_w=page.panel.w,
            viewport_h=page.panel.h,
        )
    )
    return raw, page.panel.w, page.panel.h


@bp.get("/api/pages/<page_id>/raw.png")
def api_render_raw(page_id: str) -> Response:
    """Untouched browser screenshot — the input to the quantizer."""
    raw, _, _ = _render_page_png(page_id)
    return Response(raw, mimetype="image/png")


@bp.get("/api/pages/<page_id>/preview.png")
def api_render_preview(page_id: str) -> tuple[Response, int] | Response:
    """Quantized PNG — what the panel will actually paint."""
    dither_arg = request.args.get("dither", "floyd-steinberg")
    if dither_arg not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither_arg!r}"}), 400
    raw, _, _ = _render_page_png(page_id)
    quantized = quantize_to_png(raw, dither=cast_dither(dither_arg))
    return Response(quantized, mimetype="image/png")


def cast_dither(value: str) -> DitherMode:
    """Narrow a validated string to the DitherMode literal for the quantizer."""
    assert value in _VALID_DITHER_MODES
    return value  # type: ignore[return-value]


def _push_manager() -> PushManager:
    pm: PushManager = current_app.config["PUSH_MANAGER"]
    return pm


def _bridge() -> MqttBridge:
    bridge: MqttBridge = current_app.config["MQTT_BRIDGE"]
    return bridge


def _history() -> HistoryStore:
    h: HistoryStore = current_app.config["HISTORY_STORE"]
    return h


@bp.post("/api/pages/<page_id>/push")
def api_push_page(page_id: str) -> tuple[Response, int] | Response:
    """Render → quantize → publish MQTT job.

    Body (all optional):
      { "rotate": int, "scale": str, "bg": str, "saturation": float, "dither": str }
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400

    dither_arg = body.get("dither", "floyd-steinberg")
    if not isinstance(dither_arg, str) or dither_arg not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither_arg!r}"}), 400

    options_kwargs: dict[str, Any] = {}
    for field_name in ("rotate", "scale", "bg", "saturation"):
        if field_name in body:
            options_kwargs[field_name] = body[field_name]

    try:
        options = PushOptions(**options_kwargs)
    except (TypeError, ValueError) as err:
        return jsonify({"error": str(err)}), 400

    result = _push_manager().push(page_id, options=options, dither=cast_dither(dither_arg))

    response = jsonify(
        {
            "status": result.status,
            "digest": result.digest,
            "url": result.url,
            "error": result.error,
            "duration_s": round(result.duration_s, 3),
            "history_id": result.history_id,
            "options": result.options,
        }
    )
    if result.status == "sent":
        return response
    if result.status == "busy":
        return response, 409
    if result.status == "not_found":
        return response, 404
    return response, 502


@bp.get("/api/history")
def api_history() -> Response:
    raw_limit = request.args.get("limit", "50")
    try:
        limit = max(1, min(int(raw_limit), 500))
    except ValueError:
        limit = 50
    rows = _history().recent(limit=limit)
    return jsonify(
        [
            {
                "id": r.id,
                "ts": r.ts.isoformat(),
                "page_id": r.page_id,
                "digest": r.digest,
                "status": r.status,
                "duration_s": round(r.duration_s, 3),
                "error": r.error,
                "options": r.options,
            }
            for r in rows
        ]
    )


def _schedules() -> ScheduleStore:
    s: ScheduleStore = current_app.config["SCHEDULE_STORE"]
    return s


def _scheduler() -> Scheduler:
    s: Scheduler = current_app.config["SCHEDULER"]
    return s


@bp.get("/schedules")
def schedules_page() -> str:
    return render_template("schedules.html")


@bp.get("/send")
def send_page() -> str:
    return render_template("send.html")


@bp.get("/api/schedules")
def api_list_schedules() -> Response:
    return jsonify([s.model_dump(mode="json", exclude_none=True) for s in _schedules().all()])


@bp.get("/api/schedules/<schedule_id>")
def api_get_schedule(schedule_id: str) -> Response:
    s = _schedules().get(schedule_id)
    if s is None:
        abort(404)
    return jsonify(s.model_dump(mode="json", exclude_none=True))


@bp.put("/api/schedules/<schedule_id>")
def api_save_schedule(schedule_id: str) -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    if body.get("id") != schedule_id:
        return jsonify({"error": "schedule id in body must match URL"}), 400
    try:
        schedule = Schedule.model_validate(body)
    except ValidationError as err:
        details = [
            {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in err.errors()
        ]
        return jsonify({"error": "validation", "details": details}), 400
    _schedules().upsert(schedule)
    return jsonify(schedule.model_dump(mode="json", exclude_none=True))


@bp.delete("/api/schedules/<schedule_id>")
def api_delete_schedule(schedule_id: str) -> tuple[str, int]:
    return ("", 204) if _schedules().delete(schedule_id) else ("", 404)


@bp.post("/api/schedules/<schedule_id>/fire")
def api_fire_schedule(schedule_id: str) -> tuple[Response, int] | Response:
    """Manually fire a schedule once, ignoring its time constraints."""
    result = _scheduler().fire_now(schedule_id)
    if result is None:
        return ("", 404)  # type: ignore[return-value]
    return jsonify(
        {
            "status": result.status,
            "digest": result.digest,
            "url": result.url,
            "error": result.error,
            "duration_s": round(result.duration_s, 3),
        }
    )


def _push_options_from_body(body: dict[str, Any]) -> tuple[PushOptions | None, str | None]:
    """Extract optional rotate/scale/bg/saturation overrides from a send body."""
    kwargs: dict[str, Any] = {}
    for field_name in ("rotate", "scale", "bg", "saturation"):
        if field_name in body:
            kwargs[field_name] = body[field_name]
    if not kwargs:
        return None, None
    try:
        return PushOptions(**kwargs), None
    except (TypeError, ValueError) as err:
        return None, str(err)


def _send_response(result: Any) -> Response | tuple[Response, int]:
    payload = jsonify(
        {
            "status": result.status,
            "digest": result.digest,
            "url": result.url,
            "error": result.error,
            "duration_s": round(result.duration_s, 3),
            "history_id": result.history_id,
        }
    )
    if result.status == "sent":
        return payload
    if result.status == "busy":
        return payload, 409
    if result.status == "not_found":
        return payload, 404
    return payload, 502


@bp.post("/api/send/page")
def api_send_page() -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) or {}
    page_id = body.get("page_id")
    if not page_id or not isinstance(page_id, str):
        return jsonify({"error": "page_id is required"}), 400
    dither = body.get("dither", "floyd-steinberg")
    if dither not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither!r}"}), 400
    options, err = _push_options_from_body(body)
    if err is not None:
        return jsonify({"error": err}), 400
    result = _push_manager().push(page_id, options=options, dither=cast_dither(dither))
    return _send_response(result)


@bp.post("/api/send/url")
def api_send_url() -> tuple[Response, int] | Response:
    """Download an image from a URL and push it as-is (after quantization)."""
    import urllib.request

    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must be an http(s) URL"}), 400
    dither = body.get("dither", "floyd-steinberg")
    if dither not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither!r}"}), 400
    options, err = _push_options_from_body(body)
    if err is not None:
        return jsonify({"error": err}), 400
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/0.8"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            image_bytes = resp.read()
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"download: {err}"}), 502
    result = _push_manager().push_image(
        image_bytes,
        source_label=f"url:{url[:80]}",
        options=options,
        dither=cast_dither(dither),
    )
    return _send_response(result)


@bp.post("/api/send/webpage")
def api_send_webpage() -> tuple[Response, int] | Response:
    """Screenshot any URL with the renderer, then push the result."""
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must be an http(s) URL"}), 400
    dither = body.get("dither", "floyd-steinberg")
    if dither not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither!r}"}), 400
    viewport_w = int(body.get("viewport_w", 1600) or 1600)
    viewport_h = int(body.get("viewport_h", 1200) or 1200)
    options, err = _push_options_from_body(body)
    if err is not None:
        return jsonify({"error": err}), 400
    result = _push_manager().push_webpage(
        url,
        viewport_w=viewport_w,
        viewport_h=viewport_h,
        options=options,
        dither=cast_dither(dither),
    )
    return _send_response(result)


@bp.post("/api/send/file")
def api_send_file() -> tuple[Response, int] | Response:
    """Upload an image file directly (multipart/form-data)."""
    if "file" not in request.files:
        return jsonify({"error": "expected a 'file' part in multipart body"}), 400
    upload = request.files["file"]
    if upload.filename == "":
        return jsonify({"error": "no file selected"}), 400
    dither = request.form.get("dither", "floyd-steinberg")
    if dither not in _VALID_DITHER_MODES:
        return jsonify({"error": f"invalid dither mode: {dither!r}"}), 400
    image_bytes = upload.read()
    if not image_bytes:
        return jsonify({"error": "uploaded file is empty"}), 400
    result = _push_manager().push_image(
        image_bytes,
        source_label=f"file:{upload.filename}",
        dither=cast_dither(dither),
    )
    return _send_response(result)


@bp.get("/api/listener/status")
def api_listener_status() -> Response:
    status = _bridge().listener_status
    if status is None:
        return jsonify({"state": "unknown", "received_at": None, "raw": None})
    return jsonify(
        {
            "state": status.state,
            "received_at": status.received_at.isoformat(),
            "raw": status.raw,
        }
    )
