"""Headless-browser screenshot pipeline.

Wraps Playwright's sync API. The composer route ``/compose/<id>`` is the URL
the renderer points Chromium at; the screenshot of that URL is the raw input
to the gamut quantizer.

M3 launches a fresh browser per call (~1–2 s overhead). A long-lived
singleton is the obvious optimisation — punted until the latency bites in
the editor's preview loop.

mypy --strict applies to this module — see pyproject.toml.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DEFAULT_PANEL_W: Final[int] = 1600
DEFAULT_PANEL_H: Final[int] = 1200

WaitUntil = Literal["load", "domcontentloaded", "networkidle", "commit"]

_CHROMIUM_SIDECAR: Final[Path] = (
    Path(__file__).resolve().parent.parent / "data" / "core" / ".chromium"
)


def _chromium_launch_kwargs() -> dict[str, Any]:
    """Resolve the Chromium binary in order: ``INKY_DASH_CHROMIUM_PATH``
    env var → ``data/core/.chromium`` sidecar (written by install.sh
    when Playwright has no prebuilt for the host's OS+arch) → empty
    (Playwright uses its bundled binary)."""
    path = os.environ.get("INKY_DASH_CHROMIUM_PATH", "").strip()
    if not path:
        try:
            path = _CHROMIUM_SIDECAR.read_text().strip()
        except OSError:
            path = ""
    return {"executable_path": path} if path else {}


def to_loopback_url(url: str) -> str:
    """Rewrite the host portion of ``url`` to ``127.0.0.1`` while
    preserving the port + path + query.

    The renderer always runs in-process with Flask, so internal compose
    URLs (``/compose/<id>``, ``/api/.../preview.png``, …) should always
    resolve via loopback regardless of what the user set ``base_url``
    to. Two reasons:

    1. **Auth gate.** The single-password gate has a loopback bypass for
       ``/compose/<id>`` so the renderer can fetch dashboards without
       juggling a session cookie. If we send Playwright at the LAN-IP
       base_url, ``request.remote_addr`` is the host's LAN address and
       the bypass doesn't match — Playwright gets the login page and
       screenshots that instead of the dashboard.
    2. **Routing.** A LAN-IP round-trip leaves the loopback interface
       on some OS/network configs, adding latency for no gain.

    ``base_url`` is still used as-is for OUTBOUND URLs (HA image entity,
    public render links). This helper is for the IN-process renderer
    only.
    """
    parts = urlsplit(url)
    netloc = "127.0.0.1"
    if parts.port:
        netloc = f"127.0.0.1:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


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
        browser = playwright.chromium.launch(**_chromium_launch_kwargs())
        try:
            context = browser.new_context(
                viewport={"width": request.viewport_w, "height": request.viewport_h},
                device_scale_factor=1,
                color_scheme="light",
            )
            page = context.new_page()
            page.set_default_timeout(request.timeout_ms)
            # Best-effort ``networkidle``: a single widget that keeps a
            # connection open (long-poll, slow upstream API) shouldn't
            # take down the whole render. If ``networkidle`` doesn't fire
            # by ``timeout_ms`` we fall back to ``load`` — the DOM is
            # already laid out, and the font-wait below gives a second
            # settle point before screenshotting. Other ``wait_until``
            # values are honoured strictly (callers asked for them).
            if request.wait_until == "networkidle":
                try:
                    page.goto(request.url, wait_until="networkidle")
                except PlaywrightTimeoutError:
                    page.wait_for_load_state("load", timeout=request.timeout_ms)
            else:
                page.goto(request.url, wait_until=request.wait_until)
            # Block screenshot until every cell's font is actually loaded.
            # document.fonts.ready only awaits fonts already in the pending set;
            # explicit document.fonts.load() triggers the request and waits.
            # Plugins that measure text against the cell (clock, etc.) need
            # this — fallback metrics differ enough to blow up the layout.
            page.evaluate(
                """async () => {
                    if (!document.fonts || !document.fonts.load) return;
                    const families = new Set();
                    document.querySelectorAll('.cell').forEach((cell) => {
                        const ff = getComputedStyle(cell).fontFamily;
                        if (!ff) return;
                        const first = ff.split(',')[0].trim()
                            .replace(/^['\"]|['\"]$/g, '');
                        if (first) families.add(first);
                    });
                    const loads = [];
                    for (const family of families) {
                        for (const weight of [400, 500, 600, 700]) {
                            loads.push(
                                document.fonts.load(
                                    weight + ' 100px \"' + family + '\"'
                                ).catch(() => {})
                            );
                        }
                    }
                    await Promise.all(loads);
                    await document.fonts.ready;
                }"""
            )
            png: bytes = page.screenshot(
                full_page=False,
                type="png",
                animations="disabled",
                omit_background=False,
            )
            return png
        finally:
            browser.close()
