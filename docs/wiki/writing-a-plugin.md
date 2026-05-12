# Writing a plugin

A plugin is a folder under `plugins/<id>/` that Inky Dash discovers on startup. Drop a folder in, restart the server, and your widget shows up in the editor's plugin dropdown next to all the built-ins.

This page is the **tutorial**. For the canonical reference, look at the two example plugins that ship in the repo:

- [`plugins/example_minimal/`](../../plugins/example_minimal/) — six required manifest fields + a 10-line `client.js`. The smallest possible widget.
- [`plugins/example_full/`](../../plugins/example_full/) — every contract feature in one place: all cell-option types, a static dropdown, a dynamic `choices_from` dropdown, plugin-level settings (one secret), a server-side `fetch()` + `choices()` + Flask admin blueprint, theme-aware CSS via `widget-base.css`, and a smoke test.

---

## 30-second plugin

Three files, no Python, hello-world rendered at every cell size:

```
plugins/hello/
├── plugin.json
└── client.js
```

**`plugin.json`** — six required fields, nothing else:

```json
{
  "manifest_version": 1,
  "id": "hello",
  "name": "Hello",
  "version": "1.0.0",
  "kind": "widget",
  "supports": { "sizes": ["xs", "sm", "md", "lg"] }
}
```

**`client.js`** — default-export a function. It paints into the cell's shadow-DOM host:

```js
export default function render(host, ctx) {
  host.innerHTML = `
    <div style="
      height: 100%;
      display: grid;
      place-items: center;
      background: var(--theme-bg);
      color: var(--theme-fg);
      font: 800 12cqh inherit;
    ">
      Hello, ${ctx.cell.size}!
    </div>
  `;
  host.host.dataset.rendered = "true";
}
```

Restart the dev server (`python -m app`), open the editor, pick "Hello" from the widget dropdown. Done.

Two things that aren't obvious at first:

