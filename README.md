# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 1 (v0.2.0).** Plugin contract live: the loader discovers folders under `plugins/`, validates each `plugin.json` against `schema/plugin.schema.json`, and serves `client.js`/`client.css` over HTTP. Bundled `clock` plugin renders at all four cell-size breakpoints (xs/sm/md/lg). Composer route `/compose/<page_id>` mounts plugin instances into per-cell shadow DOMs. See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium   # for plugin smoke tests

# Run the dev server
python -m app          # http://localhost:5555
                       # http://localhost:5555/compose/_demo  — clock at full panel size
                       # http://localhost:5555/_test/render?plugin=clock&size=md

# Run the checks
ruff check . && ruff format --check . && mypy && pytest
```

Python 3.11+ required.

## Layout

```
app/                Flask application (factory, plugin loader, composer)
docs/               Build brief + plugin contract
plugins/<id>/       One folder per plugin; each holds plugin.json,
                    client.js, client.css (optional), tests/
schema/             JSON Schemas (plugin manifest today; page model in M2)
static/             Composer bootstrap JS (mounts plugins into shadow DOMs)
templates/          Jinja shells (compose.html today)
tests/              Top-level pytest suite (loader unit tests, route tests)
conftest.py         Root-level fixtures shared with plugin smoke tests
.github/            CI workflow (ruff + mypy + pytest + Playwright)
```

The renderer, MQTT bridge, theme/font system, page editor, and full plugin set all land in later milestones — see the brief.

## License

MIT.
