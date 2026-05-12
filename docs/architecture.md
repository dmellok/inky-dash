# Architecture

How the pieces fit together. This is the current design — the milestone-by-milestone rebuild plan that got us here is archived at git history.

## Two-process system

There are two daemons. Both talk to each other through MQTT and an HTTP fetch:

```
┌─────────────────────────────────┐         ┌─────────────────────────────────┐
│  inky-dash (this repo)           │  MQTT   │  inky-dash-listener (Pi side)   │
│  Flask + Lit + Playwright        │ ──────► │  paho-mqtt + Inky lib           │
│  Compose dashboards in browser   │ inky/   │  Quantise + paint to panel      │
│  Render PNG, host /renders/      │ update  │                                 │
│  Push job: PNG URL + options     │         │                                 │
│                                  │ ◄────── │  Status: idle / rendering / ok  │
│  Subscribe to inky/status        │ inky/   │                                 │
└─────────────────────────────────┘ status   └─────────────────────────────────┘
              │                                              │
              └─ HTTP GET /renders/{digest}.png ◄────────────┘
                 (panel listener fetches the PNG)
```

The companion produces frames; the listener paints them. The MQTT contract is one JSON payload published to `inky/update`:

```json
{ "url": "http://.../renders/abc123.png",
  "rotate": 0, "scale": "fit", "bg": "white", "saturation": 0.5 }
```

This format is **frozen** — same wire bytes since v3. The v3 listener works with v4 unchanged.

## Render pipeline

```
Page state ──► /compose/<page_id> ──► Playwright screenshot ──► Pillow ──► PNG ──► MQTT publish
   JSON       Lit + plugin shadow DOMs        at panel res        rotate          payload
```

1. **`app.composer`** serves `/compose/<page_id>` — a Jinja shell that mounts every cell as its own shadow DOM and bootstraps each plugin's `client.js` into it. Theme tokens come down as inline `--theme-*` CSS variables on the cell element. Cell context includes the resolved palette, font family, fetched server-side data, and the cell's options.
2. **`app.renderer`** is a thin Playwright wrapper. Headless Chromium loads the compose URL at the panel's exact pixel size, waits for every cell's `data-rendered="true"`, screenshots.
3. **`app.quantizer`** is Pillow-based but mostly a no-op now: the panel listener owns gamut quantisation since it knows its own ink primaries. We rotate here for the listener's landscape-native pixel grid.
4. **`app.push.PushManager`** is single-flight + identical-push debounced. Each accepted render is written to `data/core/renders/{digest}.png` (content-addressed, LRU-evicted), then published to MQTT.

The editor's preview iframe is the same `/compose/<page_id>?for_push=1` URL. WYSIWYG by construction — what you see in the preview is byte-identical to what Playwright screenshots.

## Plugin system

A plugin is a folder under `plugins/<id>/` with at minimum a `plugin.json` and a `client.js`. The loader walks the directory at startup, validates each manifest against [`schema/plugin.schema.json`](../schema/plugin.schema.json), and registers anything that passes.

Three plugin kinds: `widget` (renders into a cell), `theme` (palette source — `themes_core` is the canonical one), `font` (woff2 source — `fonts_core`).

A widget's `server.py` can export three optional hooks:

- `fetch(options, settings, *, ctx)` — returns the `ctx.data` payload the client renderer receives. Runs once per render.
- `choices(name)` — populates dynamic dropdowns in the editor (`cell_options[*].choices_from`).
- `blueprint()` — Flask blueprint mounted at `/plugins/<id>/` for plugin-specific admin pages.

The practical usage guide lives in the [wiki tutorial](https://github.com/dmellok/inky-dash/wiki/Writing-a-plugin). The canonical worked example is [`plugins/example_full/`](../plugins/example_full/).

### Design tokens

Every cell paints in its assigned theme. The composer injects the resolved palette as `--theme-*` CSS variables on the cell element itself, so any plugin styling that uses `var(--theme-bg)` / `var(--theme-accent)` / etc. participates in the theme system without any explicit wiring.

Shared widget chrome (the header strip, stat tiles, status pills, empty/error states every widget uses) lives in [`static/style/widget-base.css`](../static/style/widget-base.css) — every shipped widget links it. Plugin-local CSS only adds what's specific.

## State

Plain JSON for things people want to hand-edit; SQLite for write-heavy logs:

- `data/core/pages.json` — every saved dashboard
- `data/core/schedules.json` — the schedule store
- `data/core/app-settings.json` — MQTT config, panel model + orientation, base URL
- `data/core/settings.json` — per-plugin settings (secrets are real values here)
- `data/core/history.db` — push history (SQLite, append-only-ish)
- `data/core/renders/{digest}.png` — content-addressed render cache, LRU-evicted
- `data/plugins/<id>/` — plugin-private data dir (todo lists, gallery uploads, render caches, schedule state)

`data/` is git-ignored — everything in it is runtime state.

## Scheduler

`app.scheduler.Scheduler` runs as a daemon thread with a 30-second tick. On each tick it pulls every enabled schedule, applies the day-of-week + time-of-day-window filters (in the **server's local timezone**, not UTC), and fires anything whose interval has elapsed or whose daily target has passed.

A `_first_seen` map prevents backfill — if you enable a daily-at-07:00 schedule at 11:00, the day's 07:00 fire is suppressed and the next fire is tomorrow at 07:00.

## Front-end build

- **Lit** for the admin Web Components (`static/components/id-*.js`) and pages (`static/pages/*.js`).
- **esbuild** bundles each page entry under `static/dist/` — one bundle per page, shared modules de-duped.
- No global stylesheet contention: every cell renders into its own shadow DOM, every widget's CSS is scoped to that root.

## Code-quality boundary

`mypy --strict` is enforced on four modules whose contracts the rest of the system relies on: `app.state.*`, `app.push`, `app.plugin_loader`, `app.renderer`. The rest of the codebase uses default mypy. The point is to keep the system's load-bearing invariants typecheck-verified, not to chase 100% strict coverage.

## Where to look next

- [`README.md`](../README.md) — feature tour with screenshots
- [Wiki: Writing a plugin](https://github.com/dmellok/inky-dash/wiki/Writing-a-plugin) — tutorial-style usage guide
- [`plugins/example_minimal/`](../plugins/example_minimal/) — six-field manifest + 10-line client
- [`plugins/example_full/`](../plugins/example_full/) — every plugin feature exercised
- [`schema/plugin.schema.json`](../schema/plugin.schema.json) — formal manifest schema
- [`schema/page.schema.json`](../schema/page.schema.json) — formal page schema
