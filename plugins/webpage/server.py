"""Webpage widget — screenshot of an arbitrary URL.

Per the brief: "preview can't always use the same render path as push (some
sites refuse <iframe> embedding via X-Frame-Options)."

Strategy:
  - preview=True  → return only the URL; client.js attempts an <iframe>, with
                    a placeholder fallback if the load handler never fires.
  - preview=False → take a server-side screenshot via Playwright, base64-embed,
                    return as data URL; client.js renders an <img>.

The screenshot uses its own sync_playwright() context. This is "Playwright in
Playwright" (since fetch() runs inside the outer compose render's Playwright)
but it's two independent processes — they don't share state. Slow but works.
"""
from __future__ import annotations

import base64
import threading
import time
from typing import Any

_lock = threading.Lock()
_cache: dict[str, tuple[float, str]] = {}  # (url, w, h, wait, extra) → (ts, base64)
_TTL_S = 5 * 60


def _cache_key(url, w, h, wait, extra) -> str:
    return f"{url}|{w}x{h}|{wait}|{extra}"


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    url = (options.get("url") or "").strip()
    if not url:
        return {"error": "no URL set"}
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"error": "URL must start with http:// or https://"}

    try:
        extra_wait_ms = max(0, min(60000, int(options.get("extra_wait_ms") or 0)))
    except (TypeError, ValueError):
        extra_wait_ms = 0
    wait_until = options.get("wait_until") or "networkidle"
    if wait_until not in ("load", "networkidle"):
        wait_until = "networkidle"
    try:
        nav_timeout = max(1000, int(settings.get("WEBPAGE_DEFAULT_TIMEOUT_MS") or 30000))
    except (TypeError, ValueError):
        nav_timeout = 30000

    if preview:
        # Live iframe path — let the client try and fall back if X-Frame-Options blocks.
        return {
            "mode": "iframe",
            "url": url,
            "extra_wait_ms": extra_wait_ms,
        }

    # Push path — server-side screenshot. Cell dims aren't known here (the
    # composer doesn't pass them through fetch yet); use the panel dims as a
    # ceiling. For tighter fidelity we'd need to plumb cell w/h into fetch.
    cw, ch = panel_w, panel_h
    key = _cache_key(url, cw, ch, wait_until, extra_wait_ms)
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] < _TTL_S:
            return {"mode": "image", "img": f"data:image/png;base64,{hit[1]}"}

    try:
        from playwright.sync_api import sync_playwright, Error as PlaywrightError
    except ImportError as exc:
        return {"error": f"playwright not installed: {exc}"}

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                ctx = browser.new_context(
                    viewport={"width": cw, "height": ch},
                    device_scale_factor=1,
                )
                page = ctx.new_page()
                page.goto(url, wait_until=wait_until, timeout=nav_timeout)
                if extra_wait_ms > 0:
                    page.wait_for_timeout(extra_wait_ms)
                png_bytes = page.screenshot(
                    clip={"x": 0, "y": 0, "width": cw, "height": ch},
                    type="png",
                )
                ctx.close()
            finally:
                browser.close()
    except PlaywrightError as exc:
        return {"error": f"render failed: {exc}"}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    encoded = base64.b64encode(png_bytes).decode("ascii")
    with _lock:
        _cache[key] = (now, encoded)
    return {"mode": "image", "img": f"data:image/png;base64,{encoded}"}
