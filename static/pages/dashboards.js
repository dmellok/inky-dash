import { LitElement, html, css } from "lit";
import "../components/index.js";

class DashboardsPage extends LitElement {
  static properties = {
    pages: { state: true },
    creating: { state: true },
    newName: { state: true },
    error: { state: true },
    pushing: { state: true },
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

    .create-card {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px;
      margin-bottom: 24px;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      flex-wrap: wrap;
    }
    .create-card input {
      flex: 1;
      min-width: 200px;
      min-height: var(--id-control-h, 40px);
      padding: 8px 12px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
    }

    .section-head {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      margin: 0 0 12px;
    }

    .list {
      display: grid;
      gap: 8px;
    }
    .row {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 12px 16px;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .row:hover {
      border-color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
    }
    .row .icon {
      color: var(--id-accent, #d97757);
      font-size: 22px;
      flex-shrink: 0;
    }
    .row .name {
      flex: 1;
      min-width: 0;
    }
    .row .name a {
      color: var(--id-fg, #1a1612);
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
    }
    .row .name a:hover {
      color: var(--id-accent, #d97757);
    }
    .row .meta {
      display: block;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      font-variant-numeric: tabular-nums;
      margin-top: 2px;
    }
    .row .actions {
      display: flex;
      gap: 6px;
      flex-shrink: 0;
    }

    .empty {
      padding: 48px 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      background: var(--id-surface, #ffffff);
      border: 1px dashed var(--id-divider, #c8b89b);
      border-radius: 10px;
    }
    .error {
      color: var(--id-danger, #c97c70);
      padding: 8px 0;
    }
    @media (max-width: 600px) {
      .row {
        flex-wrap: wrap;
      }
      .row .actions {
        width: 100%;
        justify-content: flex-end;
      }
    }
  `;

  constructor() {
    super();
    this.pages = null;
    this.creating = false;
    this.newName = "";
    this.error = null;
    this.pushing = {};
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._load();
  }

  async _load() {
    try {
      const res = await fetch("/api/pages");
      const list = await res.json();
      list.sort((a, b) => a.name.localeCompare(b.name));
      this.pages = list;
    } catch (err) {
      this.error = err.message;
      this.pages = [];
    }
  }

  async _create() {
    const name = this.newName.trim();
    if (!name) {
      this.error = "Give your dashboard a name first.";
      return;
    }
    this.creating = true;
    this.error = null;
    try {
      const res = await fetch("/api/pages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      const body = await res.json();
      if (!res.ok) {
        const detail = body.details
          ? body.details.map((d) => `${d.loc}: ${d.msg}`).join("; ")
          : body.error || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      this.newName = "";
      // Hand off to the editor.
      window.location.href = `/editor/${encodeURIComponent(body.id)}`;
    } catch (err) {
      this.error = err.message;
      this.creating = false;
    }
  }

  async _delete(page) {
    if (!confirm(`Delete dashboard "${page.name}"?`)) return;
    this.error = null;
    try {
      const res = await fetch(`/api/pages/${encodeURIComponent(page.id)}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  async _push(page) {
    this.pushing = { ...this.pushing, [page.id]: true };
    this.error = null;
    try {
      const res = await fetch(`/api/pages/${encodeURIComponent(page.id)}/push`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      if (body.status !== "sent") {
        this.error = `${body.status}${body.error ? `: ${body.error}` : ""}`;
      }
    } catch (err) {
      this.error = err.message;
    } finally {
      this.pushing = { ...this.pushing, [page.id]: false };
    }
  }

  _renderRow(page) {
    const cellCount = (page.cells || []).length;
    const w = page.panel?.w ?? 0;
    const h = page.panel?.h ?? 0;
    return html`
      <div class="row">
        <i class="ph ${page.icon || "ph-cube"} icon"></i>
        <div class="name">
          <a href=${`/editor/${encodeURIComponent(page.id)}`}>${page.name}</a>
          <span class="meta">
            ${page.id} · ${w}×${h} · ${cellCount} cell${cellCount === 1 ? "" : "s"}
            ${page.theme && page.theme !== "default" ? html` · theme: ${page.theme}` : null}
          </span>
        </div>
        <div class="actions">
          <id-button @click=${() => (window.location.href = `/editor/${encodeURIComponent(page.id)}`)}>
            <i class="ph ph-pencil-simple"></i> Edit
          </id-button>
          <id-button
            ?disabled=${this.pushing[page.id]}
            @click=${() => this._push(page)}
          >
            <i class="ph ph-paper-plane"></i>
            ${this.pushing[page.id] ? "Pushing…" : "Push"}
          </id-button>
          <id-button variant="danger" @click=${() => this._delete(page)}>
            <i class="ph ph-trash"></i>
          </id-button>
        </div>
      </div>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="editor"></id-nav>
      <div class="container">
        <h1><i class="ph ph-cube" style="color: var(--id-accent);"></i> Dashboards</h1>
        <p class="lede">
          Each dashboard is a panel-sized grid of cells you compose, render,
          and push to your Inky panel.
        </p>

        <div class="create-card">
          <i class="ph ph-plus-circle" style="font-size: 20px; color: var(--id-accent);"></i>
          <input
            type="text"
            placeholder="New dashboard name"
            .value=${this.newName}
            ?disabled=${this.creating}
            @input=${(e) => (this.newName = e.target.value)}
            @keydown=${(e) => { if (e.key === "Enter") this._create(); }}
          />
          <id-button
            variant="primary"
            ?disabled=${this.creating || !this.newName.trim()}
            @click=${() => this._create()}
          >
            <i class="ph ph-plus"></i>
            ${this.creating ? "Creating…" : "Create dashboard"}
          </id-button>
        </div>

        ${this.error ? html`<p class="error">${this.error}</p>` : null}

        <h2 class="section-head">
          ${this.pages
            ? `${this.pages.length} dashboard${this.pages.length === 1 ? "" : "s"}`
            : "Loading…"}
        </h2>

        ${this.pages === null
          ? html`<p class="empty">Loading…</p>`
          : this.pages.length === 0
            ? html`<p class="empty">No dashboards yet. Create one above to get started.</p>`
            : html`<div class="list">${this.pages.map((p) => this._renderRow(p))}</div>`}
      </div>
    `;
  }
}

customElements.define("dashboards-page", DashboardsPage);
document.body.append(document.createElement("dashboards-page"));
