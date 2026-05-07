"""Capture marketing screenshots for the README.

Two categories of shot:

  1. Admin UI pages (home / editor / schedules / send / theme builder).
     Captured at a desktop viewport (1400×900); these are normal web
     pages and adapt to the viewport.

  2. Rendered dashboards. We open the dashboard editor at /dashboards/
     <id>/edit and screenshot just the preview-frame-wrap element on
     the right — it auto-scales the panel rendering to fit the column,
     giving a web-friendly thumbnail without the cropping that hits a
     direct /compose capture (the composer renders at panel native
     pixels which are taller than any sane README image).

Outputs go to docs/screenshots/. The README links them by name, so
re-running this script and committing the new PNGs is the refresh
process.

Run with the dev server already up on :5555:

  .venv/bin/python tools/screenshot.py
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright


BASE = "http://127.0.0.1:5555"
OUT = Path("docs/screenshots")


# Admin UI pages — desktop viewport, full page captures.
UI_PAGES = [
    ("home",            "/",                                "Dashboard list"),
    ("editor",          "/dashboards/morning/edit",         "Dashboard editor"),
    ("send",            "/send",                            "Send page"),
    ("schedules",       "/schedules",                       "Schedules page"),
    ("theme-builder",   "/plugins/theme_builder/",          "Theme builder"),
    ("settings",        "/settings",                        "Settings"),
    ("widgets",         "/widgets",                         "Plugins / widgets"),
]

# Dashboards — captured at panel native size.
DASHBOARDS = [
    ("dash-morning",     "morning",      "Morning"),
    ("dash-glance",      "glance",       "Glance"),
    ("dash-night-sky",   "night-sky",    "Night Sky"),
    ("dash-year-pulse",  "year-pulse",   "Year Pulse"),
    ("dash-earth-pulse", "earth-pulse",  "Earth Pulse"),
    ("dash-outdoors",    "outdoors",     "Outdoors"),
    ("dash-planner",     "planner",      "Planner"),
    ("dash-finance",     "finance",      "Finance"),
]


async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # ---- admin UI ----
        ui_ctx = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            device_scale_factor=2,  # crisper text on retina readers
            color_scheme="light",
        )
        ui_page = await ui_ctx.new_page()
        for slug, path, label in UI_PAGES:
            url = f"{BASE}{path}"
            try:
                await ui_page.goto(url, wait_until="networkidle", timeout=15_000)
                # Small settle for any async lists rendering after networkidle.
                await ui_page.wait_for_timeout(800)
            except Exception as exc:
                print(f"  ! UI {slug}: {exc}")
                continue
            out = OUT / f"{slug}.png"
            await ui_page.screenshot(path=str(out), full_page=False)
            print(f"  ✓ UI {slug:14} → {out}")
        await ui_ctx.close()

        # ---- dashboards via the editor's preview pane ----
        # The editor scales the panel render to fit the right column.
        # We screenshot just the preview-frame-wrap div so the image
        # comes out web-friendly without us doing any resizing — and
        # without the cropping you'd get from a direct /compose capture
        # at panel native pixels.
        dash_ctx = await browser.new_context(
            viewport={"width": 1600, "height": 1100},
            device_scale_factor=2,
            color_scheme="light",
        )
        dash_page = await dash_ctx.new_page()
        for slug, page_id, label in DASHBOARDS:
            url = f"{BASE}/dashboards/{page_id}/edit"
            try:
                await dash_page.goto(url, wait_until="networkidle", timeout=20_000)
                # Wait for the preview iframe to actually paint —
                # composer.js loads the page config, builds cells, then
                # each widget fetches data + renders. networkidle alone
                # isn't enough; give the post-init renders a beat.
                await dash_page.wait_for_selector(
                    "#preview-frame-wrap iframe", state="attached", timeout=10_000
                )
                await dash_page.wait_for_timeout(2200)
            except Exception as exc:
                print(f"  ! dash {slug}: {exc}")
                continue
            try:
                preview = dash_page.locator("#preview-frame-wrap")
                out = OUT / f"{slug}.png"
                await preview.screenshot(path=str(out))
                print(f"  ✓ dash {slug:18} → {out}")
            except Exception as exc:
                print(f"  ! dash {slug}: locator screenshot: {exc}")
        await dash_ctx.close()

        await browser.close()
    print(f"[screens] done → {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
