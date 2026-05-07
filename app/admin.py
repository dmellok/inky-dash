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

from app.plugin_loader import PluginRegistry
from app.quantizer import DitherMode, quantize_to_png
from app.renderer import RenderRequest, render_to_png
from app.state import Page, PageStore

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
    return jsonify([p.model_dump(mode="json") for p in _store().all()])


@bp.get("/api/pages/<page_id>")
def api_get_page(page_id: str) -> Response:
    page = _store().get(page_id)
    if page is None:
        abort(404)
    return jsonify(page.model_dump(mode="json"))


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
    return jsonify(page.model_dump(mode="json"))


@bp.delete("/api/pages/<page_id>")
def api_delete_page(page_id: str) -> tuple[str, int]:
    return ("", 204) if _store().delete(page_id) else ("", 404)


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
    compose_url = url_for(
        "composer.compose", page_id=page_id, for_push=1, _external=True
    )
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
