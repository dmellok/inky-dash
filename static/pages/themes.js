import { LitElement, html, css } from "lit";
import "../components/index.js";

const PALETTE_KEYS = [
  "bg",
  "surface",
  "surface2",
  "fg",
  "fgSoft",
  "muted",
  "accent",
  "accentSoft",
  "divider",
  "danger",
  "warn",
  "ok",
];

const STARTER_PALETTE = {
  bg: "#fbf7f1",
  surface: "#ffffff",
  surface2: "#f5e8d8",
  fg: "#1a1612",
  fgSoft: "#5a4f44",
  muted: "#8b7e70",
  accent: "#d97757",
  accentSoft: "#aa5a3f",
  divider: "#d8c8a8",
  danger: "#c97c70",
  warn: "#d4a957",
  ok: "#7da670",
};

function slugify(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

// Bucket themes into White / Light / Medium / Dark by bg luminance
// (Rec.709). "White" is reserved for themes whose bg is pure white AND
// whose surfaces are neutral grayscale (no warm/cool tint) — the
// stark-white-plus-bold-accent family. Cream / paper / parchment
// themes have an #ffffff bg too but tinted surfaces, so they stay in
// "Light". Legacy themes without a usable bg fall back to `mode`.
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

class ThemesPage extends LitElement {
  static properties = {
    themes: { state: true },
    fonts: { state: true },
    widgets: { state: true },
    selectedFontId: { state: true },
    selectedId: { state: true },
    error: { state: true },
    editing: { state: true },
    editingId: { state: true },
    editingName: { state: true },
    editingMode: { state: true },
    editingPalette: { state: true },
    saving: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    p.lede { margin: 0 0 16px; color: var(--id-fg-soft, #5a4f44); }

    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 20px;
      align-items: start;
    }
    @media (max-width: 900px) {
      .layout { grid-template-columns: 1fr; }
    }

    .theme-list {
      display: grid;
      gap: 6px;
      align-content: start;
    }
    /* Section header above each Light / Medium / Dark bucket. */
    .bucket-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 14px 4px 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--id-fg-soft, #5a4f44);
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      margin-bottom: 4px;
    }
    .bucket-head:first-of-type { padding-top: 6px; }
    .bucket-label { font-weight: 700; color: var(--id-fg, #1a1612); }
    .bucket-count {
      font-variant-numeric: tabular-nums;
      font-weight: 600;
    }
    .list-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0 4px 4px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
    }
    .theme-row {
      display: flex;
      gap: 12px;
      align-items: center;
      padding: 10px 12px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      background: var(--id-surface, #ffffff);
      cursor: pointer;
      text-align: left;
      font: inherit;
      width: 100%;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .theme-row:hover { border-color: var(--id-accent, #d97757); }
    .theme-row[data-active="true"] {
      border-color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
    }
    .theme-mini {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 1px;
      width: 64px;
      height: 32px;
      border-radius: 4px;
      overflow: hidden;
      flex-shrink: 0;
      border: 1px solid rgba(0, 0, 0, 0.08);
    }
    .theme-mini span { display: block; }
    .theme-info { flex: 1; min-width: 0; }
    .theme-info .name {
      font-weight: 600;
      font-size: 14px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .theme-info .sub {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .theme-info .badge {
      padding: 1px 6px;
      border-radius: 999px;
      background: var(--id-surface2, #f5e8d8);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .theme-info .badge.user {
      background: var(--id-accent, #d97757);
      color: white;
    }

    /* Featured preview pane (right column) */
    .preview-pane {
      position: sticky;
      top: 70px;
      display: grid;
      gap: 12px;
    }
    .preview-card {
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 12px;
      overflow: hidden;
      background: var(--id-surface, #ffffff);
    }
    .preview-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      gap: 8px;
      flex-wrap: wrap;
    }
    .preview-head h3 { margin: 0; font-size: 16px; }
    .preview-head .actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .meta-row {
      display: flex;
      gap: 6px;
      align-items: center;
      padding: 8px 16px;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      border-bottom: 1px solid var(--id-divider, #c8b89b);
    }
    .meta-row .badge {
      padding: 1px 8px;
      border-radius: 999px;
      background: var(--id-surface2, #f5e8d8);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }
    .meta-row .badge.user {
      background: var(--id-accent, #d97757);
      color: white;
    }

    /* Inline mock dashboard themed via the live palette. Mirrors the
       flat-surface design of the real widgets (no card borders, tonal
       surface-vs-bg step, color-mix pills) so a theme that looks right
       here looks right on the panel. Every palette token has a job so
       a regression in any single token shows up immediately. */
    .widget-preview {
      padding: 12px;
      background: var(--id-bg);
    }
    .widget-preview.empty {
      padding: 32px;
      text-align: center;
      color: var(--id-fg-soft);
      font-style: italic;
    }
    .mock {
      display: grid;
      gap: 10px;
      padding: 12px;
      border-radius: 10px;
      background: var(--m-bg);
      color: var(--m-fg);
    }
    /* Header strip — matches .head in widget-base.css. */
    .mock-head {
      display: flex;
      align-items: baseline;
      gap: 10px;
      padding-bottom: 6px;
      border-bottom: 2px solid var(--m-divider);
    }
    .mock-icon {
      color: var(--m-accent);
      font-size: 16px;
      align-self: center;
    }
    .mock-title {
      font-weight: 700;
      letter-spacing: 0.08em;
      font-size: 12px;
      text-transform: uppercase;
      color: var(--m-fg);
    }
    .mock-place {
      font-weight: 600;
      color: var(--m-accent);
      font-size: 12px;
    }
    .mock-time {
      margin-left: auto;
      font-variant-numeric: tabular-nums;
      color: var(--m-fgSoft);
      font-size: 12px;
    }
    /* Hero row — compact: big temp on the left, caption inline. */
    .mock-hero {
      display: flex;
      align-items: baseline;
      gap: 10px;
    }
    .mock-hero-num {
      font-size: 34px;
      font-weight: 800;
      line-height: 1;
      letter-spacing: -0.03em;
      color: var(--m-fg);
      font-variant-numeric: tabular-nums;
    }
    .mock-hero-cap {
      font-size: 13px;
      font-weight: 700;
      color: var(--m-fg);
    }
    .mock-hero-sub {
      margin-left: auto;
      font-size: 10px;
      color: var(--m-fgSoft);
      font-weight: 700;
      letter-spacing: 0.06em;
      align-self: center;
    }
    /* Stat-card grid — flat surfaces, no borders, matches .stat. */
    .mock-stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 6px;
    }
    .mock-stat {
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 6px 8px;
      background: var(--m-surface);
      border-radius: 6px;
      min-width: 0;
    }
    .mock-stat-ico {
      color: var(--m-accent);
      font-size: 16px;
      flex-shrink: 0;
    }
    .mock-stat-text { min-width: 0; }
    .mock-stat-label {
      font-size: 8px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: var(--m-fgSoft);
      text-transform: uppercase;
    }
    .mock-stat-val {
      font-size: 13px;
      font-weight: 700;
      color: var(--m-fg);
      font-variant-numeric: tabular-nums;
    }
    /* Pill row — matches .pill in widget-base.css: translucent
       backgrounds via color-mix, no borders. */
    .mock-pills {
      display: flex;
      gap: 5px;
      flex-wrap: wrap;
    }
    .mock-pill {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 9px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.04em;
      background: var(--m-surface2);
      color: var(--m-fgSoft);
    }
    .mock-pill .ph { font-size: 11px; }
    .mock-pill.accent {
      background: var(--m-accent);
      color: var(--m-bg);
    }
    .mock-pill.ok {
      color: var(--m-ok);
      background: color-mix(in oklab, var(--m-ok) 15%, transparent);
    }
    .mock-pill.warn {
      color: var(--m-warn);
      background: color-mix(in oklab, var(--m-warn) 15%, transparent);
    }
    .mock-pill.danger {
      color: var(--m-danger);
      background: color-mix(in oklab, var(--m-danger) 15%, transparent);
    }

    .swatch-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 1px;
    }
    .swatch-grid > div {
      aspect-ratio: 1;
      position: relative;
    }
    .swatch-grid > div::after {
      content: attr(data-key);
      position: absolute;
      bottom: 4px;
      left: 4px;
      font-size: 9px;
      background: rgba(0, 0, 0, 0.5);
      color: white;
      padding: 1px 4px;
      border-radius: 2px;
      opacity: 0;
      transition: opacity 100ms ease;
    }
    .swatch-grid > div:hover::after { opacity: 1; }

    /* Editor card */
    .editor-card {
      grid-column: 1 / -1;
      margin-bottom: 16px;
    }
    .editor-fields {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    @media (max-width: 480px) {
      .editor-fields { grid-template-columns: 1fr; }
    }
    .palette-editor {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .colour-row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 6px 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      background: var(--id-surface, #ffffff);
    }
    .colour-row id-color-picker { flex: 1; min-width: 0; }
    .colour-row .label {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      width: 70px;
      flex-shrink: 0;
    }
    .editor-toolbar {
      display: flex;
      gap: 8px;
      margin-top: 12px;
      flex-wrap: wrap;
    }
    .editor-fields input,
    .editor-fields select {
      width: 100%;
      padding: 8px 10px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      box-sizing: border-box;
    }

    .empty,
    .error {
      padding: 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
    }
    .error { color: var(--id-danger, #c97c70); }

    .fonts-section { margin-top: 32px; }
    .fonts-row {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 12px;
    }
    .font-card {
      padding: 16px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      background: var(--id-surface, #ffffff);
      color: var(--id-fg, #0f172a);
      font: inherit;
      text-align: left;
      cursor: pointer;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .font-card:hover {
      border-color: var(--id-accent, #b06750);
    }
    .font-card.active {
      border-color: var(--id-accent, #b06750);
      background: var(--id-accent-bg, rgb(176 103 80 / 0.1));
    }
    .font-card h3 { margin: 0 0 8px; font-size: 14px; }
    .font-sample { font-size: 28px; line-height: 1.1; margin-bottom: 4px; }
  `;

  constructor() {
    super();
    this.themes = null;
    this.fonts = null;
    this.selectedId = null;
    this.selectedFontId = "default";
    this.error = null;
    this.editing = false;
    this.editingId = "";
    this.editingName = "";
    this.editingMode = "light";
    this.editingPalette = { ...STARTER_PALETTE };
    this.saving = false;
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._load();
  }

  async _load() {
    try {
      const [themesRes, fontsRes, widgetsRes] = await Promise.all([
        fetch("/api/themes"),
        fetch("/api/fonts"),
        fetch("/api/widgets"),
      ]);
      this.themes = await themesRes.json();
      this.fonts = await fontsRes.json();
      this.widgets = await widgetsRes.json();
      if (!this.selectedId && this.themes.length) {
        const def = this.themes.find((t) => t.id === "default") || this.themes[0];
        this.selectedId = def.id;
      }
    } catch (err) {
      this.error = err.message;
    }
  }

  _selected() {
    if (!this.themes) return null;
    return this.themes.find((t) => t.id === this.selectedId) || this.themes[0] || null;
  }

  _select(theme) {
    this.selectedId = theme.id;
    this.editing = false;
    // Re-theme already-mounted iframes — switching themes shouldn't require
    // a reload, the postMessage path handles it.
    requestAnimationFrame(() => this._broadcastPalette());
  }

  _startNew() {
    this.editing = true;
    this.editingId = "";
    this.editingName = "";
    this.editingMode = "light";
    this.editingPalette = { ...STARTER_PALETTE };
  }

  _editExisting(theme) {
    this.editing = true;
    this.editingId = theme.is_user ? theme.id : "";
    this.editingName = theme.is_user ? theme.name : `${theme.name} copy`;
    this.editingMode = theme.mode || "light";
    this.editingPalette = { ...theme.palette };
  }

  _cancelEdit() {
    this.editing = false;
    this.error = null;
  }

  async _saveEdit() {
    this.saving = true;
    this.error = null;
    const id = this.editingId || slugify(this.editingName);
    if (!id) {
      this.error = "Name is required.";
      this.saving = false;
      return;
    }
    try {
      const res = await fetch("/api/themes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id,
          name: this.editingName || id,
          mode: this.editingMode,
          palette: this.editingPalette,
        }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      this.editing = false;
      this.selectedId = id;
      await this._load();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.saving = false;
    }
  }

  async _delete(theme) {
    if (!confirm(`Delete theme "${theme.name}"?`)) return;
    try {
      const res = await fetch(`/api/themes/${encodeURIComponent(theme.id)}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      if (this.selectedId === theme.id) this.selectedId = "default";
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  _setPaletteColour(key, value) {
    this.editingPalette = { ...this.editingPalette, [key]: value };
    this._broadcastPalette();
  }

  /**
   * postMessage the current palette to every preview iframe so they re-theme
   * in place (no reload, no flicker). compose.html listens for this message
   * and applies the values as inline CSS variables on each .cell.
   */
  _broadcastPalette() {
    const palette = this.editing ? this.editingPalette : this._selected()?.palette;
    if (!palette) return;
    const iframes = this.renderRoot?.querySelectorAll(".widget-preview iframe") || [];
    iframes.forEach((f) => {
      try {
        f.contentWindow?.postMessage({ type: "palette", palette }, "*");
      } catch {
        /* iframe not yet loaded — onload handler will resend */
      }
    });
  }

  _onPreviewIframeLoad(e) {
    // First broadcast happens once compose.html is ready to receive messages.
    const palette = this.editing ? this.editingPalette : this._selected()?.palette;
    if (!palette) return;
    try {
      e.target.contentWindow?.postMessage({ type: "palette", palette }, "*");
    } catch {
      /* swallow */
    }
  }

  /**
   * Render an inline dummy "dashboard tile" themed by the live palette.
   * Replaces the previous iframe-of-weather approach — that one didn't fit
   * the preview pane and depended on the weather widget being installed.
   * This dummy exercises every palette token (bg, surface, surface2, fg,
   * fgSoft, muted, accent, accentSoft, divider, danger, warn, ok) at sizes
   * comparable to a real widget so a theme that fails here will fail in a
   * real cell too.
   */
  _renderWidgetMocks() {
    const p = this.editing ? this.editingPalette : this._selected()?.palette;
    if (!p) {
      return html`<div class="widget-preview empty">Pick a theme to preview.</div>`;
    }
    const style = (rules) =>
      Object.entries(rules)
        .map(([k, v]) => `${k}: ${v}`)
        .join("; ");
    return html`
      <div class="widget-preview">
        <div
          class="mock"
          style=${style({
            background: p.bg,
            color: p.fg,
            "--m-bg": p.bg,
            "--m-surface": p.surface,
            "--m-surface2": p.surface2,
            "--m-fg": p.fg,
            "--m-fgSoft": p.fgSoft,
            "--m-muted": p.muted,
            "--m-accent": p.accent,
            "--m-accentSoft": p.accentSoft,
            "--m-divider": p.divider,
            "--m-danger": p.danger,
            "--m-warn": p.warn,
            "--m-ok": p.ok,
          })}
        >
          <div class="mock-head">
            <span class="mock-icon"><i class="ph ph-cloud-sun"></i></span>
            <span class="mock-title">Weather</span>
            <span class="mock-place">Melbourne</span>
            <span class="mock-time">14:32</span>
          </div>

          <div class="mock-hero">
            <div class="mock-hero-num">42°</div>
            <div class="mock-hero-cap">Mostly sunny</div>
            <div class="mock-hero-sub">Feels 39°</div>
          </div>

          <div class="mock-stats">
            <div class="mock-stat">
              <span class="mock-stat-ico"><i class="ph ph-wind"></i></span>
              <div class="mock-stat-text">
                <div class="mock-stat-label">Wind</div>
                <div class="mock-stat-val">12 km/h</div>
              </div>
            </div>
            <div class="mock-stat">
              <span class="mock-stat-ico"><i class="ph ph-drop"></i></span>
              <div class="mock-stat-text">
                <div class="mock-stat-label">Humidity</div>
                <div class="mock-stat-val">58%</div>
              </div>
            </div>
            <div class="mock-stat">
              <span class="mock-stat-ico"><i class="ph ph-sun-horizon"></i></span>
              <div class="mock-stat-text">
                <div class="mock-stat-label">UV</div>
                <div class="mock-stat-val">7</div>
              </div>
            </div>
          </div>

          <div class="mock-pills">
            <span class="mock-pill accent">Now</span>
            <span class="mock-pill">14 °C</span>
            <span class="mock-pill ok"><i class="ph ph-check-circle"></i> ok</span>
            <span class="mock-pill warn"><i class="ph ph-warning-circle"></i> warn</span>
            <span class="mock-pill danger"><i class="ph ph-x-circle"></i> danger</span>
          </div>
        </div>
      </div>
    `;
  }

  _renderListRow(theme) {
    const p = theme.palette;
    return html`
      <button
        type="button"
        class="theme-row"
        data-active=${this.selectedId === theme.id ? "true" : "false"}
        @click=${() => this._select(theme)}
      >
        <div class="theme-mini" aria-hidden="true">
          <span style="background: ${p.bg};"></span>
          <span style="background: ${p.surface};"></span>
          <span style="background: ${p.fg};"></span>
          <span style="background: ${p.accent};"></span>
        </div>
        <div class="theme-info">
          <div class="name">${theme.name}</div>
          <div class="sub">
            ${theme.is_user
              ? html`<span class="badge user">user</span>`
              : html`<span class="badge">${theme.mode || "—"}</span>`}
            <span>${theme.id}</span>
          </div>
        </div>
      </button>
    `;
  }

  _renderPreview() {
    const theme = this._selected();
    if (!theme) {
      return html`<div class="preview-card"><div class="empty">No theme selected.</div></div>`;
    }
    const p = theme.palette;
    const fontFamily =
      (this.fonts && this.fonts.find((f) => f.id === this.selectedFontId))?.name ||
      (this.fonts && this.fonts.find((f) => f.id === "default"))?.name ||
      "Inter";
    const mockStyle = `
      --mock-bg: ${p.bg};
      --mock-fg: ${p.fg};
      --mock-fg-soft: ${p.fgSoft};
      --mock-surface: ${p.surface};
      --mock-surface2: ${p.surface2};
      --mock-divider: ${p.divider};
      --mock-accent: ${p.accent};
      font-family: '${fontFamily}', system-ui, sans-serif;
    `;
    return html`
      <div class="preview-card">
        <div class="preview-head">
          <h3>${theme.name}</h3>
          <div class="actions">
            ${theme.is_user
              ? html`
                  <id-button @click=${() => this._editExisting(theme)}>
                    <i class="ph ph-pencil-simple"></i> Edit
                  </id-button>
                  <id-button variant="danger" @click=${() => this._delete(theme)}>
                    <i class="ph ph-trash"></i> Delete
                  </id-button>
                `
              : html`
                  <id-button @click=${() => this._editExisting(theme)}>
                    <i class="ph ph-copy"></i> Duplicate
                  </id-button>
                `}
          </div>
        </div>
        <div class="meta-row">
          ${theme.is_user
            ? html`<span class="badge user">user theme</span>`
            : html`<span class="badge">${theme.mode || "—"}</span>`}
          <span>·</span>
          <code>${theme.id}</code>
        </div>
        ${this._renderWidgetMocks(p)}
        <div class="swatch-grid">
          ${PALETTE_KEYS.map(
            (k) => html`<div data-key=${k} style="background: ${p[k]};"></div>`
          )}
        </div>
      </div>
    `;
  }

  _renderEditor() {
    const previewStyle = `background: ${this.editingPalette.bg}; color: ${this.editingPalette.fg};`;
    return html`
      <div class="editor-card">
      <id-card heading=${this.editingId ? `Edit "${this.editingName}"` : "New theme"}>
        <div class="editor-fields">
          <div>
            <label style="font-size: 12px; color: var(--id-fg-soft);">Name</label>
            <input
              type="text"
              .value=${this.editingName}
              @input=${(e) => (this.editingName = e.target.value)}
              placeholder="e.g. Twilight"
            />
          </div>
          <div>
            <label style="font-size: 12px; color: var(--id-fg-soft);">Mode</label>
            <select
              .value=${this.editingMode}
              @change=${(e) => (this.editingMode = e.target.value)}
            >
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </select>
          </div>
        </div>
        <div class="palette-editor">
          ${PALETTE_KEYS.map(
            (key) => html`
              <div class="colour-row">
                <span class="label">${key}</span>
                <id-color-picker
                  .value=${this.editingPalette[key]}
                  @change=${(e) => this._setPaletteColour(key, e.detail.value)}
                ></id-color-picker>
              </div>
            `
          )}
        </div>
        <div
          style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap; padding: 10px; border-radius: 6px; margin-top: 12px; ${previewStyle}"
        >
          <span style="color: ${this.editingPalette.fgSoft};">Aa</span>
          <span style="padding: 3px 8px; border-radius: 999px; font-size: 11px; background: ${this.editingPalette.accent}; color: ${this.editingPalette.bg};">accent</span>
          <span style="padding: 3px 8px; border-radius: 999px; font-size: 11px; background: ${this.editingPalette.danger}; color: ${this.editingPalette.bg};">danger</span>
          <span style="padding: 3px 8px; border-radius: 999px; font-size: 11px; background: ${this.editingPalette.ok}; color: ${this.editingPalette.bg};">ok</span>
        </div>
        ${this.error ? html`<p class="error" style="text-align: left; padding: 8px 0;">${this.error}</p>` : null}
        <div class="editor-toolbar">
          <id-button variant="primary" ?disabled=${this.saving} @click=${() => this._saveEdit()}>
            <i class="ph ph-floppy-disk"></i>
            ${this.saving ? "Saving…" : "Save theme"}
          </id-button>
          <id-button @click=${() => this._cancelEdit()}>
            <i class="ph ph-x"></i> Cancel
          </id-button>
        </div>
      </id-card>
      </div>
    `;
  }

  _fontFaceCss() {
    if (!this.fonts) return "";
    const rules = [];
    for (const font of this.fonts) {
      for (const [weight, url] of Object.entries(font.files)) {
        rules.push(
          `@font-face { font-family: '${font.name}'; font-weight: ${weight}; src: url('${url}') format('woff2'); font-display: block; }`
        );
      }
    }
    return rules.join("\n");
  }

  render() {
    if (this.error && !this.editing && !this.themes)
      return html`<p class="error">Error: ${this.error}</p>`;
    if (!this.themes || !this.fonts)
      return html`<p class="empty">Loading…</p>`;
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="themes"></id-nav>
      <div class="container">
        <style>${this._fontFaceCss()}</style>
        <h1>Themes</h1>
        <p class="lede">
          Click any theme on the left to preview it on a sample dashboard.
        </p>

        <div class="layout">
          ${this.editing ? this._renderEditor() : null}

          <div class="theme-list">
            <div class="list-head">
              <span>${this.themes.length} themes</span>
              ${!this.editing
                ? html`<id-button variant="primary" @click=${() => this._startNew()}>
                    <i class="ph ph-plus"></i> New
                  </id-button>`
                : null}
            </div>
            ${(() => {
              const groups = { white: [], light: [], medium: [], dark: [] };
              for (const t of this.themes) groups[themeBucket(t)].push(t);
              for (const arr of Object.values(groups)) {
                arr.sort((a, b) => a.name.localeCompare(b.name));
              }
              return THEME_SECTIONS.map((s) => {
                const list = groups[s.key];
                if (!list.length) return null;
                return html`
                  <div class="bucket-head">
                    <span class="bucket-label">${s.label}</span>
                    <span class="bucket-count">${list.length}</span>
                  </div>
                  ${list.map((t) => this._renderListRow(t))}
                `;
              });
            })()}
          </div>

          <div class="preview-pane">
            ${this._renderPreview()}
          </div>
        </div>

        <div class="fonts-section">
          <h2 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--id-fg-soft); margin: 0 0 12px;">
            ${this.fonts.length} bundled fonts
          </h2>
          <div class="fonts-row">
            ${this.fonts.map(
              (font) => html`
                <button
                  type="button"
                  class="font-card ${this.selectedFontId === font.id ? "active" : ""}"
                  @click=${() => (this.selectedFontId = font.id)}
                  aria-pressed=${this.selectedFontId === font.id ? "true" : "false"}
                  title="Use ${font.name} in the preview"
                >
                  <h3>${font.name} <span style="color: var(--id-fg-soft); font-weight: normal;">— ${font.category || "?"}</span></h3>
                  <div class="font-sample" style="font-family: '${font.name}';">
                    The quick brown fox.
                  </div>
                  <div style="font-family: '${font.name}'; font-size: 13px;">
                    0123456789 — ${font.weights.join(", ")}
                  </div>
                </button>
              `
            )}
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define("themes-page", ThemesPage);
document.body.append(document.createElement("themes-page"));
