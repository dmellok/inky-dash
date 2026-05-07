# Inky Dash v4 — plugin system

This file specifies the plugin contract for v4. Pair with [v4-brief.md](v4-brief.md), which has the higher-level architecture.

The plugin system is the part of v3 that worked best. v4 keeps the shape (a plugin is a folder with a manifest, optional Python server, and a JS client) but tightens the contract in three deliberate places: **size breakpoints**, **manifest versioning**, and **explicit theme/font access from JS**.

## Design principles

1. **A plugin is a folder.** No npm packages. No registry. Drop a directory in `plugins/`, restart, the loader picks it up.
2. **Plugins are isolated.** Each cell renders into its own shadow DOM. Two plugins can both define `.title` without colliding.
3. **The contract is small and versioned.** Every breaking change bumps `manifest_version`. The loader refuses unknown versions instead of silently mis-rendering.
4. **Plugins target multiple cell sizes.** The contract carries `ctx.cell.size`; plugins are expected to render at all four breakpoints.
5. **The simple case stays simple.** A plugin that just renders the current time should be ~30 lines of code, no `server.py` required.

## Folder layout

```
plugins/myplugin/
├─ plugin.json              # manifest (required)
├─ client.js                # default-export render function (required)
├─ client.css               # scoped to the cell's shadow DOM (optional)
├─ server.py                # data fetching + admin pages + dropdown providers (optional)
├─ static/                  # static assets — icons, images (optional)
│  └─ icon.svg
└─ tests/
   └─ test_smoke.py         # one smoke test minimum
```

## Manifest (`plugin.json`)

```jsonc
{
  "manifest_version": 1,
  "id": "myplugin",
  "name": "My Plugin",
  "version": "0.1.0",
  "kind": "widget",                           // widget | theme | font | admin
  "description": "Short, single-line.",

  "supports": {
    "sizes": ["xs", "sm", "md", "lg"],        // which breakpoints this plugin renders at
    "panels": ["all"]                         // ["all"] or specific panel sizes
  },

  "cell_options": [                           // what the editor exposes to the user per cell
    {
      "name": "format",
      "type": "select",
      "label": "Format",
      "default": "24h",
      "choices": [
        { "value": "24h", "label": "24-hour" },
        { "value": "12h", "label": "12-hour" }
      ]
    }
  ],

  "settings": [                               // global settings (in /settings page)
    {
      "name": "API_KEY",
      "type": "string",
      "label": "API key",
      "secret": true
    }
  ],

  "render": {
    "dither": "none",                         // none | floyd-steinberg | ordered
    "full_bleed": false,                      // suppress cell padding (for image widgets)
    "needs_network": false                    // hint to the loader; affects retry policy
  }
}
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `manifest_version` | int | Must be `1`. Loader rejects unknown versions. |
| `id` | string | Unique, lowercase, snake_case. Used as the URL path. |
| `name` | string | Human-readable, shown in the editor's widget picker. |
| `version` | string | Semver. The loader uses this for the "outdated" badge in `/widgets`. |
| `kind` | string | `widget` (renders into a cell), `theme` (palette source), `font` (font source), `admin` (admin-only page, no render). |
| `supports.sizes` | string[] | Subset of `["xs", "sm", "md", "lg"]`. The composer hides this plugin in cells whose resolved size isn't supported. |

### Optional fields

`cell_options`, `settings`, `description`, `supports.panels`, `render.*`. All have sensible defaults.

## Cell-size breakpoint API

Every widget is expected to render at all four breakpoints unless `supports.sizes` declares otherwise. The composer resolves the cell's pixel size and passes it into `ctx`:

```js
// client.js
export default function render(host, ctx) {
  // ctx.cell.size is one of "xs" | "sm" | "md" | "lg"
  // ctx.cell.w and ctx.cell.h are integer pixels
  if (ctx.cell.size === "xs") return renderMini(host, ctx);
  if (ctx.cell.size === "sm") return renderCompact(host, ctx);
  return renderFull(host, ctx);
}
```

**Breakpoint thresholds** (along the longer axis of the cell):

| Size | Range | Typical use |
|---|---|---|
| `xs` | ≤ 200px | Single number, tiny clock, status pill |
| `sm` | 201–400px | Compact card with one or two key stats |
| `md` | 401–700px | Full card with chart + metadata |
| `lg` | > 700px | Hero card with full chart + secondary widgets |

A plugin that doesn't ship a layout for some size: declare it in `supports.sizes`. The composer hides the plugin from the picker for that cell.

## The `ctx` object

Passed to `render(host, ctx)` from `client.js`:

```ts
type RenderCtx = {
  cell: {
    w: number;                      // pixels
    h: number;
    size: "xs" | "sm" | "md" | "lg";
    options: Record<string, unknown>; // values from plugin.json's cell_options
  };
  panel: {
    w: number;                      // full panel resolution
    h: number;
    portrait: boolean;
  };
  theme: {
    bg: string;       fg: string;       fgSoft: string;
    surface: string;  surface2: string; muted: string;
    accent: string;   accentSoft: string;
    divider: string;  danger: string;   warn: string; ok: string;
    // Resolved hex strings, NOT CSS variables.
    // Use these when you need actual colour values (Chart.js, canvas).
    // For CSS, prefer the `--theme-*` custom properties already on the host.
  };
  font: {
    family: string;
    weight: number;
  };
  data: unknown;                    // result of server.py's fetch(), if any
  preview: boolean;                 // true when rendered in the editor preview
};
```

## `client.js` contract

```js
// Required: a default export.
// Returns void. Mutates `host` (a ShadowRoot) in place.
export default function render(host, ctx) {
  host.innerHTML = `
    <link rel="stylesheet" href="./client.css">
    <div class="card">
      <span class="time">${formatTime(new Date(), ctx.cell.options.format)}</span>
    </div>
  `;
}

