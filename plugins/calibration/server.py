"""Calibration plugin.

Renders an 8×6 hue×lightness grid of HSL swatches. Pair the dashboard widget
(``client.js``) with the marker page (``/plugins/calibration/``) to capture
which colours render acceptably on the user's specific Spectra 6 panel under
their actual lighting.

Storage: ``data/plugins/calibration/calibrations.json``::

    {
      "active_id": "default",
      "calibrations": {
        "default": {
          "id": "default",
          "name": "Default",
          "created_at": 1737000000,
          "saturation": 80,
          "ratings": {"A1": "good", "B3": "muddy", ...}
        }
      }
    }

Ratings are 3-state: "good" / "muddy" / "bad" / absent (= unrated). Changing
saturation re-keys the grid to a different palette, so saturation edits clear
the existing ratings (the page warns the user before doing it).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from coloraide import Color
from flask import Blueprint, current_app, jsonify, render_template_string, request

_STORE_FILE = "calibrations.json"

# Grid geometry. 8 rows (A–H) × 6 columns (1–6) = 48 cells per sat-tier.
ROW_LABELS = "ABCDEFGH"
HUES = (0, 30, 60, 120, 180, 210, 270, 300)
LIGHTNESS = (15, 30, 45, 60, 75, 90)
SATURATIONS = (30, 60, 80, 100)  # tabs the user can rate against
RATINGS = ("good", "muddy", "bad")
_RATING_CYCLE = (None, "good", "muddy", "bad")


# ---------------------------------------------------------------- HSL → hex


def hsl_to_hex(h: float, s: float, ll: float) -> str:
    """h: 0–360, s/ll: 0–100. Returns ``#rrggbb`` lowercase."""
    s /= 100.0
    ll /= 100.0
    c = (1 - abs(2 * ll - 1)) * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = ll - c / 2
    if h < 60:
        r, g, b = c, x, 0.0
    elif h < 120:
        r, g, b = x, c, 0.0
    elif h < 180:
        r, g, b = 0.0, c, x
    elif h < 240:
        r, g, b = 0.0, x, c
    elif h < 300:
        r, g, b = x, 0.0, c
    else:
        r, g, b = c, 0.0, x
    return (
        f"#{int(round((r + m) * 255)):02x}"
        f"{int(round((g + m) * 255)):02x}"
        f"{int(round((b + m) * 255)):02x}"
    )


def _compute_cells(saturation: int) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    for ri, hue in enumerate(HUES):
        for ci, light in enumerate(LIGHTNESS):
            cells.append(
                {
                    "id": f"{ROW_LABELS[ri]}{ci + 1}",
                    "row": ri,
                    "col": ci,
                    "h": hue,
                    "s": saturation,
                    "l": light,
                    "hex": hsl_to_hex(hue, saturation, light),
                }
            )
    return cells


VALID_CELL_IDS = {
    f"{ROW_LABELS[r]}{c + 1}" for r in range(len(HUES)) for c in range(len(LIGHTNESS))
}


# ------------------------------------------------------------------ storage


def _store_path() -> Path:
    plugin = current_app.config["PLUGIN_REGISTRY"].plugins["calibration"]
    return plugin.data_dir / _STORE_FILE


def _new_calibration(cal_id: str, name: str) -> dict[str, Any]:
    return {
        "id": cal_id,
        "name": name,
        "created_at": int(time.time()),
        "active_saturation": 80,
        "ratings_by_saturation": {str(s): {} for s in SATURATIONS},
    }


def _default_state() -> dict[str, Any]:
    return {
        "active_id": "default",
        "calibrations": {"default": _new_calibration("default", "Default")},
    }


def _migrate_calibration(cal: dict[str, Any]) -> dict[str, Any]:
    """Move a v1 single-saturation cal forward to the multi-sat schema.

    v1: ``{saturation: 80, ratings: {...}}``
    v2: ``{active_saturation: 80, ratings_by_saturation: {"30": {}, "60": {},
                                                          "80": {...}, "100": {}}}``

    Idempotent — already-migrated cals pass through. Pre-existing ratings land
    on whichever sat-tab they were captured under; missing tabs initialise empty.
    """
    if "ratings_by_saturation" in cal:
        # Make sure every standard sat tier has a key (so the UI tabs always work)
        for sat in SATURATIONS:
            cal["ratings_by_saturation"].setdefault(str(sat), {})
        cal.setdefault("active_saturation", 80)
        return cal

    legacy_sat = int(cal.get("saturation", 80))
    legacy_ratings = cal.get("ratings", {}) or {}
    rbs: dict[str, dict[str, str]] = {str(s): {} for s in SATURATIONS}
    rbs[str(legacy_sat)] = dict(legacy_ratings)  # park v1 ratings on their tier
    cal["ratings_by_saturation"] = rbs
    cal["active_saturation"] = legacy_sat
    cal.pop("saturation", None)
    cal.pop("ratings", None)
    return cal


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return _default_state()
    if not isinstance(raw, dict) or not isinstance(raw.get("calibrations"), dict):
        return _default_state()
    if not raw["calibrations"]:
        return _default_state()
    for cal_id, cal in raw["calibrations"].items():
        raw["calibrations"][cal_id] = _migrate_calibration(cal)
    if raw.get("active_id") not in raw["calibrations"]:
        raw["active_id"] = next(iter(raw["calibrations"]))
    return raw


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(path)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "calibration"


def _unique_id(state: dict[str, Any], base: str) -> str:
    if base not in state["calibrations"]:
        return base
    n = 2
    while f"{base}-{n}" in state["calibrations"]:
        n += 1
    return f"{base}-{n}"


def _resolve_calibration(state: dict[str, Any], cal_id: str | None) -> dict[str, Any]:
    """Return the requested calibration, or active when missing/blank."""
    if cal_id and cal_id in state["calibrations"]:
        return state["calibrations"][cal_id]
    return state["calibrations"][state["active_id"]]


# ----------------------------------------------------------- widget fetch()


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    path = Path(ctx["data_dir"]) / _STORE_FILE
    state = _load_state(path)
    cal = _resolve_calibration(state, str(options.get("calibration_id") or ""))
    # Widget renders ONE saturation at a time (cell layout demands it). The
    # `saturation` option lets users put multiple calibration cards on the
    # same dashboard, one per sat tier they want to test.
    requested = options.get("saturation")
    if requested in (None, "", 0):
        sat = int(cal.get("active_saturation", 80))
    else:
        sat = max(0, min(100, int(requested)))
    ratings = cal.get("ratings_by_saturation", {}).get(str(sat), {})
    return {
        "id": cal["id"],
        "name": cal["name"],
        "saturation": sat,
        "cells": _compute_cells(sat),
        "ratings": ratings,
    }


# ----------------------------------------------------- admin page (HTML+JS)


