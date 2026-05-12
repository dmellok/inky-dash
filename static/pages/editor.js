import { LitElement, html, css } from "lit";
import "../components/index.js";
import {
  isPushing,
  onPushStateChange,
  pushSource,
  runWithPushLock,
} from "../lib/push-state.js";

// Fallback panel dims (Spectra 6 13.3" landscape native). Real panel dims
// come from /api/app/settings on connectedCallback; these only matter if the
// fetch fails (offline-ish / API broken) so the editor still mounts.
const PANEL_W = 1600;
const PANEL_H = 1200;

const LAYOUTS = {
  "1x1": { label: "1 cell", cells: [{ x: 0, y: 0, w: 1, h: 1 }] },
  "2x1": {
    label: "2 columns",
    cells: [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 1, y: 0, w: 1, h: 1 },
    ],
  },
  "1x2": {
    label: "2 rows",
    cells: [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 0, y: 1, w: 1, h: 1 },
    ],
  },
  "2x2": {
    label: "2×2 grid",
    cells: [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 1, y: 0, w: 1, h: 1 },
      { x: 0, y: 1, w: 1, h: 1 },
      { x: 1, y: 1, w: 1, h: 1 },
    ],
  },
  // Hero layouts use a 2-col × 5-row grid: hero spans 2×3 (60% of one
  // dimension), two side cells span 1×2 each (40%, split across both cols).
  "hero-top": {
    label: "Hero top",
    cells: [
      { x: 0, y: 0, w: 2, h: 3 },
      { x: 0, y: 3, w: 1, h: 2 },
      { x: 1, y: 3, w: 1, h: 2 },
    ],
  },
  "hero-bottom": {
    label: "Hero bottom",
    cells: [
      { x: 0, y: 0, w: 1, h: 2 },
      { x: 1, y: 0, w: 1, h: 2 },
      { x: 0, y: 2, w: 2, h: 3 },
    ],
  },
  // Hero left/right use 5-col × 2-row: hero spans 3×2 (60% width), two
  // stacked cells span 2×1 each (40% width).
  "hero-left": {
    label: "Hero left",
    cells: [
      { x: 0, y: 0, w: 3, h: 2 },
      { x: 3, y: 0, w: 2, h: 1 },
      { x: 3, y: 1, w: 2, h: 1 },
    ],
  },
  "hero-right": {
    label: "Hero right",
    cells: [
      { x: 0, y: 0, w: 2, h: 1 },
      { x: 0, y: 1, w: 2, h: 1 },
      { x: 2, y: 0, w: 3, h: 2 },
    ],
  },
};

function pixelize(layoutKey, panel) {
  const layout = LAYOUTS[layoutKey];
  const cols = Math.max(...layout.cells.map((c) => c.x + c.w));
  const rows = Math.max(...layout.cells.map((c) => c.y + c.h));
  const cellW = Math.floor(panel.w / cols);
  const cellH = Math.floor(panel.h / rows);
  return layout.cells.map((c, i) => ({
    id: `cell-${i + 1}`,
    x: c.x * cellW,
    y: c.y * cellH,
    w: c.w * cellW,
    h: c.h * cellH,
    plugin: "clock",
    options: {},
  }));
}

function detectLayout(cells, panel) {
  for (const [key, layout] of Object.entries(LAYOUTS)) {
    const expected = pixelize(key, panel);
    if (expected.length !== cells.length) continue;
    const same = expected.every((e, i) => {
      const c = cells[i];
      return c && c.x === e.x && c.y === e.y && c.w === e.w && c.h === e.h;
    });
    if (same) return key;
  }
  return null;
}

// Group themes into White / Light / Medium / Dark buckets based on
// their bg lightness. Uses Rec.709 luminance. "White" is reserved for
// themes with a pure-white bg AND neutral-grayscale surfaces (the
// stark-white-plus-bold-accent family). Themes with a white bg but
// cream/parchment tinted surfaces (like Paper) stay in "Light".
// Falls back to the theme's declared `mode` for legacy themes without
// a usable bg.
function _parseHex(hex) {
  const m = /^#?([0-9a-f]{6})/i.exec(hex || "");
  if (!m) return null;
  return [
    parseInt(m[1].slice(0, 2), 16),
    parseInt(m[1].slice(2, 4), 16),
    parseInt(m[1].slice(4, 6), 16),
  ];
}
function _isNeutral(rgb, tolerance = 4) {
  if (!rgb) return false;
  return Math.max(...rgb) - Math.min(...rgb) <= tolerance;
}
function themeBucket(theme) {
  const bg = _parseHex(theme?.palette?.bg);
  if (!bg) return theme?.mode === "dark" ? "dark" : "light";
  const L = (0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]) / 255;
  const surface = _parseHex(theme?.palette?.surface);
  if (L >= 0.985 && _isNeutral(bg) && _isNeutral(surface)) return "white";
  if (L >= 0.78) return "light";
  if (L <= 0.32) return "dark";
  return "medium";
}

const THEME_SECTIONS = [
  { key: "white", label: "White" },
  { key: "light", label: "Light" },
  { key: "medium", label: "Medium" },
  { key: "dark", label: "Dark" },
];

function groupThemes(themes) {
  const groups = { white: [], light: [], medium: [], dark: [] };
  for (const t of themes || []) groups[themeBucket(t)].push(t);
  for (const g of Object.values(groups)) {
    g.sort((a, b) => a.name.localeCompare(b.name));
  }
  return groups;
}

class IdEditor extends LitElement {
  static properties = {
    pageId: { type: String, attribute: "page-id" },
    page: { state: true },
    widgets: { state: true },
    themes: { state: true },
    fonts: { state: true },
    dynChoices: { state: true },
    saving: { state: true },
    saved: { state: true },
    error: { state: true },
    selectedCell: { state: true },
    layoutKey: { state: true },
    lastSavedAt: { state: true },
    dither: { state: true },
    previewLoading: { state: true },
    pushing: { state: true },
    pushResult: { state: true },
    globalPushing: { state: true },
    globalPushSource: { state: true },
    previewMode: { state: true },
    previewKey: { state: true },
    appPanel: { state: true },
    iconPickerOpen: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
    }

