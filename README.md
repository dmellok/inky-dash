# Inky Dash

Flask companion that composes dashboards in the browser, renders them through Playwright + Pillow, and pushes them to a Pimoroni Inky Impression e-ink panel over MQTT. Drop a folder under `plugins/` and you have a new widget; drop another and you have a new theme. The Pi-side listener lives in [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener) — the MQTT wire format is byte-for-byte identical to v3, so the same listener works on both.

This is **v4**. Architecture overview in [`docs/architecture.md`](docs/architecture.md); usage tutorial in the [wiki](https://github.com/dmellok/inky-dash/wiki/Writing-a-plugin); two reference plugins live at [`plugins/example_minimal/`](plugins/example_minimal/) and [`plugins/example_full/`](plugins/example_full/). The v3 source is archived at the [`v3-final`](https://github.com/dmellok/inky-dash/tree/v3-final) tag.

![Editor — live preview + cell config sidebar](docs/screenshots/page-editor.png)

## Heads up — this is a hobby project

Inky Dash is built and maintained as a personal project, aimed at people who're comfortable installing Python, running an MQTT broker, and tinkering with their own Pi. It's not a polished consumer product, and a few rough edges come with the territory:

- **No authentication on the admin UI.** Anyone who can reach port 5555 gets full access — including your MQTT credentials, API keys, and any WiFi passwords stored in QR widgets. **Run it on a private network only.** Don't port-forward it to the internet; if you need remote access, use a VPN / Tailscale.
- **Single-user, single-host.** There's no concept of accounts or multi-tenancy. Whoever opens the UI is the admin.
- **Schema migrations are best-effort.** Plugin manifests and settings are versioned, but breaking changes between releases may need a manual nudge. Back up `data/` before upgrading if you've customised heavily.
- **Maintained as time allows.** Issues + PRs are welcome and read, but response times will be variable. The bus factor is one.

If those trade-offs are fine for your use case (a panel on your wall, on your home network, that you're happy to tinker with), it works well. If you need auth, multi-user, or an internet-facing install, this isn't the right tool yet.

## Quick start

```bash
# Python side
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m playwright install chromium

# JS side (Bun in CI; npm works locally too)
bun install && bun run build      # or: npm install && npm run build

# Configure MQTT before launching if you want to push to a real panel:
#   export MQTT_HOST=192.168.1.50              # broker the Pi listener subscribes to
#   export COMPANION_BASE_URL=http://192.168.1.10:5555  # how the Pi reaches us
python -m app
# http://localhost:5555/
```

Python 3.11+ required. Pre-flight checks:

```bash
ruff check . && ruff format --check . && mypy && pytest
```

## What's in the box

- **Dashboard editor** — split the panel into cells from a layout picker, click a cell to configure its widget + theme + font in the sidebar, live preview rendered in an iframe. Saved pages live in [`data/core/pages.json`](data/core/pages.json).
- **29 widget plugins** — clock, flip clock, weather, calendar, todo (multi-list), world clock, year-progress, sun & moon, AQI trend, HN, Reddit, news (RSS), Trakt watchlist posters, gallery, APOD, Unsplash, Wikimedia Picture of the Day, GitHub contributions heatmap, weather radar, star map, generative art, Home Assistant tile, Melbourne PTV departures, QR code (URL / WiFi / text), countdown, note, xkcd, webpage screenshot, calibration, frame aligner. (Two reference plugins — `example_minimal`, `example_full` — ship as the canonical "how to write one" docs.)
- **49 hand-curated themes** — bucketed into **White** (6 bold-accent stark-white themes), **Light** (Paper / Linen / Mist / Ink / Burgundy / …), **Medium**, and **Dark** (Cyber / Embers / Reef / Flamingo / Peach + 15 monochrome + 5 neon). 7 of them put the typography itself in saturated ink rather than neutral grey. Build your own at `/themes`.
- **Schedules** — one-shot daily-at-HH:MM or every-N-minutes, with day-of-week + time-of-day-window guards. Backfill-safe (won't replay a day's worth of fires when re-enabled mid-day).
- **Send page** — push any image, saved dashboard, image URL, or arbitrary webpage to the panel right now. Includes fit modes (fit / fill / stretch / center / blurred-bg) for one-off images, plus a history tab with thumbnails, resend, delete, and a click-to-zoom lightbox.
- **Per-cell theme overrides** — each cell can paint in its own theme without affecting siblings.
- **MQTT push pipeline** — single-flight `PushManager` with identical-push debounce, content-addressed render cache, LRU eviction, and a full push history.

## Editor

Click any cell in the live-preview to edit it. Theme, font, and matting apply to the whole page; cells can override theme + font individually.

| Editor list | Editor |
|---|---|
| ![Editor list page](docs/screenshots/page-editor-list.png) | ![Editor with a dashboard open](docs/screenshots/page-editor.png) |

The cell sidebar surfaces every option each plugin declares in its manifest — text fields, numbers, booleans, selects, and dynamic dropdowns (e.g. todo's list picker, gallery's folder picker). Per-cell colour overrides let you nudge individual tokens (`accent`, `surface`, `divider`, etc.) without forking the theme.

## Dashboards in the wild

Five sample 1200×1600 dashboards, each leaning on a different theme to show how the design language reskins. The screenshots below are the same Playwright render the panel actually receives; the data (groceries, reading list, today, home) comes from real lists managed at `/plugins/todo/`.

| Good morning — **Paper** | Cyber desk — **Cyber** | Ink study — **Ink** |
|---|---|---|
| ![Paper dashboard](docs/screenshots/dash-paper-morning.png) | ![Cyber dashboard](docs/screenshots/dash-cyber-desk.png) | ![Ink dashboard](docs/screenshots/dash-ink-study.png) |
| Weather hero · Groceries list · HN top stories · Year-progress footer. The default white-cream palette — what you get out of the box. | Big 24h clock · GitHub contributions heatmap · HN feed. The terminal/synthwave vibe: electric green typography, magenta accent, JetBrains Mono throughout. | Calendar with Phases of the Moon · Reading list · Year progress · Marginalia quote. Navy fountain-pen ink on warm cream — academic, monochromatic, calm. |

| Embers evening — **Embers** | Cherry pop — **Cherry** | |
|---|---|---|
| ![Embers dashboard](docs/screenshots/dash-embers-evening.png) | ![Cherry dashboard](docs/screenshots/dash-cherry-pop.png) | |
| Weather · Sun & moon · Home chores · r/EarthPorn. Warm orange ink on a deep brown bg — pairs naturally with the Spectra 6 orange primary. | Headline clock · Today list (with done items struck through) · Weather · 234-day countdown to New Year. White bg + a single bold cherry-red accent. | |

The five pages are saved as `show-paper-morning`, `show-cyber-desk`, `show-ink-study`, `show-embers-evening`, `show-cherry-pop` — open any of them at `/editor/<id>` and remix them as a starting point for your own.

## Widgets

Every widget shares a baseline of design tokens defined in [`static/style/widget-base.css`](static/style/widget-base.css) — same header strip, same flat surface tiles, same status pills — so the panel reads as one design system.

### Information widgets

| Weather | Hacker News | News (RSS) |
|---|---|---|
| ![Weather widget](docs/screenshots/widget-weather.png) | ![Hacker News widget](docs/screenshots/widget-hn.png) | ![News widget](docs/screenshots/widget-news.png) |

| Todo | Year progress | World clock |
|---|---|---|
| ![Todo widget](docs/screenshots/widget-todo.png) | ![Year progress widget](docs/screenshots/widget-year_progress.png) | ![World clock widget](docs/screenshots/widget-world_clock.png) |

| Sun & moon | Air-quality trend | GitHub contributions |
|---|---|---|
| ![Sun & moon widget](docs/screenshots/widget-sun_moon.png) | ![AQI trend widget](docs/screenshots/widget-aqi_trend.png) | ![GitHub heatmap widget](docs/screenshots/widget-github_heatmap.png) |

| Countdown | Note | Clock |
|---|---|---|
| ![Countdown widget](docs/screenshots/widget-countdown.png) | ![Note widget](docs/screenshots/widget-note.png) | ![Clock widget](docs/screenshots/widget-clock.png) |

| Star map | Calendar | QR code |
|---|---|---|
| ![Star map widget](docs/screenshots/widget-starmap.png) | ![Calendar widget](docs/screenshots/widget-calendar.png) | ![QR code widget](docs/screenshots/widget-qr.png) |

| Reddit | | |
|---|---|---|
| ![Reddit widget](docs/screenshots/widget-reddit.png) | | |

### Visual widgets

| Generative art | Wikimedia POTD |
|---|---|
| ![Generative art widget](docs/screenshots/widget-genart.png) | ![Wikimedia Picture of the Day widget](docs/screenshots/widget-wikipotd.png) |

Plus APOD, Unsplash, gallery (folder rotation with portrait/landscape/square filter), xkcd, weather radar (RainViewer + CartoDB), and webpage-screenshot widgets. All can be set `full_bleed` so they paint edge-to-edge with no surrounding chrome.

### Smart-home + transit

- **Home Assistant tile** — bundle up to 8 HA entities into a tile (grid, list, or hero layout). Needs a long-lived access token in `/settings`.
- **Melbourne PTV** — live train/tram/bus/V-Line departures for any PTV stop. Needs a free PTV dev ID + API key; lookup tool at `/plugins/ptv/?q=...`.

## Schedules

Schedules fire pushes automatically. Each row gets a deterministic per-schedule colour so the day-band timeline reads at a glance. The "now" cursor slides across all rows in unison; the band starts at 06:00 so each calendar day reads top-down naturally.

![Schedules page with day-band timeline](docs/screenshots/page-schedules.png)

Two schedule types:
- **Interval** — every N minutes within an optional `time_of_day_start..end` window on selected days of the week.
- **Daily** — once a day at HH:MM on selected days. Mid-day enables don't backfill the morning's missed firings.

## Send page

Push anything right now. Source tabs across the top: File / Saved dashboard / Image URL / Webpage / History.

| Send (compose) | Send (history) |
|---|---|
| ![Send page — compose tab](docs/screenshots/page-send.png) | ![Send page — history tab with thumbnails](docs/screenshots/page-send-history.png) |

The preview pane renders at panel aspect-ratio with the Floyd–Steinberg quantizer the panel will see. Fit modes for File + Image URL: **fit** (letterbox) · **fill** (cover-crop) · **stretch** (distort) · **center** (no scaling) · **blurred** (server-side composite — blurred cover-fit background with the original aspect-preserved on top).

The History tab is the live `PushManager` history with thumbnails of every published render. Click a thumbnail for a full-screen zoom; the resend button re-publishes the exact stored render without re-rendering; delete removes the row and (when no other row references the same digest) the PNG too.

## Themes

49 themes bucketed by background lightness — **White** (the 6 stark-white-bg bold-accent themes: Cobalt / Flame / Magenta / Kelly / Royal / Cherry), **Light** (Paper / Linen / Ink / Burgundy / …), **Medium**, and **Dark** (Cyber / Embers / Reef / Flamingo / Peach + 15 monochrome + 5 neon). A chip picker at the top of `/themes` filters down to one bucket at a time, plus a "Mine" filter for user-saved themes once any exist.

Seven themes are designed around a **vibrant foreground colour** — the typography itself prints in saturated ink rather than neutral grey: Ink (navy on cream), Burgundy (wine on parchment), Embers (orange on brown), Cyber (electric green on near-black), and the coral family (Reef / Flamingo / Peach). On Spectra 6 these dither into the actual coloured inks rather than collapsing to a near-black.

The theme picker shows a compact preview mock — built from the same flat-surface widget chrome the real cells use — so any palette regression in a single token is visible immediately. Build a new theme at `/themes`; user-created ones save alongside the built-ins and bucket into "Mine" in the picker.

![Themes page](docs/screenshots/page-themes.png)

## Settings

Per-plugin settings (the manifest declares which fields each plugin exposes), app-level MQTT + panel + base-URL config, and theme-builder admin. Secrets are masked over the wire — they live server-side and never round-trip back to the browser.

![Settings page](docs/screenshots/page-settings.png)

## Index

The status page summarises everything at a glance: MQTT bridge state, last push, listener log, available pages, scheduled jobs.

![Home / index page](docs/screenshots/page-home.png)

## Layout

```
app/                Flask application
  state/            mypy --strict — page model + stores (pages, schedules, history)
  composer.py       /compose/<page_id> + /_test/render (cell hydration, theming, fonts)
  admin.py          editor blueprint + /api/pages + /api/send + history endpoints
  push.py           mypy --strict — single-flight PushManager with debounce + LRU
  scheduler.py      tick loop, day-of-week + time-of-day windows, first-seen guard
  renderer.py       mypy --strict — Playwright wrapper, screenshot at panel resolution
  quantizer.py      Pillow gamut projection (Spectra 6) + Floyd–Steinberg
  image_ops.py      Server-side composites for the send pipeline (blurred-fit)
  mqtt_bridge.py    paho-mqtt publisher + listener-status subscriber; NullBridge fallback
docs/
  architecture.md   How the pieces fit together (Flask + Lit + Playwright + MQTT)
  screenshots/      Documentation screenshots (used by this README)
  wiki/             Source for the GitHub wiki pages
plugins/<id>/       Drop-a-folder plugin (kind=widget|theme|font|admin)
schema/             JSON Schemas (plugin manifest, page model)
static/
  components/       Lit design system (id-* web components)
  lib/              Shared modules (push-state.js, vendored Chart.js, …)
  pages/            Editor + send + schedules + themes + settings entry points
  style/            widget-base.css (shared widget chrome), tokens.css
  composer.js       Mounts plugins into shadow DOMs per cell
templates/          Jinja shells: compose, editor, send, schedules, themes, settings
tests/              Top-level pytest suite (push, scheduler, history, composer)
conftest.py         Root fixtures shared with plugin smoke tests
tools/              gen-page-types.mjs (schema → .d.ts)
.github/            CI: Python + Bun + Playwright + bundle build
```

## Writing a plugin

A widget is a folder under `plugins/<id>/` with:

- `plugin.json` — manifest declaring sizes, cell options, settings, render hints (dither, full_bleed)
- `client.js` — default export `render(host, ctx)` that paints into a shadow-DOM host element
- `client.css` — widget styling (link `/static/style/widget-base.css` for the shared chrome)
- `server.py` (optional) — declares `fetch(options, settings, ctx)` for data, plus optional Flask `blueprint()` for an admin UI

See the [wiki tutorial](https://github.com/dmellok/inky-dash/wiki/Writing-a-plugin) for a walkthrough and [`plugins/example_full/`](plugins/example_full/) for a worked example exercising every contract feature.

## License

MIT.