_PAGE = """\
<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>Calibration — Inky Dash</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/icons/phosphor.css">
  <link rel="stylesheet" href="/static/style/tokens.css">
  <script>
    (function () {
      try {
        var theme = localStorage.getItem('inky_theme') || 'auto';
        var accent = localStorage.getItem('inky_accent');
        var root = document.documentElement;
        var isDark =
          theme === 'dark' ||
          (theme === 'auto' && window.matchMedia &&
           window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) root.dataset.theme = 'dark';
        else root.removeAttribute('data-theme');
        if (accent) root.style.setProperty('--id-accent', accent);
      } catch (_) {}
    })();
  </script>
  <script type="module" src="/static/dist/_components.js"></script>
  <style>
    /* Calibration page styles. Mirrors the visual language of the rest of
       the admin UI (id-card, id-button, id-form-row): 1px borders, 12px
       card radius, --id-shadow-sm on every card, --id-control-h on form
       controls. Card headings are 16px/600 like id-card.h3. */
    body { font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
    .container { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 {
      font-size: 24px; font-weight: 700;
      margin: 0 0 4px;
      display: flex; align-items: center; gap: 10px;
      color: var(--id-fg);
    }
    h1 .ph { color: var(--id-accent); font-size: 28px; }
    .lede { color: var(--id-fg-soft); font-size: 14px; margin: 0 0 24px; max-width: 60ch; }

    /* Card primitives — match id-card.js. */
    .card {
      background: var(--id-surface);
      border: 1px solid var(--id-divider);
      border-radius: 12px;
      padding: 16px;
      box-shadow: var(--id-shadow-sm);
      margin-bottom: 16px;
    }
    .card-heading {
      margin: 0 0 12px;
      font-size: 16px;
      font-weight: 600;
      color: var(--id-fg);
    }
    .card-sub {
      margin: -8px 0 12px;
      font-size: 13px;
      color: var(--id-fg-soft);
    }

    /* Form rows — match id-form-row.js. */
    .field { display: grid; gap: 6px; min-width: 0; }
    .field label, .field-label {
      font-size: 13px;
      font-weight: 500;
      color: var(--id-fg);
    }
    .field-hint {
      font-size: 12px;
      color: var(--id-fg-soft);
    }

    /* Inputs/selects — match id-form-row inline controls. */
    select, input[type=text] {
      width: 100%;
      padding: 0 12px;
      min-height: var(--id-control-h, 40px);
      border: 1px solid var(--id-divider);
      border-radius: var(--id-radius, 8px);
      font: inherit;
      background: var(--id-bg);
      color: var(--id-fg);
      box-sizing: border-box;
    }
    select:focus, input[type=text]:focus {
      outline: none;
      border-color: var(--id-accent);
      box-shadow: 0 0 0 3px var(--id-accent-bg);
    }

    /* Buttons — match id-button.js. */
    .btn {
      min-height: var(--id-control-h, 40px);
      padding: 0 16px;
      border-radius: var(--id-radius, 8px);
      border: 1px solid var(--id-divider);
      background: var(--id-surface);
      color: var(--id-fg);
      font: inherit;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex; align-items: center; justify-content: center;
      gap: 8px;
      white-space: nowrap;
      transition: transform 80ms ease, background 120ms ease, border-color 120ms ease;
    }
    .btn:hover:not([disabled]) {
      background: var(--id-surface2);
      border-color: var(--id-fg-soft);
    }
    .btn:active:not([disabled]) { transform: scale(0.98); }
    .btn.primary {
      background: var(--id-accent);
      border-color: var(--id-accent);
      color: var(--id-accent-fg, #ffffff);
    }
    .btn.primary:hover:not([disabled]) {
      background: var(--id-accent-soft);
      border-color: var(--id-accent-soft);
    }
    .btn.danger {
      color: var(--id-danger);
      border-color: var(--id-divider);
    }
    .btn.danger:hover:not([disabled]) {
      background: var(--id-accent-bg);
      border-color: var(--id-danger);
    }

    /* Toolbar layout. */
    .toolbar {
      display: grid;
      grid-template-columns: 1fr auto auto;
      gap: 12px;
      align-items: end;
    }

    /* Editor (name + saturation tabs + actions). */
    .editor {
      display: grid;
      grid-template-columns: 1fr 2fr auto auto;
      gap: 12px;
      align-items: end;
    }
    .sat-tabs { display: flex; gap: 6px; }
    .sat-tab {
      flex: 1;
      min-height: var(--id-control-h, 40px);
      padding: 6px 8px;
      border: 1px solid var(--id-divider);
      border-radius: var(--id-radius, 8px);
      background: var(--id-bg);
      color: var(--id-fg);
      font: inherit;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      gap: 2px;
      transition: background 120ms ease, border-color 120ms ease;
    }
    .sat-tab:hover { border-color: var(--id-fg-soft); }
    .sat-tab.active {
      background: var(--id-accent);
      border-color: var(--id-accent);
      color: var(--id-accent-fg, #ffffff);
    }
    .sat-tab .sat-count {
      font-size: 11px;
      opacity: 0.8;
      font-variant-numeric: tabular-nums;
    }

    /* Stats pills. */
    .stats {
      display: flex; gap: 8px; flex-wrap: wrap;
      font-size: 13px; color: var(--id-fg-soft);
      margin-bottom: 16px;
    }
    .pill {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 10px;
      border: 1px solid var(--id-divider);
      border-radius: 999px;
      background: var(--id-surface);
    }
    .pill.good { color: var(--id-ok); border-color: currentColor; }
    .pill.muddy { color: var(--id-warn); border-color: currentColor; }
    .pill.bad { color: var(--id-danger); border-color: currentColor; }
    .pill .dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: currentColor;
    }

    /* Rating grid. */
    .grid {
      display: grid;
      grid-template-columns: auto repeat(6, minmax(0, 1fr));
      gap: 6px;
    }
    .grid .corner, .grid .col-head, .grid .row-head {
      font-size: 12px; font-weight: 600; color: var(--id-fg-soft);
      text-align: center; align-self: center; justify-self: center;
    }
    .grid .row-head { padding-right: 4px; }

    .swatch {
      position: relative;
      aspect-ratio: 1.4 / 1;
      border-radius: var(--id-radius-sm, 6px);
      border: 1px solid rgba(0, 0, 0, 0.2);
      cursor: pointer;
      overflow: hidden;
      transition: transform 80ms ease;
    }
    .swatch:hover { transform: scale(1.04); }
    .swatch .label-tl, .swatch .label-br {
      position: absolute;
      font: 700 11px/1 ui-monospace, "SF Mono", monospace;
      pointer-events: none;
      letter-spacing: 0.02em;
    }
    .swatch .label-tl {
      top: 4px; left: 5px; color: #ffffff;
      text-shadow: 0 0 3px rgba(0,0,0,0.7);
    }
    .swatch .label-br {
      bottom: 4px; right: 5px; color: #000000;
      text-shadow: 0 0 3px rgba(255,255,255,0.7);
    }

    .swatch .badge {
      position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
      width: 32px; height: 32px;
      border-radius: 50%;
      display: grid; place-items: center;
      font-size: 18px; font-weight: 700;
      color: #ffffff;
      pointer-events: none;
      box-shadow:
        0 0 0 1px rgba(0,0,0,0.3),
        0 0 0 3px rgba(255,255,255,0.6),
        var(--id-shadow-sm);
    }
    .swatch[data-rating=good] .badge { background: var(--id-ok); }
    .swatch[data-rating=muddy] .badge { background: var(--id-warn); }
    .swatch[data-rating=bad] .badge { background: var(--id-danger); }
    .swatch:not([data-rating]) .badge { display: none; }

    .legend {
      font-size: 13px;
      color: var(--id-fg-soft);
      margin: 16px 0 0;
      line-height: 1.5;
    }
    .legend kbd {
      display: inline-block;
      padding: 1px 6px;
      border-radius: 4px;
      border: 1px solid var(--id-divider);
      background: var(--id-bg);
      font: inherit;
      font-size: 11px;
      font-weight: 600;
    }

    /* Generator section. */
    .gen-controls {
      display: flex; gap: 12px; flex-wrap: wrap; align-items: end;
    }
    .gen-controls .field { flex: 1 1 160px; }
    .gen-controls .gen-buttons { display: flex; gap: 8px; flex: 0 0 auto; }

    #gen-status {
      margin: 12px 0 0;
      color: var(--id-fg-soft);
      font-size: 13px;
      min-height: 1.4em;
    }
    /* Widget-style theme preview. The mock uses every palette token in
       context (bg, two surfaces, fg, fgSoft, muted, divider, accent,
       accentSoft, danger, warn, ok) so the user can judge how the colours
       interact rather than just inspecting individual swatches. */
    #gen-preview {
      margin-top: 12px;
      display: none;
      flex-direction: column;
      gap: 12px;
    }
    #gen-preview.visible { display: flex; }

    .gen-actions {
      display: none;
      gap: 8px;
      margin-top: 12px;
      flex-wrap: wrap;
      align-items: center;
    }
    .gen-actions.visible { display: flex; }
    .gen-actions-hint {
      font-size: 12px;
      color: var(--id-fg-soft);
    }

    .preview-mock {
      border-radius: 12px;
      overflow: hidden;
      box-shadow: var(--id-shadow-sm);
      border: 1px solid var(--id-divider);
    }
    .preview-mock-frame {
      padding: 16px;
      display: grid;
      grid-template-columns: 1.4fr 1fr;
      gap: 12px;
    }
    .preview-mock-card {
      border-radius: 8px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      box-sizing: border-box;
    }
    .preview-mock-row {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .preview-mock-title {
      font-size: 15px;
      font-weight: 700;
      letter-spacing: -0.01em;
      flex: 1;
      min-width: 0;
    }
    .preview-mock-sub { font-size: 12px; }
    .preview-mock-body { font-size: 13px; line-height: 1.4; }
    .preview-mock-caption {
      font-size: 10px;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      font-weight: 600;
    }
    .preview-mock-divider { height: 1px; }
    .preview-mock-btn {
      padding: 4px 10px;
      border-radius: 6px;
      font: inherit;
      font-size: 12px;
      font-weight: 600;
      border: 1px solid currentColor;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .preview-mock-btn.solid {
      border-color: transparent;
      color: #ffffff;
    }
    .preview-mock-pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      font-size: 11px;
      font-weight: 600;
    }
    .preview-mock-pill .dot {
      width: 8px; height: 8px;
      border-radius: 50%;
      background: currentColor;
    }

    /* Token swatch grid (collapsed inside <details>). */
    .preview-tokens-details {
      border: 1px solid var(--id-divider);
      border-radius: 8px;
      padding: 8px 12px;
      background: var(--id-surface2);
    }
    .preview-tokens-details > summary {
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      color: var(--id-fg-soft);
      list-style: none;
      user-select: none;
    }
    .preview-tokens-details > summary::before {
      content: "▸ ";
      display: inline-block;
      transition: transform 120ms ease;
    }
    .preview-tokens-details[open] > summary::before {
      transform: rotate(90deg);
    }
    .preview-tokens-details > summary::-webkit-details-marker { display: none; }
    .preview-tokens {
      margin-top: 10px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(80px, 1fr));
      gap: 6px;
    }
    .preview-token {
      display: grid;
      grid-template-rows: 36px auto auto;
      border-radius: var(--id-radius-sm, 6px);
      overflow: hidden;
      border: 1px solid var(--id-divider);
      background: var(--id-surface);
    }
    .preview-token .swatch-row { display: block; width: 100%; height: 100%; }
    .preview-token .meta {
      padding: 4px 6px;
      font-size: 11px;
      color: var(--id-fg);
      font-weight: 600;
    }
    .preview-token .prov {
      padding: 2px 6px;
      font-size: 10px;
      background: var(--id-surface2);
      color: var(--id-fg-soft);
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }

    @media (max-width: 720px) {
      .preview-mock-frame { grid-template-columns: 1fr; }
    }

    /* Pool view. Uses <details> styled like a card. */
    .pool-card { padding: 0; }
    .pool-card summary {
      list-style: none;
      cursor: pointer;
      padding: 16px;
      font-size: 16px;
      font-weight: 600;
      color: var(--id-fg);
      display: flex;
      align-items: center;
      gap: 8px;
      user-select: none;
    }
    .pool-card summary::-webkit-details-marker { display: none; }
    .pool-card summary::after {
      content: "▾";
      margin-left: auto;
      color: var(--id-fg-soft);
      font-size: 14px;
      transition: transform 120ms ease;
    }
    .pool-card[open] summary::after { transform: rotate(180deg); }
    .pool-body { padding: 0 16px 16px; border-top: 1px solid var(--id-divider); padding-top: 16px; }
    .pool-controls {
      display: flex; gap: 12px; flex-wrap: wrap; align-items: end;
      margin-bottom: 12px;
    }
    .pool-controls .field { min-width: 140px; }
    .pool-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(64px, 1fr));
      gap: 6px;
    }
    .pool-swatch {
      aspect-ratio: 1.4 / 1;
      border-radius: var(--id-radius-sm, 6px);
      border: 1px solid rgba(0, 0, 0, 0.2);
      position: relative;
      overflow: hidden;
      cursor: pointer;
    }
    .pool-swatch .pool-hex {
      position: absolute;
      bottom: 2px; left: 4px; right: 4px;
      font: 700 9px ui-monospace, monospace;
      color: #ffffff;
      text-shadow:
        -1px -1px 0 #000, 1px -1px 0 #000,
        -1px  1px 0 #000, 1px  1px 0 #000;
      letter-spacing: 0.03em;
      text-align: center;
    }
    .pool-swatch.tier-0 { box-shadow: inset 0 0 0 2px var(--id-ok); }
    .pool-swatch.tier-1 { box-shadow: inset 0 0 0 2px var(--id-accent); }
    .pool-tier-legend {
      display: flex; gap: 16px; flex-wrap: wrap;
      font-size: 12px; color: var(--id-fg-soft);
      margin-top: 12px;
    }
    .pool-tier-legend .ring {
      display: inline-block; width: 12px; height: 12px;
      border-radius: 3px;
      vertical-align: middle;
      margin-right: 4px;
    }

    .empty {
      text-align: center; padding: 48px 16px;
      color: var(--id-fg-soft);
      font-style: italic;
    }

    @media (max-width: 720px) {
      .toolbar, .editor { grid-template-columns: 1fr; }
      .grid { gap: 4px; }
    }
  </style>
</head><body>
  <id-nav current="calibration"></id-nav>
  <div class="container">
    <h1><i class="ph ph-eyedropper-sample"></i> Calibration</h1>
    <p class="lede">
      Push the calibration widget to your panel, then mark each swatch good /
      muddy / bad as it actually renders. Approved colours drive the color picker
      snap-to and theme generation.
    </p>

    <div class="card toolbar">
      <div class="field">
        <label for="cal-select">Active calibration</label>
        <select id="cal-select"></select>
      </div>
      <button class="btn" id="set-active-btn"><i class="ph ph-star"></i> Set as active</button>
      <button class="btn primary" id="new-btn"><i class="ph ph-plus"></i> New</button>
    </div>

    <div class="card editor">
      <div class="field">
        <label for="name-input">Name</label>
        <input type="text" id="name-input" maxlength="80">
      </div>
      <div class="field">
        <label>Rating tier · click to switch</label>
        <div class="sat-tabs" id="sat-tabs"></div>
      </div>
      <button class="btn" id="save-btn"><i class="ph ph-floppy-disk"></i> Save name</button>
      <button class="btn danger" id="delete-btn"><i class="ph ph-trash"></i> Delete</button>
    </div>

    <div class="card">
      <h2 class="card-heading">Rating grid</h2>
      <div class="stats" id="stats"></div>
      <div id="grid-host"></div>
      <p class="legend">
        Click a swatch to cycle: <kbd>·</kbd> unrated → <kbd>✓</kbd> good →
        <kbd>~</kbd> muddy → <kbd>✗</kbd> bad → unrated. Switch saturation
        tiers with the tabs above — each tier holds its own ratings, and the
        generator pools them all.
      </p>
    </div>

    <div class="card">
      <h2 class="card-heading">Generate theme</h2>
      <p class="card-sub">Preview a palette, then save only if you like it.</p>
      <div class="gen-controls">
        <div class="field">
          <label for="gen-seed">Seed colour</label>
          <select id="gen-seed">
            <option value="">Auto · most-chromatic good</option>
          </select>
        </div>
        <div class="field">
          <label for="gen-harmony">Harmony</label>
          <select id="gen-harmony">
            <option value="complement">Complementary (seed + 180°)</option>
            <option value="analogous">Analogous (seed ±30°)</option>
            <option value="split">Split-complementary</option>
            <option value="triad">Triadic</option>
            <option value="square">Square / tetradic</option>
            <option value="mono">Monochromatic</option>
          </select>
        </div>
        <div class="gen-buttons">
          <button class="btn" id="gen-light-btn" title="Pure light bg (~white). On Spectra 6, most of the bg/surface tokens render as flat white.">
            <i class="ph ph-sun"></i> Light
          </button>
          <button class="btn" id="gen-mid-btn" title="Tinted mid-tone bg (kraft / sage / slate). Forces the panel to dither real coloured ink into the surface, so light themes actually look distinct on Spectra 6.">
            <i class="ph ph-cloud-sun"></i> Midtone
          </button>
          <button class="btn" id="gen-dark-btn">
            <i class="ph ph-moon"></i> Dark
          </button>
        </div>
      </div>
      <p id="gen-status"></p>
      <div id="gen-preview"></div>
      <div class="gen-actions" id="gen-actions">
        <button class="btn primary" id="gen-save-btn">
          <i class="ph ph-floppy-disk"></i> Save as theme
        </button>
        <button class="btn" id="gen-discard-btn">
          <i class="ph ph-x"></i> Discard
        </button>
        <span class="gen-actions-hint">
          Or change seed/harmony above and click Generate again to compare.
        </span>
      </div>
    </div>

    <details class="card pool-card" open>
      <summary>
        <i class="ph ph-eyedropper"></i>
        Theoretical pool · <span id="pool-count">…</span> candidates
      </summary>
      <div class="pool-body">
        <div class="pool-controls">
          <div class="field">
            <label for="pool-filter">Filter</label>
            <select id="pool-filter">
              <option value="all">All</option>
              <option value="calibrated">Calibrated only</option>
              <option value="muddy">Muddy</option>
            </select>
          </div>
          <div class="field">
            <label for="pool-sort">Sort</label>
            <select id="pool-sort">
              <option value="hue">Hue</option>
              <option value="lightness">Lightness</option>
              <option value="chroma">Chroma</option>
              <option value="provenance">Provenance</option>
            </select>
          </div>
        </div>
        <div class="pool-grid" id="pool-grid"></div>
        <div class="pool-tier-legend">
          <span><span class="ring" style="box-shadow: inset 0 0 0 2px var(--id-ok);"></span>Calibrated good</span>
          <span><span class="ring" style="border: 1px solid var(--id-divider);"></span>Muddy (fallback)</span>
        </div>
      </div>
    </details>
  </div>

  <script>
    const ROW_LABELS = "ABCDEFGH";
    const RATING_CYCLE = [null, "good", "muddy", "bad"];

    const state = { list: null, current: null };

    const el = (id) => document.getElementById(id);

    async function api(method, path, body) {
      const opts = { method, headers: { "Content-Type": "application/json" } };
      if (body !== undefined) opts.body = JSON.stringify(body);
      const res = await fetch(path, opts);
      if (!res.ok) throw new Error(`${method} ${path} → ${res.status}`);
      return res.status === 204 ? null : res.json();
    }

    async function refreshList() {
      state.list = await api("GET", "/plugins/calibration/api/list");
      const sel = el("cal-select");
      const prev = sel.value;
      sel.innerHTML = state.list.calibrations.map((c) =>
        `<option value="${c.id}">${escapeHtml(c.name)}${c.id === state.list.active_id ? " · active" : ""}</option>`
      ).join("");
      const target = state.list.calibrations.find((c) => c.id === prev) ? prev : state.list.active_id;
      sel.value = target;
      await loadCurrent(target);
    }

    async function loadCurrent(id) {
      state.current = await api("GET", `/plugins/calibration/api/${encodeURIComponent(id)}`);
      el("name-input").value = state.current.name;
      renderSatTabs();
      renderGrid();
      renderStats();
      await loadPool();
      populateSeedSelect();
    }

    function renderSatTabs() {
      const host = el("sat-tabs");
      const sats = state.current.saturations || [30, 60, 80, 100];
      const counts = state.current.tier_counts || {};
      const active = state.current.active_saturation;
      host.innerHTML = sats.map((s) => `
        <button class="sat-tab ${s === active ? 'active' : ''}" data-sat="${s}">
          <span>${s}%</span>
          <span class="sat-count">${counts[s] || 0} rated</span>
        </button>
      `).join("");
      host.querySelectorAll(".sat-tab").forEach((tab) => {
        tab.addEventListener("click", () => switchTier(parseInt(tab.dataset.sat, 10)));
      });
    }

    async function switchTier(sat) {
      if (sat === state.current.active_saturation) return;
      // Server tracks active_saturation so the widget stays in sync.
      await api("PATCH", `/plugins/calibration/api/${state.current.id}`, {
        active_saturation: sat,
      });
      await loadCurrent(state.current.id);
    }

    async function loadPool() {
      try {
        state.pool = await api("GET", `/plugins/calibration/api/${encodeURIComponent(state.current.id)}/pool`);
      } catch (e) {
        state.pool = { pool: [], pool_size: 0 };
      }
      el("pool-count").textContent = state.pool.pool_size.toLocaleString();
      renderPool();
    }

    function poolFilter(p) {
      const f = el("pool-filter").value;
      if (f === "all") return true;
      return p.provenance === f;
    }

    function poolSort(arr) {
      const s = el("pool-sort").value;
      const cmp = {
        hue: (a, b) => a.oklch_h - b.oklch_h || a.oklch_l - b.oklch_l,
        lightness: (a, b) => a.oklch_l - b.oklch_l || a.oklch_h - b.oklch_h,
        chroma: (a, b) => b.oklch_c - a.oklch_c || a.oklch_h - b.oklch_h,
        provenance: (a, b) => a.tier - b.tier || a.oklch_h - b.oklch_h,
      }[s] || (() => 0);
      return [...arr].sort(cmp);
    }

    function renderPool() {
      const grid = el("pool-grid");
      const items = poolSort(state.pool.pool.filter(poolFilter));
      grid.innerHTML = items.map((p) => `
        <div class="pool-swatch tier-${p.tier}"
             style="background: ${p.hex};"
             title="${p.id} · ${p.hex.toUpperCase()} · ${p.provenance}">
          <span class="pool-hex">${p.hex.toUpperCase()}</span>
        </div>
      `).join("");
    }

    function populateSeedSelect() {
      const sel = el("gen-seed");
      const calibrated = (state.pool?.pool || []).filter((p) => p.provenance === "calibrated");
      // Keep current selection if still valid.
      const prev = sel.value;
      const opts = ['<option value="">Auto · most-chromatic good</option>'];
      calibrated
        .sort((a, b) => b.oklch_c - a.oklch_c)
        .forEach((c) => {
          opts.push(`<option value="${c.hex}">${c.id} · ${c.hex.toUpperCase()}</option>`);
        });
      sel.innerHTML = opts.join("");
      if (calibrated.find((c) => c.hex === prev)) sel.value = prev;
    }

    function renderGrid() {
      const host = el("grid-host");
      const cells = state.current.cells;
      const sat = state.current.active_saturation;
      const ratings = (state.current.ratings_by_saturation || {})[String(sat)] || {};
      const head = `<div class="corner"></div>` +
        [1,2,3,4,5,6].map((c) => `<div class="col-head">${c}</div>`).join("");
      const rows = [];
      for (let r = 0; r < ROW_LABELS.length; r++) {
        rows.push(`<div class="row-head">${ROW_LABELS[r]}</div>`);
        for (let c = 0; c < 6; c++) {
          const cell = cells.find((x) => x.row === r && x.col === c);
          const rating = ratings[cell.id];
          const ratingAttr = rating ? ` data-rating="${rating}"` : "";
          const badge = rating === "good" ? "✓" : rating === "muddy" ? "~" : rating === "bad" ? "✗" : "";
          rows.push(`
            <div class="swatch" data-cell-id="${cell.id}" style="background:${cell.hex}"${ratingAttr}>
              <span class="label-tl">${cell.id}</span>
              <span class="label-br">${cell.hex}</span>
              <span class="badge">${badge}</span>
            </div>
          `);
        }
      }
      host.innerHTML = `<div class="grid">${head}${rows.join("")}</div>`;
      host.querySelectorAll(".swatch").forEach((sw) => {
        sw.addEventListener("click", () => cycleRating(sw.dataset.cellId));
      });
    }

    function renderStats() {
      const sat = state.current.active_saturation;
      const r = (state.current.ratings_by_saturation || {})[String(sat)] || {};
      let good = 0, muddy = 0, bad = 0;
      for (const v of Object.values(r)) {
        if (v === "good") good++;
        else if (v === "muddy") muddy++;
        else if (v === "bad") bad++;
      }
      const total = state.current.cells.length;
      const unrated = total - good - muddy - bad;
      // Across all sat tiers
      let totalGood = 0;
      for (const tier of Object.values(state.current.ratings_by_saturation || {})) {
        for (const v of Object.values(tier)) if (v === "good") totalGood++;
      }
      el("stats").innerHTML = `
        <span class="pill" style="font-weight: 700;">Tier ${sat}%</span>
        <span class="pill good"><span class="dot"></span> ${good} good</span>
        <span class="pill muddy"><span class="dot"></span> ${muddy} muddy</span>
        <span class="pill bad"><span class="dot"></span> ${bad} bad</span>
        <span class="pill"><span class="dot" style="background:var(--id-fg-soft)"></span> ${unrated} unrated</span>
        <span class="pill" style="margin-left: auto;">${totalGood} good across all tiers</span>
      `;
    }

    async function cycleRating(cellId) {
      const sat = state.current.active_saturation;
      const tierRatings = (state.current.ratings_by_saturation || {})[String(sat)] || {};
      const cur = tierRatings[cellId] || null;
      const idx = RATING_CYCLE.indexOf(cur);
      const next = RATING_CYCLE[(idx + 1) % RATING_CYCLE.length];
      await api("POST", `/plugins/calibration/api/${state.current.id}/rate`, {
        cell_id: cellId, rating: next, saturation: sat,
      });
      // Local cache mirror so the grid updates immediately.
      if (!state.current.ratings_by_saturation[String(sat)]) {
        state.current.ratings_by_saturation[String(sat)] = {};
      }
      if (next === null) {
        delete state.current.ratings_by_saturation[String(sat)][cellId];
      } else {
        state.current.ratings_by_saturation[String(sat)][cellId] = next;
      }
      // Update tier_counts so tab badges stay accurate.
      state.current.tier_counts = state.current.tier_counts || {};
      state.current.tier_counts[sat] = Object.keys(
        state.current.ratings_by_saturation[String(sat)]
      ).length;
      renderSatTabs();
      renderGrid();
      renderStats();
      // Pool changes whenever a rating changes — refresh.
      await loadPool();
      populateSeedSelect();
    }

    async function onSave() {
      const name = el("name-input").value.trim() || "Untitled";
      await api("PATCH", `/plugins/calibration/api/${state.current.id}`, { name });
      await loadCurrent(state.current.id);
      await refreshList();
    }

    async function onNew() {
      const name = prompt("Name for the new calibration?", "New calibration");
      if (!name) return;
      const created = await api("POST", "/plugins/calibration/api/create", { name });
      await refreshList();
      el("cal-select").value = created.id;
      await loadCurrent(created.id);
    }

    async function onDelete() {
      if (state.list.calibrations.length <= 1) {
        alert("Can't delete the last calibration.");
        return;
      }
      if (!confirm(`Delete "${state.current.name}"?`)) return;
      await api("DELETE", `/plugins/calibration/api/${state.current.id}`);
      await refreshList();
    }

    async function onSetActive() {
      await api("POST", `/plugins/calibration/api/${state.current.id}/activate`);
      await refreshList();
    }

    async function onGenerate(mode) {
      const harmony = el("gen-harmony").value;
      const seed = el("gen-seed").value || null;
      el("gen-status").textContent = "Generating preview…";
      el("gen-preview").classList.remove("visible");
      el("gen-actions").classList.remove("visible");
      try {
        const res = await api("POST",
          `/plugins/calibration/api/${state.current.id}/preview-theme`,
          { mode, seed_hex: seed, harmony });
        // Stash the previewed result so Save can use it without recomputing.
        state.preview = res;
        const c = res.provenance_counts || {};
        const parts = [];
        if (c.calibrated) parts.push(`${c.calibrated} calibrated`);
        if (c.muddy) parts.push(`${c.muddy} muddy`);
        if (c.seed) parts.push(`${c.seed} seed`);
        if (c.fallback) parts.push(`${c.fallback} fallback`);
        const seedLabel = res.seed_hex
          ? `seed ${res.seed_hex.toUpperCase()}`
          : "no seed";
        const warnLabel = res.contrast_warnings?.length
          ? ` · ⚠ ${res.contrast_warnings.join(", ")}`
          : "";
        el("gen-status").innerHTML =
          `<strong>Preview</strong> · ${mode} · ${seedLabel} · ${res.harmony} · ` +
          parts.join(", ") + `${warnLabel}. Save to keep, or regenerate.`;
        renderPreview(res.palette, res.provenance);
        el("gen-actions").classList.add("visible");
      } catch (err) {
        el("gen-status").textContent = `Failed: ${err.message}`;
      }
    }

    async function onSavePreview() {
      if (!state.preview) return;
      const harmony = state.preview.harmony;
      const mode = state.preview.mode;
      const defaultName = `${state.current.name} ${harmony} (${mode})`;
      const name = prompt("Save this theme as:", defaultName);
      if (!name) return;
      const themeId = slugify(name);
      // The theme schema only knows "light"/"dark"; midtone is fg-on-light-bg so
      // it stores as light.
      const storageMode = mode === "midtone" ? "light" : mode;
      try {
        await api("POST", "/api/themes", {
          id: themeId,
          name: name.slice(0, 80),
          mode: storageMode,
          palette: state.preview.palette,
        });
        el("gen-status").innerHTML =
          `<strong>Saved</strong> as <code>${themeId}</code>. ` +
          `Open <a href="/themes" style="color: var(--id-accent);">Themes</a> to use it.`;
        el("gen-actions").classList.remove("visible");
        state.preview = null;
      } catch (err) {
        el("gen-status").textContent = `Save failed: ${err.message}`;
      }
    }

    function onDiscardPreview() {
      state.preview = null;
      el("gen-preview").classList.remove("visible");
      el("gen-actions").style.display = "none";
      el("gen-status").textContent = "Preview discarded.";
    }

    function slugify(name) {
      return String(name).toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        || "theme";
    }

    function renderPreview(palette, provenance) {
      const order = ["bg", "surface", "surface2", "fg", "fgSoft", "muted",
                     "divider", "accent", "accentSoft", "danger", "warn", "ok"];
      const p = palette;
      const host = el("gen-preview");
      // Widget mock — exercises every token in a layout closer to how a
      // real dashboard cell looks.
      const mock = `
        <div class="preview-mock" style="background: ${p.bg};">
          <div class="preview-mock-frame">
            <div class="preview-mock-card primary"
                 style="background: ${p.surface};">
              <div class="preview-mock-row">
                <div class="preview-mock-title" style="color: ${p.fg};">Widget Title</div>
                <button type="button" class="preview-mock-btn solid"
                        style="background: ${p.accent};">Action</button>
              </div>
              <div class="preview-mock-sub" style="color: ${p.fgSoft};">
                Subtitle in fgSoft — secondary information sits here.
              </div>
              <div class="preview-mock-divider" style="background: ${p.divider};"></div>
              <div class="preview-mock-body" style="color: ${p.fg};">
                Body text in fg sits on top of the surface card.
              </div>
              <div class="preview-mock-caption" style="color: ${p.muted};">caption · muted</div>
            </div>
            <div class="preview-mock-card secondary"
                 style="background: ${p.surface2};">
              <div class="preview-mock-caption" style="color: ${p.muted};">status</div>
              <div class="preview-mock-row">
                <span class="preview-mock-pill" style="color: ${p.ok};"><span class="dot"></span>ok</span>
                <span class="preview-mock-pill" style="color: ${p.warn};"><span class="dot"></span>warn</span>
                <span class="preview-mock-pill" style="color: ${p.danger};"><span class="dot"></span>danger</span>
              </div>
              <div class="preview-mock-divider" style="background: ${p.divider};"></div>
              <div class="preview-mock-body" style="color: ${p.fgSoft};">
                Secondary surface with a softer body tone.
              </div>
              <div class="preview-mock-row">
                <button type="button" class="preview-mock-btn solid"
                        style="background: ${p.accentSoft};">Soft action</button>
              </div>
            </div>
          </div>
        </div>
      `;
      // Collapsed token-by-token breakdown for hex inspection / debugging.
      const swatches = order.map((token) => `
        <div class="preview-token">
          <span class="swatch-row" style="background: ${p[token]};"></span>
          <span class="meta">${token}<br><span style="font-family: ui-monospace, monospace; font-size: 10px;">${p[token].toUpperCase()}</span></span>
          <span class="prov">${provenance[token] || ""}</span>
        </div>
      `).join("");
      host.innerHTML = `
        ${mock}
        <details class="preview-tokens-details">
          <summary>Show all 12 token swatches</summary>
          <div class="preview-tokens">${swatches}</div>
        </details>
      `;
      host.classList.add("visible");
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, (c) => ({
        "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;",
      }[c]));
    }

    el("cal-select").addEventListener("change", (e) => loadCurrent(e.target.value));
    el("new-btn").addEventListener("click", onNew);
    el("delete-btn").addEventListener("click", onDelete);
    el("save-btn").addEventListener("click", onSave);
    el("set-active-btn").addEventListener("click", onSetActive);
    el("gen-light-btn").addEventListener("click", () => onGenerate("light"));
    el("gen-mid-btn").addEventListener("click", () => onGenerate("midtone"));
    el("gen-dark-btn").addEventListener("click", () => onGenerate("dark"));
    el("gen-save-btn").addEventListener("click", onSavePreview);
    el("gen-discard-btn").addEventListener("click", onDiscardPreview);
    el("pool-filter").addEventListener("change", renderPool);
    el("pool-sort").addEventListener("change", renderPool);

    refreshList().catch((e) => {
      el("grid-host").innerHTML = `<div class="empty">Failed to load: ${e.message}</div>`;
    });
  </script>
</body></html>
"""


