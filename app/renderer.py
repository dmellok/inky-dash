"""Headless-browser screenshot pipeline.

Wraps Playwright's sync API. The composer route ``/compose/<id>`` is the URL
the renderer points Chromium at; the screenshot of that URL is the raw input
to the gamut quantizer.

M3 launches a fresh browser per call (~1–2 s overhead). A long-lived
singleton is the obvious optimisation — punted until the latency bites in
the editor's preview loop.

mypy --strict applies to this module per v4-brief §6.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from playwright.sync_api import sync_playwright

DEFAULT_PANEL_W: Final[int] = 1600
DEFAULT_PANEL_H: Final[int] = 1200

WaitUntil = Literal["load", "domcontentloaded", "networkidle", "commit"]


@dataclass(frozen=True)
class RenderRequest:
    url: str
    viewport_w: int = DEFAULT_PANEL_W
    viewport_h: int = DEFAULT_PANEL_H
    timeout_ms: int = 15_000
    wait_until: WaitUntil = "networkidle"


def render_to_png(request: RenderRequest) -> bytes:
    """Open the URL in headless Chromium and return a PNG screenshot.

    The browser viewport matches the request's viewport_w/h exactly so the
    screenshot is pixel-equal to what the panel will receive (after the
    quantizer projects to gamut).
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": request.viewport_w, "height": request.viewport_h},
                device_scale_factor=1,
                color_scheme="light",
            )
            page = context.new_page()
            page.set_default_timeout(request.timeout_ms)
            page.goto(request.url, wait_until=request.wait_until)
            png: bytes = page.screenshot(
                full_page=False,
                type="png",
                animations="disabled",
                omit_background=False,
            )
            return png
        finally:
            browser.close()
