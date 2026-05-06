from __future__ import annotations

from pathlib import Path


class RenderError(Exception):
    """Raised when the composer fails to render or signal readiness."""


def render_url_to_png(
    url: str,
    *,
    panel_w: int,
    panel_h: int,
    output_path: Path,
    extra_wait_ms: int = 0,
    wait_until: str = "networkidle",
    nav_timeout_ms: int = 30000,
) -> None:
    """Render an arbitrary external URL via Playwright.

    Used by the Send page's 'From webpage' source. Unlike `render_to_png`
    (which expects a composer page that signals `__inkyReady`), this one
    waits on Playwright's page-load lifecycle plus an optional extra delay.
    """
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError  # type: ignore
    except ImportError as exc:
        raise RenderError(
            "playwright is not installed. "
            "Run: pip install playwright && playwright install chromium"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": panel_w, "height": panel_h},
                device_scale_factor=1,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until=wait_until, timeout=nav_timeout_ms)
            except PlaywrightError as exc:
                raise RenderError(f"navigation failed: {exc}") from exc
            if extra_wait_ms > 0:
                page.wait_for_timeout(extra_wait_ms)
            page.screenshot(
                path=str(output_path),
                clip={"x": 0, "y": 0, "width": panel_w, "height": panel_h},
                type="png",
                omit_background=False,
            )
            context.close()
        finally:
            browser.close()


def render_to_png(
    url: str,
    *,
    panel_w: int,
    panel_h: int,
    output_path: Path,
    ready_timeout_ms: int = 30000,
    nav_timeout_ms: int = 30000,
) -> None:
    """Drive headless Chromium through the composer and dump a PNG.

    The composer signals readiness via `window.__inkyReady`; this function
    waits for that flag, then screenshots at exact panel dimensions (DPR=1
    so the PNG is byte-aligned to the panel's pixel grid).
    """
    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError  # type: ignore
    except ImportError as exc:
        raise RenderError(
            "playwright is not installed. "
            "Run: pip install playwright && playwright install chromium"
        ) from exc

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = browser.new_context(
                viewport={"width": panel_w, "height": panel_h},
                device_scale_factor=1,
            )
            page = context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=nav_timeout_ms)
            except PlaywrightError as exc:
                raise RenderError(f"navigation failed: {exc}") from exc

            try:
                page.wait_for_function(
                    "window.__inkyReady === true", timeout=ready_timeout_ms
                )
            except PlaywrightError as exc:
                raise RenderError(
                    f"composer never signalled __inkyReady within "
                    f"{ready_timeout_ms}ms: {exc}"
                ) from exc

            page.screenshot(
                path=str(output_path),
                clip={"x": 0, "y": 0, "width": panel_w, "height": panel_h},
                type="png",
                omit_background=False,
            )
            context.close()
        finally:
            browser.close()