# ---------------------------------------------------------------- blueprint


def blueprint() -> Blueprint:
    bp = Blueprint("calibration_admin", __name__)

    @bp.get("/")
    def index() -> str:
        return render_template_string(_PAGE)

    @bp.get("/api/list")
    def api_list() -> Any:
        state = _load_state(_store_path())
        return jsonify(
            {
                "active_id": state["active_id"],
                "saturations": list(SATURATIONS),
                "calibrations": [
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "active_saturation": c["active_saturation"],
                        "rated_count": sum(
                            len(r) for r in c.get("ratings_by_saturation", {}).values()
                        ),
                    }
                    for c in state["calibrations"].values()
                ],
            }
        )

    @bp.get("/api/<cal_id>")
    def api_get(cal_id: str) -> Any:
        state = _load_state(_store_path())
        cal = state["calibrations"].get(cal_id)
        if cal is None:
            return jsonify({"error": "not found"}), 404
        active_sat = int(cal.get("active_saturation", 80))
        # Per-tier rated counts so the UI can show ticks on tabs.
        tier_counts = {
            sat: len(cal["ratings_by_saturation"].get(str(sat), {})) for sat in SATURATIONS
        }
        return jsonify(
            {
                **cal,
                "is_active": state["active_id"] == cal_id,
                "saturations": list(SATURATIONS),
                "tier_counts": tier_counts,
                "cells": _compute_cells(active_sat),
            }
        )

    @bp.post("/api/create")
    def api_create() -> Any:
        body = request.get_json(silent=True) or {}
        name = str(body.get("name") or "").strip() or "Untitled"
        path = _store_path()
        state = _load_state(path)
        new_id = _unique_id(state, _slugify(name))
        cal = _new_calibration(new_id, name[:80])
        state["calibrations"][new_id] = cal
        _save_state(path, state)
        return jsonify(cal), 201

    @bp.patch("/api/<cal_id>")
    def api_update(cal_id: str) -> Any:
        body = request.get_json(silent=True) or {}
        path = _store_path()
        state = _load_state(path)
        cal = state["calibrations"].get(cal_id)
        if cal is None:
            return jsonify({"error": "not found"}), 404
        if "name" in body:
            cal["name"] = str(body["name"] or "").strip()[:80] or cal["name"]
        if "active_saturation" in body:
            requested = int(body["active_saturation"])
            if requested in SATURATIONS:
                cal["active_saturation"] = requested
        _save_state(path, state)
        return jsonify(cal)

    @bp.post("/api/<cal_id>/rate")
    def api_rate(cal_id: str) -> Any:
        body = request.get_json(silent=True) or {}
        cell_id = str(body.get("cell_id") or "")
        rating = body.get("rating")
        sat = body.get("saturation")
        if cell_id not in VALID_CELL_IDS:
            return jsonify({"error": f"unknown cell {cell_id!r}"}), 400
        if rating is not None and rating not in RATINGS:
            return jsonify({"error": f"rating must be one of {RATINGS} or null"}), 400
        path = _store_path()
        state = _load_state(path)
        cal = state["calibrations"].get(cal_id)
        if cal is None:
            return jsonify({"error": "not found"}), 404
        # Default to the calibration's active sat tier when caller doesn't say.
        sat_int = int(sat) if sat is not None else int(cal.get("active_saturation", 80))
        if sat_int not in SATURATIONS:
            return jsonify({"error": f"saturation must be one of {list(SATURATIONS)}"}), 400
        rbs = cal.setdefault("ratings_by_saturation", {})
        ratings = rbs.setdefault(str(sat_int), {})
        if rating is None:
            ratings.pop(cell_id, None)
        else:
            ratings[cell_id] = rating
        _save_state(path, state)
        return jsonify({"cell_id": cell_id, "rating": rating, "saturation": sat_int})

    @bp.post("/api/<cal_id>/activate")
    def api_activate(cal_id: str) -> Any:
        path = _store_path()
        state = _load_state(path)
        if cal_id not in state["calibrations"]:
            return jsonify({"error": "not found"}), 404
        state["active_id"] = cal_id
        _save_state(path, state)
        return jsonify({"active_id": cal_id})

    @bp.delete("/api/<cal_id>")
    def api_delete(cal_id: str) -> Any:
        path = _store_path()
        state = _load_state(path)
        if cal_id not in state["calibrations"]:
            return jsonify({"error": "not found"}), 404
        if len(state["calibrations"]) <= 1:
            return jsonify({"error": "cannot delete the last calibration"}), 400
        del state["calibrations"][cal_id]
        if state["active_id"] == cal_id:
            state["active_id"] = next(iter(state["calibrations"]))
        _save_state(path, state)
        return ("", 204)

    @bp.get("/api/<cal_id>/pool")
    def api_pool(cal_id: str) -> Any:
        """Full theoretical-good pool — visible on the marker page so the user
        can see what the generator has to work with. Unions ratings across
        every saturation tier."""
        state = _load_state(_store_path())
        cal = state["calibrations"].get(cal_id)
        if cal is None:
            return jsonify({"error": "not found"}), 404
        pool = _build_pool(cal.get("ratings_by_saturation", {}))
        # Return a slim payload — drop the cached oklab tuple (only used
        # server-side for snap distance).
        slim = [
            {
                "id": p["id"],
                "hex": p["hex"],
                "provenance": p["provenance"],
                "tier": p["tier"],
                "oklch_l": round(p["oklch_l"], 4),
                "oklch_c": round(p["oklch_c"], 4),
                "oklch_h": round(p["oklch_h"], 2),
            }
            for p in pool
        ]
        return jsonify(
            {
                "calibration_id": cal["id"],
                "calibration_name": cal["name"],
                "active_saturation": cal["active_saturation"],
                "pool_size": len(slim),
                "pool": slim,
            }
        )

    @bp.post("/api/<cal_id>/preview-theme")
    def api_preview_theme(cal_id: str) -> Any:
        """Compute a theme palette without saving. The caller decides whether
        to persist it via POST /api/themes after eyeballing the preview."""
        body = request.get_json(silent=True) or {}
        mode = body.get("mode")
        if mode not in ("light", "midtone", "dark"):
            return jsonify({"error": "mode must be 'light', 'midtone', or 'dark'"}), 400
        seed_hex = body.get("seed_hex") or None
        harmony = body.get("harmony") or "complement"

        state = _load_state(_store_path())
        cal = state["calibrations"].get(cal_id)
        if cal is None:
            return jsonify({"error": "not found"}), 404

        result = _generate_theme_palette(
            cal.get("ratings_by_saturation", {}),
            mode,
            seed_hex=seed_hex,
            harmony=harmony,
        )
        return jsonify(
            {
                "mode": mode,
                "palette": result["palette"],
                "filled": result["filled"],
                "total": 12,
                "fallbacks": result["fallbacks"],
                "provenance": result["provenance"],
                "provenance_counts": result["provenance_counts"],
                "pool_size": result["pool_size"],
                "seed_hex": result["seed_hex"],
                "harmony": result["harmony"],
                "contrast_warnings": result["contrast_warnings"],
            }
        )

    return bp


