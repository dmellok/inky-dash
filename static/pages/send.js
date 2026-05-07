import { LitElement, html, css } from "lit";
import "../components/index.js";

class SendPage extends LitElement {
  static properties = {
    pages: { state: true },
    history: { state: true },
    source: { state: true },
    pageId: { state: true },
    url: { state: true },
    file: { state: true },
    dither: { state: true },
    sending: { state: true },
    result: { state: true },
    error: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      max-width: 760px;
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
    .source-tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
    }
    .source-tabs button {
      min-height: 44px;
      padding: 0 16px;
      border: 0;
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      font: inherit;
      font-weight: 500;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .source-tabs button[aria-selected="true"] {
      color: var(--id-accent, #d97757);
      border-bottom-color: var(--id-accent, #d97757);
    }
    .form {
      display: grid;
      gap: 12px;
    }
    .form-row {
      display: grid;
      grid-template-columns: 180px 1fr;
      gap: 12px;
      align-items: center;
    }
    @media (max-width: 700px) {
      .form-row { grid-template-columns: 1fr; gap: 4px; }
    }
    label.field { font-size: 13px; color: var(--id-fg-soft, #5a4f44); font-weight: 500; }
    input[type="text"], input[type="url"], input[type="file"], select {
      width: 100%;
      padding: 8px 10px;
      box-sizing: border-box;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      min-height: 38px;
      background: var(--id-bg, #ffffff);
    }
    .actions {
      display: flex;
      gap: 8px;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    .result {
      margin-top: 16px;
      padding: 12px 14px;
      border-radius: 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface2, #f5e8d8);
      font-size: 14px;
    }
    .result.error {
      border-color: var(--id-danger, #c97c70);
      background: rgba(201, 124, 112, 0.1);
      color: var(--id-danger, #c97c70);
    }
    .result.success {
      border-color: var(--id-accent, #d97757);
    }
    .result img {
      display: block;
      max-width: 240px;
      margin-top: 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 4px;
    }
    a.nav {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.3em;
    }
    a.nav:hover { color: var(--id-accent, #d97757); }
  `;

  constructor() {
    super();
    this.pages = [];
    this.source = "page";
    this.pageId = "";
    this.url = "";
    this.file = null;
    this.dither = "floyd-steinberg";
    this.sending = false;
    this.result = null;
    this.error = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const res = await fetch("/api/pages");
      this.pages = await res.json();
      if (this.pages.length && !this.pageId) this.pageId = this.pages[0].id;
    } catch (err) {
      this.error = err.message;
    }
  }

  async _send() {
    this.sending = true;
    this.result = null;
    this.error = null;
    try {
      let res;
      if (this.source === "page") {
        res = await fetch("/api/send/page", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page_id: this.pageId, dither: this.dither }),
        });
      } else if (this.source === "url") {
        res = await fetch("/api/send/url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: this.url, dither: this.dither }),
        });
      } else if (this.source === "webpage") {
        res = await fetch("/api/send/webpage", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: this.url, dither: this.dither }),
        });
      } else {
        // file
        if (!this.file) throw new Error("No file chosen");
        const form = new FormData();
        form.append("file", this.file);
        form.append("dither", this.dither);
        res = await fetch("/api/send/file", { method: "POST", body: form });
      }
      const body = await res.json();
      if (!res.ok && res.status !== 200) {
        this.error = body.error || `HTTP ${res.status}`;
      }
      this.result = body;
    } catch (err) {
      this.error = err.message;
    } finally {
      this.sending = false;
    }
  }

  _renderSourceForm() {
    if (this.source === "page") {
      return html`
        <div class="form-row">
          <label class="field">Saved page</label>
          <select @change=${(e) => (this.pageId = e.target.value)}>
            ${this.pages.map(
              (p) => html`<option value=${p.id} ?selected=${p.id === this.pageId}>${p.name} (${p.id})</option>`
            )}
          </select>
        </div>
      `;
    }
    if (this.source === "url") {
      return html`
        <div class="form-row">
          <label class="field">Image URL</label>
          <input
            type="url"
            placeholder="https://example.com/photo.jpg"
            .value=${this.url}
            @input=${(e) => (this.url = e.target.value)}
          />
        </div>
      `;
    }
    if (this.source === "webpage") {
      return html`
        <div class="form-row">
          <label class="field">Webpage URL</label>
          <input
            type="url"
            placeholder="https://example.com/dashboard"
            .value=${this.url}
            @input=${(e) => (this.url = e.target.value)}
          />
        </div>
      `;
    }
    return html`
      <div class="form-row">
        <label class="field">Image file</label>
        <input
          type="file"
          accept="image/*"
          @change=${(e) => (this.file = e.target.files[0])}
        />
      </div>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <a class="nav" href="/editor"><i class="ph ph-arrow-left"></i> back to editor</a>
      <h1>Send to panel</h1>
      <p class="lede">Push any image, dashboard, or webpage to the panel right now.</p>

      <div class="source-tabs" role="tablist">
        ${[
          { id: "page", label: "Saved", icon: "ph-cube" },
          { id: "url", label: "Image URL", icon: "ph-link" },
          { id: "webpage", label: "Webpage", icon: "ph-globe" },
          { id: "file", label: "File", icon: "ph-file-arrow-up" },
        ].map(
          (tab) => html`
            <button
              role="tab"
              aria-selected=${this.source === tab.id ? "true" : "false"}
              @click=${() => (this.source = tab.id)}
            >
              <i class="ph ${tab.icon}"></i> ${tab.label}
            </button>
          `
        )}
      </div>

      <div class="form">
        ${this._renderSourceForm()}
        <div class="form-row">
          <label class="field">Dither</label>
          <select @change=${(e) => (this.dither = e.target.value)}>
            <option value="floyd-steinberg" ?selected=${this.dither === "floyd-steinberg"}>Floyd–Steinberg</option>
            <option value="none" ?selected=${this.dither === "none"}>None (nearest)</option>
          </select>
        </div>
      </div>

      <div class="actions">
        <id-button variant="primary" ?disabled=${this.sending} @click=${() => this._send()}>
          <i class="ph ph-paper-plane-tilt"></i>
          ${this.sending ? "Sending…" : "Send to panel"}
        </id-button>
      </div>

      ${this.error
        ? html`<div class="result error">${this.error}</div>`
        : this.result
          ? html`<div class="result success">
              <div>
                <strong>${this.result.status}</strong>
                ${this.result.duration_s ? html` · ${this.result.duration_s}s` : null}
              </div>
              ${this.result.url
                ? html`<a href=${this.result.url} target="_blank">${this.result.url}</a>
                       <img src=${this.result.url} alt="quantized result" />`
                : null}
            </div>`
          : null}
    `;
  }
}

customElements.define("send-page", SendPage);
document.body.append(document.createElement("send-page"));
