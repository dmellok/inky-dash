"""Admin UI blueprint: editor, design-system demo, and the JSON API the editor talks to.

The editor and components-demo entry points are bundled by esbuild into
``static/dist/{editor,components-demo}.js``. The Jinja templates here just
render the shell HTML and load that bundle.
"""

from __future__ import annotations

import re
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
from app.state import (
    PANEL_MODELS,
    AppSettings,
    AppSettingsStore,
    Cell,
    HistoryStore,
    Page,
    PageStore,
    Panel,
    PanelSettings,
    Schedule,
    ScheduleStore,
    SettingsStore,
)

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
    return render_template("dashboards.html")


@bp.get("/editor/<page_id>")
def editor(page_id: str) -> str:
    return render_template("editor.html", page_id=page_id)


_PAGE_ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]*$")


def _slugify(name: str) -> str:
    """Best-effort slug for page IDs. Lowercases, strips, replaces non-[a-z0-9_-] with '-'."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", slug)
    slug = slug.strip("-")
    return slug


def _unique_page_id(base: str, existing: set[str]) -> str:
    """Return ``base`` if free, else ``base-2``, ``base-3``, …"""
    if base and base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


@bp.get("/api/pages")
def api_list_pages() -> Response:
    return jsonify([p.model_dump(mode="json", exclude_none=True) for p in _store().all()])


@bp.post("/api/pages")
def api_create_page() -> tuple[Response, int] | Response:
    """Create a fresh dashboard with panel-aware defaults.

    Body: ``{"name": str, "id"?: str}``. If ``id`` is omitted it's slugified
    from ``name``; collisions get a numeric suffix.
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    explicit_id = (body.get("id") or "").strip().lower()
    derived_id = explicit_id or _slugify(name)
    if not derived_id:
        return jsonify({"error": "could not derive a valid id from name"}), 400
    if not _PAGE_ID_RE.match(derived_id):
        return jsonify({"error": "id must match ^[a-z0-9_][a-z0-9_-]*$"}), 400

    store = _store()
    existing_ids = {p.id for p in store.all()}
    if explicit_id and explicit_id in existing_ids:
        return jsonify({"error": "id already exists"}), 409
    # Auto-derived collisions get a numeric suffix so the create flow is friendly.
    final_id = _unique_page_id(derived_id, existing_ids)

    panel = _app_settings_store().load().panel
    w, h = panel.render_dimensions()
    page = Page(
        id=final_id,
        name=name,
        panel=Panel(w=w, h=h),
        cells=[Cell(id="cell-1", x=0, y=0, w=w, h=h, plugin="clock", options={})],
    )
    store.upsert(page)
    return jsonify(page.model_dump(mode="json", exclude_none=True)), 201


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
    # Saved state supersedes any in-flight preview draft.
    current_app.config.get("PREVIEW_CACHE", {}).pop(page_id, None)
    return jsonify(page.model_dump(mode="json", exclude_none=True))


@bp.delete("/api/pages/<page_id>")
def api_delete_page(page_id: str) -> tuple[str, int]:
    # Drop any preview cache entry too, in case it lingers.
    current_app.config.get("PREVIEW_CACHE", {}).pop(page_id, None)
    return ("", 204) if _store().delete(page_id) else ("", 404)


def _rotate_page(page: Page, *, direction: str = "cw") -> Page:
    """Rotate a Page 90°. Swaps panel dims and rotates every cell's coords
    so the layout stays coherent in the new orientation."""
    old_w, old_h = page.panel.w, page.panel.h
    rotated_cells: list[Cell] = []
    for c in page.cells:
        if direction == "cw":
            # 90° CW: (x, y) → (old_h - y - h, x); w/h swap.
            new_x = old_h - c.y - c.h
            new_y = c.x
        else:
            # 90° CCW: (x, y) → (y, old_w - x - w); w/h swap.
            new_x = c.y
            new_y = old_w - c.x - c.w
        rotated_cells.append(
            Cell(
                id=c.id,
                x=max(0, new_x),
                y=max(0, new_y),
                w=c.h,
                h=c.w,
                plugin=c.plugin,
                options=c.options,
                theme=c.theme,
                font=c.font,
            )
        )
    return Page(
        id=page.id,
        name=page.name,
        panel=Panel(w=old_h, h=old_w),
        theme=page.theme,
        font=page.font,
        gap=page.gap,
        corner_radius=page.corner_radius,
        cells=rotated_cells,
        icon=page.icon,
    )