# --------------------------------------------------------- theme generation


_DEFAULT_LIGHT = {
    "bg": "#e8d8be",
    "surface": "#ffffff",
    "surface2": "#f5e8d8",
    "fg": "#1a1612",
    "fgSoft": "#5a4f44",
    "muted": "#8b7e70",
    "accent": "#d97757",
    "accentSoft": "#aa5a3f",
    "divider": "#c8b89b",
    "danger": "#c97c70",
    "warn": "#d4a957",
    "ok": "#7da670",
}
_DEFAULT_DARK = {
    "bg": "#1a1612",
    "surface": "#241e18",
    "surface2": "#2e261d",
    "fg": "#f5e8d8",
    "fgSoft": "#c8b89b",
    "muted": "#8b7e70",
    "accent": "#d97757",
    "accentSoft": "#e89a7b",
    "divider": "#5a4f44",
    "danger": "#c97c70",
    "warn": "#d4a957",
    "ok": "#7da670",
}


# Tier ranks used for tiebreak ordering. Lower = preferred.
# White (#ffffff at L=1.0) and black (#000000 at L=0.0) used to be auto-injected
# as a tier-1 "always good" set. The OKLab snap metric treats lightness extremes
# as exact matches for any high/low-lightness target, so they monopolised
# bg/surface/fg slots that should hold the user's actual rated paler/darker
# cells. Removed — pool is now exclusively user-rated cells. If the user wants
# pure black or white in their themes, they can rate the closest-lightness grid
# cells (A6, etc.) at high saturation tiers; or the algorithm will fall back to
# muddy or default-theme values.
_TIER_CALIBRATED = 0
_TIER_MUDDY = 3


