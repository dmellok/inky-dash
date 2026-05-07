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

class ThemesPage extends LitElement {
  static properties = {
    themes: { state: true },
    fonts: { state: true },
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
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px 16px;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 22px;
    }
    p.lede {
      margin: 0 0 16px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
      gap: 16px;
    }
    .swatch-grid {
      display: grid;
      grid-template-columns: repeat(6, 1fr);
      gap: 4px;
      margin-top: 12px;
    }
    .swatch {
      aspect-ratio: 1;
      border-radius: 4px;
      border: 1px solid rgba(0, 0, 0, 0.1);
      position: relative;
    }
    .swatch[data-key]:hover::after {
      content: attr(data-key);
      position: absolute;
      bottom: 4px;
      left: 4px;
      font-size: 9px;
      background: rgba(0, 0, 0, 0.6);
      color: white;
      padding: 1px 4px;
      border-radius: 2px;
    }
    .preview-strip {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
      padding: 10px;
      border-radius: 6px;
      margin-top: 12px;
      border: 1px solid var(--id-divider, #c8b89b);
      overflow: hidden;
    }
    .preview-strip .pill {
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 500;
      white-space: nowrap;
    }
    .meta {
      display: flex;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      margin-top: 8px;
    }
    .badge {
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--id-surface2, #f5e8d8);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .badge.user {
      background: var(--id-accent, #d97757);
      color: white;
    }
    .card-actions {
      display: flex;
      gap: 6px;
      margin-top: 10px;
      justify-content: flex-end;
    }
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
    }
    .font-card h3 {
      margin: 0 0 8px;
      font-size: 14px;
    }
    .font-sample {
      font-size: 28px;
      line-height: 1.1;
      margin-bottom: 4px;
    }
    .empty,
    .error {
      padding: 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
    }
    .error {
      color: var(--id-danger, #c97c70);
    }
    section {
      margin-bottom: 32px;
    }
    section h2 {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      margin: 0 0 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .palette-editor {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
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
    .colour-row input[type="color"] {
      width: 28px;
      height: 28px;
      padding: 0;
      border: 0;
      background: transparent;
      cursor: pointer;
    }
    .colour-row input[type="text"] {
      flex: 1;
      min-width: 0;
      padding: 6px 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 4px;
      font: 12px ui-monospace, "JetBrains Mono", monospace;
      text-transform: uppercase;
    }
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
    .editor-fields {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
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
  `;

  constructor() {
    super();
    this.themes = null;
    this.fonts = null;
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
      const [themesRes, fontsRes] = await Promise.all([
        fetch("/api/themes"),
        fetch("/api/fonts"),
      ]);
      this.themes = await themesRes.json();
      this.fonts = await fontsRes.json();
    } catch (err) {
      this.error = err.message;
    }
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
    this.editingId = theme.id;
    this.editingName = theme.name;
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
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  _setPaletteColour(key, value) {
    this.editingPalette = { ...this.editingPalette, [key]: value };
  }

  _renderEditor() {
    const previewStyle = `background: ${this.editingPalette.bg}; color: ${this.editingPalette.fg};`;
    return html`
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
                <input
                  type="color"
                  .value=${this.editingPalette[key]}
                  @input=${(e) => this._setPaletteColour(key, e.target.value)}
                />
                <span class="label">${key}</span>
                <input
                  type="text"
                  .value=${this.editingPalette[key].toUpperCase()}
                  @change=${(e) => {
                    const v = e.target.value.trim();
                    if (/^#[0-9a-fA-F]{6}$/.test(v))
                      this._setPaletteColour(key, v.toLowerCase());
                  }}
                />
              </div>
            `
          )}
        </div>

        <div class="preview-strip" style=${previewStyle}>
          <span style="color: ${this.editingPalette.fgSoft};">Aa</span>
          <span class="pill" style="background: ${this.editingPalette.accent}; color: ${this.editingPalette.bg};">accent</span>
          <span class="pill" style="background: ${this.editingPalette.danger}; color: ${this.editingPalette.bg};">danger</span>
          <span class="pill" style="background: ${this.editingPalette.ok}; color: ${this.editingPalette.bg};">ok</span>
        </div>

        ${this.error
          ? html`<p class="error" style="text-align: left; padding: 8px 0;">${this.error}</p>`
          : null}

        <div class="editor-toolbar">
          <id-button
            variant="primary"
            ?disabled=${this.saving}
            @click=${() => this._saveEdit()}
          >
            <i class="ph ph-floppy-disk"></i> ${this.saving ? "Saving…" : "Save theme"}
          </id-button>
          <id-button @click=${() => this._cancelEdit()}>
            <i class="ph ph-x"></i> Cancel
          </id-button>
        </div>
      </id-card>
    `;
  }

  _renderThemeCard(theme) {
    const p = theme.palette;
    return html`
      <id-card heading=${theme.name}>
        <div class="meta">
          ${theme.is_user
            ? html`<span class="badge user">user</span>`
            : html`<span class="badge">${theme.mode || "—"}</span>`}
          <span>${theme.id}</span>
        </div>
        <div class="swatch-grid">
          ${PALETTE_KEYS.map(
            (key) => html`
              <div
                class="swatch"
                data-key=${key}
                style="background: ${p[key]}"
                title="${key}: ${p[key]}"
              ></div>
            `
          )}
        </div>
        <div
          class="preview-strip"
          style="background: ${p.bg}; color: ${p.fg};"
        >
          <span style="color: ${p.fgSoft};">Aa</span>
          <span class="pill" style="background: ${p.accent}; color: ${p.bg};">accent</span>
          <span class="pill" style="background: ${p.danger}; color: ${p.bg};">danger</span>
          <span class="pill" style="background: ${p.ok}; color: ${p.bg};">ok</span>
        </div>
        ${theme.is_user
          ? html`
              <div class="card-actions">
                <id-button @click=${() => this._editExisting(theme)}>
                  <i class="ph ph-pencil-simple"></i> Edit
                </id-button>
                <id-button variant="danger" @click=${() => this._delete(theme)}>
                  <i class="ph ph-trash"></i> Delete
                </id-button>
              </div>
            `
          : null}
      </id-card>
    `;
  }

  _renderFontCard(font) {
    return html`
      <div class="font-card">
        <h3>${font.name} <span style="color: var(--id-fg-soft); font-weight: normal;">— ${font.category || "?"}</span></h3>
        <div class="font-sample" style="font-family: '${font.name}';">
          The quick brown fox.
        </div>
        <div style="font-family: '${font.name}'; font-size: 13px;">
          0123456789 — ${font.weights.join(", ")}
        </div>
      </div>
    `;
  }

  _fontFaceCss() {
    if (!this.fonts) return "";
    const rules = [];
    for (const font of this.fonts) {
      for (const [weight, url] of Object.entries(font.files)) {
        rules.push(`@font-face {
          font-family: '${font.name}';
          font-weight: ${weight};
          src: url('${url}') format('woff2');
          font-display: block;
        }`);
      }
    }
    return rules.join("\n");
  }

  render() {
    if (this.error && !this.editing)
      return html`<p class="error">Error: ${this.error}</p>`;
    if (!this.themes || !this.fonts) return html`<p class="empty">Loading…</p>`;
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <style>${this._fontFaceCss()}</style>

      <h1>Themes &amp; fonts</h1>
      <p class="lede">
        Loaded from <code>themes_core</code> and <code>fonts_core</code>. Click
        <strong>+ New theme</strong> to design your own.
      </p>

      ${this.editing ? this._renderEditor() : null}

      <section>
        <h2>
          ${this.themes.length} themes
          ${!this.editing
            ? html`<id-button variant="primary" @click=${() => this._startNew()}>
                <i class="ph ph-plus"></i> New theme
              </id-button>`
            : null}
        </h2>
        <div class="grid">${this.themes.map((t) => this._renderThemeCard(t))}</div>
      </section>

      <section>
        <h2>${this.fonts.length} fonts</h2>
        <div class="fonts-row">${this.fonts.map((f) => this._renderFontCard(f))}</div>
      </section>
    `;
  }
}

customElements.define("themes-page", ThemesPage);
document.body.append(document.createElement("themes-page"));