// Optional: cleanup hook called when the cell is removed or re-rendered.
export function cleanup(host) {
  // Cancel any timers, observers, fetch controllers.
}
```

`render()` is called once per cell mount. If the user changes `cell_options` in the editor, the composer calls `cleanup()` then `render()` again — don't try to be clever about diffing.

## `client.css`

Scoped to the cell's shadow root. Use `--theme-*` custom properties for colours, `inherit` for fonts:

```css
/* All --theme-* vars are injected on the shadow root. */
.card {
  background: var(--theme-surface);
  color: var(--theme-fg);
  border: 1px solid var(--theme-divider);
  font-family: inherit;            /* picks up the page's font */
}
.card .accent {
  color: var(--theme-accent);
}
```

Don't reset global styles. Don't import external stylesheets (security boundary). Don't use `@import` for fonts — fonts are managed by the `fonts_core` plugin and injected globally.

## `server.py` (optional)

Three optional functions. Implement what you need.

```python
# plugins/myplugin/server.py

def fetch(options: dict, settings: dict, *, ctx: dict) -> dict:
    """Server-side data fetch. Result is JSON-serialised and passed to client.js
    as ctx.data. Called per render — cache externally if expensive.

    Args:
        options: values from cell_options for this cell
        settings: values from the plugin's settings (env vars)
        ctx: { panel_w, panel_h, preview, data_dir }
    """
    return { "now": datetime.now().isoformat() }


def blueprint() -> Blueprint:
    """Optional: a Flask Blueprint for an admin page.

    Mounted at /plugins/<id>/. Use for plugins that need their own UI
    (gallery folder picker, todo list, habit grid editor).
    """
    bp = Blueprint("myplugin", __name__, template_folder="templates")
    @bp.route("/")
    def index():
        return render_template("myplugin/admin.html")
    return bp


def choices(name: str) -> list[dict]:
    """Optional: provide dynamic dropdown choices for a cell_option.

    Called by the editor when a cell_option declares `choices_from: "<name>"`
    instead of a static `choices` array. Useful for things like "list of
    saved galleries" or "list of timezones".
    """
    if name == "timezones":
        return [{ "value": tz, "label": tz } for tz in ZONES]
    return []
```

Plugins without a `server.py` are pure client-side — clocks, year-progress widgets, anything that just computes from the current time. The loader handles them identically; they just don't appear in `/settings`.

## State directory

The loader creates `data/plugins/<id>/` and passes the path into `ctx.data_dir`:

```python
def fetch(options, settings, *, ctx):
    cache = Path(ctx["data_dir"]) / "cache.json"
    if cache.exists() and (time.time() - cache.stat().st_mtime) < 300:
        return json.loads(cache.read_text())
    # ... fetch fresh ...