def _hex_to_rgb(hx: str) -> tuple[int, int, int]:
    h = hx.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(hx: str) -> float:
    """Relative luminance per WCAG, 0–1."""
    r, g, b = (c / 255.0 for c in _hex_to_rgb(hx))

    def lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = (la, lb) if la > lb else (lb, la)
    return (lighter + 0.05) / (darker + 0.05)


def _to_oklab(hx: str) -> tuple[float, float, float]:
    """OKLab coordinates of a hex string (L: 0–1, a/b: ~−0.4 to 0.4)."""
    c = Color(hx).convert("oklab")
    return float(c["lightness"]), float(c["a"]), float(c["b"])


def _to_oklch(hx: str) -> tuple[float, float, float]:
    """OKLCH coordinates (L: 0–1, C: 0–~0.4, H: 0–360). Hue is 0 for grays."""
    c = Color(hx).convert("oklch")
    h = 0.0 if c.is_nan("hue") else float(c["hue"])
    return float(c["lightness"]), float(c["chroma"]), h


def _oklab_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _annotate(cell: dict[str, Any], *, tier: int, provenance: str) -> dict[str, Any]:
    """Pool entry with cached perceptual coords for distance + display."""
    oklch_l, oklch_c, oklch_h = _to_oklch(cell["hex"])
    oklab = _to_oklab(cell["hex"])
    return {
        **cell,
        "tier": tier,
        "provenance": provenance,
        "luminance": _luminance(cell["hex"]),
        "oklab": oklab,
        "oklch_l": oklch_l,
        "oklch_c": oklch_c,
        "oklch_h": oklch_h,
    }


