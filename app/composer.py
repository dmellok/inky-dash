"""Composer: builds the page that Playwright screenshots and the editor previews.

Reads pages from the file-backed ``PageStore``, resolves theme + font references
through the plugin registry, emits ``@font-face`` rules for every loaded font,
and renders one ``<div class="cell">`` per cell with its resolved palette
already applied as CSS custom properties (``--theme-*``).

For plugins that ship a ``server.py``, the composer calls ``fetch()`` and
embeds the result as ``data-data`` on the cell so client.js receives it via
``ctx.data``.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, abort, current_app, render_template, request

from app.plugin_loader import Font, PluginRegistry
from app.state import Page, PageStore

logger = logging.getLogger(__name__)

bp = Blueprint("composer", __name__)


SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "xs": (180, 180),
    "sm": (380, 240),
    "md": (640, 400),
    "lg": (1200, 800),
}


# Hardcoded fallback used only if themes_core is missing or fails to load.
_BUILTIN_DEFAULT_PALETTE: dict[str, str] = {
    "bg": "#fbf7f1",
    "surface": "#ffffff",
    "surface2": "#f5e8d8",
    "fg": "#1a1612",
    "fgSoft": "#5a4f44",
    "muted": "#8b7e70",
    "accent": "#d97757",
    "accentSoft": "#aa5a3f",
    "divider": "#d8c8a8",
    "danger": "#c97c70",
    "warn": "#d4a957",
    "ok": "#7da670",
}


def _registry() -> PluginRegistry:
    registry: PluginRegistry = current_app.config["PLUGIN_REGISTRY"]
    return registry


def _resolved_options(plugin_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    plugin = _registry().get(plugin_id)
    if plugin is None:
        return dict(raw)
    merged: dict[str, Any] = plugin.cell_option_defaults()
    merged.update(raw)
    return merged


def _resolve_palette(theme_id: str | None, registry: PluginRegistry) -> dict[str, str]:
    if theme_id:
        theme = registry.get_theme(theme_id)
        if theme is not None:
            return theme.palette
    fallback = registry.get_theme("default")
    if fallback is not None:
        return fallback.palette
    return dict(_BUILTIN_DEFAULT_PALETTE)


def _resolve_font(font_id: str | None, registry: PluginRegistry) -> Font | None:
    if font_id:
        font = registry.get_font(font_id)
        if font is not None:
            return font
    return registry.get_font("default")


def _font_face_css(fonts: dict[str, Font]) -> str:
    """Emit @font-face rules for every loaded font + weight."""
    rules: list[str] = []
    for font in fonts.values():
        for weight, url in font.files.items():
            rules.append(
                "@font-face { "
                f"font-family: '{font.name}'; "
                f"font-weight: {weight}; "
                f"src: url('{url}') format('woff2'); "
                "font-display: block; }"
            )
    return "\n".join(rules)


def _fetch_plugin_data(
    plugin_id: str,
    options: dict[str, Any],
    panel_w: int,
    panel_h: int,
    preview: bool,
) -> Any:
    """Call the plugin's server.py fetch() if present. Returns None on miss."""
    plugin = _registry().get(plugin_id)
    if plugin is None or plugin.server_module is None:
        return None
    fetch_fn = getattr(plugin.server_module, "fetch", None)
    if fetch_fn is None:
        return None
    settings_store = current_app.config["SETTINGS_STORE"]
    settings = settings_store.get(plugin_id)
    try:
        return fetch_fn(
            options,
            settings,
            ctx={
                "panel_w": panel_w,
                "panel_h": panel_h,
                "preview": preview,
                "data_dir": str(plugin.data_dir),
            },
        )
    except Exception as err:  # noqa: BLE001 — surface failure to the plugin
        logger.warning("plugin %s fetch() raised: %s", plugin_id, err)
        return {"error": f"{type(err).__name__}: {err}"}


def _hydrate_page(page_dict: dict[str, Any], *, preview: bool = False) -> dict[str, Any]:
    """Resolve options, themes, fonts, server-side data, and visual layout."""
    registry = _registry()
    page_palette = _resolve_palette(page_dict.get("theme"), registry)
    page_font = _resolve_font(page_dict.get("font"), registry)
    page_font_family = page_font.name if page_font else "system-ui"

    gap = int(page_dict.get("gap", 0) or 0)
    half_gap = gap // 2
    corner_radius = int(page_dict.get("corner_radius", 0) or 0)
    panel_w = int(page_dict["panel"]["w"])
    panel_h = int(page_dict["panel"]["h"])

    cells_out: list[dict[str, Any]] = []
    for cell in page_dict["cells"]:
        cell_palette = dict(
            _resolve_palette(cell["theme"], registry) if cell.get("theme") else page_palette
        )
        # Per-cell colour overrides win over the resolved theme. Hex values
        # are validated by the page schema; we trust whatever the editor saved.
        for token, hex_value in (cell.get("palette_overrides") or {}).items():
            if isinstance(hex_value, str) and hex_value:
                cell_palette[token] = hex_value
        cell_font = _resolve_font(cell["font"], registry) if cell.get("font") else page_font
        cell_font_family = cell_font.name if cell_font else page_font_family
        resolved_options = _resolved_options(cell["plugin"], cell.get("options", {}))
        plugin = registry.get(cell["plugin"])
        full_bleed = bool(
            plugin and plugin.manifest.get("render", {}).get("full_bleed")
        )
        cells_out.append(
            {
                **cell,
                "x": cell["x"] + half_gap,
                "y": cell["y"] + half_gap,
                "w": max(1, cell["w"] - half_gap * 2),
                "h": max(1, cell["h"] - half_gap * 2),
                "options": resolved_options,
                "data": _fetch_plugin_data(
                    cell["plugin"], resolved_options, panel_w, panel_h, preview
                ),
                "palette": cell_palette,
                "font_family": cell_font_family,
                "full_bleed": full_bleed,
            }
        )

    return {
        **page_dict,
        "cells": cells_out,
        "palette": page_palette,
        "font_family": page_font_family,
        "font_face_css": _font_face_css(registry.fonts),
        "corner_radius": corner_radius,
    }


@bp.get("/compose/<page_id>")
def compose(page_id: str) -> str:
    # An in-memory preview cache lets the editor show unsaved edits in the
    # iframe without persisting them. The cache is populated by
    # PUT /api/pages/<id>/preview and lives only in-process.
    preview_cache: dict[str, Page] = current_app.config.get("PREVIEW_CACHE", {})
    page = preview_cache.get(page_id)
    if page is None:
        store: PageStore = current_app.config["PAGE_STORE"]
        page = store.get(page_id)
    if page is None:
        abort(404)
    for_push = request.args.get("for_push") == "1"
    return render_template(
        "compose.html",
        page=_hydrate_page(
            page.model_dump(mode="json", exclude_none=True),
            preview=not for_push,
        ),
        for_push=for_push,
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
        "theme": "default",
        "font": "default",
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
        page=_hydrate_page(page, preview=True),
        for_push=False,
    )