```

Plugins that need persistent state (todo, habits, gallery folder paths) write JSON files here. The loader doesn't touch this directory — plugins own it.

## Themes (kind: "theme")

A theme plugin contributes one or more named palettes:

```json
{
  "manifest_version": 1,
  "id": "themes_core",
  "kind": "theme",
  "themes": [
    {
      "id": "ember",
      "name": "Ember",
      "mode": "dark",
      "palette": {
        "bg": "#1a1612",  "surface": "#241e18",   "surface2": "#2e261d",
        "fg": "#f5e8d8",  "fgSoft": "#c8b89b",    "muted": "#8b7e70",
        "accent": "#d97757", "accentSoft": "#aa5a3f",
        "divider": "#3a2f24", "danger": "#c97c70", "warn": "#d4a957", "ok": "#7da670"
      }
    }
  ]
}
```

All 12 keys must be present. The validator rejects palettes drifting outside the panel's gamut beyond a configurable ΔE threshold (default: ΔE76 ≤ 30).

## Fonts (kind: "font")

A font plugin contributes one or more fonts with woff2 files:

```json
{
  "manifest_version": 1,
  "id": "fonts_core",
  "kind": "font",
  "fonts": [
    {
      "id": "lexend",
      "name": "Lexend",
      "weights": [300, 400, 500, 700],
      "files": {
        "300": "files/lexend-300.woff2",
        "400": "files/lexend-400.woff2",
        "500": "files/lexend-500.woff2",
        "700": "files/lexend-700.woff2"
      }
    }
  ]
}
```

The loader serves `files/*` under `/plugins/<id>/files/` and emits `@font-face` rules in the page head.

## Bundled plugins to ship in v1.0

A deliberately smaller core than v3's ~30 plugins. Each must render at all four breakpoints with smoke tests passing.

### Time + dates

| ID | Sizes | Notes |
|---|---|---|
| `clock` | xs / sm / md / lg | Digital + analog modes, 12h / 24h |
| `countdown` | xs / sm / md | Days-until / since for a target date |
| `year_progress` | sm / md / lg | Day-of-year hero + 52-week ribbon |

### Astronomy + sky

| ID | Sizes | Notes |
|---|---|---|
| `sun_moon` | sm / md / lg | Sunrise/sunset/twilight + moon phase tile |
| `nasa_apod` | md / lg | Picture of the day with fallback through prior days |

### Weather + environment

| ID | Sizes | Notes |
|---|---|---|
| `weather` | xs / sm / md / lg | open-meteo current + hourly + daily |
| `air_quality` | sm / md / lg | AQI hero + pollutant tiles |

### News + reading

| ID | Sizes | Notes |
|---|---|---|
| `hn` | sm / md / lg | Hacker News top / new / best |
| `news` | sm / md / lg | Generic RSS / Atom |

### Image / display

| ID | Sizes | Notes |
|---|---|---|
| `gallery` | md / lg | Random or sequential rotation from a local folder. `full_bleed: true`. |

### Personal data + tools

| ID | Sizes | Notes |
|---|---|---|
| `todo` | xs / sm / md / lg | Quick-entry list with auto-prune |

That's 11. Anything beyond ships post-v1.0 — once the size-breakpoint pattern is proven across this set, adding more plugins is mechanical.

## Smoke test (per plugin, required)

```python
# plugins/myplugin/tests/test_smoke.py
def test_renders_at_all_supported_sizes(plugin_loader, browser):
    plugin = plugin_loader.get("myplugin")
    for size in plugin.manifest["supports"]["sizes"]:
        page = browser.new_page()
        page.goto(f"/_test/render?plugin=myplugin&size={size}")
        page.wait_for_selector("[data-rendered=true]", timeout=5000)
        assert page.evaluate("() => !document.querySelector('.error')")
```

The composer exposes `/_test/render` in test mode, which mounts a single plugin into a known cell size and emits `data-rendered=true` on completion or `.error` on failure. Plugins must paint `data-rendered=true` themselves once they've finished initial render.

## Versioning the contract

`manifest_version: 1` is the v4.0 contract. Future changes:

- **Additive (new optional fields)** — no version bump, document in the changelog.
- **Breaking (renamed fields, changed defaults, removed fields)** — bump to `2`. The loader supports both old and new versions for one minor release, then drops the old.
- **Loader changes (new `ctx` fields)** — additive, no bump.

Plugins MUST declare a `manifest_version` they were built against. The loader refuses any plugin with a missing or unknown version, surfacing the error in `/widgets`.

## How to write a new plugin (the simple case)

Three files, ~50 lines total:

```
plugins/hello/
├─ plugin.json
├─ client.js
└─ client.css
```

```json
{
  "manifest_version": 1,
  "id": "hello",
  "name": "Hello",
  "version": "0.1.0",
  "kind": "widget",
  "supports": { "sizes": ["xs", "sm", "md", "lg"] }
}
```

```js
export default function render(host, ctx) {
  host.innerHTML = `
    <link rel="stylesheet" href="./client.css">
    <div class="card">Hello, ${ctx.cell.size} cell</div>
  `;
  host.host.dataset.rendered = "true";
}
```

```css
.card {
  display: grid;
  place-items: center;
  height: 100%;
  background: var(--theme-surface);
  color: var(--theme-fg);
}
```

Drop the folder in `plugins/`, restart, it shows up in the editor's widget picker. That's the bar.

## Notes for the agent

- The contract is the user-facing API. **Don't expand it casually** — every field is a long-term commitment.
- When tempted to add a new manifest field, first check whether the existing surface (e.g. `cell_options`) can express the same thing.
- Generate TS-style typedefs from the manifest schema so plugin authors get autocomplete in `client.js` (post-v1.0 nice-to-have).
- Write the manifest schema as JSON Schema in `schema/plugin.schema.json`. Validate every plugin against it at load time.