    /* -- Sticky toolbar (sits beneath id-nav, which is sticky at top: 0) - */
    .toolbar {
      position: sticky;
      top: var(--id-nav-height, 51px);
      z-index: 5;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      border-bottom: 1px solid var(--id-divider, #c8b89b);
    }
    .toolbar-inner {
      max-width: 1200px;
      margin: 0 auto;
      padding: 10px 16px;
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }
    .back-btn {
      width: var(--id-control-h, 40px);
      height: var(--id-control-h, 40px);
      border-radius: 6px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      text-decoration: none;
      flex-shrink: 0;
    }
    .back-btn:hover {
      color: var(--id-fg, #1a1612);
      background: var(--id-surface2, #f5e8d8);
    }
    .icon-btn {
      width: var(--id-control-h, 40px);
      height: var(--id-control-h, 40px);
      border-radius: 6px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: transparent;
      color: var(--id-accent, #4f46e5);
      cursor: pointer;
      font-size: 18px;
      display: inline-grid;
      place-items: center;
      flex-shrink: 0;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .icon-btn:hover {
      border-color: var(--id-accent, #4f46e5);
      background: var(--id-accent-bg, rgb(79 70 229 / 0.1));
    }
    .name-input {
      flex: 1;
      min-width: 200px;
      max-width: 480px;
      height: var(--id-control-h, 40px);
      font-size: 17px;
      font-weight: 600;
      color: var(--id-fg, #1a1612);
      padding: 0 10px;
      border: 1px solid transparent;
      background: transparent;
      border-radius: 6px;
      font-family: inherit;
      box-sizing: border-box;
    }
    .name-input:hover {
      border-color: var(--id-divider, #c8b89b);
    }
    .name-input:focus {
      outline: none;
      border-color: var(--id-accent, #d97757);
      background: var(--id-bg, #ffffff);
    }
    .toolbar-spacer { flex: 1; min-width: 0; }
    .toolbar-actions {
      display: flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    /* -- Status pill ----------------------------------------------------- */
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 500;
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-fg-soft, #5a4f44);
      white-space: nowrap;
    }
    .status-pill.dirty {
      background: var(--id-accent-bg, rgb(176 103 80 / 0.12));
      color: var(--id-accent, #b06750);
    }
    .status-pill.ok {
      background: color-mix(in srgb, var(--id-ok, #4d8b6c) 16%, transparent);
      color: var(--id-ok, #4d8b6c);
    }
    .status-pill.error {
      background: color-mix(in srgb, var(--id-danger, #b8534f) 16%, transparent);
      color: var(--id-danger, #b8534f);
    }
    .status-pill .ph { font-size: 13px; }

    /* -- Push result toast ---------------------------------------------- */
    .toast {
      margin: 0 0 12px;
      padding: 10px 14px;
      border-radius: 8px;
      background: color-mix(in srgb, var(--id-ok, #4d8b6c) 16%, transparent);
      color: var(--id-ok, #4d8b6c);
      border: 1px solid color-mix(in srgb, var(--id-ok, #4d8b6c) 35%, transparent);
      font-size: 13px;
    }
    .toast.error {
      background: color-mix(in srgb, var(--id-danger, #b8534f) 16%, transparent);
      color: var(--id-danger, #b8534f);
      border-color: color-mix(in srgb, var(--id-danger, #b8534f) 35%, transparent);
    }

    /* -- Main 2-column grid --------------------------------------------- */
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 16px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
      align-items: start;
    }
    @media (min-width: 1000px) {
      .grid {
        /* Sidebar on the left, preview on the right. */
        grid-template-columns: minmax(360px, 1fr) minmax(0, 1.1fr);
      }
      .preview-col {
        /* Pin preview below the nav + toolbar (~51 + 60 = 111px). */
        position: sticky;
        top: 124px;
      }
    }
    .preview-col,
    .sidebar-col {
      display: flex;
      flex-direction: column;
      gap: 12px;
      min-width: 0;
    }
    .preview-meta {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      padding: 0 4px;
      flex-wrap: wrap;
    }

    /* -- Preview frames -------------------------------------------------- */
    .picker-frame {
      position: relative;
      width: 100%;
      aspect-ratio: var(--panel-w, ${PANEL_W}) / var(--panel-h, ${PANEL_H});
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      overflow: hidden;
      background: var(--id-surface2, #f5e8d8);
    }
    .picker-frame iframe {
      position: absolute;
      top: 0;
      left: 0;
      width: calc(var(--panel-w, ${PANEL_W}) * 1px);
      height: calc(var(--panel-h, ${PANEL_H}) * 1px);
      border: 0;
      transform-origin: top left;
      pointer-events: none;
    }
    .cell-overlay {
      position: absolute;
      inset: 0;
      pointer-events: none;
    }
    .cell-hit {
      position: absolute;
      box-sizing: border-box;
      border: 2px solid transparent;
      cursor: pointer;
      pointer-events: auto;
      transition: border-color 100ms ease;
    }
    .cell-hit:hover {
      border-color: color-mix(in srgb, var(--id-accent, #b06750) 50%, transparent);
    }
    .cell-hit[data-selected="true"] {
      border-color: var(--id-accent, #b06750);
    }
    .cell-hit-label {
      position: absolute;
      top: 4px;
      left: 4px;
      padding: 2px 6px;
      border-radius: 3px;
      font-size: 10px;
      background: rgba(0, 0, 0, 0.6);
      color: white;
      pointer-events: none;
    }
    input[type="text"], select, textarea {
      width: 100%;
      padding: 10px;
      box-sizing: border-box;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      min-height: var(--id-control-h, 40px);
    }
    textarea {
      resize: vertical;
      min-height: 96px;
      line-height: 1.4;
    }
    /* Accent-colored focus ring — overrides the browser default blue. */
    input:focus,
    select:focus,
    textarea:focus {
      outline: none;
      border-color: var(--id-accent, #b06750);
      box-shadow: 0 0 0 3px var(--id-accent-bg, rgb(176 103 80 / 0.12));
    }
    /* Custom select chevron — disables the native widget so the
       box matches plain inputs in size, padding, and theme. */
    select {
      appearance: none;
      -webkit-appearance: none;
      -moz-appearance: none;
      background-image: url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2371717a' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 12px center;
      background-size: 12px;
      padding-right: 32px;
    }
    label.checkbox {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-height: var(--id-control-h, 40px);
      cursor: pointer;
    }

    /* Per-cell colour overrides — collapsed details summary acts like a card
       header. Each token row pairs the color picker with a Reset button (when
       overridden) or an "inherited" hint (when not). Inherited values appear
       slightly dimmed so the user can see at a glance which tokens they've
       customised. */
    .overrides-details > .overrides-summary {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      list-style: none;
      user-select: none;
    }
    .overrides-details > .overrides-summary::-webkit-details-marker { display: none; }
    .overrides-details > .overrides-summary::before {
      content: "▸ ";
      color: var(--id-fg-soft, #5a4f44);
      transition: transform 120ms ease;
      display: inline-block;
    }
    .overrides-details[open] > .overrides-summary::before { transform: rotate(90deg); }
    .overrides-label {
      font-size: 14px;
      font-weight: 600;
      color: var(--id-fg, #0f172a);
    }
    .overrides-count {
      margin-left: auto;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .overrides-hint {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      margin: 8px 0 12px;
    }
    .overrides-grid {
      display: grid;
      gap: 8px;
    }
    .override-row {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .override-row.inherited id-color-picker { opacity: 0.55; }
    .override-row.inherited id-color-picker:hover,
    .override-row.inherited id-color-picker:focus-within { opacity: 1; }
    .override-reset {
      padding: 0 10px;
      min-height: 32px;
      border: 1px solid var(--id-divider, #e2e8f0);
      border-radius: 6px;
      background: var(--id-surface, #ffffff);
      color: var(--id-fg, #0f172a);
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }
    .override-reset:hover {
      background: var(--id-surface2, #f1f5f9);
      border-color: var(--id-fg-soft, #64748b);
    }
    .override-inherit {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      letter-spacing: 0.04em;
    }

    /* Toggle switch — replaces native checkbox styling. */
    label.checkbox input[type="checkbox"] {
      appearance: none;
      -webkit-appearance: none;
      width: 36px;
      height: 20px;
      background: var(--id-divider, #c8b89b);
      border-radius: 999px;
      position: relative;
      cursor: pointer;
      margin: 0;
      flex-shrink: 0;
      transition: background 150ms ease;
    }
    label.checkbox input[type="checkbox"]::before {
      content: "";
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #ffffff;
      box-shadow: 0 1px 3px rgb(0 0 0 / 0.2);
      transition: transform 150ms ease;
    }
    label.checkbox input[type="checkbox"]:checked {
      background: var(--id-accent, #b06750);
    }
    label.checkbox input[type="checkbox"]:checked::before {
      transform: translateX(16px);
    }
    label.checkbox input[type="checkbox"]:focus-visible {
      outline: 2px solid var(--id-accent, #b06750);
      outline-offset: 2px;
    }
    .empty {
      padding: 16px;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
    }

    /* -- Layout picker thumbnails -------------------------------------- */
    .layout-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(78px, 1fr));
      gap: 8px;
    }
    .layout-thumb {
      cursor: pointer;
      border: 1.5px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      padding: 6px;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 4px;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .layout-thumb:hover {
      border-color: var(--id-accent, #d97757);
    }
    .layout-thumb[aria-pressed="true"] {
      border-color: var(--id-accent, #b06750);
      background: var(--id-accent-bg, rgb(176 103 80 / 0.1));
    }
    .layout-thumb-shape {
      position: relative;
      width: 100%;
      aspect-ratio: 4 / 3;
      background: var(--id-surface2, #f1f5f9);
      border-radius: 4px;
      overflow: hidden;
    }
    .layout-thumb-cell {
      position: absolute;
      background: color-mix(in srgb, var(--id-accent, #b06750) 60%, transparent);
      border: 1px solid color-mix(in srgb, var(--id-accent, #b06750) 85%, transparent);
      box-sizing: border-box;
    }
    .layout-thumb-label {
      font-size: 10px;
      color: var(--id-fg-soft, #5a4f44);
      line-height: 1.2;
      text-align: center;
    }
    .layout-thumb[aria-pressed="true"] .layout-thumb-label {
      color: var(--id-accent-soft, #aa5a3f);
      font-weight: 600;
    }

    /* -- Cell badge in card heading ----------------------------------- */
    .cell-heading {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px;
    }
    .cell-heading h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--id-fg, #1a1612);
    }
    .cell-heading .cell-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 24px;
      height: 24px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 700;
      background: var(--id-accent, #d97757);
      color: white;
      flex-shrink: 0;
    }
    .cell-heading .plugin-tag {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      font-weight: 500;
    }

    .quantized-frame {
      position: relative;
      width: 100%;
      aspect-ratio: var(--panel-w, ${PANEL_W}) / var(--panel-h, ${PANEL_H});
      background: var(--id-surface2, #f5e8d8);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      overflow: hidden;
    }
    .quantized-frame img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .preview-spinner {
      width: 16px;
      height: 16px;
      border: 2px solid var(--id-divider, #c8b89b);
      border-top-color: var(--id-accent, #d97757);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      display: inline-block;
      vertical-align: middle;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.45);
      display: grid;
      place-items: center;
      padding: 24px;
      z-index: 50;
    }
    .overlay-card {
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      max-width: 460px;
      width: 100%;
      padding: 24px;
      border-radius: 12px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.25);
    }
    .overlay-card h3 {
      margin: 0 0 12px;
      font-size: 18px;
    }
    .overlay-card kbd {
      display: inline-block;
      min-width: 22px;
      padding: 2px 6px;
      font: 12px/1 ui-monospace, "JetBrains Mono", monospace;
      background: var(--id-surface2, #f5e8d8);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 4px;
      text-align: center;
    }
    .overlay-shortcuts {
      display: grid;
      grid-template-columns: auto 1fr;
      gap: 8px 12px;
      margin: 12px 0;
      align-items: baseline;
    }
    .overlay-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 16px;
      gap: 8px;
    }
    @media (max-width: 600px) {
      .toolbar-inner { padding: 8px 12px; gap: 6px; }
      .name-input { font-size: 16px; min-width: 140px; }
    }
  `;

  constructor() {
    super();
    this.pageId = null;
    this.page = null;
    this.widgets = [];
    this.themes = [];
    this.fonts = [];
    this.dynChoices = {};
    this.saving = false;
    this.saved = false;
    this.error = null;
    this.selectedCell = 0;
    this.layoutKey = "1x1";
    this.lastSavedAt = 0;
    this.dither = "floyd-steinberg";
    this.previewMode = "live";
    this.previewLoading = false;
    this.previewKey = 0;
    this.pushing = false;
    this.pushResult = null;
    this.globalPushing = isPushing();
    this.globalPushSource = pushSource();
    this._unsubPushState = null;
    this.appPanel = null; // { model, orientation, width, height }
    this.iconPickerOpen = false;
    this._onBeforeUnload = this._onBeforeUnload.bind(this);
  }

  _setPageIcon(icon) {
    this.page = { ...this.page, icon: icon || undefined };
    this.saved = false;
  }

  _onBeforeUnload(event) {
    // Prompt the browser's native "leave this site?" dialog when there are
    // unsaved edits. Returning a string (or setting returnValue) is the
    // legacy contract; modern browsers ignore the actual text but show their
    // own generic message.
    if (this.page && !this.saved && !this.saving) {
      event.preventDefault();
      event.returnValue = "";
      return "";
    }
  }

  // Dimensions for new-page defaults: derived from app panel settings,
  // honouring orientation (landscape native, portrait swaps).
  _defaultPanelDims() {
    const p = this.appPanel;
    if (!p) return { w: PANEL_W, h: PANEL_H };
    return p.orientation === "landscape"
      ? { w: p.width, h: p.height }
      : { w: p.height, h: p.width };
  }

  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener("beforeunload", this._onBeforeUnload);
    this._unsubPushState = onPushStateChange(() => {
      this.globalPushing = isPushing();
      this.globalPushSource = pushSource();
    });
    try {
      const [widgetsRes, themesRes, fontsRes, appRes, panelsRes] =
        await Promise.all([
          fetch("/api/widgets"),
          fetch("/api/themes"),
          fetch("/api/fonts"),
          fetch("/api/app/settings"),
          fetch("/api/app/panels"),
        ]);
      this.widgets = await widgetsRes.json();
      this.themes = await themesRes.json();
      this.fonts = await fontsRes.json();
      try {
        const app = await appRes.json();
        const panels = await panelsRes.json();
        const spec = panels.find((p) => p.id === app?.panel?.model);
        if (spec) {
          this.appPanel = {
            model: app.panel.model,
            orientation: app.panel.orientation,
            width: spec.width,
            height: spec.height,
          };
        }
      } catch {
        /* leave appPanel null; falls back to PANEL_W/PANEL_H */
      }
      // Pre-fetch dynamic choices for any cell_option declaring choices_from.
      const dyn = {};
      const tasks = [];
      for (const w of this.widgets) {
        for (const opt of w.cell_options || []) {
          if (!opt.choices_from) continue;
          tasks.push(
            fetch(
              `/api/plugins/${encodeURIComponent(w.id)}/choices/${encodeURIComponent(opt.choices_from)}`
            )
              .then((r) => r.json())
              .then((list) => {
                dyn[`${w.id}:${opt.name}`] = Array.isArray(list) ? list : [];
              })
              .catch(() => {
                dyn[`${w.id}:${opt.name}`] = [];
              })
          );
        }
      }
      await Promise.all(tasks);
      this.dynChoices = dyn;
      if (this.pageId) {
        const pageRes = await fetch(`/api/pages/${encodeURIComponent(this.pageId)}`);
        if (pageRes.ok) {
          this.page = await pageRes.json();
          this.layoutKey =
            detectLayout(this.page.cells, this.page.panel) || "custom";
          // Backfill any choices_from option that was saved empty (e.g. an
          // older page where gallery folder was never picked) with the
          // first available choice. If anything changed, mark as dirty so
          // the next save persists the fix.
          const backfilled = this._backfillCellOptions(this.page.cells);
          if (backfilled !== this.page.cells) {
            this.page = { ...this.page, cells: backfilled };
            this.saved = false;
          } else {
            this.saved = true;
          }
          return;
        }
      }
      this.page = this._newPage(this.pageId || "untitled");
    } catch (err) {
      this.error = err.message;
    }
  }

  _newPage(id) {
    const dims = this._defaultPanelDims();
    return {
      id,
      name: id === "untitled" ? "Untitled" : id,
      panel: { w: dims.w, h: dims.h },
      theme: "default",
      font: "default",
      cells: pixelize("1x1", dims),
    };
  }

  _onLayoutChange(key) {
    if (!LAYOUTS[key]) return;
    const newCells = pixelize(key, this.page.panel);
    for (let i = 0; i < newCells.length && i < this.page.cells.length; i++) {
      newCells[i].plugin = this.page.cells[i].plugin;
      newCells[i].options = this.page.cells[i].options;
    }
    this.page = { ...this.page, cells: newCells };
    this.layoutKey = key;
    if (this.selectedCell >= newCells.length) this.selectedCell = 0;
    this.saved = false;
  }

  // Compute initial cell.options for a freshly-picked plugin. Honours the
  // manifest's defaults AND auto-selects the first dynamic choice for any
  // ``choices_from`` option whose default is empty. Without this, a select
  // like gallery's "folder" stores "" while the browser visually shows the
  // first folder — clicking that visible option doesn't fire @change, so
  // the cell stays unconfigured and renders the "_root" empty-folder error.
  _defaultsForPlugin(pluginId) {
    const widget = this.widgets.find((w) => w.id === pluginId);
    if (!widget) return {};
    const opts = {};
    for (const opt of widget.cell_options || []) {
      if (opt.default !== undefined) opts[opt.name] = opt.default;
      const empty = opts[opt.name] === undefined || opts[opt.name] === "";
      if (opt.type === "select" && opt.choices_from && empty) {
        const choices = this.dynChoices?.[`${pluginId}:${opt.name}`] || [];
        const firstReal = choices.find((c) => c.value !== "");
        if (firstReal) opts[opt.name] = firstReal.value;
      }
    }
    return opts;
  }

  _setCellPlugin(index, pluginId) {
    const newCells = this.page.cells.slice();
    newCells[index] = {
      ...newCells[index],
      plugin: pluginId,
      options: this._defaultsForPlugin(pluginId),
    };
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
  }

  // Sweep a list of cells; for each ``choices_from`` option still empty,
  // fill in the first real choice. Returns the same list when nothing
  // needed filling so the caller can keep the existing reference.
  _backfillCellOptions(cells) {
    let changed = false;
    const out = cells.map((cell) => {
      const widget = this.widgets.find((w) => w.id === cell.plugin);
      if (!widget) return cell;
      const newOpts = { ...(cell.options || {}) };
      let cellChanged = false;
      for (const opt of widget.cell_options || []) {
        if (opt.type !== "select" || !opt.choices_from) continue;
        if (newOpts[opt.name] !== undefined && newOpts[opt.name] !== "") continue;
        const choices = this.dynChoices?.[`${cell.plugin}:${opt.name}`] || [];
        const first = choices.find((c) => c.value !== "");
        if (first) {
          newOpts[opt.name] = first.value;
          cellChanged = true;
        }
      }
      if (cellChanged) {
        changed = true;
        return { ...cell, options: newOpts };
      }
      return cell;
    });
    return changed ? out : cells;
  }

  _setCellOption(index, optName, value) {
    const newCells = this.page.cells.slice();
    newCells[index] = {
      ...newCells[index],
      options: { ...newCells[index].options, [optName]: value },
    };
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
  }

  _setName(name) {
    this.page = { ...this.page, name };
    this.saved = false;
  }

  _setPageBleed(hex) {
    this.page = { ...this.page, bleed_color: hex };
    this.saved = false;
  }

  _setPageTheme(themeId) {
    this.page = { ...this.page, theme: themeId };
    this.saved = false;
  }

  _selectCell(idx) {
    if (this.selectedCell === idx) return;
    this.selectedCell = idx;
  }

  _setPageFont(fontId) {
    this.page = { ...this.page, font: fontId };
    this.saved = false;
  }

  _setPageGap(value) {
    this.page = { ...this.page, gap: Number(value) || 0 };
    this.saved = false;
  }

  _setPageCornerRadius(value) {
    this.page = { ...this.page, corner_radius: Number(value) || 0 };
    this.saved = false;
  }

  _setCellOverride(index, field, value) {
    const newCells = this.page.cells.slice();
    const cell = { ...newCells[index] };
    if (value === "" || value === null) {
      delete cell[field];
    } else {
      cell[field] = value;
    }
    newCells[index] = cell;
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
  }

  /**
   * Per-cell colour-token overrides. When `hex` is null/empty the override is
   * removed and the cell falls back to the resolved theme palette. Empty
   * palette_overrides objects get pruned so saved JSON stays clean.
   */
  _setCellPaletteOverride(index, token, hex) {
    const newCells = this.page.cells.slice();
    const overrides = { ...(newCells[index].palette_overrides || {}) };
    if (hex == null || hex === "") {
      delete overrides[token];
    } else {
      overrides[token] = hex;
    }
    const cell = { ...newCells[index] };
    if (Object.keys(overrides).length === 0) {
      delete cell.palette_overrides;
    } else {
      cell.palette_overrides = overrides;
    }
    newCells[index] = cell;
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
  }

  async _save() {
    this.saving = true;
    this.error = null;
    try {
      const res = await fetch(`/api/pages/${encodeURIComponent(this.page.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.page),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      this.page = await res.json();
      this.saved = true;
      this.lastSavedAt = Date.now();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.saving = false;
    }
  }

  // Debounced live preview: stage the in-memory page in the server's preview
  // cache so the iframe at /compose/<id> reflects unsaved edits.
  _schedulePreview() {
    if (this._previewTimer) clearTimeout(this._previewTimer);
    this._previewTimer = setTimeout(() => this._stagePreview(), 200);
  }

  async _stagePreview() {
    if (!this.page) return;
    try {
      const res = await fetch(
        `/api/pages/${encodeURIComponent(this.page.id)}/preview`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(this.page),
        }
      );
      if (!res.ok) return;
      this.previewKey = Date.now();
    } catch {
      /* ignore — saved state still renders, just not the live edit */
    }
  }

  async _send() {
    // Push the in-memory draft state to the panel WITHOUT persisting it
    // back to the page store. Server stages the page under a transient id,
    // pushes, then deletes it.
    if (isPushing()) {
      this.pushResult = {
        ok: false,
        error: "Another push is already in flight. Wait for it to finish.",
      };
      return;
    }
    this.pushing = true;
    this.pushResult = null;
    try {
      await runWithPushLock(`editor:${this.page?.id ?? ""}`, async () => {
        const res = await fetch("/api/pages/push-inline", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page: this.page, dither: this.dither }),
        });
        const body = await res.json();
        this.pushResult = { ok: res.ok, ...body };
      });
    } catch (err) {
      this.pushResult = { ok: false, error: err.message };
    } finally {
      this.pushing = false;
    }
  }

  _scaleIframes() {
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    if (!wraps) return;
    const w = this.page?.panel?.w || PANEL_W;
    for (const wrap of wraps) {
      const iframe = wrap.querySelector("iframe");
      if (!iframe) continue;
      const scale = wrap.clientWidth / w;
      iframe.style.transform = `scale(${scale})`;
    }
  }

  firstUpdated() {
    this._resizeObserver = new ResizeObserver(() => this._scaleIframes());
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    wraps?.forEach((w) => this._resizeObserver.observe(w));
    this._scaleIframes();
  }

  updated(changed) {
    this._scaleIframes();
    // Watch any newly-added iframe-wraps (e.g. quantized preview tile appearing).
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    wraps?.forEach((w) => this._resizeObserver?.observe(w));
    // Whenever the page state mutates and there are unsaved edits, push them
    // to the server's preview cache so the iframe reflects them live.
    if (changed.has("page") && this.page && !this.saved) {
      this._schedulePreview();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resizeObserver?.disconnect();
    window.removeEventListener("beforeunload", this._onBeforeUnload);
    this._unsubPushState?.();
    if (this._previewTimer) clearTimeout(this._previewTimer);
    // Best-effort cleanup so abandoned previews don't shadow saved data.
    if (this.page) {
      try {
        navigator.sendBeacon?.(
          `/api/pages/${encodeURIComponent(this.page.id)}/preview`
        );
      } catch {
        /* ignore */
      }
      // sendBeacon is POST-only; fall back to fetch DELETE for cleanup
      // (fire-and-forget; ignore failures).
      try {
        fetch(`/api/pages/${encodeURIComponent(this.page.id)}/preview`, {
          method: "DELETE",
          keepalive: true,
        });
      } catch {
        /* ignore */
      }
    }
  }

  _renderQuantizedFrame() {
    const id = encodeURIComponent(this.page.id);
    // Use the most-recent of (preview stage / save) as the cache-bust so the
    // iframe + quantized image refresh after every live edit, not just saves.
    const cacheBust = this.previewKey || this.lastSavedAt || "initial";
    const previewUrl = `/api/pages/${id}/preview.png?dither=${this.dither}&t=${cacheBust}`;
    // Frame matches the page's composition dims — preview is "what you see
    // looking at the panel face-on", upright. The push pipeline rotates the
    // bytes separately for the panel's landscape-native pixel grid.
    return html`
      <div
        class="quantized-frame"
        style="--panel-w: ${this.page.panel.w}; --panel-h: ${this.page.panel.h};"
      >
        <img
          src=${previewUrl}
          alt="Quantized preview"
          loading="lazy"
          @load=${() => (this.previewLoading = false)}
          @loadstart=${() => (this.previewLoading = true)}
        />
      </div>
    `;
  }

  _renderPicker() {
    const cells = this.page.cells;
    const id = encodeURIComponent(this.page.id);
    // Use the most-recent of (preview stage / save) as the cache-bust so the
    // iframe + quantized image refresh after every live edit, not just saves.
    const cacheBust = this.previewKey || this.lastSavedAt || "initial";
    const composeUrl = `/compose/${id}?for_push=1&t=${cacheBust}`;
    // Match the composer's gap inset so the click targets sit on top of the
    // visually-shrunken cells in the iframe. Sides on the panel edge inset
    // by gap/2; sides facing another cell inset by gap/4 so cell-to-cell
    // and cell-to-edge gaps look identical.
    const gap = this.page.gap || 0;
    const outerPad = Math.floor(gap / 2);
    const innerPad = Math.floor(gap / 4);
    const panelW = this.page.panel.w;
    const panelH = this.page.panel.h;
    return html`<div
      class="picker-frame iframe-wrap"
      style="--panel-w: ${panelW}; --panel-h: ${panelH};"
    >
      <iframe src=${composeUrl} title="Live preview"></iframe>
      <div class="cell-overlay">
        ${cells.map((c, i) => {
          const left = c.x === 0 ? outerPad : innerPad;
          const top = c.y === 0 ? outerPad : innerPad;
          const right = c.x + c.w === panelW ? outerPad : innerPad;
          const bottom = c.y + c.h === panelH ? outerPad : innerPad;
          const x = c.x + left;
          const y = c.y + top;
          const w = Math.max(1, c.w - left - right);
          const h = Math.max(1, c.h - top - bottom);
          return html`
            <div
              class="cell-hit"
              data-selected=${i === this.selectedCell ? "true" : "false"}
              style="left: ${(x / panelW) * 100}%;
                     top: ${(y / panelH) * 100}%;
                     width: ${(w / panelW) * 100}%;
                     height: ${(h / panelH) * 100}%;"
              @click=${() => this._selectCell(i)}
            >
              <span class="cell-hit-label">${i + 1} · ${c.plugin}</span>
            </div>
          `;
        })}
      </div>
    </div>`;
  }

  _renderCellOptions() {
    const cell = this.page.cells[this.selectedCell];
    if (!cell) return null;
    const widget = this.widgets.find((w) => w.id === cell.plugin);
    return html`
      <id-card>
        <div class="cell-heading">
          <span class="cell-badge">${this.selectedCell + 1}</span>
          <h3>Cell ${this.selectedCell + 1}</h3>
          <span class="plugin-tag">·  ${widget?.name || cell.plugin}</span>
        </div>
        <id-form-row label="Plugin">
          <select
            @change=${(e) => this._setCellPlugin(this.selectedCell, e.target.value)}
          >
            ${this.widgets.length === 0
              ? html`<option>(no widgets)</option>`
              : null}
            ${this.widgets.map(
              (w) => html`
                <option value=${w.id} ?selected=${w.id === cell.plugin}>
                  ${w.name}
                </option>
              `
            )}
          </select>
        </id-form-row>
        <id-form-row label="Theme override" hint="Leave on Inherit to use the page theme.">
          <select
            @change=${(e) =>
              this._setCellOverride(this.selectedCell, "theme", e.target.value || null)}
          >
            <option value="" ?selected=${!cell.theme}>Inherit page</option>
            ${(() => {
              const groups = groupThemes(this.themes);
              return THEME_SECTIONS.map((s) => {
                const list = groups[s.key];
                if (!list.length) return null;
                return html`<optgroup label=${s.label}>
                  ${list.map(
                    (t) => html`<option value=${t.id} ?selected=${t.id === cell.theme}>
                      ${t.name}
                    </option>`,
                  )}
                </optgroup>`;
              });
            })()}
          </select>
        </id-form-row>
        <id-form-row label="Font override">
          <select
            @change=${(e) =>
              this._setCellOverride(this.selectedCell, "font", e.target.value || null)}
          >
            <option value="" ?selected=${!cell.font}>Inherit page</option>
            ${this.fonts.map(
              (f) => html`
                <option value=${f.id} ?selected=${f.id === cell.font}>
                  ${f.name}
                </option>
              `
            )}
          </select>
        </id-form-row>
        ${widget && (widget.cell_options || []).length
          ? widget.cell_options.map((opt) => this._renderOption(cell, opt))
          : html`<p class="empty">No widget options.</p>`}
      </id-card>
    `;
  }

  _renderColorOverrides() {
    const cell = this.page.cells[this.selectedCell];
    if (!cell) return null;
    const themeId = cell.theme || this.page.theme;
    const theme = this.themes.find((t) => t.id === themeId);
    const inherited = theme?.palette || {};
    const overrides = cell.palette_overrides || {};
    const tokens = [
      "bg", "surface", "surface2",
      "fg", "fgSoft", "muted",
      "divider",
      "accent", "accentSoft",
      "danger", "warn", "ok",
    ];
    const overrideCount = Object.keys(overrides).length;
    return html`
      <id-card>
        <details class="overrides-details" ?open=${overrideCount > 0}>
          <summary class="overrides-summary">
            <span class="overrides-label">Per-cell colour overrides</span>
            <span class="overrides-count">${overrideCount} of ${tokens.length} overridden</span>
          </summary>
          <p class="overrides-hint">
            Override individual theme tokens for this cell only. Leave a token at
            its inherited value (no Reset button shown) to follow the page theme.
          </p>
          <div class="overrides-grid">
            ${tokens.map((tok) => {
              const isOverridden = Object.prototype.hasOwnProperty.call(overrides, tok);
              const value = isOverridden ? overrides[tok] : (inherited[tok] || "#ffffff");
              return html`
                <id-form-row label=${tok}>
                  <div class="override-row ${isOverridden ? "overridden" : "inherited"}">
                    <id-color-picker
                      .value=${value}
                      @change=${(e) =>
                        this._setCellPaletteOverride(
                          this.selectedCell,
                          tok,
                          e.detail.value
                        )}
                    ></id-color-picker>
                    ${isOverridden
                      ? html`<button
                          type="button"
                          class="override-reset"
                          title="Reset to inherited theme value"
                          @click=${() =>
                            this._setCellPaletteOverride(this.selectedCell, tok, null)}
                        >Reset</button>`
                      : html`<span class="override-inherit">inherited</span>`}
                  </div>
                </id-form-row>
              `;
            })}
          </div>
        </details>
      </id-card>
    `;
  }

  _renderOption(cell, opt) {
    const value = cell.options[opt.name] ?? opt.default ?? "";
    if (opt.type === "select") {
      // Static choices on the manifest, OR dynamic via choices_from
      const choices = opt.choices_from
        ? (this.dynChoices && this.dynChoices[`${cell.plugin}:${opt.name}`]) || []
        : opt.choices || [];
      return html`<id-form-row label=${opt.label}>
        <select
          @change=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.value)}
        >
          ${choices.length === 0
            ? html`<option value="">(none)</option>`
            : choices.map(
                (c) => html`<option value=${c.value} ?selected=${String(c.value) === String(value)}>${c.label}</option>`
              )}
        </select>
      </id-form-row>`;
    }
    if (opt.type === "boolean") {
      return html`<id-form-row label=${opt.label}>
        <label class="checkbox">
          <input
            type="checkbox"
            ?checked=${value === true}
            @change=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.checked)}
          />
          ${value === true ? "On" : "Off"}
        </label>
      </id-form-row>`;
    }
    if (opt.type === "color") {
      return html`<id-form-row label=${opt.label}>
        <id-color-picker
          .value=${String(value || "#ffffff")}
          @change=${(e) =>
            this._setCellOption(this.selectedCell, opt.name, e.detail.value)}
        ></id-color-picker>
      </id-form-row>`;
    }
    if (opt.type === "textarea") {
      return html`<id-form-row label=${opt.label}>
        <textarea
          rows="4"
          .value=${String(value)}
          @input=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.value)}
        ></textarea>
      </id-form-row>`;
    }
    return html`<id-form-row label=${opt.label}>
      <input
        type="text"
        .value=${String(value)}
        @input=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.value)}
      />
    </id-form-row>`;
  }

  _renderToolbar() {
    let pill;
    if (this.error) {
      pill = html`<span class="status-pill error"
        ><i class="ph ph-warning-circle"></i> ${this.error}</span
      >`;
    } else if (this.saving) {
      pill = html`<span class="status-pill"
        ><span class="preview-spinner" style="width:10px;height:10px;border-width:1.5px;"></span>
        Saving…</span
      >`;
    } else if (this.saved) {
      pill = html`<span class="status-pill ok"
        ><i class="ph ph-check-circle"></i> Saved</span
      >`;
    } else {
      pill = html`<span class="status-pill dirty"
        ><i class="ph ph-circle-dashed"></i> Unsaved</span
      >`;
    }
    return html`
      <div class="toolbar">
        <div class="toolbar-inner">
          <a href="/editor" class="back-btn" title="All dashboards" aria-label="All dashboards">
            <i class="ph ph-arrow-left"></i>
          </a>
          <button
            class="icon-btn"
            @click=${() => (this.iconPickerOpen = true)}
            title="Pick an icon"
            aria-label="Pick an icon"
          >
            <i class="ph ${this.page.icon || "ph-cube"}"></i>
          </button>
          <input
            class="name-input"
            type="text"
            .value=${this.page.name}
            placeholder="Untitled dashboard"
            aria-label="Dashboard name"
            @input=${(e) => this._setName(e.target.value)}
          />
          ${pill}
          <span class="toolbar-spacer"></span>
          <div class="toolbar-actions">
            <id-button
              variant="primary"
              ?disabled=${this.saving || this.pushing || this.saved}
              @click=${() => this._save()}
              title="Save"
            >
              <i class="ph ph-floppy-disk"></i>
              ${this.saving ? "Saving…" : this.saved ? "Saved" : "Save"}
            </id-button>
            <id-button
              ?disabled=${this.pushing || this.saving || this.globalPushing}
              @click=${() => this._send()}
              title=${this.globalPushing
                ? `Another push is in flight${this.globalPushSource ? ` (${this.globalPushSource})` : ""}`
                : "Send to panel without saving"}
            >
              <i class="ph ph-paper-plane-tilt"></i>
              ${this.pushing
                ? "Sending…"
                : this.globalPushing
                  ? "Push in flight"
                  : "Send"}
            </id-button>
          </div>
        </div>
      </div>
    `;
  }

  _renderLayoutPicker() {
    return html`
      <div class="layout-grid">
        ${Object.entries(LAYOUTS).map(([key, l]) => {
          // Compute layout shape on a 0..1 grid for the thumbnail.
          const cols = Math.max(...l.cells.map((c) => c.x + c.w));
          const rows = Math.max(...l.cells.map((c) => c.y + c.h));
          return html`
            <button
              type="button"
              class="layout-thumb"
              aria-pressed=${this.layoutKey === key ? "true" : "false"}
              title=${l.label}
              @click=${() => this._onLayoutChange(key)}
            >
              <div class="layout-thumb-shape">
                ${l.cells.map(
                  (c) => html`
                    <div
                      class="layout-thumb-cell"
                      style="left: ${(c.x / cols) * 100}%;
                             top: ${(c.y / rows) * 100}%;
                             width: ${(c.w / cols) * 100}%;
                             height: ${(c.h / rows) * 100}%;"
                    ></div>
                  `
                )}
              </div>
              <span class="layout-thumb-label">${l.label}</span>
            </button>
          `;
        })}
        ${this.layoutKey === "custom"
          ? html`<div
              class="layout-thumb"
              aria-pressed="true"
              style="cursor: default;"
            >
              <div class="layout-thumb-shape"></div>
              <span class="layout-thumb-label">Custom</span>
            </div>`
          : null}
      </div>
    `;
  }

  _renderPreviewPane() {
    return html`
      <div class="preview-col">
        <id-tab-bar
          .tabs=${[
            { id: "live", label: "Live preview" },
            { id: "quantized", label: "Panel paint" },
          ]}
          .selected=${this.previewMode}
          @change=${(e) => (this.previewMode = e.detail.selected)}
        ></id-tab-bar>
        ${this.previewMode === "quantized"
          ? this._renderQuantizedFrame()
          : this._renderPicker()}
        <div class="preview-meta">
          <span>
            ${this.previewMode === "quantized"
              ? html`Spectra 6 dithered output`
              : html`<i class="ph ph-cursor-click"></i> Click a cell to edit it`}
          </span>
          ${this.previewMode === "quantized"
            ? html`<label
                style="display: inline-flex; align-items: center; gap: 6px;"
              >
                Dither:
                <select
                  .value=${this.dither}
                  @change=${(e) => {
                    this.dither = e.target.value;
                    this.lastSavedAt = Date.now();
                  }}
                  style="padding: 4px 6px; border: 1px solid var(--id-divider); border-radius: 4px; min-height: 0; background: var(--id-bg);"
                >
                  <option value="floyd-steinberg">Floyd–Steinberg</option>
                  <option value="none">None (nearest)</option>
                </select>
              </label>`
            : html`<span>${this.page.panel.w}×${this.page.panel.h}</span>`}
        </div>
      </div>
    `;
  }

  render() {
    if (!this.page) {
      return html`<p style="padding: 24px;">
        ${this.error ? `Error: ${this.error}` : "Loading…"}
      </p>`;
    }
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="editor"></id-nav>
      ${this._renderToolbar()}

      <div class="container">
        ${this.pushResult
          ? html`<div class="toast ${this.pushResult.ok ? "" : "error"}">
              ${this.pushResult.ok
                ? html`<i class="ph ph-check-circle"></i>
                    Sent to panel · ${this.pushResult.digest} ·
                    ${this.pushResult.duration_s}s`
                : html`<i class="ph ph-warning-circle"></i> Send failed:
                    ${this.pushResult.error || this.pushResult.status}`}
            </div>`
          : null}
        <div class="grid">
          <div class="sidebar-col">
            <id-card heading="Page" subheading="Theme + font + matting + spacing applied to every cell.">
              <id-form-row label="Theme" hint="Sets the --theme-* CSS variables every widget paints with.">
                <select @change=${(e) => this._setPageTheme(e.target.value)}>
                  ${this.themes.length === 0
                    ? html`<option>(no themes loaded)</option>`
                    : null}
                  ${(() => {
                    const groups = groupThemes(this.themes);
                    const current = this.page.theme || "default";
                    return THEME_SECTIONS.map((s) => {
                      const list = groups[s.key];
                      if (!list.length) return null;
                      return html`<optgroup label=${s.label}>
                        ${list.map(
                          (t) => html`<option value=${t.id} ?selected=${t.id === current}>
                            ${t.name}
                          </option>`,
                        )}
                      </optgroup>`;
                    });
                  })()}
                </select>
              </id-form-row>
              <id-form-row label="Font">
                <select @change=${(e) => this._setPageFont(e.target.value)}>
                  ${this.fonts.length === 0
                    ? html`<option>(no fonts loaded)</option>`
                    : null}
                  ${this.fonts.map(
                    (f) => html`<option
                      value=${f.id}
                      ?selected=${f.id === (this.page.font || "default")}
                    >
                      ${f.name}${f.category ? ` — ${f.category}` : ""}
                    </option>`
                  )}
                </select>
              </id-form-row>
              <id-form-row label="Matting" hint="Color that bleeds through the gap between widgets and behind rounded corners.">
                <id-color-picker
                  .value=${this.page.bleed_color || "#ffffff"}
                  @change=${(e) => this._setPageBleed(e.detail.value)}
                ></id-color-picker>
              </id-form-row>
              <id-form-row label="Gap" hint="Pixels between cells + around the panel edge.">
                <id-slider
                  min="0"
                  max="120"
                  step="2"
                  value=${this.page.gap || 0}
                  suffix="px"
                  @change=${(e) => this._setPageGap(e.detail.value)}
                ></id-slider>
              </id-form-row>
              <id-form-row label="Corner radius">
                <id-slider
                  min="0"
                  max="120"
                  step="2"
                  value=${this.page.corner_radius || 0}
                  suffix="px"
                  @change=${(e) => this._setPageCornerRadius(e.detail.value)}
                ></id-slider>
              </id-form-row>
            </id-card>

            <id-card heading="Layout" subheading="Pick a layout to split the panel into cells.">
              ${this._renderLayoutPicker()}
            </id-card>

            ${this._renderCellOptions()}
            ${this.selectedCell != null && this.page.cells[this.selectedCell]
              ? this._renderColorOverrides()
              : null}
          </div>

          ${this._renderPreviewPane()}
        </div>
      </div>
      <id-icon-picker
        ?open=${this.iconPickerOpen}
        .value=${this.page?.icon || null}
        @change=${(e) => this._setPageIcon(e.detail.value)}
        @close=${() => (this.iconPickerOpen = false)}
      ></id-icon-picker>
    `;
  }

}

customElements.define("id-editor", IdEditor);

const params = new URLSearchParams(location.search);
const pageIdFromBody = document.body.dataset.pageId || params.get("id") || null;
const editor = document.createElement("id-editor");
if (pageIdFromBody) editor.setAttribute("page-id", pageIdFromBody);
document.body.append(editor);
