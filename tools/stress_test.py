"""Render every loaded widget at every Inky-Impression-relevant cell
size and screenshot the result. Generates STRESS_REPORT.md alongside.

Run from the repo root with the dev server already up on :5555:

  .venv/bin/python tools/stress_test.py

The script:
  - Hits /api/plugins to enumerate widget kinds (skips theme/font/admin
    plugins and disabled ones).
  - For each widget, walks a fixed list of (label, w, h) cell sizes that
    cover the Inky Impression range (4" / 5.7" / 7.3" / 13.3", landscape
    + portrait, plus the cropped cell sizes from stack/grid/hero layouts).
  - Loads /widget-stress for each combo, waits for body[data-ready], and
    crops a screenshot to exactly the cell rect.
  - Records overflow signal for each shadow-root descendant (any element
    whose right/bottom rect exceeds the cell rect) — so the report can
    flag which sizes break.
  - Writes screenshots to renders/stress/ and a markdown report to
    STRESS_REPORT.md.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright


BASE = "http://127.0.0.1:5555"
OUT_DIR = Path("renders/stress")
REPORT = Path("STRESS_REPORT.md")


# Cell-size matrix covering the Inky Impression range.
# (label, width, height, source) — source is just for the report.
SIZES: list[tuple[str, int, int, str]] = [
    ("strip-mini",   200,  100, "smallest possible cell (stack_3 on 4\" portrait)"),
    ("grid-4in",     320,  200, "grid_2x2 on 4\""),
    ("med-square",   400,  300, "wHAT-ish / 5.7\" half"),
    ("4in-single",   640,  400, "Impression 4\" single"),
    ("5.7in-single", 600,  448, "Impression 5.7\" single"),
    ("7.3in-single", 800,  480, "Impression 7.3\" single"),
    ("7.3in-portrait", 480, 800, "Impression 7.3\" portrait single"),
    ("13.3in-single", 1600, 1200, "Impression 13.3\" single landscape"),
    ("13.3in-port",   1200, 1600, "Impression 13.3\" portrait single"),
    ("wide-thin",    800,  200, "stack_3 cell on 7.3\""),
    ("tall-thin",    400,  800, "row_2 half on 7.3\" portrait"),
]


def _fetch_widgets() -> list[str]:
    with urllib.request.urlopen(f"{BASE}/api/plugins", timeout=10) as r:
        body = json.loads(r.read())
    out = []
    for p in body.get("plugins", []):
        if "widget" not in (p.get("kinds") or []):
            continue
        if not p.get("enabled"):
            continue
        if p.get("error"):
            continue
        out.append(p["id"])
    return sorted(out)


async def _capture(page, widget: str, w: int, h: int, label: str) -> dict:
    """Goto, wait for ready, screenshot the cell rect, return overflow info."""
    url = f"{BASE}/widget-stress?widget={widget}&w={w}&h={h}"
    try:
        await page.goto(url, wait_until="load", timeout=15_000)
    except Exception as exc:
        return {"error": f"goto: {type(exc).__name__}: {exc}"}
    try:
        await page.wait_for_function(
            "document.body.dataset.ready === 'true'",
            timeout=12_000,
        )
    except Exception as exc:
        return {"error": f"ready-wait: {type(exc).__name__}: {exc}"}
    # A short settle for chart.js / async fetches inside widgets.
    await page.wait_for_timeout(450)
    # Detect overflow inside the shadow root by walking descendants and
    # checking if their bounding rect extends past the cell rect.
    overflow = await page.evaluate(
        """(args) => {
            const cell = document.getElementById("cell");
            const cw = args.w, ch = args.h;
            const sr = cell.shadowRoot;
            if (!sr) return { count: 0, max_dx: 0, max_dy: 0 };
            const all = sr.querySelectorAll("*");
            let count = 0, max_dx = 0, max_dy = 0;
            for (const el of all) {
                const r = el.getBoundingClientRect();
                const dx = Math.max(0, r.right - cw);
                const dy = Math.max(0, r.bottom - ch);
                if (dx > 1 || dy > 1) {
                    count++;
                    if (dx > max_dx) max_dx = dx;
                    if (dy > max_dy) max_dy = dy;
                }
            }
            return { count, max_dx: Math.round(max_dx), max_dy: Math.round(max_dy) };
        }""",
        {"w": w, "h": h},
    )
    out_path = OUT_DIR / f"{widget}-{label}.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(
        path=str(out_path),
        clip={"x": 0, "y": 0, "width": w, "height": h},
    )
    # OUT_DIR is already a repo-relative path so just stringify it.
    return {"overflow": overflow, "path": str(out_path)}


async def main():
    widgets = _fetch_widgets()
    print(f"[stress] {len(widgets)} widgets · {len(SIZES)} sizes = "
          f"{len(widgets) * len(SIZES)} renders")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, list[tuple[str, int, int, str, dict]]] = {}
    started = time.monotonic()
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1700, "height": 1700},
            device_scale_factor=1,
        )
        page = await context.new_page()
        for widget in widgets:
            results[widget] = []
            for label, w, h, source in SIZES:
                t0 = time.monotonic()
                info = await _capture(page, widget, w, h, label)
                dt = time.monotonic() - t0
                results[widget].append((label, w, h, source, info))
                marker = "✓" if "error" not in info and info.get("overflow", {}).get("count", 0) == 0 else "!"
                print(f"  {marker} {widget:18} {label:14} {w:>5}×{h:<5} {dt:>5.1f}s")
        await browser.close()
    print(f"[stress] done in {time.monotonic() - started:.1f}s")

    # Markdown report.
    lines = [
        "# Widget stress test report",
        "",
        "Renders every enabled widget at the cell sizes that fall out of the "
        "Inky Impression range (4\" / 5.7\" / 7.3\" / 13.3\", landscape and "
        "portrait, plus the smaller-cell shapes from stack/grid/hero layouts).",
        "",
        "Each row's check is **PASS** when no shadow-root descendant extends "
        "past the cell bounds, **OVER** when one or more do (the `dx`/`dy` "
        "columns are the worst-case overshoot in CSS pixels).",
        "",
        "Sizes:",
        "",
    ]
    for label, w, h, source in SIZES:
        lines.append(f"- **{label}** — {w}×{h} ({source})")
    lines.append("")

    for widget in widgets:
        lines.append(f"## {widget}")
        lines.append("")
        lines.append("| size | label | check | dx | dy | screenshot |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for label, w, h, source, info in results[widget]:
            if "error" in info:
                lines.append(f"| {w}×{h} | {label} | **ERROR** | — | — | — |")
                lines.append(f"| | | `{info['error']}` | | | |")
                continue
            ov = info.get("overflow") or {}
            cnt = ov.get("count", 0)
            check = "PASS" if cnt == 0 else f"OVER ×{cnt}"
            dx = ov.get("max_dx", 0) or "—"
            dy = ov.get("max_dy", 0) or "—"
            shot = info.get("path", "")
            lines.append(f"| {w}×{h} | {label} | {check} | {dx} | {dy} | ![]({shot}) |")
        lines.append("")
    REPORT.write_text("\n".join(lines))
    print(f"[stress] report → {REPORT}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