def _build_pool(
    ratings_by_saturation: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """Theme-generation candidate pool — strictly user-validated colours.

    Contents (in tier order):
      - calibrated good cells across ALL sat tiers   (tier 0)
      - calibrated muddy cells (fallback only)        (tier 3)

    No synthetic mixes, no auto-injected pure white/black. Earlier versions
    auto-injected #ffffff and #000000 as "always-good" seeds since they're
    Spectra 6 native inks, but they sit at OKLab lightness extremes (1.0 and
    0.0) so the snap metric defaulted to them for any high/low-lightness
    target — drowning out the user's actual rated pale or dark cells.
    Constraining to validated cells produces themes that are 100% colours the
    user has signed off on; if no candidate exists the per-token fallback to
    `_DEFAULT_LIGHT`/`_DEFAULT_DARK` kicks in.
    """
    good_cells: list[dict[str, Any]] = []
    muddy_cells: list[dict[str, Any]] = []
    for sat_str, ratings in ratings_by_saturation.items():
        try:
            sat = int(sat_str)
        except ValueError:
            continue
        sat_cells = _compute_cells(sat)
        by_id = {c["id"]: c for c in sat_cells}
        for cell_id, rating in ratings.items():
            cell = by_id.get(cell_id)
            if not cell:
                continue
            tagged = {**cell, "id": f"{cell_id}@s{sat}"}
            if rating == "good":
                good_cells.append(tagged)
            elif rating == "muddy":
                muddy_cells.append(tagged)

    pool: list[dict[str, Any]] = []
    seen_hex: set[str] = set()

    def add(entry: dict[str, Any]) -> None:
        hx = entry["hex"].lower()
        if hx in seen_hex:
            return
        seen_hex.add(hx)
        pool.append(entry)

    for cell in good_cells:
        add(_annotate(cell, tier=_TIER_CALIBRATED, provenance="calibrated"))
    for cell in muddy_cells:
        add(_annotate(cell, tier=_TIER_MUDDY, provenance="muddy"))

    return pool


# ============================================================================
# Color-theory-driven theme generation.
#
# The naive "pick closest L per token" generator produced incoherent themes
# because every token was chosen independently. This version derives every
# token from a single seed colour via Material-3-inspired tonal palettes:
#
#   1. Pick a SEED — most-chromatic calibrated good colour (or user-provided).
#   2. Apply a HARMONY rule (complement / split / triad / etc.) to derive 1–3
#      additional anchor hues.
#   3. Build five logical PALETTES at OKLCH(target_L, anchor_chroma, anchor_hue):
#        - primary, secondary, tertiary  (driven by the harmony hues)
#        - neutral, neutral-variant      (very low chroma at the seed hue —
#          gives the theme a "tinted gray" feel coherent with the accent)
#      Plus three semantic palettes pinned to fixed hues:
#        - error (red), warn (orange), ok (green)
#   4. Map each of our 12 tokens to a (palette, target_L) pair (LIGHT_TOKENS /
#      DARK_TOKENS), compute the ideal OKLCH colour, then SNAP it to the
#      nearest pool colour by OKLab distance — so every token lands on a hex
#      the user has validated (or a mix of validated colours).
#   5. CONTRAST PASS: re-pick fg / fgSoft from the pool if they don't reach
#      WCAG targets vs. bg.
# ============================================================================

# Token → (palette name, target OKLCH lightness 0–1).
# Duotone token maps: every theme uses TWO opposite hues — the seed family
# for bg/surface (the page's "warmth"), and the complement family for fg /
# divider / muted (the ink that sits ON it). On Spectra 6 this guarantees
# strong colour contrast in addition to lightness contrast, so widgets render
# clearly even when surrounding palette tones dither down to similar luminance.
#
# Light-mode targets sit at L≈0.78-0.85 (not L=0.97/1.00) because:
#   1. Without #ffffff in the pool, the user's lightest rated cell tops out at
#      ~L=0.85; targeting higher just means every bg/surface token snaps to
#      that same lightest cell (collapsing distinct tokens onto one colour).
#   2. At the pool's actual lightness range, real chroma is available, so a
#      red-seeded theme can pick a pale-red cell rather than collapsing to
#      whichever cell happens to be lightest regardless of hue.
LIGHT_TOKENS: dict[str, tuple[str, float]] = {
    "bg": ("neutral", 0.83),
    "surface": ("neutral", 0.88),
    "surface2": ("neutral-variant", 0.73),
    "fg": ("neutral-complement", 0.22),
    "fgSoft": ("neutral-complement", 0.40),
    "muted": ("neutral-variant-complement", 0.50),
    "divider": ("neutral-variant-complement", 0.68),
    "accent": ("primary", 0.55),
    "accentSoft": ("secondary", 0.55),
    "danger": ("error", 0.55),
    "warn": ("warn", 0.65),
    "ok": ("ok", 0.55),
}

DARK_TOKENS: dict[str, tuple[str, float]] = {
    "bg": ("neutral", 0.18),
    "surface": ("neutral", 0.22),
    "surface2": ("neutral-variant", 0.28),
    "fg": ("neutral-complement", 0.95),
    "fgSoft": ("neutral-complement", 0.78),
    "muted": ("neutral-variant-complement", 0.62),
    "divider": ("neutral-variant-complement", 0.35),
    "accent": ("primary", 0.72),
    "accentSoft": ("secondary", 0.72),
    "danger": ("error", 0.72),
    "warn": ("warn", 0.78),
    "ok": ("ok", 0.70),
}

# Midtone — bg sits at L≈0.72 with substantial chroma so the panel's dither
# actually has to mix coloured ink into the surface, producing kraft / sage /
# coral / slate. Without this, light themes with bg L≈0.97 collapse to white
# on Spectra 6's 6-ink gamut. Stored as a light-mode theme since fg < bg.
MIDTONE_TOKENS: dict[str, tuple[str, float]] = {
    "bg": ("neutral", 0.72),
    "surface": ("neutral", 0.80),
    "surface2": ("neutral-variant", 0.62),
    "fg": ("neutral-complement", 0.18),
    "fgSoft": ("neutral-complement", 0.35),
    "muted": ("neutral-variant-complement", 0.45),
    "divider": ("neutral-variant-complement", 0.50),
    "accent": ("primary", 0.45),
    "accentSoft": ("secondary", 0.45),
    "danger": ("error", 0.48),
    "warn": ("warn", 0.55),
    "ok": ("ok", 0.48),
}

# Per-palette anchor chromas. Lower = more muted. These were tuned by eye
# against the OKLCH gamut: too-high chroma at extreme lightness gets clipped
# and produces the same hex regardless of hue.
_PALETTE_CHROMA: dict[str, float] = {
    "primary": 0.16,
    "secondary": 0.10,
    "tertiary": 0.13,
    "neutral": 0.005,
    "neutral-variant": 0.022,
    "error": 0.18,
    "warn": 0.16,
    "ok": 0.16,
}

# Hue anchors (OKLCH) for the semantic palettes — these are pinned to the
# hue family the role demands, regardless of the user's seed.
_SEMANTIC_HUES: dict[str, float] = {
    "error": 28.0,  # red
    "warn": 75.0,  # orange-yellow
    "ok": 145.0,  # green
}

HARMONIES = ("complement", "split", "triad", "square", "analogous", "mono")


def _hues_from_harmony(seed_h: float, name: str) -> list[float]:
    """Return [primary, secondary?, tertiary?] hues in OKLCH."""
    if name == "mono":
        return [seed_h, seed_h, seed_h]
    if name == "complement":
        return [seed_h, (seed_h + 180) % 360, (seed_h + 180) % 360]
    if name == "analogous":
        return [seed_h, (seed_h - 30) % 360, (seed_h + 30) % 360]
    if name == "split":
        return [seed_h, (seed_h + 150) % 360, (seed_h + 210) % 360]
    if name == "triad":
        return [seed_h, (seed_h + 120) % 360, (seed_h + 240) % 360]
    if name == "square":
        return [seed_h, (seed_h + 90) % 360, (seed_h + 180) % 360]
    return [seed_h, seed_h, seed_h]


def _pick_seed(pool: list[dict[str, Any]]) -> str:
    """Most-chromatic calibrated good colour. Falls back to white if none."""
    calibrated = [c for c in pool if c["provenance"] == "calibrated"]
    if not calibrated:
        # No user input at all — use a tasteful default seed (warm coral).
        return "#d97757"
    return max(calibrated, key=lambda c: c["oklch_c"])["hex"]


def _ideal_color(
    palette_name: str,
    target_l: float,
    hues: list[float],
    chroma_map: dict[str, float] | None = None,
) -> tuple[float, float, float]:
    """Compute ideal OKLab colour for a (palette, lightness) target.

    `chroma_map` overrides the per-generation chroma values (e.g. neutrals
    that have been tinted to match the seed). Falls back to the static map.

    The ``-complement`` palettes share their counterpart's chroma but use the
    secondary harmony hue — these power the duotone bg/fg split, where the
    background sits in the seed hue family and the foreground in the
    complementary family for maximum hue + lightness contrast.
    """
    cmap = chroma_map or _PALETTE_CHROMA
    if palette_name == "neutral-complement":
        chroma = cmap["neutral"]
        hue = hues[1]
    elif palette_name == "neutral-variant-complement":
        chroma = cmap["neutral-variant"]
        hue = hues[1]
    else:
        chroma = cmap[palette_name]
        if palette_name in _SEMANTIC_HUES:
            hue = _SEMANTIC_HUES[palette_name]
        elif palette_name == "primary":
            hue = hues[0]
        elif palette_name == "secondary":
            hue = hues[1]
        elif palette_name == "tertiary":
            hue = hues[2]
        else:  # neutral, neutral-variant — anchor on seed hue for coherence
            hue = hues[0]
    c = Color("oklch", [target_l, chroma, hue]).convert("oklab")
    return float(c["lightness"]), float(c["a"]), float(c["b"])


def _snap(target_oklab: tuple[float, float, float], pool: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick pool entry minimising OKLab distance to target. Tiebreak by tier."""
    return min(
        pool,
        key=lambda c: (_oklab_distance(target_oklab, c["oklab"]), c["tier"]),
    )


def _enforce_contrast(
    palette: dict[str, str],
    provenance: dict[str, str],
    pool: list[dict[str, Any]],
    mode: str,
) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Walk fg/fgSoft toward black/white if they don't meet WCAG targets."""
    warnings: list[str] = []
    bg_hex = palette["bg"]
    # midtone is light-ish (fg < bg), so we walk toward black like a light theme.
    extreme_oklab = _to_oklab("#ffffff" if mode == "dark" else "#000000")

    for fg_token, target_ratio in (("fg", 7.0), ("fgSoft", 4.5)):
        if _contrast(palette[fg_token], bg_hex) >= target_ratio:
            continue
        candidates = [c for c in pool if _contrast(c["hex"], bg_hex) >= target_ratio]
        if not candidates:
            warnings.append(f"{fg_token}: no candidate hits {target_ratio}:1 vs bg")
            continue
        best = min(candidates, key=lambda c: _oklab_distance(c["oklab"], extreme_oklab))
        palette[fg_token] = best["hex"]
        provenance[fg_token] = best["provenance"]
    return palette, provenance, warnings


def _generate_theme_palette(
    ratings_by_saturation: dict[str, dict[str, str]],
    mode: str,
    *,
    seed_hex: str | None = None,
    harmony: str = "complement",
) -> dict[str, Any]:
    """Color-theory-driven palette generation.

    Builds tonal palettes around the seed + harmony anchors, snaps each token
    target to the nearest pool colour in OKLab distance, then enforces WCAG
    contrast on fg / fgSoft. The neutral palette's chroma scales with the
    seed's chroma so themes carry their identity into bg/surface, not just
    accent. The accent itself is anchored to the seed hex when available so
    each generated theme has a distinctive primary colour.
    """
    if harmony not in HARMONIES:
        harmony = "complement"

    pool = _build_pool(ratings_by_saturation)
    # Midtone is a light-ish theme (fg < bg), so its fallback uses light defaults.
    fallback_palette = _DEFAULT_DARK if mode == "dark" else _DEFAULT_LIGHT

    if not pool:
        return {
            "palette": dict(fallback_palette),
            "provenance": {k: "fallback" for k in fallback_palette},
            "provenance_counts": {"fallback": 12},
            "fallbacks": list(fallback_palette.keys()),
            "filled": 0,
            "pool_size": 0,
            "seed_hex": None,
            "harmony": harmony,
            "contrast_warnings": [],
        }

    actual_seed = seed_hex or _pick_seed(pool)
    seed_oklch = _to_oklch(actual_seed)
    seed_l, seed_c, seed_h = seed_oklch
    hues = _hues_from_harmony(seed_h, harmony)

    # Per-generation chroma map, derived from the seed. A vivid seed pushes
    # chroma into bg/surface (themed neutrals); a muted seed keeps them gray.
    chroma_map = dict(_PALETTE_CHROMA)
    if mode == "midtone":
        # Midtone bgs sit at L≈0.70 — they need real chroma to look like
        # tinted paper rather than dirty gray. Push chroma 3-4× higher than
        # the dark presets so the panel dithers actual coloured ink in.
        chroma_map["neutral"] = max(0.030, min(0.090, seed_c * 0.35))
        chroma_map["neutral-variant"] = max(0.050, min(0.130, seed_c * 0.55))
    elif mode == "light":
        # Light bgs at L≈0.85 need substantial chroma so the snap-to-pool
        # actually picks a seed-tinted pale cell rather than whichever pale
        # cell is closest to neutral grey. With chroma <0.02 the target's a/b
        # values are tiny, so the pool cell with the smallest |a|+|b| wins
        # regardless of seed → all light themes converge on the same colour.
        chroma_map["neutral"] = max(0.025, min(0.070, seed_c * 0.25))
        chroma_map["neutral-variant"] = max(0.040, min(0.100, seed_c * 0.40))
    else:
        # Dark mode — bgs at L≈0.18 sit far enough from any pool cell that
        # subtle chroma is fine; pushing harder muddies the dark tone.
        chroma_map["neutral"] = max(0.005, min(0.022, seed_c * 0.08))
        chroma_map["neutral-variant"] = max(0.020, min(0.070, seed_c * 0.20))

    if mode == "light":
        token_map = LIGHT_TOKENS
    elif mode == "midtone":
        token_map = MIDTONE_TOKENS
    else:
        token_map = DARK_TOKENS
    palette: dict[str, str] = {}
    provenance: dict[str, str] = {}

    for token, (palette_name, target_l) in token_map.items():
        # `accent` anchors directly on the seed hex when the user picked it.
        # The seed is by definition calibrated, so it's safe — and using it
        # verbatim makes the generated theme actually feel like the seed.
        if token == "accent":
            palette[token] = actual_seed
            provenance[token] = "seed"
            continue
        target_oklab = _ideal_color(palette_name, target_l, hues, chroma_map)
        snapped = _snap(target_oklab, pool)
        palette[token] = snapped["hex"]
        provenance[token] = snapped["provenance"]

    palette, provenance, warnings = _enforce_contrast(palette, provenance, pool, mode)

    counts: dict[str, int] = {}
    for prov in provenance.values():
        counts[prov] = counts.get(prov, 0) + 1
    fallbacks = [t for t, p in provenance.items() if p == "fallback"]
    return {
        "palette": palette,
        "provenance": provenance,
        "provenance_counts": counts,
        "fallbacks": fallbacks,
        "filled": 12 - len(fallbacks),
        "pool_size": len(pool),
        "seed_hex": actual_seed,
        "harmony": harmony,
        "contrast_warnings": warnings,
    }