- **`host` is a `ShadowRoot`, not the cell element.** `host.host` is the cell element itself. The `data-rendered="true"` attribute on the cell tells the Playwright screenshot pipeline the cell is finished painting — skip it and the panel push will fire before your render has stabilised.
- **CSS variables `--theme-*` come for free.** The composer injects the current theme palette as CSS variables onto the cell, so any widget that uses `var(--theme-bg)` / `var(--theme-fg)` / `var(--theme-accent)` etc. immediately participates in the theme system. See the [Theming and design tokens](#theming-and-design-tokens) section below for the full token list.

---

## The shadow-root contract

When the composer mounts your widget it attaches an **empty** shadow root and hands it to you as `host`. Nothing else is in there — no inherited page CSS, no auto-linked stylesheets, no parent fonts. Whatever you want inside the shadow root, you put there. Whatever you forget will just be missing.

The two consequences worth burning into your brain before you start splitting things into files:

1. **CSS doesn't load itself.** Any `client.css` you write must be linked explicitly from your `client.js` — there is no auto-injection from `plugin.json`. The two canonical patterns:

   ```js
   // Pattern A — set the whole tree at once via innerHTML (most plugins do this).
   host.innerHTML = `
     <link rel="stylesheet" href="/static/style/widget-base.css">
     <link rel="stylesheet" href="/plugins/myplugin/client.css">
     <div class="widget">…</div>
   `;
   ```

   ```js
   // Pattern B — DOM API (useful when you build up nodes dynamically).
   const link = document.createElement("link");
   link.rel = "stylesheet";
   link.href = "/plugins/myplugin/client.css";
   host.appendChild(link);
   host.appendChild(myWrapperEl);
   ```

   If you forget the link, your widget renders with *every browser default* — no flex, no fonts, no theme colours, everything stacked at the top-left. The most common symptom is "it renders, but it looks like the 1996 web".

2. **The shadow root is fully isolated.** `document.querySelector` will not find anything inside your shadow root, and your widget cannot reach `document` to find anything in the page either. Don't try — even when it works in a one-off test, it will silently break under the Playwright screenshot loop or when two cells use your plugin on the same page.

The other half of the contract — `host.host.dataset.rendered = "true"` — is what gates the screenshot. Set it once you've painted the synchronous part of the widget; if you have async work (image loads, font loads), `await` them first.

---

## Adding configuration

Most widgets want at least one knob per cell. Declare them under `cell_options` in the manifest, and the editor will render the right input control in its sidebar.

Six types are supported:

| `type` | Editor renders | Common uses |
|---|---|---|
| `string` | Single-line text input | Title, label, username |
| `textarea` | Multiline text | Body of a note widget |
| `number` | Number input | Item count, refresh interval |
| `boolean` | Toggle | "Show captions", "Compact layout" |
| `select` | Dropdown with static `choices` or dynamic `choices_from` | Mode picker, list selector |
| `color` | Colour picker | Per-cell accent override |

```jsonc
"cell_options": [
  { "name": "title",    "type": "string",   "label": "Title",          "default": "EXAMPLE" },
  { "name": "subtitle", "type": "textarea", "label": "Subtitle",       "default": "Multiline." },
  { "name": "count",    "type": "number",   "label": "Item count",     "default": 4 },
  { "name": "compact",  "type": "boolean",  "label": "Compact layout", "default": false },
  {
    "name": "tone", "type": "select", "label": "Tone", "default": "info",
    "choices": [
      { "value": "info",   "label": "Info" },
      { "value": "ok",     "label": "OK" },
      { "value": "warn",   "label": "Warn" },
      { "value": "danger", "label": "Danger" }
    ]
  },
  {
    "name": "category", "type": "select", "label": "Category", "default": "",
    "choices_from": "categories"   // populated by server.py choices("categories")
  },
  { "name": "tint", "type": "color", "label": "Accent override", "default": "" }
]
```

Read them at render-time from `ctx.cell.options`:

```js
const { title, count, compact, tone } = ctx.cell.options;
```

The defaults from the manifest are merged in before the client sees them, so you'll always get the declared keys.

---

## Server-side data: `fetch()`

If your widget needs anything Python can do better than the browser — HTTP requests with retries, disk reads, image processing, scheduled work — drop a `server.py` next to `client.js` and export a `fetch()` function:

```python
# plugins/myplugin/server.py
from __future__ import annotations
from typing import Any


def fetch(
    options: dict[str, Any],
    settings: dict[str, Any],
    *,
    ctx: dict[str, Any],
) -> dict[str, Any]:
    """Return whatever should land as ctx.data in the client renderer."""
    return {"items": ["a", "b", "c"], "now": ...}
```

The framework will call `fetch()` once per cell render, pass it the cell's options + the plugin's settings (see below), and put whatever you return on `ctx.data` in the client.

The third argument is a dict with a few framework-provided extras:

- `ctx["data_dir"]` — a plugin-private `Path` under `data/plugins/<id>/`. Survives restarts; the directory is created automatically on first read. Use this for caches, user-uploaded files, schedule state.
- `ctx["panel"]` — `{ "w": int, "h": int }` for the active panel.
- `ctx["preview"]` — `True` when rendering inside the editor (vs an actual push). Useful if you want to make fetch faster during interactive previews.

**Keep `fetch()` fast.** The render loop won't wait forever on you. Cache anything expensive: write JSON to `ctx["data_dir"]`, set a TTL, check the cache before hitting the network. Look at `plugins/apod/server.py` for the canonical pattern.

If `fetch()` raises, the cell renders an error state. If you want to surface a specific error message to the widget, return `{"error": "..."}` and have your client check `ctx.data?.error`.

---

## Plugin-level settings

`cell_options` are per-cell. **Settings** are per-plugin, shared across every cell that uses the plugin, and edited at `/settings`. Use them for things that don't change between cells: an API key, a base URL, "show debug info globally". Declare them in `plugin.json`:

```jsonc
"settings": [
  { "name": "base_url", "type": "string",  "label": "Source URL", "default": "https://example.com" },
  { "name": "api_key",  "type": "string",  "label": "API key",    "secret": true },
  { "name": "show_debug", "type": "boolean", "label": "Surface debug", "default": false }
]
```

`secret: true` tells the editor to mask the field — the value never round-trips back to the browser, only a `•••` placeholder. Your `server.py` still sees the real value.

Read them at render-time:

```python
def fetch(options, settings, *, ctx):
    api_key = (settings.get("api_key") or "").strip()
    if not api_key:
        return {"error": "Set api_key in /settings."}
    ...
```

---

## Dynamic dropdowns: `choices()`

Sometimes a `select`'s options aren't known at manifest-write time — they depend on user state. The gallery plugin's "folder" dropdown lists every uploaded folder; the todo plugin's "list" dropdown lists every user-created list. Two pieces wire this together:

1. **In the manifest**, use `choices_from` instead of `choices`:

   ```jsonc
   { "name": "folder", "type": "select", "label": "Folder",
     "default": "", "choices_from": "folders" }
   ```

2. **In `server.py`**, export a `choices(name)` function:

   ```python
   def choices(name: str) -> list[dict[str, Any]]:
       if name == "folders":
           return [{"value": "vacation", "label": "Vacation"}, ...]
       return []
   ```

The editor calls `GET /api/plugins/<plugin_id>/choices/<name>` whenever it needs the dropdown's contents — including immediately after the user edits something elsewhere that might change them.

---

## Admin pages: `blueprint()`

When a configure-this-thing flow doesn't fit the per-cell sidebar (file uploads, multi-step setup, integration test panels), expose your own admin page. Export a `blueprint()` from `server.py`:

```python
from flask import Blueprint, render_template_string

def blueprint() -> Blueprint:
    bp = Blueprint("myplugin_admin", __name__)

    @bp.get("/")
    def index() -> str:
        return render_template_string("<h1>Hello from my plugin</h1>")

    return bp
```

The blueprint mounts at **`/plugins/<id>/`**. It'll automatically appear in the top-nav's "Plugins" dropdown, with the icon you set in the manifest (`"icon": "ph-..."` — Phosphor icon class).

`plugins/gallery/server.py` and `plugins/todo/server.py` are good full-featured examples (upload forms, REST APIs for CRUD, list-management UIs).

---

## Theming and design tokens

Every cell gets the active theme injected as CSS variables on the cell element itself. So `var(--theme-bg)`, `var(--theme-accent)`, etc. work without any import:

| Token | Role |
|---|---|
| `--theme-bg` | Cell background |
| `--theme-surface` / `--theme-surface2` | Card / tile surfaces |
| `--theme-fg` | Primary text |
| `--theme-fgSoft` | Secondary text, labels, meta |
| `--theme-muted` | Even softer text (rarely used) |
| `--theme-accent` / `--theme-accentSoft` | Brand colour, icon tint |
| `--theme-divider` | Borders, hairlines (sparingly) |
| `--theme-danger` / `--theme-warn` / `--theme-ok` | Status colours |

Per-cell theme overrides are picked up automatically — a cell that sets `theme: "midnight"` paints with Midnight's palette regardless of the page theme.

### Shared widget chrome

To avoid each widget reinventing the same header strip and stat-tile shapes, link the shared baseline before your own CSS. (As covered in [The shadow-root contract](#the-shadow-root-contract), *all* stylesheets — yours and the shared one — must be linked from your `client.js`; the platform does not auto-inject anything.)

```html
<link rel="stylesheet" href="/static/style/widget-base.css">
<link rel="stylesheet" href="/plugins/myplugin/client.css">
```

It gives you:

- `.widget` — outer wrapper with theme bg + container queries set up
- `.head` + `.head-icon` + `.head-title` + `.head-place` + `.head-time` — the canonical header strip
- `.tile` — surface card
- `.stat` + `.stat-ico` + `.stat-text` + `.stat-label` + `.stat-value` — compact stat tile
- `.state-empty` + `.state-error` — centered empty/error blocks (use the `<i class="ph">` + `<div class="msg">` shape)
- `.pill` + `.pill.is-accent` / `.is-ok` / `.is-warn` / `.is-danger` — status pills

All of those use the `--theme-*` tokens so they reskin automatically with the theme.

---

## Cell sizes

Every widget renders at four breakpoints picked up from `supports.sizes` in the manifest: `xs` / `sm` / `md` / `lg`. The actual pixel dimensions depend on the panel + layout the user picks — `lg` is roughly 1200×800, `xs` is roughly 600×400 — but the resolved `ctx.cell.size` string is what your client should branch on, not the raw pixel dims.

Two patterns work well:

1. **CSS container queries** — every cell is a sizing container, so `cqw`, `cqh`, `cqmin` units scale automatically:

   ```css
   .stat-value { font-size: min(3.4cqw, 5.2cqh); }
   ```

2. **Size-tiered layout in JS** — pick a slot count based on `ctx.cell.size`:

   ```js
   const visible = { xs: 3, sm: 6, md: 10, lg: 16 }[ctx.cell.size] ?? 8;
   ```

Both. They compose.

---

## Render hints

The `render` block in the manifest carries a few hints for the push pipeline:

```jsonc
"render": {
  "dither": "floyd-steinberg",   // "none" | "floyd-steinberg" | "ordered"
  "full_bleed": true,            // draw edge-to-edge, no cell outline
  "needs_network": true          // fetch() does HTTP; surfaces in /healthz
}
```

- **`full_bleed: true`** kills the cell's debug outline so your widget paints flush against the panel edge. Used by image widgets (gallery, APOD, Wikimedia, generative art, weather radar).
- **`dither`** is the default dither mode for the panel listener when it composites this widget's render. Override per-push via `/api/send/*?dither=...`.
- **`needs_network`** is a hint only — it doesn't gate anything, just lets the healthz endpoint flag which plugins might be at risk if the network goes down.

---

## Testing

Every shipped widget has a smoke test under `plugins/<id>/tests/test_smoke.py`. It uses Playwright to render the widget at each size and asserts the cell came out with `data-rendered=true`. Copy-paste this:

```python
import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["xs", "sm", "md", "lg"])
def test_renders_at_every_size(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=myplugin&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0
```

Run with `pytest plugins/myplugin/tests/ -q`.

For server-side logic — `fetch()`, `choices()`, blueprint endpoints — add regular pytest modules that import from `plugins.<id>.server`. Mock external HTTP with `urllib.request.urlopen` patches.

---

## Tips, gotchas, and house style

- **Set `host.host.dataset.rendered = "true"`** when your widget is fully painted. If your render does async image loads, wait for them first (see `plugins/wikipotd/client.js` for the pattern).
- **Don't reach outside the shadow root.** No `document.querySelector`, no global state. Each cell is isolated — making them not so breaks the panel render.
- **Cache things that look up the same way each minute.** Use `ctx["data_dir"]` for JSON caches with a TTL. The push pipeline calls `fetch()` once per push; the editor preview hits it on every save.
- **Surface errors loudly.** Return `{"error": "..."}` from `fetch()` and use the `.state-error` block in the client. Silently rendering nothing is worse than showing "Set api_key in /settings."
- **Default to flat surfaces.** Cards in this app don't have outlines — they rely on the surface-vs-bg tonal step for their boundary. Use `.tile` or `.stat` from the shared CSS and you'll match.
- **Phosphor icons** are available everywhere — `<i class="ph ph-name"></i>` after linking `/static/icons/phosphor.css`. Browse the full set at [phosphoricons.com](https://phosphoricons.com).
- **Spectra 6 has six inks**: black, white, red, green, blue, yellow, plus orange. Floyd–Steinberg dithering blends these into perceived mids. Avoid hairlines — anything thinner than 2px tends to disappear into the dither.

---

## Common pitfalls

Quick lookup by symptom. If your widget is misbehaving, scan this list first.

- **"My widget renders but has no styling at all — looks like the 1996 web."** You forgot to `<link rel="stylesheet" href="/plugins/<id>/client.css">` from `client.js`. The shadow root starts empty; the platform doesn't auto-load `client.css` based on `plugin.json`. See [The shadow-root contract](#the-shadow-root-contract).

- **"My text is enormous / fills the whole cell."** `cqw` / `cqh` / `cqmin` units resolve against the **nearest ancestor with `container-type`**, not always what you think. The cell element already has `container-type: size`, so `cqh` on a top-level element correctly resolves to "% of cell height". But the moment you set `container-type` on an inner wrapper, every descendant's `cqh` now resolves against *that wrapper's* height instead. Either don't set `container-type` redundantly on inner elements, or expect the resolution scope to change and re-tune your sizes accordingly.

- **"The push pipeline screenshots a blank cell."** You forgot `host.host.dataset.rendered = "true"`. The Playwright screenshot loop waits for that attribute as the "ready to capture" signal. If you only set it inside a promise callback that hasn't resolved yet, the screenshot fires too early — `await` your async work *first*, set the flag *last*.

- **"My fonts metrics drift / split-text or hinge tricks land in the wrong place."** Default fallback fonts (`sans-serif`, `Helvetica`, `Arial`) have different cap-height and x-height metrics across systems. If your visual depends on glyphs landing at specific positions (split-flap clocks, vertical alignment of icons with text), pick a specific font from `plugins/<font>/plugin.json`, link it explicitly, and verify on at least Chromium + the actual panel render.

- **"Two cells with my plugin interfere with each other."** You're reaching outside the shadow root somewhere — `document.querySelector`, global state on `window`, a singleton in the module's top-level scope. Each cell mount must be fully self-contained. Module-level constants are fine; module-level *mutable state* is not.

- **"`fetch()` runs every second in the editor."** The editor calls `fetch()` on every cell-options change for live preview, so anything expensive (HTTP, image processing) needs caching in `ctx["data_dir"]`. Check `ctx["preview"]` if you want different behaviour for editor vs push.

---

## Where to look next

- [`docs/architecture.md`](../architecture.md) — how the pieces fit together
- [`schema/plugin.schema.json`](../../schema/plugin.schema.json) — formal manifest schema (source of truth for which fields exist)
- [`plugins/example_minimal/`](../../plugins/example_minimal/) — minimum viable widget
- [`plugins/example_full/`](../../plugins/example_full/) — every feature in one place
- [`plugins/clock/`](../../plugins/clock/) — a real ~80-line widget with no `server.py`
- [`plugins/gallery/`](../../plugins/gallery/) — full-fat plugin: data dir, admin blueprint, dynamic dropdowns, file uploads
- [`plugins/weather/`](../../plugins/weather/) — `fetch()` with disk caching + Chart.js + size-tiered layout
- [`static/style/widget-base.css`](../../static/style/widget-base.css) — every shared design token
