from __future__ import annotations

import base64
import threading
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
)

from config import Config
from plugin_loader import FontEntry, PluginRegistry
from state.pages import (
    DraftStore,
    HEADER_HEIGHT_PX,
    LAYOUTS,
    Page,
    PageStore,
    layout_cell_count,
    slugify,
)


# Process-wide cache of base64-encoded woff2 payloads.
# Key: (plugin_id, weight, src_path) — invalidated naturally by plugin_id.
_FONT_CACHE: dict[tuple[str, str, str], str] = {}
_FONT_CACHE_LOCK = threading.Lock()


def _encode_font(plugin_path: Path, src_rel: str) -> str | None:
    """Read `plugin_path/src_rel` and return its base64-encoded contents.

    Cached process-wide. Returns None if the file is missing.
    """
    abs_path = (plugin_path / src_rel).resolve()
    cache_key = ("@", "@", str(abs_path))
    with _FONT_CACHE_LOCK:
        cached = _FONT_CACHE.get(cache_key)
        if cached is not None:
            return cached
    try:
        data = abs_path.read_bytes()
    except OSError:
        return None
    encoded = base64.b64encode(data).decode("ascii")
    with _FONT_CACHE_LOCK:
        _FONT_CACHE[cache_key] = encoded
    return encoded

# Fallback palette used when no theme plugin is loaded yet (stage 10 lands themes_core).
# Keys mirror the contract from v3-plugins.md (themes_core).
FALLBACK_PALETTE: dict[str, str] = {
    "bg": "#fafaf6",
    "surface": "#ffffff",
    "surface-2": "#f0eee8",
    "fg": "#1a140d",
    "fg-soft": "#4a4a4a",
    "muted": "#7a7a7a",
    "accent": "#2b6cb0",
    "accent-soft": "#dde7f2",
    "divider": "#e2e0d9",
    "danger": "#c53030",
    "warn": "#b7791f",
    "ok": "#2f855a",
}


def _resolve_palette(theme_id: str | None, registry: PluginRegistry) -> dict[str, str]:
    if theme_id:
        t = registry.theme(theme_id)
        if t:
            return dict(t.palette)
    light = registry.theme("light")
    if light:
        return dict(light.palette)
    return dict(FALLBACK_PALETTE)


def _font_view(font_id: str | None, registry: PluginRegistry) -> dict[str, Any]:
    f: FontEntry | None = None
    if font_id:
        f = registry.font(font_id)
    if f is None:
        f = registry.font("system")
    if f is None:
        return {
            "id": "system",
            "family": "system-ui",
            "fallback_stack": "system-ui, sans-serif",
            "is_system": True,
            "embedded_faces": [],
        }
    # Resolve the plugin's path so we can read the woff2 files for embedding.
    embedded_faces: list[dict[str, str]] = []
    if not f.is_system:
        plugin = registry.plugins.get(f.source_plugin)
        if plugin:
            for weight, src_rel in f.weights.items():
                payload = _encode_font(plugin.path, src_rel)
                if payload is None:
                    continue
                # data:font/woff2;base64,... inlined into the rendered HTML so
                # Playwright doesn't have to re-download woff2s on every render
                # (the brief calls this out — `set_content` loads about:blank
                # and our HTTP-fetched compose route gets a fresh context per
                # push, so caching across renders helps).
                embedded_faces.append({
                    "weight": str(weight),
                    "data_url": f"data:font/woff2;base64,{payload}",
                })
    return {
        "id": f.id,
        "family": f.family,
        "fallback_stack": f.fallback_stack,
        "is_system": f.is_system,
        "embedded_faces": embedded_faces,
    }


