# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 2 (v0.3.0).** Page model live: `schema/page.schema.json` is the source of truth, hand-aligned pydantic models in `app/state/`, and TS type definitions auto-generated into `static/types/page.d.ts`. The composer reads pages from `data/core/pages.json` (atomic writes via tmp-rename); a demo page is seeded on first run. The Lit-based design system (`id-button`, `id-card`, `id-slider`, `id-tab-bar`, `id-form-row`) lives at `/_components`. The editor at `/editor/<page_id>` exercises the full schema flow: pick a layout preset, assign a plugin per cell, edit `cell_options`, save → server validates with pydantic → file. Bundle is built by esbuild (~30 KB minified per entry). See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

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
# http://localhost:5555/                          — index
# http://localhost:5555/editor/_demo              — page editor
# http://localhost:5555/_components               — design system demo
# http://localhost:5555/compose/_demo             — composer (what Playwright will screenshot)
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
  admin.py          /editor + /_components + /api/pages + /api/widgets
  plugin_loader.py  mypy --strict — discovery + schema validation + asset routes
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
