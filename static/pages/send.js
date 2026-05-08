import { LitElement, html, css } from "lit";
import "../components/index.js";

class SendPage extends LitElement {
  static properties = {
    pages: { state: true },
    source: { state: true },
    pageId: { state: true },
    url: { state: true },
    file: { state: true },
    fileObjectUrl: { state: true },
    dither: { state: true },
    sending: { state: true },
    result: { state: true },
    error: { state: true },
    previewUrl: { state: true },
    previewLoading: { state: true },
    previewError: { state: true },
    dragOver: { state: true },
    appPanel: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
    }
    .container {
      max-width: 980px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    p.lede { margin: 0 0 16px; color: var(--id-fg-soft, #5a4f44); }

    .source-tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      flex-wrap: wrap;
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

    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
      gap: 16px;
    }
    @media (max-width: 760px) {
      .layout { grid-template-columns: 1fr; }
    }

    .form {
      display: grid;
      gap: 12px;
      align-content: start;
      /* Without min-width:0 the implicit grid track is min-content sized,
         which lets a long filename in the dropzone push the column wider
         than its 1fr share of the layout (overlapping the preview card). */
      min-width: 0;
    }
    .form-row {
      display: grid;
      grid-template-columns: 140px 1fr;
      gap: 12px;
      align-items: center;
    }
    @media (max-width: 760px) {
      .form-row { grid-template-columns: 1fr; gap: 4px; }
    }
    label.field {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      font-weight: 500;
    }
    input[type="text"], input[type="url"], select {
      width: 100%;
      padding: 8px 10px;
      box-sizing: border-box;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      min-height: 38px;
      background: var(--id-bg, #ffffff);
    }

    /* File drop zone */
    .dropzone {
      grid-column: 1 / -1;
      position: relative;
      border: 2px dashed var(--id-divider, #c8b89b);
      border-radius: 12px;
      padding: 32px 24px;
      text-align: center;
      background: var(--id-surface, #ffffff);
      cursor: pointer;
      transition: border-color 120ms ease, background 120ms ease, transform 120ms ease;
      /* Defensive: prevent a long filename inside the file-card from blowing
         out the column width and overlapping the preview card to the right. */
      min-width: 0;
      overflow: hidden;
    }
    .dropzone:hover {
      border-color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
    }
    .dropzone.drag-over {
      border-color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
      transform: scale(1.005);
    }
    .dropzone.has-file {
      padding: 16px;
      text-align: left;
      cursor: default;
    }
    .dropzone .ph {
      font-size: 48px;
      color: var(--id-accent, #d97757);
    }
    .dropzone .label {
      font-size: 16px;
      font-weight: 600;
      margin-top: 8px;
    }
    .dropzone .hint {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      margin-top: 4px;
    }
    .dropzone input[type="file"] {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
    }
    .dropzone.has-file input[type="file"] {
      pointer-events: none;
    }
    .file-card {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .file-thumb {
      width: 80px;
      height: 80px;
      flex-shrink: 0;
      border-radius: 6px;
      background: var(--id-surface2, #f5e8d8);
      overflow: hidden;
      display: grid;
      place-items: center;
      border: 1px solid var(--id-divider, #c8b89b);
    }
    .file-thumb img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
    }
    .file-thumb .ph {
      font-size: 32px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .file-meta {
      flex: 1;
      min-width: 0;
    }
    .file-meta .name {
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .file-meta .sub {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .file-clear {
      border: 0;
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      cursor: pointer;
      padding: 6px;
      border-radius: 4px;
      font-size: 18px;
    }
    .file-clear:hover {
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-fg, #1a1612);
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

    /* Preview pane */
    .preview-card {
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      overflow: hidden;
      align-self: start;
      position: sticky;
      top: 70px;
    }
    .preview-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      gap: 8px;
    }
    .preview-head h3 {
      margin: 0;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .preview-head button {
      border: 0;
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      font: inherit;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .preview-head button:hover { color: var(--id-accent, #d97757); }
    .preview-frame {
      /* Aspect comes from app panel settings + orientation, fed via inline
         CSS variables (defaults match the 13.3" Spectra 6 landscape native). */
      aspect-ratio: var(--panel-w, 1600) / var(--panel-h, 1200);
      background: var(--id-surface2, #f5e8d8);
      display: grid;
      place-items: center;
      position: relative;
    }
    .preview-frame img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
    }
    .preview-empty,
    .preview-error,
    .preview-spinner {
      padding: 16px;
      color: var(--id-fg-soft, #5a4f44);
      font-size: 13px;
      text-align: center;
      max-width: 80%;
    }
    .preview-error { color: var(--id-danger, #c97c70); }
    .preview-spinner-icon {
      width: 24px;
      height: 24px;
      border: 3px solid var(--id-divider, #c8b89b);
      border-top-color: var(--id-accent, #d97757);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 8px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
  `;

  constructor() {
    super();
    this.pages = [];
    this.source = "file";
    this.pageId = "";
    this.url = "";
    this.file = null;
    this.fileObjectUrl = null;
    this.dither = "floyd-steinberg";
    this.sending = false;
    this.result = null;
    this.error = null;
    this.previewUrl = null;
    this.previewLoading = false;
    this.previewError = null;
    this.dragOver = false;
    this.appPanel = null; // { width, height, orientation }
  }

  // Panel display dims (post-rotation). Mirrors PanelSettings.render_dimensions
  // server-side: landscape uses native, portrait swaps.
  _panelDisplayDims() {
    const p = this.appPanel;
    if (!p) return { w: 1600, h: 1200 };
    return p.orientation === "landscape"
      ? { w: p.width, h: p.height }
      : { w: p.height, h: p.width };
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const [pagesRes, appRes, panelsRes] = await Promise.all([
        fetch("/api/pages"),
        fetch("/api/app/settings"),
        fetch("/api/app/panels"),
      ]);
      this.pages = await pagesRes.json();
      if (this.pages.length && !this.pageId) this.pageId = this.pages[0].id;
      try {
        const app = await appRes.json();
        const panels = await panelsRes.json();
        const spec = panels.find((p) => p.id === app?.panel?.model);
        if (spec) {
          this.appPanel = {
            orientation: app.panel.orientation,
            width: spec.width,
            height: spec.height,
          };
        }
      } catch {
        /* fall back to default 1600×1200 ratio */
      }
    } catch (err) {
      this.error = err.message;
    }
    // ?image=<url>&name=<filename> — gallery thumbnails hand off here.
    // We fetch the URL, build a File, drop it into the file source.
    const params = new URLSearchParams(window.location.search);
    const imgUrl = params.get("image");
    if (imgUrl) {
      this.source = "file";
      const name = params.get("name") || imgUrl.split("/").pop() || "image";
      try {
        const res = await fetch(imgUrl);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        const file = new File([blob], name, {
          type: blob.type || "image/jpeg",
        });
        this._setFile(file);
      } catch (err) {
        this.error = `Couldn't load ${name}: ${err.message}`;
      }
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this.fileObjectUrl) URL.revokeObjectURL(this.fileObjectUrl);
    if (this.previewUrl) URL.revokeObjectURL(this.previewUrl);
  }

  // ----- file handling ------------------------------------------------

  _setFile(file) {
    if (this.fileObjectUrl) URL.revokeObjectURL(this.fileObjectUrl);
    if (file) {
      this.file = file;
      this.fileObjectUrl = URL.createObjectURL(file);
    } else {
      this.file = null;
      this.fileObjectUrl = null;
    }
    this._clearPreview();
    if (file) this._loadPreview();
  }

  _onFileInput(event) {
    const file = event.target.files?.[0];
    if (file) this._setFile(file);
  }

  _onDragOver(event) {
    event.preventDefault();
    this.dragOver = true;
  }

  _onDragLeave() {
    this.dragOver = false;
  }

  _onDrop(event) {
    event.preventDefault();
    this.dragOver = false;
    const file = event.dataTransfer?.files?.[0];
    if (file) this._setFile(file);
  }

  _formatBytes(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  // ----- preview ------------------------------------------------------

  _switchSource(id) {
    this.source = id;
    this._clearPreview();
    // Auto-render whenever the new source already has enough info to preview.
    if (id === "page" && this.pageId) this._loadPreview();
    else if (id === "file" && this.file) this._loadPreview();
  }

  _clearPreview() {
    if (this.previewUrl) URL.revokeObjectURL(this.previewUrl);
    this.previewUrl = null;
    this.previewError = null;
  }

  async _loadPreview() {
    this._clearPreview();
    this.previewLoading = true;
    try {
      let res;
      if (this.source === "page") {
        if (!this.pageId) throw new Error("Pick a dashboard");
        res = await fetch("/api/send/preview/page", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ page_id: this.pageId, dither: this.dither }),
        });
      } else if (this.source === "url") {
        if (!this.url) throw new Error("Enter an image URL");
        res = await fetch("/api/send/preview/url", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: this.url, dither: this.dither }),
        });
      } else if (this.source === "webpage") {
        if (!this.url) throw new Error("Enter a webpage URL");
        res = await fetch("/api/send/preview/webpage", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: this.url, dither: this.dither }),
        });
      } else {
        if (!this.file) throw new Error("Pick a file");
        const form = new FormData();
        form.append("file", this.file);
        form.append("dither", this.dither);
        res = await fetch("/api/send/preview/file", {
          method: "POST",
          body: form,
        });
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      const blob = await res.blob();
      this.previewUrl = URL.createObjectURL(blob);
    } catch (err) {
      this.previewError = err.message;
    } finally {
      this.previewLoading = false;
    }
  }

  // ----- send ---------------------------------------------------------

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

  // ----- render -------------------------------------------------------

  _renderSourceForm() {
    if (this.source === "file") {
      const hasFile = !!this.file;
      return html`
        <div
          class="dropzone ${this.dragOver ? "drag-over" : ""} ${hasFile ? "has-file" : ""}"
          @dragover=${this._onDragOver}
          @dragleave=${this._onDragLeave}
          @drop=${this._onDrop}
        >
          ${hasFile
            ? html`
                <div class="file-card">
                  <div class="file-thumb">
                    ${this.fileObjectUrl
                      ? html`<img src=${this.fileObjectUrl} alt="" />`
                      : html`<i class="ph ph-image"></i>`}
                  </div>
                  <div class="file-meta">
                    <div class="name">${this.file.name}</div>
                    <div class="sub">
                      ${this._formatBytes(this.file.size)} · ${this.file.type || "unknown type"}
                    </div>
                  </div>
                  <button class="file-clear" @click=${() => this._setFile(null)} aria-label="Remove file">
                    <i class="ph ph-x"></i>
                  </button>
                </div>
              `
            : html`
                <i class="ph ph-cloud-arrow-up"></i>
                <div class="label">Drop an image here</div>
                <div class="hint">or click to choose · JPG / PNG / WEBP / GIF</div>
              `}
          <input
            type="file"
            accept="image/*"
            @change=${this._onFileInput}
          />
        </div>
      `;
    }
    if (this.source === "page") {
      return html`
        <div class="form-row">
          <label class="field">Saved dashboard</label>
          <select
            @change=${(e) => {
              this.pageId = e.target.value;
              this._clearPreview();
              if (this.pageId) this._loadPreview();
            }}
          >
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
            @input=${(e) => { this.url = e.target.value; this._clearPreview(); }}
          />
        </div>
      `;
    }
    return html`
      <div class="form-row">
        <label class="field">Webpage URL</label>
        <input
          type="url"
          placeholder="https://example.com/dashboard"
          .value=${this.url}
          @input=${(e) => { this.url = e.target.value; this._clearPreview(); }}
        />
      </div>
    `;
  }

  _renderPreview() {
    const dims = this._panelDisplayDims();
    return html`
      <div class="preview-card">
        <div class="preview-head">
          <h3><i class="ph ph-monitor"></i> Panel preview</h3>
          <button @click=${() => this._loadPreview()} ?disabled=${this.previewLoading}>
            <i class="ph ph-arrows-clockwise"></i>
            ${this.previewLoading ? "Rendering…" : this.previewUrl ? "Refresh" : "Render preview"}
          </button>
        </div>
        <div
          class="preview-frame"
          style="--panel-w: ${dims.w}; --panel-h: ${dims.h};"
        >
          ${this.previewLoading
            ? html`
                <div class="preview-spinner">
                  <div class="preview-spinner-icon"></div>
                  Rendering at panel resolution + quantizing to Spectra 6…
                </div>
              `
            : this.previewError
              ? html`<div class="preview-error">${this.previewError}</div>`
              : this.previewUrl
                ? html`<img src=${this.previewUrl} alt="quantized panel preview" />`
                : html`
                    <div class="preview-empty">
                      Click <strong>Render preview</strong> to see what the panel will paint.
                    </div>
                  `}
        </div>
      </div>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="send"></id-nav>
      <div class="container">
        <h1>Send to panel</h1>
        <p class="lede">Push any image, dashboard, or webpage to the panel right now.</p>

        <div class="source-tabs" role="tablist">
          ${[
            { id: "file", label: "File", icon: "ph-file-arrow-up" },
            { id: "page", label: "Saved dashboard", icon: "ph-cube" },
            { id: "url", label: "Image URL", icon: "ph-link" },
            { id: "webpage", label: "Webpage", icon: "ph-globe" },
          ].map(
            (tab) => html`
              <button
                role="tab"
                aria-selected=${this.source === tab.id ? "true" : "false"}
                @click=${() => this._switchSource(tab.id)}
              >
                <i class="ph ${tab.icon}"></i> ${tab.label}
              </button>
            `
          )}
        </div>

        <div class="layout">
          <div class="form">
            ${this._renderSourceForm()}
            <div class="form-row">
              <label class="field">Dither</label>
              <select @change=${(e) => { this.dither = e.target.value; this._clearPreview(); }}>
                <option value="floyd-steinberg" ?selected=${this.dither === "floyd-steinberg"}>Floyd–Steinberg</option>
                <option value="none" ?selected=${this.dither === "none"}>None (nearest)</option>
              </select>
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
                      ? html`<a href=${this.result.url} target="_blank">${this.result.url}</a>`
                      : null}
                  </div>`
                : null}
          </div>
          ${this._renderPreview()}
        </div>
      </div>
    `;
  }
}

customElements.define("send-page", SendPage);
document.body.append(document.createElement("send-page"));
