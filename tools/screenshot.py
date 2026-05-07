"""Capture marketing screenshots for the README.

Two categories of shot:

  1. Admin UI pages (home / editor / schedules / send / theme builder).
     Captured at a desktop viewport (1400×900); these are normal web
     pages and adapt to the viewport.

  2. Rendered dashboards via /compose/<page_id>. Captured at the panel's
     native pixel size — for the dev's panel that's 1200×1600 portrait.
     GitHub renders these scaled-down in the README.

Outputs go to docs/screenshots/. The README links them by name, so
re-running this script and committing the new PNGs is the refresh
process.

Run with the dev server already up on :5555:

  .venv/bin/python tools/screenshot.py
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright


BASE = "http://127.0.0.1:5555"
OUT = Path("docs/screenshots")


def _config_panel() -> tuple[int, int]:
    """Read panel size from /api/status so the screenshots match the
    user's actual panel resolution rather than a hardcoded guess."""
    try:
        with urllib.request.urlopen(f"{BASE}/api/status", timeout=5) as r:
            body = json.loads(r.read())
        w = int(body.get("panel_width") or 800)
        h = int(body.get("panel_height") or 480)
    except Exception:
        w, h = 1200, 1600
    return w, h


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
    panel_w, panel_h = _config_panel()
    print(f"[screens] panel size = {panel_w}×{panel_h}")
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

        # ---- dashboards via /compose ----
        dash_ctx = await browser.new_context(
            viewport={"width": panel_w, "height": panel_h},
            device_scale_factor=1,
            color_scheme="light",
        )
        dash_page = await dash_ctx.new_page()
        for slug, page_id, label in DASHBOARDS:
            url = f"{BASE}/compose/{page_id}?preview=1"
            try:
                await dash_page.goto(url, wait_until="networkidle", timeout=20_000)
                # Widgets (charts especially) finish painting after the
                # initial network-idle tick — give them a beat.
                await dash_page.wait_for_timeout(1500)
            except Exception as exc:
                print(f"  ! dash {slug}: {exc}")
                continue
            out = OUT / f"{slug}.png"
            await dash_page.screenshot(
                path=str(out),
                clip={"x": 0, "y": 0, "width": panel_w, "height": panel_h},
            )
            print(f"  ✓ dash {slug:18} → {out}")
        await dash_ctx.close()

        await browser.close()
    print(f"[screens] done → {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