def _page_view(
    page: Page,
    registry: PluginRegistry,
    *,
    panel_w: int,
    panel_h: int,
    data_url_base: str,
    is_draft: bool = False,
) -> dict[str, Any]:
    layout_rects = LAYOUTS.get(page.layout, LAYOUTS["single"])
    if len(page.cells) > len(layout_rects):
        cells = page.cells[: len(layout_rects)]
    else:
        cells = list(page.cells)

    cells_view: list[dict[str, Any]] = []
    for i, cell in enumerate(cells):
        plugin = registry.plugins.get(cell.widget)
        is_widget = bool(plugin and "widget" in plugin.kinds)
        cells_view.append(
            {
                "index": i,
                "widget_id": cell.widget,
                "widget_label": (
                    plugin.manifest.label if plugin else cell.widget
                ),
                "options": dict(cell.options),
                "theme": _resolve_palette(cell.theme or page.theme, registry),
                "rect": [layout_rects[i].x, layout_rects[i].y,
                         layout_rects[i].w, layout_rects[i].h],
                "client_js_url": (
                    f"/plugins/{cell.widget}/client.js"
                    if plugin and plugin.has_client_js else None
                ),
                "client_css_url": (
                    f"/plugins/{cell.widget}/client.css"
                    if plugin and plugin.has_client_css else None
                ),
                "missing": plugin is None,
                "is_widget": is_widget,
                "enabled": (
                    is_widget and registry.is_enabled(cell.widget)
                ),
                # Image widgets opt into edge-to-edge rendering by setting
                # `full_bleed: true` in their plugin.json — composer.js then
                # drops the inner cell padding so the image fills the cell.
                "full_bleed": bool(plugin and getattr(plugin.manifest, "full_bleed", False)),
            }
        )

    has_header = len(cells) > 1
    return {
        "id": page.id,
        "name": page.name,
        "icon": page.icon,
        "layout": page.layout,
        "panel": [panel_w, panel_h],
        "cell_gap": page.cell_gap,
        "cell_radius": page.cell_radius,
        "bg_color": page.bg_color,
        "header_height": HEADER_HEIGHT_PX if has_header else 0,
        "header_theme": _resolve_palette(
            page.header_theme or page.theme, registry
        ),
        "page_theme": _resolve_palette(page.theme, registry),
        "single_cell": not has_header,
        "data_url_base": data_url_base,
        "is_draft": is_draft,
        "cells": cells_view,
    }


def _cell_data_payload(
    page: Page,
    cell_index: int,
    *,
    preview: bool,
) -> tuple[dict[str, Any], int]:
    if not (0 <= cell_index < len(page.cells)):
        return {"error": "cell index out of range"}, 404
    cfg: Config = current_app.config["INKY"]
    registry: PluginRegistry = current_app.config["PLUGINS"]
    cell = page.cells[cell_index]
    palette = _resolve_palette(cell.theme or page.theme, registry)

    plugin = registry.plugins.get(cell.widget)
    if plugin is None:
        return ({
            "data": {},
            "theme": palette,
            "options": dict(cell.options),
            "missing": True,
        }, 200)
    if not registry.is_enabled(cell.widget):
        return ({
            "data": {},
            "theme": palette,
            "options": dict(cell.options),
            "disabled": True,
        }, 200)
    if "widget" not in plugin.kinds:
        return ({
            "data": {},
            "theme": palette,
            "options": dict(cell.options),
            "not_a_widget": True,
        }, 200)

    try:
        data = registry.fetch_widget_data(
            cell.widget,
            dict(cell.options),
            panel_w=cfg.panel_width,
            panel_h=cfg.panel_height,
            preview=preview,
        )
    except Exception as exc:
        return ({
            "data": {},
            "theme": palette,
            "options": dict(cell.options),
            "error": f"{type(exc).__name__}: {exc}",
        }, 200)

    return ({
        "data": data,
        "theme": palette,
        "options": dict(cell.options),
    }, 200)


