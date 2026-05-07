# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 5 (v0.6.0).** Themes + fonts are first-class plugins. `themes_core` ships 12 hand-tuned palettes (light + dark) with all 12 schema-required keys; `fonts_core` ships 5 webfonts (Inter, Lexend, Lora, JetBrains Mono, Bebas Neue) as latin-subset woff2. The composer resolves `page.theme` / `page.font` against the registry and emits `@font-face` rules + per-cell `--theme-*` CSS variables. Cells override their page's theme or font via optional `cell.theme` / `cell.font`. The editor at `/editor/<page_id>` now drives everything live: layout dropdown (with four hero presets), theme + font selectors, gap + corner-radius sliders, per-cell overrides, and auto-save on every edit. The abstract layout canvas is gone — the live iframe IS the cell picker, with click-targets that follow the gap inset. `/themes` shows every loaded theme as palette swatches and every font as a live sample. See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

## Quick start

```bash
# Python side
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium

# JS side (Bun in CI; npm works locally too)
bun install && bun run build      # or: npm install && npm run build

# Run the dev server
# To enable push, set MQTT_HOST (and friends) before launching:
#   export MQTT_HOST=192.168.1.50     # broker the Pi listener subscribes to
#   export COMPANION_BASE_URL=http://192.168.1.10:5555  # how the Pi reaches us
python -m app
# http://localhost:5555/                                   — index
# http://localhost:5555/editor/_demo                       — page editor + preview + push
# http://localhost:5555/themes                             — themes + fonts viewer
# http://localhost:5555/_components                        — design system demo
# http://localhost:5555/compose/_demo                      — what Playwright screenshots
# http://localhost:5555/api/pages/_demo/raw.png            — pre-quantize render
# http://localhost:5555/api/pages/_demo/preview.png        — quantized render (panel paint)
# http://localhost:5555/api/pages/_demo/push  (POST)       — render + quantize + publish
# http://localhost:5555/api/history                        — recent push attempts
# http://localhost:5555/api/listener/status                — last retained status from listener
# http://localhost:5555/api/themes                         — loaded themes (JSON)
# http://localhost:5555/api/fonts                          — loaded fonts (JSON)
# http://localhost:5555/_test/render?plugin=clock&size=md

# Run the checks
ruff check . && ruff format --check . && mypy && pytest
```

Python 3.11+ required.

## Layout

```
app/                Flask application
  state/            mypy --strict — page model, page store, future schedules + history
  composer.py       /compose/<page_id> + /_test/render
  admin.py          /editor + /_components + /api/pages + /api/widgets + preview PNGs
  plugin_loader.py  mypy --strict — discovery + schema validation + asset routes
  renderer.py       mypy --strict — Playwright wrapper, screenshot at panel resolution
  quantizer.py      Pillow-based gamut projection (Spectra 6) + Floyd–Steinberg dither
  mqtt_bridge.py    paho-mqtt publisher + listener-status subscriber; NullBridge fallback
  push.py           mypy --strict — single-flight PushManager (render→quantize→publish)
docs/               Build brief + plugin contract
plugins/<id>/       Drop-a-folder plugin (kind=widget|theme|font|admin)
  clock/            Bundled widget — fits text via JS measurement
  themes_core/      12 starter palettes
  fonts_core/       Inter / Lexend / Lora / JetBrains Mono / Bebas Neue (woff2)
schema/             JSON Schemas (plugin manifest, page model)
static/
  components/       Lit design system (id-* web components)
  pages/            Editor + components-demo entry points
  composer.js       Bootstrap that mounts plugins into shadow DOMs
  dist/             Build output (gitignored)
  types/            Generated TS types (gitignored)
templates/          Jinja shells: compose, editor, components_demo
tests/              Top-level pytest suite
conftest.py         Root fixtures shared with plugin smoke tests
tools/              gen-page-types.mjs (schema → .d.ts)
.github/            CI: Python + Bun + Playwright + bundle build
```

The renderer, MQTT bridge, theme/font system, schedules, and the rest of the plugin set land in later milestones — see the brief.

## License

MIT.