def _scale_page(page: Page, target_w: int, target_h: int) -> Page:
    """Scale a Page's panel + cells to ``target_w × target_h``.

    Preserves layout proportionally — cells stay in the same relative spots
    and keep the same fractional sizes. Used when the user picks a panel
    with different native dimensions in settings.
    """
    if page.panel.w == target_w and page.panel.h == target_h:
        return page
    sx = target_w / page.panel.w
    sy = target_h / page.panel.h
    scaled_cells: list[Cell] = []
    for c in page.cells:
        scaled_cells.append(
            Cell(
                id=c.id,
                x=max(0, round(c.x * sx)),
                y=max(0, round(c.y * sy)),
                w=max(1, round(c.w * sx)),
                h=max(1, round(c.h * sy)),
                plugin=c.plugin,
                options=c.options,
                theme=c.theme,
                font=c.font,
            )
        )
    return Page(
        id=page.id,
        name=page.name,
        panel=Panel(w=target_w, h=target_h),
        theme=page.theme,
        font=page.font,
        gap=page.gap,
        corner_radius=page.corner_radius,
        cells=scaled_cells,
        icon=page.icon,
    )


def _align_pages_to_panel(store: PageStore, panel: PanelSettings) -> int:
    """Reshape every page so its panel + cells match the active panel
    settings. Handles both orientation flips (rotate cells 90°) and
    resolution changes (scale cells proportionally) — including both at
    once if the user switched from a 7.3" landscape to a 13.3" portrait
    in one settings save.

    Returns the count of pages migrated. Idempotent — pages already at
    the target dims are skipped.
    """
    target_w, target_h = panel.render_dimensions()
    target_landscape = target_w > target_h
    migrated = 0
    for page in store.all():
        if page.panel.w == target_w and page.panel.h == target_h:
            continue
        new_page = page
        # Step 1: rotate first if orientation differs, so the subsequent
        # scale operates on the right axis-aligned cells.
        page_landscape = new_page.panel.w > new_page.panel.h
        if page_landscape != target_landscape:
            direction = "cw" if not target_landscape else "ccw"
            new_page = _rotate_page(new_page, direction=direction)
        # Step 2: proportionally rescale cells to the target resolution.
        if (new_page.panel.w, new_page.panel.h) != (target_w, target_h):
            new_page = _scale_page(new_page, target_w, target_h)
        store.upsert(new_page)
        migrated += 1
    return migrated




@bp.post("/api/pages/<page_id>/rotate")
def api_rotate_page(page_id: str) -> tuple[Response, int] | Response:
    """Manual page rotation. Body (optional): ``{"direction": "cw" | "ccw"}``."""
    page = _store().get(page_id)
    if page is None:
        return jsonify({"error": "page not found"}), 404
    body = request.get_json(silent=True) or {}
    direction = body.get("direction", "cw")
    if direction not in ("cw", "ccw"):
        return jsonify({"error": "direction must be 'cw' or 'ccw'"}), 400
    rotated = _rotate_page(page, direction=direction)
    _store().upsert(rotated)
    current_app.config.get("PREVIEW_CACHE", {}).pop(page_id, None)
    return jsonify(rotated.model_dump(mode="json", exclude_none=True))


