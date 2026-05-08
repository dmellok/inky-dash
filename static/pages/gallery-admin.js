import { LitElement, html, css } from "lit";
import "../components/index.js";

const FOLDER_NAME_RE = /^[a-z0-9][a-z0-9_-]{0,63}$/;

class GalleryAdminPage extends LitElement {
  static properties = {
    folders: { state: true },
    creating: { state: true },
    newName: { state: true },
    newExternalPath: { state: true },
    error: { state: true },
    uploading: { state: true },
    collapsed: { state: true },
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

    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin: 24px 0 12px;
      flex-wrap: wrap;
    }
    .section-head h2 {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      margin: 0;
      padding-top: 10px;
    }
    .new-form {
      display: grid;
      grid-template-columns: minmax(160px, 200px) minmax(200px, 320px) auto;
      gap: 8px;
      align-items: center;
      flex: 1;
      max-width: 720px;
    }
    .new-form input {
      min-height: var(--id-control-h, 40px);
      padding: 8px 10px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      width: 100%;
      box-sizing: border-box;
    }
    .new-form .field {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }
    .new-form .hint {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      padding: 0 2px;
    }
    @media (max-width: 720px) {
      .new-form {
        grid-template-columns: 1fr;
        max-width: none;
      }
    }

    .folder-card {
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      padding: 16px;
      margin-bottom: 16px;
    }
    .folder-card.external {
      border-left: 3px solid var(--id-accent, #d97757);
    }
    .folder-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    .folder-title {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 0;
    }
    .folder-title h3 {
      margin: 0;
      font-size: 16px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .folder-title .ph {
      color: var(--id-accent, #d97757);
    }
    .folder-title .count {
      color: var(--id-fg-soft, #5a4f44);
      font-size: 13px;
      font-variant-numeric: tabular-nums;
    }
    .folder-title .ext-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 6px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--id-accent-soft, #aa5a3f);
      background: rgba(217, 119, 87, 0.1);
      border: 1px solid rgba(217, 119, 87, 0.25);
      border-radius: 4px;
    }
    .ext-path {
      flex-basis: 100%;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      font-family: ui-monospace, "SF Mono", Menlo, monospace;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      padding-left: 28px;
      margin-top: -4px;
    }
    .folder-actions {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
      align-items: center;
    }
    .folder-actions input[type="file"] {
      display: none;
    }
    .collapse-btn {
      background: transparent;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      width: 32px;
      height: 32px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--id-fg-soft, #5a4f44);
      padding: 0;
      transition: transform 150ms ease;
    }
    .collapse-btn:hover {
      color: var(--id-fg, #1a1612);
      background: var(--id-surface2, #f5e8d8);
    }
    .collapse-btn.collapsed .ph {
      transform: rotate(-90deg);
    }
    .collapse-btn .ph {
      transition: transform 150ms ease;
    }

    .images {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
      gap: 8px;
      margin-top: 12px;
    }
    .image {
      position: relative;
      aspect-ratio: 4 / 3;
      border-radius: 6px;
      overflow: hidden;
      background: var(--id-surface2, #f5e8d8);
      border: 1px solid var(--id-divider, #c8b89b);
    }
    .image img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .image .delete,
    .image .send {
      position: absolute;
      top: 4px;
      width: 28px;
      height: 28px;
      border: 0;
      border-radius: 14px;
      background: rgba(0, 0, 0, 0.5);
      color: white;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
      opacity: 0;
      transition: opacity 100ms ease, background 100ms ease;
    }
    .image .delete { right: 4px; }
    .image .send {
      left: 4px;
      background: rgba(217, 119, 87, 0.85);
    }
    .image .send:hover { background: var(--id-accent, #d97757); }
    .image:hover .delete,
    .image:hover .send,
    .image:focus-within .delete,
    .image:focus-within .send {
      opacity: 1;
    }
    .image .name {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      padding: 4px 6px;
      font-size: 10px;
      color: white;
      background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .empty-images {
      padding: 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      border: 1px dashed var(--id-divider, #c8b89b);
      border-radius: 6px;
      margin-top: 12px;
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

    .drop-target {
      transition: background 100ms ease, border-color 100ms ease;
    }
    .drop-target.drop-active {
      border-color: var(--id-accent, #d97757);
      background: rgba(217, 119, 87, 0.05);
    }
  `;

  constructor() {
    super();
    this.folders = null;
    this.creating = false;
    this.newName = "";
    this.newExternalPath = "";
    this.error = null;
    this.uploading = {};
    this.collapsed = {};
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._load();
  }

  async _load() {
    try {
      const res = await fetch("/plugins/gallery/api/folders");
      const folders = await res.json();
      // Default-collapse every folder so the page opens without firing a
      // thousand <img> requests at once. The first click on a folder
      // expands it. Folders the user hasn't seen before start collapsed.
      const next = { ...this.collapsed };
      for (const f of folders) {
        if (!(f.name in next)) next[f.name] = true;
      }
      this.collapsed = next;
      this.folders = folders;
    } catch (err) {
      this.error = err.message;
      this.folders = [];
    }
  }

  async _createFolder() {
    const name = this.newName.trim().toLowerCase();
    if (!FOLDER_NAME_RE.test(name)) {
      this.error = "Folder names: lowercase letters, digits, - or _";
      return;
    }
    this.creating = true;
    this.error = null;
    try {
      const body = { name };
      const ext = this.newExternalPath.trim();
      if (ext) body.external_path = ext;
      const res = await fetch("/plugins/gallery/api/folders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.error || `HTTP ${res.status}`);
      }
      this.newName = "";
      this.newExternalPath = "";
      await this._load();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.creating = false;
    }
  }

  async _deleteFolder(folder) {
    const msg = folder.external_path
      ? `Remove external folder "${folder.label}"? (Files at ${folder.external_path} won't be touched.)`
      : `Delete folder "${folder.label}" and ${folder.image_count} image(s)?`;
    if (!confirm(msg)) return;
    this.error = null;
    try {
      const res = await fetch(
        `/plugins/gallery/api/folders/${encodeURIComponent(folder.name)}`,
        { method: "DELETE" }
      );
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  _sendImage(folder, image) {
    // Hand the image off to the Send page via ?image=<full-resolution URL>.
    // The Send page fetches it on load and stages it as the file to send.
    const url = new URL("/send", window.location.origin);
    url.searchParams.set("image", image.url);
    url.searchParams.set("name", image.name);
    window.location.href = url.toString();
  }

  async _deleteImage(folder, image) {
    this.error = null;
    try {
      const res = await fetch(
        `/plugins/gallery/api/folders/${encodeURIComponent(folder.name)}/images/${encodeURIComponent(image.name)}`,
        { method: "DELETE" }
      );
      if (!res.ok && res.status !== 204) throw new Error(`HTTP ${res.status}`);
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  async _upload(folder, fileList) {
    if (!fileList || fileList.length === 0) return;
    if (folder.external_path) {
      this.error = "Uploads to external folders aren't allowed.";
      return;
    }
    this.uploading = { ...this.uploading, [folder.name]: true };
    this.error = null;
    try {
      const form = new FormData();
      for (const f of fileList) form.append("file", f);
      const res = await fetch(
        `/plugins/gallery/api/folders/${encodeURIComponent(folder.name)}/images`,
        { method: "POST", body: form }
      );
      const body = await res.json();
      if (!res.ok) {
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      if (body.skipped && body.skipped.length) {
        this.error = `Skipped: ${body.skipped.join(", ")}`;
      }
      await this._load();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.uploading = { ...this.uploading, [folder.name]: false };
    }
  }

  _onDrop(folder, event) {
    event.preventDefault();
    event.currentTarget.classList.remove("drop-active");
    if (folder.external_path) return;
    const files = Array.from(event.dataTransfer?.files || []);
    if (files.length) this._upload(folder, files);
  }

  _onDragOver(folder, event) {
    event.preventDefault();
    if (folder.external_path) return;
    event.currentTarget.classList.add("drop-active");
  }

  _onDragLeave(event) {
    event.currentTarget.classList.remove("drop-active");
  }

  _toggleCollapsed(folder) {
    this.collapsed = {
      ...this.collapsed,
      [folder.name]: !this.collapsed[folder.name],
    };
  }

  _renderFolderCard(folder) {
    const uploading = this.uploading[folder.name];
    const isRoot = folder.name === "_root";
    const isExternal = !!folder.external_path;
    const isCollapsed = !!this.collapsed[folder.name];
    const folderIcon = isExternal
      ? "ph-folder-notch"
      : isRoot
        ? "ph-folder-simple"
        : "ph-folder";
    return html`
      <div
        class="folder-card drop-target ${isExternal ? "external" : ""}"
        @dragover=${(e) => this._onDragOver(folder, e)}
        @dragleave=${this._onDragLeave}
        @drop=${(e) => this._onDrop(folder, e)}
      >
        <div class="folder-head">
          <div class="folder-title">
            <button
              class="collapse-btn ${isCollapsed ? "collapsed" : ""}"
              @click=${() => this._toggleCollapsed(folder)}
              aria-label=${isCollapsed ? "Expand thumbnails" : "Collapse thumbnails"}
              aria-expanded=${isCollapsed ? "false" : "true"}
              title=${isCollapsed ? "Expand thumbnails" : "Collapse thumbnails"}
            >
              <i class="ph ph-caret-down"></i>
            </button>
            <h3>
              <i class="ph ${folderIcon}"></i>
              ${folder.label}
              <span class="count">${folder.image_count} image${folder.image_count === 1 ? "" : "s"}</span>
              ${isExternal
                ? html`<span class="ext-badge"><i class="ph ph-arrow-square-out"></i> external</span>`
                : null}
            </h3>
          </div>
          <div class="folder-actions">
            ${isExternal
              ? null
              : html`
                  <id-button @click=${(e) => e.currentTarget.parentElement.querySelector("input[type=file]").click()}>
                    <i class="ph ph-upload"></i>
                    ${uploading ? "Uploading…" : "Upload"}
                  </id-button>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    @change=${(e) => this._upload(folder, e.target.files)}
                  />
                `}
            ${!isRoot
              ? html`
                  <id-button variant="danger" @click=${() => this._deleteFolder(folder)}>
                    <i class="ph ph-trash"></i> ${isExternal ? "Remove" : "Delete folder"}
                  </id-button>
                `
              : null}
          </div>
          ${isExternal
            ? html`<div class="ext-path" title=${folder.external_path}>${folder.external_path}</div>`
            : null}
        </div>
        ${isCollapsed
          ? null
          : folder.images.length === 0
            ? html`<div class="empty-images">
                ${isExternal
                  ? "No supported images in this folder."
                  : "Drop images here, or use the Upload button."}
              </div>`
            : html`
                <div class="images">
                  ${folder.images.map(
                    (img) => html`
                      <div class="image">
                        <img
                          src=${img.thumb_url || img.url}
                          alt=${img.name}
                          loading="lazy"
                        />
                        <button
                          class="send"
                          @click=${() => this._sendImage(folder, img)}
                          title="Open in Send to panel"
                          aria-label="Send ${img.name}"
                        >
                          <i class="ph ph-paper-plane-tilt"></i>
                        </button>
                        ${isExternal
                          ? null
                          : html`
                              <button
                                class="delete"
                                @click=${() => this._deleteImage(folder, img)}
                                aria-label="Delete ${img.name}"
                              >
                                <i class="ph ph-x"></i>
                              </button>
                            `}
                        <div class="name">${img.name}</div>
                      </div>
                    `
                  )}
                </div>
              `}
      </div>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav></id-nav>
      <div class="container">
        <h1><i class="ph ph-images" style="color: var(--id-accent);"></i> Gallery</h1>
        <p class="lede">
          Group images into folders, then pick one from the editor when you
          add a Gallery cell. Folders can either hold uploads here, or point
          at an existing directory on the host (read-only).
        </p>

        <div class="section-head">
          <h2>${this.folders ? `${this.folders.length} folder${this.folders.length === 1 ? "" : "s"}` : "Loading…"}</h2>
          <div class="new-form">
            <div class="field">
              <input
                type="text"
                placeholder="folder name"
                .value=${this.newName}
                ?disabled=${this.creating}
                @input=${(e) => (this.newName = e.target.value)}
                @keydown=${(e) => { if (e.key === "Enter") this._createFolder(); }}
              />
              <span class="hint">lowercase, digits, - or _</span>
            </div>
            <div class="field">
              <input
                type="text"
                placeholder="optional: /path/to/external/folder"
                .value=${this.newExternalPath}
                ?disabled=${this.creating}
                @input=${(e) => (this.newExternalPath = e.target.value)}
                @keydown=${(e) => { if (e.key === "Enter") this._createFolder(); }}
              />
              <span class="hint">leave blank for an internal folder you upload into</span>
            </div>
            <id-button variant="primary" ?disabled=${this.creating} @click=${() => this._createFolder()}>
              <i class="ph ph-plus"></i>
              ${this.creating ? "Creating…" : "Create"}
            </id-button>
          </div>
        </div>

        ${this.error ? html`<p class="error">${this.error}</p>` : null}

        ${this.folders === null
          ? html`<p class="empty">Loading…</p>`
          : this.folders.length === 0
            ? html`<p class="empty">No folders yet. Create one above to get started.</p>`
            : this.folders.map((f) => this._renderFolderCard(f))}
      </div>
    `;
  }
}

customElements.define("gallery-admin", GalleryAdminPage);
document.body.append(document.createElement("gallery-admin"));