def make_blueprint(store: PageStore, drafts: DraftStore) -> Blueprint:
    bp = Blueprint("composer", __name__)

    # ---------- /api/pages CRUD ----------

    @bp.get("/api/pages")
    def list_pages():
        return jsonify({"pages": [p.to_json() for p in store.list()]})

    @bp.get("/api/pages/<page_id>")
    def get_page(page_id):
        p = store.get(page_id)
        if not p:
            abort(404)
        return jsonify(p.to_json())

    @bp.post("/api/pages")
    def create_page():
        try:
            data = request.get_json(force=True) or {}
            if not data.get("id"):
                data["id"] = store.unique_slug(data.get("name", "page"))
            page = Page.from_json(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        store.upsert(page)
        return jsonify(page.to_json()), 201

    @bp.post("/api/pages/<page_id>/duplicate")
    def duplicate_page(page_id):
        original = store.get(page_id)
        if not original:
            abort(404)
        new_id = store.unique_slug(f"{original.id}-copy")
        copy = Page.from_json(original.to_json())
        copy.id = new_id
        copy.name = f"{original.name} (copy)"
        store.upsert(copy)
        return jsonify(copy.to_json()), 201

    @bp.put("/api/pages/<page_id>")
    def update_page(page_id):
        try:
            data = request.get_json(force=True) or {}
            data["id"] = page_id
            page = Page.from_json(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        store.upsert(page)
        return jsonify(page.to_json())

    @bp.delete("/api/pages/<page_id>")
    def delete_page(page_id):
        if not store.delete(page_id):
            abort(404)
        return ("", 204)

    # ---------- drafts ----------

    @bp.post("/api/preview-page-draft")
    def post_draft():
        data = request.get_json(force=True) or {}
        # Drafts may not have an id yet; coerce so validation passes.
        if "id" not in data:
            data["id"] = "_draft"
        if "name" not in data:
            data["name"] = "Draft"
        try:
            Page.from_json(data)  # validate shape
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        draft_id = drafts.put(data)
        return jsonify({"draft_id": draft_id})

    # ---------- composer route (preview + push share this) ----------

    def _render(page: Page, *, data_url_base: str, is_draft: bool):
        cfg: Config = current_app.config["INKY"]
        registry: PluginRegistry = current_app.config["PLUGINS"]
        view = _page_view(
            page, registry,
            panel_w=cfg.panel_width, panel_h=cfg.panel_height,
            data_url_base=data_url_base, is_draft=is_draft,
        )
        # Single global font for the whole app — set in the theme builder
        # sidebar. `page.font` is still honoured if hand-set in JSON (escape
        # hatch); no UI surfaces it.
        prefs = current_app.config.get("PREFERENCES")
        effective_font = page.font
        if not effective_font and prefs is not None:
            effective_font = prefs.get_default_font()
        font = _font_view(effective_font, registry)
        # Body font-weight override — only emitted when not the default (400).
        # Widgets that hardcode their own weights (display-bold hero numbers,
        # uppercase labels) still win; everything else inherits from body.
        font_weight = prefs.get_font_weight() if prefs is not None else 400
        return render_template(
            "composer.html",
            view=view,
            font=font,
            font_weight=font_weight,
        )

    @bp.get("/compose/<page_id>")
    def compose_page(page_id):
        p = store.get(page_id)
        if not p:
            abort(404)
        return _render(p, data_url_base=f"/api/cell-data/{page_id}", is_draft=False)

    @bp.get("/compose/draft/<draft_id>")
    def compose_draft(draft_id):
        data = drafts.get(draft_id)
        if not data:
            abort(404)
        try:
            page = Page.from_json(data)
        except Exception:
            abort(400)
        return _render(
            page,
            data_url_base=f"/api/cell-data/draft/{draft_id}",
            is_draft=True,
        )

    # ---------- per-cell data ----------

    @bp.get("/api/cell-data/<page_id>/<int:cell_index>")
    def cell_data(page_id, cell_index):
        page = store.get(page_id)
        if not page:
            abort(404)
        preview = request.args.get("preview") == "1"
        body, status = _cell_data_payload(page, cell_index, preview=preview)
        return jsonify(body), status

    @bp.get("/api/cell-data/draft/<draft_id>/<int:cell_index>")
    def cell_data_draft(draft_id, cell_index):
        data = drafts.get(draft_id)
        if not data:
            abort(404)
        try:
            page = Page.from_json(data)
        except Exception:
            abort(400)
        preview = request.args.get("preview") == "1"
        body, status = _cell_data_payload(page, cell_index, preview=preview)
        return jsonify(body), status

    # ---------- introspection ----------

    @bp.get("/api/layouts")
    def list_layouts():
        return jsonify({
            name: [{"x": r.x, "y": r.y, "w": r.w, "h": r.h} for r in rects]
            for name, rects in LAYOUTS.items()
        })

    return bp
