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
    saving: { state: true },
    saved: { state: true },
    error: { state: true },
    selectedCell: { state: true },
    layoutKey: { state: true },
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
    .canvas {
      position: relative;
      background: var(--id-surface2, #f5e8d8);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      aspect-ratio: ${PANEL_W} / ${PANEL_H};
      overflow: hidden;
    }
    .canvas-cell {
      position: absolute;
      border: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface, #ffffff);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      cursor: pointer;
      box-sizing: border-box;
    }
    .canvas-cell.selected {
      border: 2px solid var(--id-accent, #d97757);
      z-index: 1;
    }
    .layout-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
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
  `;

  constructor() {
    super();
    this.pageId = null;
    this.page = null;
    this.widgets = [];
    this.saving = false;
    this.saved = false;
    this.error = null;
    this.selectedCell = 0;
    this.layoutKey = "1x1";
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const widgetsRes = await fetch("/api/widgets");
      this.widgets = await widgetsRes.json();
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
  }

  _setCellPlugin(index, pluginId) {
    const newCells = this.page.cells.slice();
    newCells[index] = { ...newCells[index], plugin: pluginId, options: {} };
    this.page = { ...this.page, cells: newCells };
    this.saved = false;
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
    } catch (err) {
      this.error = err.message;
    } finally {
      this.saving = false;
    }
  }

  _renderCanvas() {
    const cells = this.page.cells;
    return html`<div class="canvas">
      ${cells.map(
        (c, i) => html`
          <div
            class="canvas-cell ${i === this.selectedCell ? "selected" : ""}"
            style="left: ${(c.x / PANEL_W) * 100}%;
                   top: ${(c.y / PANEL_H) * 100}%;
                   width: ${(c.w / PANEL_W) * 100}%;
                   height: ${(c.h / PANEL_H) * 100}%;"
            @click=${() => (this.selectedCell = i)}
          >
            ${c.plugin}
          </div>
        `
      )}
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
        ${widget && (widget.cell_options || []).length
          ? widget.cell_options.map((opt) => this._renderOption(cell, opt))
          : html`<p class="empty">No options.</p>`}
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
      <div class="header">
        <h1>Editor — ${this.page.id}</h1>
        <div>
          ${this.error
            ? html`<span class="status error">${this.error}</span>`
            : this.saved
              ? html`<span class="status">Saved.</span>`
              : html`<span class="status">Unsaved changes</span>`}
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
        <id-form-row label="Layout" hint="Pick a preset; M2 ships four.">
          <div class="layout-row">
            ${Object.entries(LAYOUTS).map(
              ([key, l]) => html`
                <id-button
                  variant=${this.layoutKey === key ? "primary" : "default"}
                  @click=${() => this._onLayoutChange(key)}
                >
                  ${l.label}
                </id-button>
              `
            )}
          </div>
        </id-form-row>
      </id-card>

      <div style="height: 16px"></div>

      <div class="grid">
        <div>
          <h2 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--id-fg-soft); margin: 0 0 8px;">
            Layout (${PANEL_W}×${PANEL_H})
          </h2>
          ${this._renderCanvas()}
        </div>
        <div>${this._renderCellOptions()}</div>
      </div>

      <div style="height: 16px"></div>

      <div class="actions">
        <id-button
          variant="primary"
          ?disabled=${this.saving}
          @click=${() => this._save()}
        >
          ${this.saving ? "Saving…" : "Save"}
        </id-button>
        <id-button
          @click=${() =>
            window.open(`/compose/${encodeURIComponent(this.page.id)}`, "_blank")}
        >
          Open compose ↗
        </id-button>
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
