# Inky Dash

Flask companion that composes dashboards in the browser, renders them to PNG, and pushes them to a Pimoroni Inky Impression panel over MQTT.

This is **v4** — a from-scratch rebuild of v3 (now archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag). The v3 → v4 rationale and the milestone roadmap live in [`docs/v4-brief.md`](docs/v4-brief.md); the plugin contract lives in [`docs/v4-plugins.md`](docs/v4-plugins.md). User-facing docs live in the [GitHub Wiki](https://github.com/dmellok/inky-dash/wiki).

The Pi-side listener is a separate project: [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener). The MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

## Status

**Milestone 7 (v0.8.0).** Schedules + Send page. A background `Scheduler` daemon thread fires schedules whose time has come — `interval` (every N minutes) or `oneshot` (a single fire at a specific datetime). Both honour a day-of-week mask, an optional time-of-day window (with wrap-around for night-time hours), and a numeric priority. `/schedules` is the admin page (list + create/edit/delete + manual "Fire now"); `/send` is a one-page push tool that takes saved dashboards, image URLs, webpages (screenshotted), or uploaded files. PushManager grew `push_image` (raw bytes) and `push_webpage` (any URL) entry points; everything still goes through the same single-flight lock + history pipeline. See [`docs/v4-brief.md`](docs/v4-brief.md) for the full milestone plan up to v1.0.

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
# http://localhost:5555/schedules                          — schedules admin
# http://localhost:5555/send                               — send-anything page
# http://localhost:5555/api/schedules                      — schedules CRUD
# http://localhost:5555/api/send/{page,url,webpage,file}   — send pipelines
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
  clock/            Digital time, fits to cell via JS measurement
  countdown/        Days until / since a target date
  year_progress/    Day-of-year hero + 52-week ribbon
  sun_moon/         SVG sun arc (current position) + moon-phase disc
  weather/          Open-meteo current + 3-day outlook
  air_quality/      Open-meteo European AQI + pollutant tiles
  hn/               Hacker News top / new / best / ask / show
  news/             Generic RSS / Atom feed
  todo/             Quick-entry list (admin form at /plugins/todo/)
  gallery/          Folder rotation, full_bleed (admin at /plugins/gallery/)
  themes_core/      12 starter palettes + user-created via /themes
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
