import { LitElement, html, css } from "lit";
import "../components/index.js";

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
  // Hero layouts use a 2-col × 3-row grid: hero spans 2×2, two side cells are 1×1.
  "hero-top": {
    label: "Hero top",
    cells: [
      { x: 0, y: 0, w: 2, h: 2 },
      { x: 0, y: 2, w: 1, h: 1 },
      { x: 1, y: 2, w: 1, h: 1 },
    ],
  },
  "hero-bottom": {
    label: "Hero bottom",
    cells: [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 1, y: 0, w: 1, h: 1 },
      { x: 0, y: 1, w: 2, h: 2 },
    ],
  },
  // Hero left/right use 3-col × 2-row: hero spans 2×2, two stacked cells are 1×1.
  "hero-left": {
    label: "Hero left",
    cells: [
      { x: 0, y: 0, w: 2, h: 2 },
      { x: 2, y: 0, w: 1, h: 1 },
      { x: 2, y: 1, w: 1, h: 1 },
    ],
  },
  "hero-right": {
    label: "Hero right",
    cells: [
      { x: 0, y: 0, w: 1, h: 1 },
      { x: 0, y: 1, w: 1, h: 1 },
      { x: 1, y: 0, w: 2, h: 2 },
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

class IdEditor extends LitElement {
  static properties = {
    pageId: { type: String, attribute: "page-id" },
    page: { state: true },
    widgets: { state: true },
    themes: { state: true },
    fonts: { state: true },
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
    .header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 16px;
      flex-wrap: wrap;
    }
    h1 {
      margin: 0;
      font-size: 20px;
    }
    .status {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .status.error {
      color: var(--id-danger, #c97c70);
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 16px;
    }
    @media (min-width: 900px) {
      .grid {
        grid-template-columns: 1fr 1fr;
      }
    }
    .picker-frame {
      position: relative;
      width: 100%;
      aspect-ratio: ${PANEL_W} / ${PANEL_H};
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      overflow: hidden;
      background: var(--id-surface2, #f5e8d8);
    }
    .picker-frame iframe {
      position: absolute;
      top: 0;
      left: 0;
      width: ${PANEL_W}px;
      height: ${PANEL_H}px;
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
      transition: background 100ms ease, border-color 100ms ease;
    }
    .cell-hit:hover {
      background: rgba(0, 0, 0, 0.06);
      border-color: rgba(0, 0, 0, 0.2);
    }
    .cell-hit[data-selected="true"] {
      border-color: var(--id-accent, #d97757);
      background: rgba(217, 119, 87, 0.12);
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
    input[type="text"], select {
      width: 100%;
      padding: 10px;
      box-sizing: border-box;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      background: var(--id-bg, #ffffff);
      min-height: 44px;
    }
    label.checkbox {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 44px;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .empty {
      padding: 16px;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
    }
    .preview-grid {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
    }
    @media (min-width: 700px) {
      .preview-grid {
        grid-template-columns: 1fr 1fr;
      }
    }
    .preview-tile {
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      overflow: hidden;
      background: var(--id-bg, #ffffff);
    }
    .preview-tile-label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 8px 12px;
      color: var(--id-fg-soft, #5a4f44);
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .preview-tile-frame {
      position: relative;
      width: 100%;
      aspect-ratio: ${PANEL_W} / ${PANEL_H};
      background: var(--id-surface2, #f5e8d8);
      overflow: hidden;
    }
    .preview-tile-frame iframe {
      position: absolute;
      top: 0;
      left: 0;
      width: ${PANEL_W}px;
      height: ${PANEL_H}px;
      border: 0;
      transform-origin: top left;
    }
    .preview-tile-frame img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
    }
    .preview-tile-empty {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 100%;
      color: var(--id-fg-soft, #5a4f44);
      font-size: 13px;
      text-align: center;
      padding: 16px;
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
    .actions { gap: 8px; flex-wrap: wrap; }
    @media (max-width: 700px) {
      :host { padding: 16px 12px; }
      .actions id-button { flex: 1; min-width: 110px; }
    }
  `;

  constructor() {
    super();
    this.pageId = null;
    this.page = null;
    this.widgets = [];
    this.themes = [];
    this.fonts = [];
    this.saving = false;
    this.saved = false;
    this.error = null;
    this.selectedCell = 0;
    this.layoutKey = "1x1";
    this.lastSavedAt = 0;
    this.dither = "floyd-steinberg";
    this.previewLoading = false;
    this.pushing = false;
    this.pushResult = null;
    this.showHelp = false;
    this.showOnboarding =
      typeof localStorage !== "undefined" &&
      localStorage.getItem("inky_onboarded_v1") !== "yes";
    this._onKeydown = this._onKeydown.bind(this);
  }

  async connectedCallback() {
    super.connectedCallback();
    window.addEventListener("keydown", this._onKeydown);
    try {
      const [widgetsRes, themesRes, fontsRes] = await Promise.all([
        fetch("/api/widgets"),
        fetch("/api/themes"),
        fetch("/api/fonts"),
      ]);
      this.widgets = await widgetsRes.json();
      this.themes = await themesRes.json();
      this.fonts = await fontsRes.json();
      if (this.pageId) {
        const pageRes = await fetch(`/api/pages/${encodeURIComponent(this.pageId)}`);
        if (pageRes.ok) {
          this.page = await pageRes.json();
          this.layoutKey =
            detectLayout(this.page.cells, this.page.panel) || "custom";
          return;
        }
      }
      this.page = this._newPage(this.pageId || "untitled");
    } catch (err) {
      this.error = err.message;
    }
  }

  _newPage(id) {
    return {
      id,
      name: id === "untitled" ? "Untitled" : id,
      panel: { w: PANEL_W, h: PANEL_H },
      theme: "default",
      font: "default",
      cells: pixelize("1x1", { w: PANEL_W, h: PANEL_H }),
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
    this._scheduleAutoSave();
  }

  _setCellPlugin(index, pluginId) {
    const newCells = this.page.cells.slice();
    newCells[index] = { ...newCells[index], plugin: pluginId, options: {} };
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setCellOption(index, optName, value) {
    const newCells = this.page.cells.slice();
    newCells[index] = {
      ...newCells[index],
      options: { ...newCells[index].options, [optName]: value },
    };
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setName(name) {
    this.page = { ...this.page, name };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setPageTheme(themeId) {
    this.page = { ...this.page, theme: themeId };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setPageFont(fontId) {
    this.page = { ...this.page, font: fontId };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setPageGap(value) {
    this.page = { ...this.page, gap: Number(value) || 0 };
    this.saved = false;
    this._scheduleAutoSave();
  }

  _setPageCornerRadius(value) {
    this.page = { ...this.page, corner_radius: Number(value) || 0 };
    this.saved = false;
    this._scheduleAutoSave();
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
    this._scheduleAutoSave();
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

  // Debounced auto-save: every edit triggers a save 250ms after the last
  // change, then the iframe URL's cache-bust forces a reload.
  _scheduleAutoSave() {
    if (this._saveTimer) clearTimeout(this._saveTimer);
    this._saveTimer = setTimeout(() => {
      if (this.page) this._save();
    }, 250);
  }

  async _push() {
    this.pushing = true;
    this.pushResult = null;
    try {
      const res = await fetch(
        `/api/pages/${encodeURIComponent(this.page.id)}/push`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dither: this.dither }),
        }
      );
      const body = await res.json();
      this.pushResult = { ok: res.ok, ...body };
    } catch (err) {
      this.pushResult = { ok: false, error: err.message };
    } finally {
      this.pushing = false;
    }
  }

  _scaleIframes() {
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    if (!wraps) return;
    for (const wrap of wraps) {
      const iframe = wrap.querySelector("iframe");
      if (!iframe) continue;
      const scale = wrap.clientWidth / PANEL_W;
      iframe.style.transform = `scale(${scale})`;
    }
  }

  firstUpdated() {
    this._resizeObserver = new ResizeObserver(() => this._scaleIframes());
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    wraps?.forEach((w) => this._resizeObserver.observe(w));
    this._scaleIframes();
  }

  updated() {
    this._scaleIframes();
    // Watch any newly-added iframe-wraps (e.g. quantized preview tile appearing).
    const wraps = this.shadowRoot?.querySelectorAll(".iframe-wrap");
    wraps?.forEach((w) => this._resizeObserver?.observe(w));
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this._resizeObserver?.disconnect();
    window.removeEventListener("keydown", this._onKeydown);
  }

  _onKeydown(event) {
    // Don't intercept when the user is typing in a text input.
    const tag = (event.target?.tagName || "").toLowerCase();
    const inEditable = ["input", "textarea", "select"].includes(tag);

    const meta = event.metaKey || event.ctrlKey;
    if (meta && (event.key === "s" || event.key === "S")) {
      event.preventDefault();
      this._save();
      return;
    }
    if (meta && event.key === "Enter") {
      event.preventDefault();
      this._push();
      return;
    }
    if (event.key === "Escape" && (this.showHelp || this.showOnboarding)) {
      event.preventDefault();
      this._dismissOverlays();
      return;
    }
    if (event.key === "?" && !inEditable) {
      event.preventDefault();
      this.showHelp = !this.showHelp;
      return;
    }
    if (!inEditable && /^[1-9]$/.test(event.key)) {
      const idx = Number(event.key) - 1;
      if (this.page && idx < this.page.cells.length) {
        this.selectedCell = idx;
      }
    }
  }

  _dismissOverlays() {
    this.showHelp = false;
    this.showOnboarding = false;
    try {
      localStorage.setItem("inky_onboarded_v1", "yes");
    } catch {
      /* ignore */
    }
  }

  _renderQuantizedPreview() {
    if (!this.page) return null;
    const id = encodeURIComponent(this.page.id);
    const cacheBust = this.lastSavedAt || "initial";
    const previewUrl = `/api/pages/${id}/preview.png?dither=${this.dither}&t=${cacheBust}`;
    return html`
      <id-card heading="Panel paint" subheading="The same render projected to the Spectra 6 gamut — what the panel will actually paint.">
        <id-form-row label="Dither">
          <select
            .value=${this.dither}
            @change=${(e) => {
              this.dither = e.target.value;
              this.lastSavedAt = Date.now();
            }}
          >
            <option value="floyd-steinberg">Floyd–Steinberg (default)</option>
            <option value="none">None (nearest colour)</option>
          </select>
        </id-form-row>
        <div class="preview-tile">
          <div class="preview-tile-label">
            <span>Quantized</span>
            ${this.previewLoading ? html`<span class="preview-spinner"></span>` : null}
          </div>
          <div class="preview-tile-frame">
            <img
              src=${previewUrl}
              alt="Quantized preview"
              loading="lazy"
              @load=${() => (this.previewLoading = false)}
              @loadstart=${() => (this.previewLoading = true)}
            />
          </div>
        </div>
      </id-card>
    `;
  }

  _renderPicker() {
    const cells = this.page.cells;
    const id = encodeURIComponent(this.page.id);
    const cacheBust = this.lastSavedAt || "initial";
    const composeUrl = `/compose/${id}?for_push=1&t=${cacheBust}`;
    // Match the composer's gap inset so the click targets sit on top of the
    // visually-shrunken cells in the iframe.
    const halfGap = (this.page.gap || 0) / 2;
    return html`<div class="picker-frame iframe-wrap">
      <iframe src=${composeUrl} title="Live preview"></iframe>
      <div class="cell-overlay">
        ${cells.map((c, i) => {
          const x = c.x + halfGap;
          const y = c.y + halfGap;
          const w = Math.max(1, c.w - halfGap * 2);
          const h = Math.max(1, c.h - halfGap * 2);
          return html`
            <div
              class="cell-hit"
              data-selected=${i === this.selectedCell ? "true" : "false"}
              style="left: ${(x / PANEL_W) * 100}%;
                     top: ${(y / PANEL_H) * 100}%;
                     width: ${(w / PANEL_W) * 100}%;
                     height: ${(h / PANEL_H) * 100}%;"
              @click=${() => (this.selectedCell = i)}
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
      <id-card heading="Cell ${this.selectedCell + 1}">
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
            ${this.themes.map(
              (t) => html`
                <option value=${t.id} ?selected=${t.id === cell.theme}>
                  ${t.name}
                </option>
              `
            )}
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

  _renderOption(cell, opt) {
    const value = cell.options[opt.name] ?? opt.default ?? "";
    if (opt.type === "select") {
      return html`<id-form-row label=${opt.label}>
        <select
          @change=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.value)}
        >
          ${(opt.choices || []).map(
            (c) => html`<option value=${c.value} ?selected=${c.value === value}>${c.label}</option>`
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
    return html`<id-form-row label=${opt.label}>
      <input
        type="text"
        .value=${String(value)}
        @input=${(e) => this._setCellOption(this.selectedCell, opt.name, e.target.value)}
      />
    </id-form-row>`;
  }

  render() {
    if (!this.page) {
      return html`<p>${this.error ? `Error: ${this.error}` : "Loading…"}</p>`;
    }
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="header">
        <h1>Editor — ${this.page.id}</h1>
        <div>
          ${this.error
            ? html`<span class="status error">${this.error}</span>`
            : this.saving
              ? html`<span class="status">Saving…</span>`
              : this.saved
                ? html`<span class="status">Saved · auto-saves on edit</span>`
                : html`<span class="status">Auto-saves on edit</span>`}
        </div>
      </div>

      <id-card heading="Page">
        <id-form-row label="Name">
          <input
            type="text"
            .value=${this.page.name}
            @input=${(e) => this._setName(e.target.value)}
          />
        </id-form-row>
        <id-form-row label="Layout">
          <select
            @change=${(e) => this._onLayoutChange(e.target.value)}
          >
            ${Object.entries(LAYOUTS).map(
              ([key, l]) => html`
                <option value=${key} ?selected=${this.layoutKey === key}>
                  ${l.label}
                </option>
              `
            )}
            ${this.layoutKey === "custom"
              ? html`<option value="custom" selected>Custom (manual)</option>`
              : null}
          </select>
        </id-form-row>
        <id-form-row label="Theme" hint="Page-wide; cells can override.">
          <select
            @change=${(e) => this._setPageTheme(e.target.value)}
          >
            ${this.themes.length === 0
              ? html`<option>(no themes loaded)</option>`
              : null}
            ${this.themes.map(
              (t) => html`
                <option value=${t.id} ?selected=${t.id === (this.page.theme || "default")}>
                  ${t.name}${t.mode ? ` — ${t.mode}` : ""}
                </option>
              `
            )}
          </select>
        </id-form-row>
        <id-form-row label="Font">
          <select
            @change=${(e) => this._setPageFont(e.target.value)}
          >
            ${this.fonts.length === 0
              ? html`<option>(no fonts loaded)</option>`
              : null}
            ${this.fonts.map(
              (f) => html`
                <option value=${f.id} ?selected=${f.id === (this.page.font || "default")}>
                  ${f.name}${f.category ? ` — ${f.category}` : ""}
                </option>
              `
            )}
          </select>
        </id-form-row>
        <id-form-row label="Gap" hint="Pixels between widgets and around the panel edge.">
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

      <div style="height: 16px"></div>

      <div class="grid">
        <div>
          <h2 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--id-fg-soft); margin: 0 0 8px;">
            Live preview · ${PANEL_W}×${PANEL_H} · click a region to edit it
          </h2>
          ${this._renderPicker()}
        </div>
        <div>${this._renderCellOptions()}</div>
      </div>

      <div style="height: 16px"></div>

      <div class="actions">
        <id-button
          variant="primary"
          ?disabled=${this.pushing || this.saving}
          @click=${() => this._push()}
          title="Push (⌘↵)"
        >
          <i class="ph ph-paper-plane-tilt"></i>
          ${this.pushing ? "Pushing…" : "Push to panel"}
        </id-button>
        <id-button @click=${() => (window.location.href = "/send")}>
          <i class="ph ph-paper-plane"></i> Send
        </id-button>
        <id-button @click=${() => (window.location.href = "/schedules")}>
          <i class="ph ph-clock-clockwise"></i> Schedules
        </id-button>
        <id-button @click=${() => (window.location.href = "/themes")}>
          <i class="ph ph-palette"></i> Themes
        </id-button>
        <id-button @click=${() => (window.location.href = "/settings")}>
          <i class="ph ph-gear"></i> Settings
        </id-button>
        <id-button @click=${() => (this.showHelp = true)} title="Shortcuts (?)">
          <i class="ph ph-keyboard"></i>
        </id-button>
        <id-button
          @click=${() =>
            window.open(`/compose/${encodeURIComponent(this.page.id)}`, "_blank")}
        >
          <i class="ph ph-arrow-square-out"></i> Compose
        </id-button>
      </div>
      ${this.pushResult
        ? html`<div class="status ${this.pushResult.ok ? "" : "error"}" style="margin-top: 8px;">
            ${this.pushResult.ok
              ? `Sent (${this.pushResult.digest}, ${this.pushResult.duration_s}s)`
              : `Push failed: ${this.pushResult.error || this.pushResult.status}`}
          </div>`
        : null}

      <div style="height: 16px"></div>

      ${this._renderQuantizedPreview()}
      ${this.showOnboarding ? this._renderOnboarding() : null}
      ${this.showHelp ? this._renderHelp() : null}
    `;
  }

  _renderOnboarding() {
    return html`
      <div class="overlay" @click=${() => this._dismissOverlays()}>
        <div class="overlay-card" @click=${(e) => e.stopPropagation()}>
          <h3>Welcome to Inky Dash</h3>
          <p style="color: var(--id-fg-soft); margin: 0 0 12px;">
            A quick tour of what's here:
          </p>
          <ol style="margin: 0 0 12px; padding-left: 20px; line-height: 1.7;">
            <li>Pick a <strong>layout</strong> (top of the page) to split the panel into cells.</li>
            <li>Click any cell in the live preview to <strong>edit it</strong> on the right.</li>
            <li>Set <strong>theme</strong>, <strong>font</strong>, <strong>gap</strong>, <strong>radius</strong> per page.</li>
            <li><strong>Push to panel</strong> renders, dithers, publishes via MQTT.</li>
          </ol>
          <p style="color: var(--id-fg-soft); font-size: 13px; margin: 0 0 8px;">
            Press <kbd>?</kbd> any time to see all shortcuts.
          </p>
          <div class="overlay-actions">
            <id-button variant="primary" @click=${() => this._dismissOverlays()}>
              <i class="ph ph-check"></i> Got it
            </id-button>
          </div>
        </div>
      </div>
    `;
  }

  _renderHelp() {
    const platform =
      typeof navigator !== "undefined" && /mac/i.test(navigator.platform)
        ? "⌘"
        : "Ctrl";
    return html`
      <div class="overlay" @click=${() => (this.showHelp = false)}>
        <div class="overlay-card" @click=${(e) => e.stopPropagation()}>
          <h3>Keyboard shortcuts</h3>
          <div class="overlay-shortcuts">
            <span><kbd>${platform}</kbd>+<kbd>S</kbd></span><span>Save now</span>
            <span><kbd>${platform}</kbd>+<kbd>↵</kbd></span><span>Push to panel</span>
            <span><kbd>1</kbd>–<kbd>9</kbd></span><span>Select cell N</span>
            <span><kbd>?</kbd></span><span>Toggle this help</span>
            <span><kbd>Esc</kbd></span><span>Close overlays</span>
          </div>
          <p style="color: var(--id-fg-soft); font-size: 12px; margin: 12px 0 0;">
            Edits auto-save 250 ms after you stop changing things.
          </p>
          <div class="overlay-actions">
            <id-button @click=${() => (this.showHelp = false)}>
              <i class="ph ph-x"></i> Close
            </id-button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define("id-editor", IdEditor);

const params = new URLSearchParams(location.search);
const pageIdFromBody = document.body.dataset.pageId || params.get("id") || null;
const editor = document.createElement("id-editor");
if (pageIdFromBody) editor.setAttribute("page-id", pageIdFromBody);
document.body.append(editor);
