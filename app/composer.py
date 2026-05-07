"""Composer: builds the page that Playwright screenshots and the editor previews.

Reads pages from the file-backed ``PageStore``, resolves theme + font references
through the plugin registry, emits ``@font-face`` rules for every loaded font,
and renders one ``<div class="cell">`` per cell with its resolved palette
already applied as CSS custom properties (``--theme-*``).
"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, abort, current_app, render_template, request

from app.plugin_loader import Font, PluginRegistry
from app.state import PageStore

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


def _hydrate_page(page_dict: dict[str, Any]) -> dict[str, Any]:
    """Resolve options, themes, fonts, and visual layout (gap + corner_radius).

    The page model stores raw cell xywh; the gap is applied here so the inner
    coordinates the template renders match the picker's click targets.
    """
    registry = _registry()
    page_palette = _resolve_palette(page_dict.get("theme"), registry)
    page_font = _resolve_font(page_dict.get("font"), registry)
    page_font_family = page_font.name if page_font else "system-ui"

    gap = int(page_dict.get("gap", 0) or 0)
    half_gap = gap // 2
    corner_radius = int(page_dict.get("corner_radius", 0) or 0)

    cells_out: list[dict[str, Any]] = []
    for cell in page_dict["cells"]:
        cell_palette = (
            _resolve_palette(cell["theme"], registry) if cell.get("theme") else page_palette
        )
        cell_font = _resolve_font(cell["font"], registry) if cell.get("font") else page_font
        cell_font_family = cell_font.name if cell_font else page_font_family
        cells_out.append(
            {
                **cell,
                "x": cell["x"] + half_gap,
                "y": cell["y"] + half_gap,
                "w": max(1, cell["w"] - half_gap * 2),
                "h": max(1, cell["h"] - half_gap * 2),
                "options": _resolved_options(cell["plugin"], cell.get("options", {})),
                "palette": cell_palette,
                "font_family": cell_font_family,
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
    store: PageStore = current_app.config["PAGE_STORE"]
    page = store.get(page_id)
    if page is None:
        abort(404)
    return render_template(
        "compose.html",
        page=_hydrate_page(page.model_dump(mode="json", exclude_none=True)),
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
        page=_hydrate_page(page),
        for_push=False,
    )
