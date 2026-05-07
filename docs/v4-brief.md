# Inky Dash v4 — build brief

## Goal

Rebuild Inky Dash from scratch, learning from v3. Same concept (Flask companion that composes dashboards in the browser, renders to PNG, pushes to a Pimoroni Inky Impression panel over MQTT) but with a cleaner architecture, multi-panel-size support baked in from day one, a proper component-based admin UI, and colour rendering that respects the e-ink panel's gamut.

This brief is the spec the agent follows. The plugin contract has its own file: [v4-plugins.md](v4-plugins.md).

## What we're keeping from v3

These were the right calls. Don't second-guess them.

- **Flask + Python on the server.** Playwright works equally well in Python and Node; the Pi listener has to be Python anyway because of the `inky` library; keeping one language across both halves is a real win.
- **Headless Chromium + Playwright as the renderer.** The editor's preview iframe loads the same composer URL Playwright screenshots — WYSIWYG by construction. Don't rebuild as a custom layout engine.
- **Plugin = folder.** Drop a directory in `plugins/`, the loader picks it up. No npm packages, no registry.
- **Shadow DOM per cell with theme CSS variables.** Each cell renders into its own shadow root; theme palette injected as `--theme-*` vars. No global stylesheet contention.
- **MQTT contract is a single JSON object.** Don't invent a bigger protocol. The Pi listener stays simple.
- **State in plain JSON files** for things you'd want to hand-edit (pages, schedules, todos). SQLite for history.

## What changes in v4

These are the deliberate departures, each tied to a specific v3 pain point.

### 1. Cell-size breakpoints in the plugin contract from day one

