# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 3 (v0.4.0).** Render + quantize pipeline live. `app/renderer.py` drives headless Chromium via Playwright at panel resolution; `app/quantizer.py` projects to the Spectra 6 7-colour gamut (Floyd–Steinberg dither default, nearest-colour for "none"). The editor's preview pane shows the live iframe and the quantized PNG side-by-side — what the user sees in the browser is what the panel will paint. WYSIWYG by construction. See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

## Quick start

```bash
# Python side
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium

# JS side (Bun in CI; npm works locally too)
bun install && bun run build      # or: npm install && npm run build

# Run the dev server
python -m app
# http://localhost:5555/                                   — index
# http://localhost:5555/editor/_demo                       — page editor + preview pane
# http://localhost:5555/_components                        — design system demo
# http://localhost:5555/compose/_demo                      — what Playwright screenshots
# http://localhost:5555/api/pages/_demo/raw.png            — pre-quantize render
# http://localhost:5555/api/pages/_demo/preview.png        — quantized render (panel paint)
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
docs/               Build brief + plugin contract
plugins/<id>/       Drop-a-folder plugin: plugin.json + client.js + tests/
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
