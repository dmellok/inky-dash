"""Composer: builds the page that Playwright screenshots and the editor previews.

Reads pages from the file-backed ``PageStore`` (data/core/pages.json). The
demo page is seeded on first run by ``create_app``. ``/_test/render`` mounts
a single plugin at a chosen breakpoint without persisting anything.
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, render_template, request

from app.plugin_loader import PluginRegistry
from app.state import PageStore

bp = Blueprint("composer", __name__)


SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "xs": (180, 180),
    "sm": (380, 240),
    "md": (640, 400),
    "lg": (1200, 800),
}


def _resolved_options(plugin_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Merge plugin-defined defaults with the cell's overrides."""
    registry: PluginRegistry = current_app.config["PLUGIN_REGISTRY"]
    plugin = registry.get(plugin_id)
    if plugin is None:
        return dict(raw)
    merged: dict[str, Any] = plugin.cell_option_defaults()
    merged.update(raw)
    return merged


def _hydrated_page(page: dict[str, Any]) -> dict[str, Any]:
    """Return a page dict with each cell's ``options`` filled with plugin defaults."""
    return {
        **page,
        "cells": [
            {**cell, "options": _resolved_options(cell["plugin"], cell.get("options", {}))}
            for cell in page["cells"]
        ],
    }


@bp.get("/compose/<page_id>")
def compose(page_id: str) -> str:
    store: PageStore = current_app.config["PAGE_STORE"]
    page = store.get(page_id)
    if page is None:
        abort(404)
    return render_template(
        "compose.html",
        page=_hydrated_page(page.model_dump(mode="json")),
        for_push=request.args.get("for_push") == "1",
    )


@bp.get("/_test/render")
def test_render() -> str:
    """Test-mode route: mount one plugin into a known cell size.

    Available when the app is in debug or testing mode. The smoke-test pattern
    in v4-plugins.md relies on this route.
    """
    if not (current_app.debug or current_app.testing):
        abort(404)

    plugin_id = request.args.get("plugin")
    if not plugin_id:
        abort(400)

    size = request.args.get("size", "md")
    if size not in SIZE_DIMENSIONS:
        abort(400)

    cell_w, cell_h = SIZE_DIMENSIONS[size]
    page = {
        "id": "_test",
        "name": f"Test: {plugin_id} @ {size}",
        "panel": {"w": cell_w, "h": cell_h},
        "cells": [
            {
                "id": "test-cell",
                "x": 0,
                "y": 0,
                "w": cell_w,
                "h": cell_h,
                "plugin": plugin_id,
                "options": {},
            }
        ],
    }
    return render_template(
        "compose.html",
        page=_hydrated_page(page),
        for_push=False,
    )
