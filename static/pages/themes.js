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

class ThemesPage extends LitElement {
  static properties = {
    themes: { state: true },
    fonts: { state: true },
    error: { state: true },
    filter: { state: true },
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
    }
  `;

  constructor() {
    super();
    this.themes = null;
    this.fonts = null;
    this.error = null;
  }

  async connectedCallback() {
    super.connectedCallback();
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

  _renderThemeCard(theme) {
    const p = theme.palette;
    return html`
      <id-card heading=${theme.name}>
        <div class="meta">
          <span class="badge">${theme.mode || "—"}</span>
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
    if (this.error) return html`<p class="error">Error: ${this.error}</p>`;
    if (!this.themes || !this.fonts) return html`<p class="empty">Loading…</p>`;
    return html`
      <style>${this._fontFaceCss()}</style>

      <h1>Themes &amp; fonts</h1>
      <p class="lede">
        Loaded from <code>themes_core</code> and <code>fonts_core</code> plugins.
        Off-gamut colours are intentional — Floyd–Steinberg dithers them into
        pleasing results on the panel.
      </p>

      <section>
        <h2>${this.themes.length} themes</h2>
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