v3 was built assuming 1600×1200 (13.3" panel). Retrofitting smaller-panel support means revisiting every plugin. v4 bakes the contract in upfront:

- Cell context (`ctx.cell`) carries `{ w, h, size }` where `size ∈ "xs" | "sm" | "md" | "lg"`.
- Documented thresholds: `xs ≤ 200px`, `sm ≤ 400px`, `md ≤ 700px`, `lg > 700px` (along the longer axis).
- Plugins are expected to render at all four sizes — full doc in [v4-plugins.md](v4-plugins.md).
- The composer resolves cell sizes and writes them into the per-cell context the client receives.

### 2. Lit + Web Components for the admin UI

v3's vanilla-JS-as-ES-modules approach worked but every page reinvented form patterns. v4 standardises on Lit:

- Native shadow DOM model — already what we use for cells, now used for the whole admin UI too.
- Small runtime (~5KB), tree-shakable, no React-style framework lock-in.
- Bundle with `esbuild` (single CLI invocation, no config file). Output to `static/dist/`.
- Build a small **design system** under `static/components/` first: `id-button`, `id-slider`, `id-card`, `id-tab-bar`, `id-color-picker`, `id-form-row`. Reuse across every page. Document each one with a single example.
- The build step is allowed but must remain **trivial** — `bun run build` (or `npm run build`) hits one esbuild call. No webpack, no vite config gymnastics.

### 3. Colour rendering that matches the panel

v3's biggest invisible failure: the editor preview is full sRGB but the panel renders to ~7 colours, so things "looked great in browser, muddy on panel."

- **Server-side gamut quantization.** After Playwright screenshots the page, project all pixels to the Spectra 6 7-colour gamut (Floyd-Steinberg dither by default). The push image is the *quantized* PNG. The browser preview shows the same quantized image, not the raw sRGB output.
- **Themes can use non-gamut colours.** Don't restrict the palette. Many off-gamut colours dither into surprisingly nice results on the panel — they're just hard to discover by eye. The build does *not* reject themes for drifting outside the gamut.
- **Calibration tool — new admin page.** `/calibrate` renders a grid of candidate swatches through the same quantizer + dither pipeline the renderer uses, so you can see how each sRGB colour actually paints on the panel before committing it to a theme. Inputs: a base colour + lightness/saturation sweep ranges, or paste a list of hex values. Output: a clickable grid showing each candidate's quantized rendering side-by-side with its source. "Save to palette" copies a result straight into the theme builder. This is how the bundled themes get their non-gamut accents — it's curation work, not a hard constraint.
- **Per-widget dither control** in the plugin manifest: `dither: "floyd-steinberg" | "ordered" | "none"`. Photos want diffusion; flat UI cards want none.
- Editor preview shows the quantized PNG below the live iframe ("preview as panel will paint it"), so the user sees both.

### 4. Mobile-first admin UI

v3's editor is desktop-only. The 80% case for editing is "I'm near the panel, want to tweak one thing" — that's a phone.

- Every page must be usable at 375px viewport.
- Editor cell picker = bottom sheet on mobile, side panel on desktop. Same component, different breakpoint.
- Touch targets ≥ 44px.

### 5. Tests + CI from day one

Zero tests in v3. Add the harness *before* the second feature.

- `pytest` for unit + integration. `pytest-playwright` for end-to-end smoke (composer renders without errors).
- Target ~30% coverage on the push pipeline, plugin loader, page model — these are where the regressions hide. Don't chase 100%.
- GitHub Actions: on every push, run `ruff check`, `mypy`, `pytest`. Block merge on red.
- Add a smoke test for every plugin: load it, render with default options, assert no exceptions. ~15 lines per plugin.

### 6. Types

`mypy --strict` on `state/`, `push.py`, `plugin_loader.py`, the renderer. The rest of the codebase can stay relaxed but those four areas are where typos cost weeks.

### 7. Plugin manifest versioning

Every `plugin.json` must declare `manifest_version: 1`. The loader rejects manifests without it. Bump when the contract changes; the loader can then refuse / migrate older plugins explicitly instead of silently mis-rendering.

### 8. State namespacing

v3's `data/` folder is a flat collection of unrelated JSON files. v4 namespaces by plugin:

```
data/
├─ core/
│  ├─ pages.json
│  ├─ schedules.json
│  ├─ preferences.json
│  └─ history.db
└─ plugins/
   ├─ todo/items.json
   ├─ habits/grid.json
   ├─ gallery/folders.json
   └─ ...
```

Each plugin gets its own subdirectory; the plugin loader passes the path into `server.py` as `ctx.data_dir`. Migration from v3 happens at first boot (one-time script).

### 9. Render cache eviction

LRU cap on `data/core/renders/` — keep the most recent 500 PNGs (configurable). Evict on push, not on a timer.

### 10. JSON Schema as the source of truth for the page model

v3 has the `Page` dataclass on Python, a separate `state.page` shape on JS, and they drift every time you add a field (the saturation work touched five places). v4:

- Single JSON Schema file at `schema/page.schema.json`.
- Python uses `pydantic` to load + validate (auto-derived from schema or hand-aligned).
- JS uses the schema to generate TS-style typedefs at build time (`tools/gen-page-types.ts`). Editor state is typed against those.
- Adding a field = edit the schema, regenerate types, both sides see it.

## Tech stack

| Layer | v3 | v4 |
|---|---|---|
| Server framework | Flask | Flask |
| Templating | Jinja | Jinja (server-rendered shells) |
| Admin UI | Vanilla JS as ES modules | Lit + Web Components |
| Build | None | esbuild (one CLI call) |
| Validation / models | dataclasses | pydantic v2 |
| Renderer | Playwright + Chromium | Playwright + Chromium (unchanged) |
| Push transport | MQTT (paho) | MQTT (paho) — wire format unchanged |
| Storage | JSON files + SQLite | JSON files + SQLite (now namespaced) |
| Charts | Chart.js | Chart.js (vendored, shared loader) |
| Testing | None | pytest + pytest-playwright |
| Type checking | None | mypy --strict on critical modules |
| CI | None | GitHub Actions |
| Schema source | Implicit | JSON Schema + pydantic |
| Frontend types | None | Generated from JSON Schema |

## Architecture in one diagram

```
   browser (Lit + WC)         companion (Flask, Python)             Pi
   ┌────────────────┐  HTTP  ┌─────────────────────────┐       ┌──────────┐
   │ /editor        │ ─────▶ │  composer (HTML+CSS)    │       │ listener │
   │ /send          │        │  plugin loader          │       │  ↓       │
   │ /schedules     │        │  scheduler + push       │ MQTT  │ inky     │
   │ /themes        │        │  history (SQLite)       │ ────▶ │  driver  │
   └────────────────┘        │  Playwright ───┐        │       │  ↓       │
                             │      ↓         ↓        │       │  panel   │
                             │  raw PNG ─▶ gamut       │       └──────────┘
                             │             quantizer   │
                             │             ↓           │
                             │             push image  │
                             └─────────────────────────┘
```

The interesting design choice (kept from v3): the editor's preview iframe and the panel render load the *same* `/compose/<page_id>` URL. Playwright screenshots that URL → the quantizer projects to the panel gamut → the push image goes out. WYSIWYG by construction.

## MQTT contract — frozen interface

This is the wire format the Pi listener at [dmellok/inky-dash-listener](https://github.com/dmellok/inky-dash-listener) speaks. v4 keeps it **byte-for-byte identical** to v3 so the same listener works on both. Treat this as a frozen API: don't add fields, don't rename, don't change types.

### Job payload — companion publishes to `inky/update` (QoS 1)

```jsonc
{
  "url":        "http://<companion-host>:5555/renders/<digest>.png",   // OR
  "path":       "/home/pi/images/photo.jpg",                           // local file on the Pi

  "rotate":     0,         // 0 | 90 | 180 | 270
  "scale":      "fit",     // "fit" | "fill" | "stretch" | "center"
  "bg":         "white",   // "white" | "black" | "red" | "green" | "blue" | "yellow" | "orange"
  "saturation": 0.5        // 0.0 – 1.0; only meaningful for 7-colour panels
}
```

- Exactly one of `url` or `path` is required. Everything else has a default.
- The listener also accepts a bare URL or path string (anything not starting with `{`) as a convenience form. The companion always emits the JSON object form.
- `bg` is the colour the listener uses when `scale: "fit"` produces letterboxing. The companion's `"blurred"` background is **companion-internal only** — it gets pre-composed into the PNG and the wire `bg` becomes `"white"`.
- `saturation` is the inky driver's saturation parameter, not a CSS-style filter. The listener forwards it directly to `inky.set_image(img, saturation=…)`.

### Status payload — listener publishes to `inky/status` (QoS 1, retained)

Three retained shapes the listener cycles through:

```jsonc
// Mid-render — published when a job is dequeued
{
  "state":      "rendering",
  "ts":         "2026-05-08T07:00:00Z",
  "url":        "http://...",
  "started_at": "2026-05-08T07:00:00Z"
}

// Idle — published immediately after a render finishes (success or failure)
{
  "state":           "idle",
  "ts":              "2026-05-08T07:00:32Z",
  "last_url":        "http://...",
  "last_result":     "ok",                       // "ok" | "failed" | "timeout"
  "last_render_at":  "2026-05-08T07:00:32Z",
  "last_duration_s": 32.1
}

// Offline — set as the MQTT Last Will. Broker auto-publishes if the listener dies uncleanly.
{ "state": "offline" }
```

- `retain=true` means a fresh subscriber sees the current state immediately on connect.
- `state` is the only field the companion's UI strictly relies on; `last_*` fields are best-effort context for the Send page's status pill.
- The companion never publishes to `inky/status`. Only the listener does.

### Defaults + validation (server-side)

The companion validates the job payload before publishing:

```python
DEFAULT_OPTIONS = {"rotate": 0, "scale": "fit", "bg": "white", "saturation": 0.5}
VALID_ROTATIONS = (0, 90, 180, 270)
VALID_SCALES    = ("fit", "fill", "stretch", "center")
VALID_BGS       = ("black", "white", "red", "green", "blue", "yellow", "orange")
# saturation: float in [0.0, 1.0]
```

Reject anything that doesn't validate before it touches the broker — surface a 400 to the user with a helpful message. Don't silently coerce.

### Topics

| Topic | Direction | Retained | QoS |
|---|---|---|---|
| `inky/update` | companion → listener | no | 1 |
| `inky/status` | listener → companion | **yes** | 1 |

Topic names are configurable in both halves' `.env`; default to the above so a fresh install of either side just works.

## Build order

Each milestone is independently shippable. Don't move on until the previous one has tests + docs + a git tag.

### Milestone 0 — Skeleton (1 day)

- Flask app boots, serves `/` with placeholder.
- pytest harness in place, one passing test.
- GitHub Actions running ruff + pytest on every push.
- Repo on GitHub with README pointing at the wiki.
- **Tag: v0.1.0**

### Milestone 1 — Plugin contract + sample plugin (2 days)

- `plugin_loader.py` discovers folders under `plugins/`, validates `manifest_version: 1`, loads `server.py` if present, exposes `client.js` + `client.css` via static routes.
- One bundled plugin: `clock`. Renders at all four cell-size breakpoints. Has a simple options surface.
- Composer route `/compose/<page_id>` mounts plugin instances into shadow DOMs.
- Smoke test: clock renders without errors at xs/sm/md/lg.
- **Tag: v0.2.0**

### Milestone 2 — Page model + JSON schema + Lit components (3 days)

- `schema/page.schema.json` defined.
- pydantic models on the server, generated TS types on the client.
- Build the design system: `id-button`, `id-card`, `id-slider`, `id-tab-bar`, `id-form-row`. Each with a one-page demo at `/_components`.
- Editor page (Lit): cell layout picker, single cell, save/load. Just enough to validate the schema flow.
- **Tag: v0.3.0**

### Milestone 3 — Renderer + gamut quantizer (2 days)

- `renderer.py` calls Playwright, returns raw PNG.
- `quantizer.py` projects to Spectra 6 gamut (use a small lookup table; Floyd-Steinberg dither).
- `/compose/<id>?for_push=1` wraps body in 1600×1200 (configurable) viewport for the renderer.
- Editor preview shows both the live iframe AND the quantized output side-by-side.
- **Tag: v0.4.0**

### Milestone 4 — MQTT push (1 day)

- `mqtt_bridge.py` connects to the broker, publishes the JSON payload on `inky/update`.
- Single-flight `PushManager` (no concurrent pushes).
- History recorded to SQLite.
- Pi listener already exists at `dmellok/inky-dash-listener` — reuse unchanged.
- **Tag: v0.5.0**

### Milestone 5 — Themes + fonts (2 days)

- `themes_core` plugin: 12 starter themes, gamut-restricted palettes.
- `fonts_core` plugin: 10–15 woff2 fonts (start small, expand later).
- Theme builder admin page using the design system.
- Per-cell theme override; per-cell font override (new for v4).
- **Tag: v0.6.0**

### Milestone 6 — Full plugin set (1 week)

- ~10 bundled plugins covering the core use cases. Full list in [v4-plugins.md](v4-plugins.md).
- Each plugin ships with smoke tests + size-breakpoint demos.
- **Tag: v0.7.0**

### Milestone 7 — Schedules + Send page (3 days)

- Schedules: interval + one-shot, day-of-week mask, drag-to-reorder priority. Same model as v3.
- Send page: file / URL / webpage / saved dashboard. One pipeline.
- **Tag: v0.8.0**

### Milestone 8 — Polish (1 week)

- Mobile-first responsive layouts on every page.
- Keyboard shortcuts for the editor.
- Onboarding tour for first-time users (3 steps).
- Settings page consolidates plugin config.
- **Tag: v1.0.0**

## Git + docs cadence

**This is non-negotiable.**

- Every change is committed and pushed to `main` immediately. Don't accumulate changes locally.
- Bump `VERSION` (semver) on user-visible changes. Tag with `v<version>` and push the tag.
- Wiki docs in `<repo>.wiki.git` are updated *in the same session* the feature lands. Not "I'll write docs later." If the feature needs a wiki page, write the wiki page as part of the feature.
- README updated with each milestone — keeps the project entrance current.
- Commit messages follow the pattern `vX.Y.Z - <summary>` for tagged commits, `<area>: <change>` for untagged ones.

## Out of scope (don't build)

- Multi-user / auth. Personal LAN tool.
- Cloud sync. State stays on disk.
- Custom panel firmware. The Pi listener handles all panel interaction.
- A plugin marketplace / registry. Plugins are folders.
- Mobile app. Mobile-first responsive admin UI is enough.
- Docker / container support in v1. Add later if requested.

## Open questions to surface to the user

Don't assume; ask. Listed in priority:

1. **Should the v4 repo be a fresh GitHub repo (`inky-dash-v4`) or replace the current `inky-dash` repo?** Affects whether we keep v3 history.
2. **Frontend bundler — esbuild via npm or Bun?** Both work; user preference.
3. **Plugin language for `client.js` — TypeScript with esbuild compilation, or stay with vanilla JS?** TS is cleaner; vanilla keeps the "drop a folder in" promise simpler.
4. **Migration path from v3 data files** — automatic on first boot, or manual one-shot script the user runs?

## Notes for the agent

- Read this file and `v4-plugins.md` end-to-end before writing any code.
- When unsure about a design decision, **ask the user** rather than guessing. The 30 minutes of conversation costs less than rewriting a foundation.
- Don't add features beyond what's specified. The temptation to "while I'm here, also add X" is what made v3 ~30 plugins deep before the contract was solid.
- When you hit something not covered here, write down the assumption you made and surface it to the user at the end of the session.