@bp.put("/api/pages/<page_id>/preview")
def api_stage_preview(page_id: str) -> tuple[Response, int] | tuple[str, int]:
    """Stage a draft Page in the in-memory preview cache so the editor's
    iframe at /compose/<page_id> reflects unsaved edits."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    body = {**body, "id": page_id}
    try:
        page = Page.model_validate(body)
    except ValidationError as err:
        return jsonify({"error": "validation", "details": err.errors()}), 400
    cache: dict[str, Page] = current_app.config.setdefault("PREVIEW_CACHE", {})
    cache[page_id] = page
    return ("", 204)


@bp.delete("/api/pages/<page_id>/preview")
def api_clear_preview(page_id: str) -> tuple[str, int]:
    current_app.config.get("PREVIEW_CACHE", {}).pop(page_id, None)
    return ("", 204)


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


@bp.get("/api/plugins/<plugin_id>/choices/<choice_name>")
def api_plugin_choices(plugin_id: str, choice_name: str) -> tuple[Response, int] | Response:
    """Dynamic dropdown values for ``cell_options[*].choices_from``.

    The plugin's ``server.py`` may export ``choices(name) -> list[{value, label}]``;
    we call it here so the editor can populate dropdowns whose contents change
    at runtime (e.g. gallery folders, available timezones)."""
    plugin = _registry().plugins.get(plugin_id)
    if plugin is None or plugin.server_module is None:
        return ("", 404)  # type: ignore[return-value]
    fn = getattr(plugin.server_module, "choices", None)
    if fn is None:
        return jsonify([])
    try:
        result = fn(choice_name)
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"{type(err).__name__}: {err}"}), 502
    return jsonify(result or [])


@bp.get("/api/plugins/admin-pages")
def api_plugin_admin_pages() -> Response:
    """List plugins that expose a Flask blueprint (an admin page).

    Used by id-nav's "Plugins" dropdown so the user can find /plugins/todo/
    etc. without typing URLs.
    """
    out: list[dict[str, Any]] = []
    for plugin_id, plugin in _registry().plugins.items():
        if plugin.server_module is None:
            continue
        if getattr(plugin.server_module, "blueprint", None) is None:
            continue
        icon = plugin.manifest.get("icon") or "ph-puzzle-piece"
        out.append(
            {
                "id": plugin_id,
                "name": plugin.name,
                "url": f"/plugins/{plugin_id}/",
                "icon": icon,
            }
        )
    return jsonify(sorted(out, key=lambda r: r["name"]))


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
    """Quantized PNG — what the panel will paint, viewed face-on. Composed
    at the page's dims (which already match the panel orientation thanks to
    auto-alignment). The MQTT pre-publish rotation is **not** applied here:
    the user wants to see content upright, not the rotated byte stream that
    gets shipped to the panel's landscape-native pixel grid."""
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


@bp.post("/api/pages/push-inline")
def api_push_page_inline() -> tuple[Response, int] | Response:
    """Render + push a Page object supplied in the request body, without persisting.

    The supplied page is staged under a transient id, pushed, then deleted —
    the user's saved page record is never touched. This is the back-end of
    the editor's "Send without saving" button.

    Body: ``{"page": <full Page JSON>, "dither"?: str, "rotate"?: int, ...}``
    """
    import uuid

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    page_dict = body.get("page")
    if not isinstance(page_dict, dict):
        return jsonify({"error": "page is required and must be an object"}), 400

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

    # Transient id — collision-free for the duration of this request.
    transient_id = f"_preview_{uuid.uuid4().hex[:12]}"
    page_dict = {**page_dict, "id": transient_id}
    try:
        page = Page.model_validate(page_dict)
    except ValidationError as err:
        return jsonify({"error": "validation", "details": err.errors()}), 400

    store = _store()
    store.upsert(page)
    try:
        result = _push_manager().push(
            transient_id, options=options, dither=cast_dither(dither_arg)
        )
    finally:
        store.delete(transient_id)

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
                "payload": r.payload,
                "topic": r.topic,
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


# --- Send-page previews -----------------------------------------------------
# Same source pipelines as /api/send/{type} but they short-circuit at the
# quantizer and return PNG bytes instead of going through PushManager.publish.
# The Send page calls these to show a "this is what gets pushed" preview before
# the user commits.


def _quantize_or_400(raw: bytes, dither_arg: str) -> tuple[bytes, str | None]:
    """Quantize raw render bytes for preview display. The pre-publish rotation
    that ships to MQTT is **not** applied — previews show the dashboard in
    its composition orientation (upright to the viewer). The push pipeline
    handles rotation separately when it actually sends to the panel."""
    if dither_arg not in _VALID_DITHER_MODES:
        return b"", f"invalid dither mode: {dither_arg!r}"
    try:
        return quantize_to_png(raw, dither=cast_dither(dither_arg)), None
    except Exception as err:  # noqa: BLE001
        return b"", f"quantize: {err}"


@bp.post("/api/send/preview/page")
def api_preview_page() -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) or {}
    page_id = body.get("page_id")
    if not page_id or not isinstance(page_id, str):
        return jsonify({"error": "page_id is required"}), 400
    page = _store().get(page_id)
    if page is None:
        return ("", 404)  # type: ignore[return-value]
    dither_arg = body.get("dither", "floyd-steinberg")
    compose_url = url_for("composer.compose", page_id=page_id, for_push=1, _external=True)
    try:
        raw = render_to_png(
            RenderRequest(url=compose_url, viewport_w=page.panel.w, viewport_h=page.panel.h)
        )
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"render: {err}"}), 502
    png, qerr = _quantize_or_400(raw, dither_arg)
    if qerr is not None:
        return jsonify({"error": qerr}), 400
    return Response(png, mimetype="image/png")


