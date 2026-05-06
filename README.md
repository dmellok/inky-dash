# Inky Dash

A Flask companion for [Pimoroni Inky Impression](https://shop.pimoroni.com/products/inky-impression-7-3) e-ink panels. Build dashboards in the browser, render them to PNG via headless Chromium, and push the result to your panel over MQTT.

Composable widgets, themeable everything, drag-and-drop schedule priorities, push-from-anywhere over the LAN.

![version](https://img.shields.io/github/v/tag/dmellok/inky-dash?label=version&sort=semver) ![status](https://img.shields.io/badge/status-personal_project-blue) ![python](https://img.shields.io/badge/python-3.11+-green) ![flask](https://img.shields.io/badge/flask-3.0+-lightgrey)

---

## What it does

- **Dashboards.** Compose pages from cell layouts (single, stack, row, hero, grid) populated with plugin-rendered widgets — weather, calendar, todo, news, xkcd, NASA APOD, image galleries, arbitrary webpages, more.
- **Themes.** 19 bundled themes split between light and dark, plus a theme builder UI. Each theme exposes the full `bg / surface / surface-2 / fg / fg-soft / muted / accent / accent-soft / divider / danger / warn / ok` palette, applied per-cell via shadow DOM CSS variables.
- **Fonts.** 38 bundled woff2 fonts in three flavours — modern, mid-century, thick punchy — with a global weight picker filtered to whatever weights each font ships with.
- **Schedules.** Interval and one-shot schedules with day-of-week masks. Drag rows to set priority — when several fire at the same tick, the topmost wins.
- **Push.** A unified `/send` page accepts files, URLs, live webpages and saved dashboards, all going through one render → publish pipeline with a panel-aspect live preview, history, and replay.
- **Plugins.** Drop a folder into `plugins/` with a `plugin.json` manifest, optional `server.py` (`fetch()` / `blueprint()` / `choices()`), and `client.{js,css}`. The loader picks them up at boot. The 13 plugins shipping today were built against the same contract.

## Architecture in one diagram

```
   browser                companion (this repo)              panel
   ┌────────┐  HTTP    ┌─────────────────────────┐       ┌──────────┐
   │ /send  │─────────▶│  Flask                  │       │ listener │
   │ /comp* │          │   ├ composer (HTML+CSS) │       │ (Pi)     │
   └────────┘          │   ├ plugin loader       │       │          │
                       │   ├ schedule + push     │       │          │
                       │   └ history (SQLite)    │       │          │
                       │                         │ MQTT  │          │
                       │  Playwright ──────PNG──▶│──────▶│  paint   │
                       └─────────────────────────┘       └──────────┘
```

## Quickstart

```bash
git clone https://github.com/dmellok/inky-dash.git
cd inky-dash

# Python 3.11+ recommended
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# Configure — copy the example and fill in panel size, MQTT, API keys
cp .env.example .env
$EDITOR .env

# Run
python app.py
# → http://localhost:5555
```

The first launch creates `data/` (pages, schedules, todos, history.db, render cache). Open `/widgets` to enable/disable plugins, `/schedules` for cron-style runs, and `/dashboards/new` to compose your first page.

## Configuration

`.env` (see `.env.example` for the template):

| Var | Default | Notes |
|---|---|---|
| `HOST` / `PORT` | `0.0.0.0` / `5555` | Flask bind |
| `PUBLIC_BASE_URL` | `http://localhost:5555` | URL the panel listener fetches PNGs from |
| `PANEL_WIDTH` / `PANEL_HEIGHT` | `800` / `480` | Native panel resolution. Portrait (height > width) is detected automatically and adds a base 90° rotation to pushed renders. |
| `MQTT_*` | — | Topics + creds for the panel listener |
| `REFRESH_LOCKOUT_SECONDS` | `30` | Minimum gap between pushes |
| `STATUS_STALE_SECONDS` | `120` | When the panel's status is considered offline |
| `MAX_UPLOAD_BYTES` | `52428800` (50 MB) | Image upload cap |
| `DATA_DIR` / `RENDER_DIR` / `UPLOAD_DIR` | `data/` etc. | Where state lives |

Plugin-specific settings (`NASA_API_KEY`, `UNSPLASH_ACCESS_KEY`, `WEATHER_ICON_SET`, `TODO_PRUNE_HOURS`, …) live in the same `.env`. The `/settings` UI lets you tune them with a "Save & restart" — the helper subprocess scrubs managed env keys and re-execs cleanly.

## Bundled plugins

| Plugin | Kind | Purpose |
|---|---|---|
| `weather` | widget | open-meteo + bundled meteocons / phosphor icons |
| `calendar` | widget | iCal feed (URL or file), agenda view |
| `todo` | widget + admin | quick-entry list, age-based auto-prune |
| `news` | widget | RSS/Atom feed digest |
| `the_age` | widget | The Age homepage scrape |
| `xkcd` | widget | comic of the day |
| `nasa_apod` | widget | astronomy picture of the day (falls back through prior days if today's is video / 400) |
| `gallery` | widget + admin | random or sequential image rotation from a folder |
| `unsplash` | widget | curated Unsplash photo of the day |
| `webpage` | widget | render any URL through headless Chromium |
| `themes_core` | theme | 19 light + dark themes |
| `theme_builder` | admin | palette editor with live widget-style preview |
| `fonts_core` | font | 38 bundled woff2 fonts (modern / mid-century / thick punchy) |

## Building a plugin

A plugin is a directory under `plugins/` with:

```
plugins/myplugin/
  plugin.json        # manifest: id, kinds, cell_options, settings, etc.
  server.py          # optional: fetch(options, settings, *, panel_w, panel_h, preview)
                     #           blueprint() -> Flask Blueprint   (admin pages)
                     #           choices(name)                   (dropdown providers)
  client.js          # default export render(host: ShadowRoot, ctx)
  client.css         # scoped to the cell's shadow DOM
```

The composer renders each cell into its own shadow DOM with theme palette CSS vars (`--theme-bg`, `--theme-fg`, `--theme-accent`, …) plus the global font family on `<html>`. `client.js` paints into that shadow root. There's no global stylesheet contention — every plugin's CSS is local to its cell.

The composer route at `/compose/<page_id>` is what Playwright loads for a real push *and* what the dashboard editor / send page show in their preview iframes. WYSIWYG by construction.

## Project layout

```
app.py                    Flask app factory, top-level routes
composer.py               /compose/* + per-cell data API
push.py                   PushManager: render → publish → history
scheduler.py              Background ticker, priority resolution
plugin_loader.py          Manifest parsing, hot-reload of user themes
state/
  pages.py / schedules.py / history.py / preferences.py
  widget_settings.py
templates/                Jinja for the admin UI + composer.html
static/                   Admin CSS + JS, vendored Phosphor icons
plugins/<id>/             Bundled plugins (see table above)
data/                     Per-user state (gitignored — generated at runtime)
```

## Third-party assets

Each bundled asset retains its upstream license; this project's MIT covers
the source code only.

| Asset | License | Path | Source |
|---|---|---|---|
| Phosphor Icons (font + CSS) | MIT | [`static/vendor/phosphor/`](static/vendor/phosphor/LICENSE.txt) | [phosphoricons.com](https://phosphoricons.com/) |
| Meteocons (weather SVGs) | MIT | [`plugins/weather/static/icons/`](plugins/weather/static/icons/LICENSE.txt) | [github.com/basmilius/weather-icons](https://github.com/basmilius/weather-icons) |
| Chart.js v4.4.6 | MIT | [`static/vendor/chartjs/`](static/vendor/chartjs/) | [chartjs.org](https://www.chartjs.org/) |
| 38 bundled fonts | SIL OFL 1.1 | [`plugins/fonts_core/`](plugins/fonts_core/LICENSE.txt) | [fontsource.org](https://fontsource.org) (Google Fonts) |

## Data sources

- [Open-Meteo](https://open-meteo.com) — weather (no key required)
- [NASA APOD](https://api.nasa.gov) — astronomy picture of the day (`NASA_API_KEY`)
- [Unsplash](https://unsplash.com/developers) — curated photos (`UNSPLASH_ACCESS_KEY`)
- [xkcd JSON API](https://xkcd.com/json.html), The Age homepage scrape, generic RSS/Atom

## Acknowledgements

- [Pimoroni](https://shop.pimoroni.com) for the Inky Impression hardware.
- The folks behind every dependency above for shipping things permissively.

## License

MIT — see [LICENSE](LICENSE). Third-party assets keep their own licenses (table above).
