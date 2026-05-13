import { LitElement, html, css } from "lit";
import "../components/index.js";
import {
  isPushing,
  onPushStateChange,
  pushSource,
  runWithPushLock,
} from "../lib/push-state.js";

class SendPage extends LitElement {
  static properties = {
    pages: { state: true },
    source: { state: true },
    pageId: { state: true },
    url: { state: true },
    file: { state: true },
    fileObjectUrl: { state: true },
    dither: { state: true },
    scale: { state: true },
    sending: { state: true },
    result: { state: true },
    error: { state: true },
    previewError: { state: true },
    dragOver: { state: true },
    appPanel: { state: true },
    history: { state: true },
    historyError: { state: true },
    lightboxSrc: { state: true },
    pendingHistoryId: { state: true },
    globalPushing: { state: true },
    globalPushSource: { state: true },
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

    .source-tabs {
      display: flex;
      gap: 4px;
      margin-bottom: 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      flex-wrap: wrap;
    }
    .source-tabs button {
      min-height: var(--id-control-h, 40px);
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
      min-height: var(--id-control-h, 40px);
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
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
         CSS variables (defaults match the 13.3" Spectra 6 landscape native).
         --underscan-zoom matches the history grid — see the comment there. */
      --underscan-zoom: calc(
        var(--panel-w) / (var(--panel-w) - 2 * var(--underscan-px, 0))
      );
      aspect-ratio: var(--panel-w, 1600) / var(--panel-h, 1200);
      background: var(--id-surface2, #f5e8d8);
      display: grid;
      place-items: center;
      position: relative;
      overflow: hidden;
    }
    .preview-frame img {
      width: 100%;
      height: 100%;
      object-fit: contain;
      display: block;
      transform: scale(var(--underscan-zoom, 1));
    }
    /* Live iframe preview — renders the source (saved dashboard or
       webpage URL) at panel resolution then scales down to fit the
       container via a transform we set from JS (mirrors the editor's
       live preview). pointer-events:none so clicks fall through to
       the lightbox trigger instead of the iframe. */
    .preview-frame iframe {
      position: absolute;
      top: 0;
      left: 0;
      width: calc(var(--panel-w, 1600) * 1px);
      height: calc(var(--panel-h, 1200) * 1px);
      border: 0;
      transform-origin: top left;
      pointer-events: none;
      background: var(--id-surface, #ffffff);
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

    /* Recent pushes — thumbnail grid. */
    .history-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 12px;
    }
    .history-head .meta {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .history-empty {
      padding: 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
    }
    /* List view — one row per push attempt. The thumb is a fixed 80×80
       square so the rows align cleanly regardless of panel orientation.
       Image is center-cropped (object-fit: cover) plus the underscan
       zoom so the white border falls outside the square. */
    .history-grid {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .history-card {
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      gap: 14px;
      padding: 10px 14px 10px 10px;
      transition: border-color 100ms ease;
    }
    .history-card:hover { border-color: var(--id-accent, #d97757); }
    .history-thumb {
      /* The grid sets --panel-w / --panel-h (unitless ints) + --underscan-px
         (unitless int, default 0). --underscan-zoom is the scale factor
         needed to crop the white underscan border out of the visible
         window: ratio of the full panel to the inner content area. */
      --underscan-zoom: calc(
        var(--panel-w) / (var(--panel-w) - 2 * var(--underscan-px, 0))
      );
      width: 80px;
      height: 80px;
      flex-shrink: 0;
      background: var(--id-surface2, #f5e8d8);
      border-radius: 8px;
      cursor: zoom-in;
      overflow: hidden;
      display: grid;
      place-items: center;
      position: relative;
    }
    .history-thumb img {
      width: 100%;
      height: 100%;
      /* Square thumb + cover = centered crop. Same treatment for landscape
         and portrait panels; portrait just chains a 90° rotation onto
         the same transform to restore the composed orientation. */
      object-fit: cover;
      display: block;
      transform: scale(var(--underscan-zoom, 1));
      transition: transform 200ms ease;
    }
    .history-thumb:hover img {
      transform: scale(calc(var(--underscan-zoom, 1) * 1.06));
    }
    .history-thumb.portrait img {
      transform: rotate(90deg) scale(var(--underscan-zoom, 1));
    }
    .history-thumb.portrait:hover img {
      transform: rotate(90deg) scale(calc(var(--underscan-zoom, 1) * 1.06));
    }
    .history-thumb-missing {
      font-size: 10px;
      color: var(--id-fg-soft, #5a4f44);
      text-align: center;
      padding: 6px;
    }
    .history-thumb-missing .ph {
      display: block;
      font-size: 22px;
      margin-bottom: 2px;
    }
    .history-body {
      display: grid;
      gap: 3px;
      min-width: 0;
    }
    .history-line1 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 14px;
    }
    .history-line2 {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      min-width: 0;
    }
    .history-page {
      font-weight: 600;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
      min-width: 0;
    }
    .history-age {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      flex-shrink: 0;
    }
    .history-duration {
      color: var(--id-fg-soft, #5a4f44);
      flex-shrink: 0;
      font-variant-numeric: tabular-nums;
    }
    .history-error {
      color: var(--id-danger, #c97c70);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
      flex: 1;
    }
    .history-actions {
      display: flex;
      gap: 6px;
      align-items: center;
    }
    .history-btn {
      background: transparent;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      color: var(--id-fg-soft, #5a4f44);
      cursor: pointer;
      padding: 5px 10px;
      font: inherit;
      font-size: 12px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
      min-height: 28px;
    }
    .history-btn:hover {
      color: var(--id-fg, #1a1612);
      border-color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
    }
    .history-btn.primary {
      color: var(--id-accent, #d97757);
      border-color: var(--id-accent, #d97757);
    }
    .history-btn.danger:hover {
      color: var(--id-danger, #c97c70);
      border-color: var(--id-danger, #c97c70);
    }
    .history-btn[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }

    /* Lightbox — backdrop blur + centered image. */
    .lightbox {
      position: fixed;
      inset: 0;
      background: rgba(20, 16, 12, 0.55);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      z-index: 1000;
      display: grid;
      place-items: center;
      padding: 32px;
      animation: fade-in 120ms ease;
    }
    @keyframes fade-in { from { opacity: 0; } to { opacity: 1; } }
    .lightbox img {
      max-width: 100%;
      max-height: 100%;
      object-fit: contain;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
      border-radius: 8px;
      cursor: zoom-out;
    }
    /* Portrait: rotate the stored landscape PNG back upright. Swap the
       max constraints so the rotated bounding box fits the viewport. */
    .lightbox img.portrait {
      max-width: calc(100vh - 64px);
      max-height: calc(100vw - 64px);
      transform: rotate(90deg);
    }
    .lightbox-close {
      position: absolute;
      top: 16px;
      right: 16px;
      width: 40px;
      height: 40px;
      border-radius: 999px;
      border: 0;
      background: rgba(255, 255, 255, 0.9);
      color: #1a1612;
      cursor: pointer;
      font-size: 22px;
      display: grid;
      place-items: center;
    }

    /* Cross-tab "push in flight" warning bar — appears whenever another
       Send / Resend / Fire-now is mid-flight, in this tab or another. */
    .push-banner {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 10px 14px;
      margin-bottom: 16px;
      border-radius: 8px;
      background: var(--id-surface2, #f5e8d8);
      border: 1px solid var(--id-accent, #d97757);
      color: var(--id-fg, #1a1612);
      font-size: 14px;
    }
    .push-banner .ph {
      color: var(--id-accent, #d97757);
      animation: spin 1.2s linear infinite;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 500;
    }
    .pill.sent { background: rgba(125, 166, 112, 0.18); color: var(--id-ok, #7da670); }
    .pill.failed { background: rgba(201, 124, 112, 0.18); color: var(--id-danger, #c97c70); }
    .pill.busy { background: rgba(217, 119, 87, 0.18); color: var(--id-accent, #d97757); }
    .pill.not_found { background: rgba(90, 79, 68, 0.18); color: var(--id-fg-soft, #5a4f44); }
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
    this.scale = "fit";
    this.sending = false;
    this.result = null;
    this.error = null;
    this.previewError = null;
    this.dragOver = false;
    this.appPanel = null; // { width, height, orientation }
    this.history = [];
    this.historyError = null;
    this.lightboxSrc = null;
    this.pendingHistoryId = null;
    this.globalPushing = isPushing();
    this.globalPushSource = pushSource();
    this._unsubPushState = null;
    if (window.location.pathname.endsWith("/history")) this.source = "history";
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
            underscan: Number(app.panel.underscan) || 0,
          };
        }
      } catch {
        /* fall back to default 1600×1200 ratio */
      }
    } catch (err) {
      this.error = err.message;
    }
    this._loadHistory();
    this._unsubPushState = onPushStateChange(() => {
      this.globalPushing = isPushing();
      this.globalPushSource = pushSource();
    });
    window.addEventListener("keydown", this._onKeydown);
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
    this._previewResizeObserver?.disconnect();
    window.removeEventListener("keydown", this._onKeydown);
    this._unsubPushState?.();
  }

  _onKeydown = (event) => {
    if (event.key === "Escape" && this.lightboxSrc) {
      this.lightboxSrc = null;
    }
  };

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
    // Keep the URL in step so /send/history bookmarks land on the right tab.
    const target = id === "history" ? "/send/history" : "/send";
    if (window.location.pathname !== target) {
      window.history.replaceState({}, "", target);
    }
    if (id === "history") this._loadHistory();
  }

  // The preview is now LIVE — an iframe or <img> reflecting the source
  // directly, no server round-trip. _clearPreview just resets any error
  // overlay; the live element re-mounts on input change via Lit's normal
  // render cycle.
  _clearPreview() {
    this.previewError = null;
  }

  // Live iframes render at the panel's native pixel dimensions; we
  // scale them down with a CSS transform so they fit the preview pane.
  // Composite scale = container_width / inner_panel_width, where
  // inner_panel_width = panel_w - 2*underscan. A translate(-u, -u) in
  // iframe coordinates aligns the inner area's top-left with the
  // container's top-left so the mat-occluded ring falls outside the
  // overflow:hidden box.
  _scaleLiveIframes() {
    const wrap = this.shadowRoot?.querySelector(".preview-frame");
    if (!wrap) return;
    const iframe = wrap.querySelector(".live-iframe");
    if (!iframe) return;
    const w = this._panelDisplayDims().w;
    const u = this.appPanel?.underscan || 0;
    const inner = Math.max(1, w - 2 * u);
    const scale = wrap.clientWidth / inner;
    iframe.style.transform = `scale(${scale}) translate(${-u}px, ${-u}px)`;
  }

  firstUpdated() {
    this._previewResizeObserver = new ResizeObserver(() =>
      this._scaleLiveIframes()
    );
    const wrap = this.shadowRoot?.querySelector(".preview-frame");
    if (wrap) this._previewResizeObserver.observe(wrap);
    this._scaleLiveIframes();
  }

  updated() {
    // The .preview-frame element survives across source switches, but
    // a freshly-mounted iframe inside it needs the transform set right
    // after Lit's update lands.
    this._scaleLiveIframes();
    const wrap = this.shadowRoot?.querySelector(".preview-frame");
    if (wrap && this._previewResizeObserver) {
      this._previewResizeObserver.observe(wrap);
    }
  }

  // ----- send ---------------------------------------------------------

  async _send() {
    if (isPushing()) {
      this.error = "Another push is already in flight. Wait for it to finish.";
      return;
    }
    this.sending = true;
    this.result = null;
    this.error = null;
    try {
      await runWithPushLock(`send:${this.source}`, async () => {
        await this._sendRequest();
      });
    } finally {
      this.sending = false;
    }
  }

  async _sendRequest() {
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
          body: JSON.stringify({
            url: this.url,
            dither: this.dither,
            scale: this.scale,
          }),
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
        form.append("scale", this.scale);
        res = await fetch("/api/send/file", { method: "POST", body: form });
      }
      const body = await res.json();
      if (!res.ok && res.status !== 200) {
        this.error = body.error || `HTTP ${res.status}`;
      }
      this.result = body;
      // A successful send produces a new history row — refresh the list.
      if (res.ok) this._loadHistory();
    } catch (err) {
      this.error = err.message;
    }
  }

  // ----- history ------------------------------------------------------

  async _loadHistory() {
    try {
      const res = await fetch("/api/history?limit=24");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      this.history = await res.json();
      this.historyError = null;
    } catch (err) {
      this.historyError = err.message;
    }
  }

  _fmtAge(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    const mins = Math.round((Date.now() - d.getTime()) / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.round(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return `${Math.round(hours / 24)}d ago`;
  }

  async _resendHistory(record) {
    if (isPushing()) {
      this.error = "Another push is already in flight. Wait for it to finish.";
      return;
    }
    this.pendingHistoryId = record.id;
    this.error = null;
    try {
      await runWithPushLock(`resend:${record.id}`, async () => {
        const res = await fetch(`/api/history/${record.id}/resend`, {
          method: "POST",
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) {
          this.error = body.error || `HTTP ${res.status}`;
        } else {
          this.result = body;
          this._loadHistory();
        }
      });
    } catch (err) {
      this.error = err.message;
    } finally {
      this.pendingHistoryId = null;
    }
  }

  async _deleteHistory(record) {
    if (!confirm(`Delete this push from history?`)) return;
    this.pendingHistoryId = record.id;
    try {
      const res = await fetch(`/api/history/${record.id}`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 404) {
        const body = await res.json().catch(() => ({}));
        this.error = body.error || `HTTP ${res.status}`;
      } else {
        this.history = this.history.filter((h) => h.id !== record.id);
      }
    } catch (err) {
      this.error = err.message;
    } finally {
      this.pendingHistoryId = null;
    }
  }

  _openLightbox(src) {
    this.lightboxSrc = src;
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
          <h3><i class="ph ph-monitor"></i> Live preview</h3>
        </div>
        <div
          class="preview-frame"
          style="--panel-w: ${dims.w}; --panel-h: ${dims.h}; --underscan-px: ${this.appPanel?.underscan || 0};"
        >
          ${this._renderPreviewBody()}
        </div>
      </div>
    `;
  }

  // Live preview content per source. Returns either a live iframe (for
  // dashboards + webpages), an <img> (for image URLs + uploaded files),
  // or an empty-state hint. Nothing is fetched server-side; the iframe /
  // img sources straight from the user's input. The dither + final
  // quantisation only happens at push time.
  _renderPreviewBody() {
    if (this.previewError) {
      return html`<div class="preview-error">${this.previewError}</div>`;
    }
    if (this.source === "page") {
      if (!this.pageId) {
        return html`<div class="preview-empty">Pick a dashboard above.</div>`;
      }
      const src = `/compose/${encodeURIComponent(this.pageId)}?for_push=1&preview=1`;
      // class hook for the resize-observer that scales the iframe to fit
      // the container, accounting for underscan.
      return html`<iframe
        class="live-iframe"
        src=${src}
        title="Dashboard preview"
        loading="lazy"
      ></iframe>`;
    }
    if (this.source === "url") {
      if (!this.url) {
        return html`<div class="preview-empty">Enter an image URL above.</div>`;
      }
      return html`<img
        src=${this.url}
        alt="Source image preview"
        @error=${() =>
          (this.previewError = "Image failed to load — check the URL.")}
      />`;
    }
    if (this.source === "webpage") {
      if (!this.url) {
        return html`<div class="preview-empty">Enter a webpage URL above.</div>`;
      }
      // Some sites set X-Frame-Options: DENY and won't embed. Browsers
      // render a blank/error state in that case; we can't detect it
      // reliably cross-origin, so we just let the iframe try.
      return html`<iframe
        class="live-iframe"
        src=${this.url}
        title="Webpage preview"
        loading="lazy"
      ></iframe>`;
    }
    // file
    if (!this.fileObjectUrl) {
      return html`<div class="preview-empty">Drop or pick a file above.</div>`;
    }
    return html`<img src=${this.fileObjectUrl} alt="Picked file preview" />`;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="send"></id-nav>
      <div class="container">
        <h1>Send to panel</h1>
        <p class="lede">Push any image, dashboard, or webpage to the panel right now.</p>

        ${this.globalPushing
          ? html`<div class="push-banner">
              <i class="ph ph-spinner-gap"></i>
              Push in flight${this.globalPushSource ? html` · ${this.globalPushSource}` : ""}.
              Sends are paused until it finishes.
            </div>`
          : null}

        <div class="source-tabs" role="tablist">
          ${[
            { id: "file", label: "File", icon: "ph-file-arrow-up" },
            { id: "page", label: "Saved dashboard", icon: "ph-cube" },
            { id: "url", label: "Image URL", icon: "ph-link" },
            { id: "webpage", label: "Webpage", icon: "ph-globe" },
            { id: "history", label: "History", icon: "ph-clock-counter-clockwise" },
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

        ${this.source === "history"
          ? this._renderHistorySection()
          : this._renderComposeBody()}
      </div>
      ${this.lightboxSrc
        ? html`
            <div class="lightbox" @click=${() => (this.lightboxSrc = null)}>
              <button
                class="lightbox-close"
                aria-label="Close"
                @click=${(e) => {
                  e.stopPropagation();
                  this.lightboxSrc = null;
                }}
              >
                <i class="ph ph-x"></i>
              </button>
              <img
                class=${this.appPanel?.orientation === "portrait" ? "portrait" : ""}
                src=${this.lightboxSrc}
                alt=""
                @click=${(e) => e.stopPropagation()}
              />
            </div>
          `
        : null}
    `;
  }

  _renderComposeBody() {
    return html`
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
          ${this.source === "file" || this.source === "url"
            ? html`
                <div class="form-row">
                  <label class="field">Fit</label>
                  <select @change=${(e) => {
                    this.scale = e.target.value;
                    this._clearPreview();
                  }}>
                    <option value="fit" ?selected=${this.scale === "fit"}>Fit (letterbox)</option>
                    <option value="fill" ?selected=${this.scale === "fill"}>Fill (crop to cover)</option>
                    <option value="stretch" ?selected=${this.scale === "stretch"}>Stretch (distort)</option>
                    <option value="center" ?selected=${this.scale === "center"}>Center (no scaling)</option>
                    <option value="blurred" ?selected=${this.scale === "blurred"}>Fit with blurred background</option>
                  </select>
                </div>
              `
            : null}
          <div class="actions">
            <id-button
              variant="primary"
              ?disabled=${this.sending || this.globalPushing}
              @click=${() => this._send()}
            >
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
    `;
  }

  _renderHistorySection() {
    const dims = this._panelDisplayDims();
    const isPortrait = this.appPanel?.orientation === "portrait";
    return html`
      <div>
        <div class="history-head">
          <span class="meta">
            ${this.historyError
              ? html`Failed to load history: ${this.historyError}`
              : html`${this.history.length} record${this.history.length === 1 ? "" : "s"}`}
          </span>
          <id-button @click=${() => this._loadHistory()}>
            <i class="ph ph-arrows-clockwise"></i> Refresh
          </id-button>
        </div>
        ${this.history.length === 0
          ? html`<div class="history-empty">
              No push attempts yet. Send something to the panel to start a history.
            </div>`
          : html`
              <div
                class="history-grid"
                style="--panel-w: ${dims.w}; --panel-h: ${dims.h}; --underscan-px: ${this.appPanel?.underscan || 0};"
              >
                ${this.history.map((h) => this._renderHistoryCard(h, isPortrait))}
              </div>
            `}
      </div>
    `;
  }

  _renderHistoryCard(h, isPortrait) {
    const thumbUrl = h.digest ? `/renders/${h.digest}.png` : null;
    const isPending = this.pendingHistoryId === h.id;
    const canResend = !!h.digest && h.status !== "not_found";
    return html`
      <div class="history-card">
        <div
          class="history-thumb ${isPortrait ? "portrait" : ""}"
          @click=${() => thumbUrl && this._openLightbox(thumbUrl)}
        >
          ${thumbUrl
            ? html`<img src=${thumbUrl} alt="push ${h.id}" loading="lazy" />`
            : html`<div class="history-thumb-missing">
                <i class="ph ph-image-broken"></i>
                no render
              </div>`}
        </div>
        <div class="history-body">
          <div class="history-line1">
            <span class="history-page" title=${h.page_id}>${h.page_id}</span>
            <span class="history-age">${this._fmtAge(h.ts)}</span>
          </div>
          <div class="history-line2">
            <span class="pill ${h.status}">${h.status}</span>
            ${h.duration_s
              ? html`<span class="history-duration">${h.duration_s}s</span>`
              : null}
            ${h.error
              ? html`<span class="history-error" title=${h.error}>${h.error}</span>`
              : null}
          </div>
        </div>
        <div class="history-actions">
          <button
            class="history-btn primary"
            ?disabled=${!canResend || isPending || this.globalPushing}
            @click=${() => this._resendHistory(h)}
            title=${canResend ? "Re-publish this exact render" : "No render to resend"}
          >
            <i class="ph ph-paper-plane-tilt"></i>
            ${isPending ? "…" : "Resend"}
          </button>
          <button
            class="history-btn danger"
            ?disabled=${isPending}
            @click=${() => this._deleteHistory(h)}
            title="Delete from history"
          >
            <i class="ph ph-trash"></i>
          </button>
        </div>
      </div>
    `;
  }
}

customElements.define("send-page", SendPage);
document.body.append(document.createElement("send-page"));