@bp.post("/api/send/preview/url")
def api_preview_url() -> tuple[Response, int] | Response:
    import urllib.request

    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must be an http(s) URL"}), 400
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"download: {err}"}), 502
    png, qerr = _quantize_or_400(raw, body.get("dither", "floyd-steinberg"))
    if qerr is not None:
        return jsonify({"error": qerr}), 400
    return Response(png, mimetype="image/png")


@bp.post("/api/send/preview/webpage")
def api_preview_webpage() -> tuple[Response, int] | Response:
    body = request.get_json(silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return jsonify({"error": "url must be an http(s) URL"}), 400
    viewport_w = int(body.get("viewport_w", 1600) or 1600)
    viewport_h = int(body.get("viewport_h", 1200) or 1200)
    try:
        raw = render_to_png(RenderRequest(url=url, viewport_w=viewport_w, viewport_h=viewport_h))
    except Exception as err:  # noqa: BLE001
        return jsonify({"error": f"render: {err}"}), 502
    png, qerr = _quantize_or_400(raw, body.get("dither", "floyd-steinberg"))
    if qerr is not None:
        return jsonify({"error": qerr}), 400
    return Response(png, mimetype="image/png")


@bp.post("/api/send/preview/file")
def api_preview_file() -> tuple[Response, int] | Response:
    if "file" not in request.files:
        return jsonify({"error": "expected a 'file' part"}), 400
    upload = request.files["file"]
    raw = upload.read()
    if not raw:
        return jsonify({"error": "file is empty"}), 400
    png, err = _quantize_or_400(raw, request.form.get("dither", "floyd-steinberg"))
    if err is not None:
        return jsonify({"error": err}), 400
    return Response(png, mimetype="image/png")


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


def _settings() -> SettingsStore:
    s: SettingsStore = current_app.config["SETTINGS_STORE"]
    return s


_SECRET_PLACEHOLDER = "•••"


def _app_settings_store() -> AppSettingsStore:
    s: AppSettingsStore = current_app.config["APP_SETTINGS_STORE"]
    return s


def _mask_password(settings: AppSettings) -> dict[str, Any]:
    """Serialize app settings with the password masked if it's set."""
    dumped = settings.model_dump(mode="json")
    if dumped.get("mqtt", {}).get("password"):
        dumped["mqtt"]["password"] = _SECRET_PLACEHOLDER
    return dumped


@bp.get("/settings")
def settings_page() -> str:
    return render_template("settings.html")


@bp.get("/api/app/settings")
def api_get_app_settings() -> Response:
    return jsonify(_mask_password(_app_settings_store().load()))


@bp.get("/api/app/panels")
def api_list_panels() -> Response:
    """Catalog of supported panels for the settings UI to populate a dropdown."""
    return jsonify(
        [
            {
                "id": panel_id,
                "label": spec.label,
                "width": spec.width,
                "height": spec.height,
                "palette": spec.palette,
            }
            for panel_id, spec in PANEL_MODELS.items()
        ]
    )


@bp.put("/api/app/settings")
def api_save_app_settings() -> tuple[Response, int] | Response:
    """Save app settings; hot-reload the MQTT bridge if the broker config changed."""
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400

    store = _app_settings_store()
    existing = store.load()

    # Don't clobber the existing password if the client sent the placeholder
    # or an empty string — same pattern as plugin secrets.
    mqtt_in = body.get("mqtt") or {}
    if isinstance(mqtt_in, dict):
        pw = mqtt_in.get("password")
        if pw == _SECRET_PLACEHOLDER or pw == "":
            mqtt_in.pop("password", None)
        body["mqtt"] = {**existing.mqtt.model_dump(), **mqtt_in}

    # Shallow-merge panel sub-object so partial updates (e.g. just orientation)
    # don't reset the panel model to default.
    panel_in = body.get("panel")
    if isinstance(panel_in, dict):
        body["panel"] = {**existing.panel.model_dump(), **panel_in}

    # Same for appearance (theme + accent often updated independently).
    appearance_in = body.get("appearance")
    if isinstance(appearance_in, dict):
        body["appearance"] = {**existing.appearance.model_dump(), **appearance_in}

    merged = {**existing.model_dump(), **body}

    try:
        new_settings = AppSettings.model_validate(merged)
    except ValidationError as err:
        details = [
            {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in err.errors()
        ]
        return jsonify({"error": "validation", "details": details}), 400

    store.save(new_settings)

    # Hot-reload: rebuild the bridge if MQTT config changed; update PushManager
    # base_url + topic + panel rotation in any case (idempotent).
    pm = _push_manager()
    pm.set_base_url(new_settings.base_url)
    pm.set_topic(new_settings.mqtt.topic_update)
    pm.set_rotate_quarters(new_settings.panel.rotate_quarters())

    # When the panel changes (orientation OR model — i.e. the active
    # resolution changed), every page must follow. The panel setting is
    # the source of truth; dashboards never override it.
    panel_changed = (
        existing.panel.orientation != new_settings.panel.orientation
        or existing.panel.model != new_settings.panel.model
    )
    if panel_changed:
        _align_pages_to_panel(_store(), new_settings.panel)
        # Drop any stale preview drafts that were keyed to the old dims.
        current_app.config.get("PREVIEW_CACHE", {}).clear()

    mqtt_changed = (
        new_settings.mqtt.host != existing.mqtt.host
        or new_settings.mqtt.port != existing.mqtt.port
        or new_settings.mqtt.username != existing.mqtt.username
        or new_settings.mqtt.password != existing.mqtt.password
        or new_settings.mqtt.topic_status != existing.mqtt.topic_status
        or new_settings.mqtt.client_id != existing.mqtt.client_id
    )
    if mqtt_changed:
        # Local import keeps app/__init__.py and admin.py free of a circular
        # reference at module load time.
        from app import build_bridge_from_settings

        new_bridge = build_bridge_from_settings(new_settings)
        pm.set_bridge(new_bridge)
        current_app.config["MQTT_BRIDGE"] = new_bridge

    return jsonify(_mask_password(new_settings))


@bp.get("/api/settings")
def api_list_settings() -> Response:
    """List every plugin that declares ``settings`` in its manifest, with
    current values. Secrets cross the wire as a placeholder + ``is_set`` flag —
    real values stay on the server."""
    registry = _registry()
    store = _settings()
    out: list[dict[str, Any]] = []
    for plugin_id, plugin in registry.plugins.items():
        decls = plugin.manifest.get("settings") or []
        if not decls:
            continue
        current = store.get(plugin_id)
        fields: list[dict[str, Any]] = []
        for d in decls:
            name = str(d["name"])
            secret = bool(d.get("secret", False))
            value = current.get(name)
            is_set = name in current and value not in (None, "")
            fields.append(
                {
                    "name": name,
                    "type": d.get("type", "string"),
                    "label": d.get("label", name),
                    "default": d.get("default"),
                    "choices": d.get("choices"),
                    "secret": secret,
                    "is_set": is_set,
                    "value": (_SECRET_PLACEHOLDER if secret and is_set else value),
                }
            )
        out.append(
            {
                "plugin_id": plugin_id,
                "plugin_name": plugin.name,
                "settings": fields,
            }
        )
    return jsonify(out)


@bp.put("/api/settings/<plugin_id>")
def api_save_settings(plugin_id: str) -> tuple[Response, int] | tuple[str, int]:
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "body must be a JSON object"}), 400
    plugin = _registry().plugins.get(plugin_id)
    if plugin is None:
        return ("", 404)

    decls = plugin.manifest.get("settings") or []
    decl_by_name = {str(d["name"]): d for d in decls}
    valid_names = set(decl_by_name)

    store = _settings()
    existing = store.get(plugin_id)
    merged: dict[str, Any] = dict(existing)
    for name, raw in body.items():
        if name not in valid_names:
            continue
        decl = decl_by_name[name]
        is_secret = bool(decl.get("secret", False))
        # Secrets: empty string or the placeholder means "leave unchanged".
        if is_secret and (raw == "" or raw == _SECRET_PLACEHOLDER):
            continue
        if decl.get("type") == "boolean":
            merged[name] = bool(raw)
        elif decl.get("type") == "number":
            try:
                merged[name] = float(raw) if raw not in (None, "") else None
            except (TypeError, ValueError):
                return jsonify({"error": f"{name} must be a number"}), 400
        else:
            merged[name] = raw
    store.set(plugin_id, merged)
    return ("", 204)


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


@bp.get("/api/listener/log")
def api_listener_log() -> Response:
    """Recent inky/status messages received from the panel listener,
    newest-first. Useful for debugging 'why isn't the panel updating?' —
    pair with /api/history (which shows what we sent on inky/update)."""
    return jsonify(
        [
            {
                "state": s.state,
                "received_at": s.received_at.isoformat(),
                "raw": s.raw,
            }
            for s in _bridge().status_log()
        ]
    )
