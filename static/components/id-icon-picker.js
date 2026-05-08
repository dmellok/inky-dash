import { LitElement, html, css } from "lit";

// A curated subset of Phosphor icons that fit dashboard naming. Listed by
// theme so the search experience surfaces relevant matches first. The icon
// names match the .ph-* class on the Phosphor web font.
const ICON_LIBRARY = [
  // Generic
  "ph-cube", "ph-square", "ph-circle", "ph-grid-four", "ph-squares-four",
  "ph-stack", "ph-layout", "ph-sparkle", "ph-star", "ph-heart",
  // Time + scheduling
  "ph-clock", "ph-clock-clockwise", "ph-clock-countdown", "ph-alarm",
  "ph-calendar", "ph-calendar-blank", "ph-hourglass", "ph-timer",
  // Home + spaces
  "ph-house", "ph-house-line", "ph-buildings", "ph-bed", "ph-couch",
  "ph-armchair", "ph-bathtub", "ph-cooking-pot", "ph-fork-knife", "ph-coffee",
  "ph-tree", "ph-plant", "ph-leaf", "ph-flower", "ph-tree-palm",
  // Weather
  "ph-sun", "ph-moon", "ph-cloud", "ph-cloud-rain", "ph-cloud-snow",
  "ph-cloud-sun", "ph-cloud-moon", "ph-lightning", "ph-rainbow", "ph-thermometer",
  "ph-snowflake", "ph-wind", "ph-umbrella",
  // Media + photos
  "ph-image", "ph-images", "ph-camera", "ph-film-strip", "ph-music-notes",
  "ph-headphones", "ph-microphone", "ph-play-circle", "ph-vinyl-record",
  // Devices
  "ph-monitor", "ph-monitor-play", "ph-television", "ph-laptop", "ph-desktop",
  "ph-device-mobile", "ph-device-tablet", "ph-keyboard", "ph-mouse",
  "ph-printer", "ph-router", "ph-broadcast", "ph-wifi-high",
  // Productivity
  "ph-list", "ph-list-checks", "ph-check-square", "ph-note", "ph-notebook",
  "ph-bookmark", "ph-target", "ph-trophy", "ph-flag", "ph-pencil-simple",
  "ph-paperclip", "ph-lightbulb", "ph-magnifying-glass",
  // Travel + places
  "ph-airplane", "ph-train", "ph-car", "ph-bicycle", "ph-map-pin",
  "ph-compass", "ph-globe", "ph-globe-hemisphere-east",
  // Shopping + finance
  "ph-shopping-cart", "ph-shopping-bag", "ph-wallet", "ph-coin", "ph-currency-dollar",
  "ph-gift", "ph-package",
  // Comms + social
  "ph-chat", "ph-chat-circle", "ph-envelope", "ph-paper-plane", "ph-phone",
  "ph-users", "ph-user", "ph-user-circle",
  // News + reading
  "ph-newspaper", "ph-book", "ph-book-open", "ph-rss",
  // Health + body
  "ph-pulse", "ph-heartbeat", "ph-barbell", "ph-person-simple-run", "ph-bicycle",
  // Misc
  "ph-puzzle-piece", "ph-paint-brush", "ph-palette", "ph-fire", "ph-rocket",
  "ph-anchor", "ph-key", "ph-gear", "ph-toolbox", "ph-wrench",
  "ph-graduation-cap", "ph-medal", "ph-cake",
];

// Cheap searchable label: drop "ph-" and split hyphens into words.
function labelFor(icon) {
  return icon.replace(/^ph-/, "").replace(/-/g, " ");
}

export class IdIconPicker extends LitElement {
  static properties = {
    open: { type: Boolean, reflect: true },
    value: { type: String },
    query: { state: true },
  };

  static styles = css`
    :host {
      display: contents;
    }
    .backdrop {
      position: fixed;
      inset: 0;
      background: rgb(0 0 0 / 0.45);
      z-index: 50;
      display: grid;
      place-items: center;
      padding: 24px;
    }
    .panel {
      width: min(640px, 100%);
      max-height: min(72vh, 640px);
      display: flex;
      flex-direction: column;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 12px;
      box-shadow: var(--id-shadow-lg, 0 12px 32px rgb(0 0 0 / 0.25));
      overflow: hidden;
    }
    .head {
      padding: 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .head h3 {
      margin: 0;
      font-size: 15px;
      flex: 1;
    }
    .close {
      background: transparent;
      border: 0;
      color: var(--id-fg-soft, #5a4f44);
      cursor: pointer;
      width: 32px;
      height: 32px;
      border-radius: 6px;
      font-size: 18px;
      display: inline-grid;
      place-items: center;
    }
    .close:hover {
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-fg, #1a1612);
    }
    .search {
      position: relative;
      padding: 0 16px 12px;
    }
    .search i {
      position: absolute;
      left: 26px;
      top: 50%;
      transform: translateY(-50%);
      margin-top: -6px;
      color: var(--id-fg-soft, #5a4f44);
      pointer-events: none;
    }
    .search input {
      width: 100%;
      box-sizing: border-box;
      padding: 0 12px 0 36px;
      height: var(--id-control-h, 40px);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      font: inherit;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
    }
    .search input:focus {
      outline: none;
      border-color: var(--id-accent, #4f46e5);
    }
    .grid {
      flex: 1;
      overflow-y: auto;
      padding: 0 16px 16px;
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(56px, 1fr));
      gap: 6px;
    }
    .icon-btn {
      aspect-ratio: 1;
      display: grid;
      place-items: center;
      border: 1px solid transparent;
      border-radius: 8px;
      background: transparent;
      color: var(--id-fg, #1a1612);
      cursor: pointer;
      font-size: 22px;
      transition: background 100ms ease, border-color 100ms ease, color 100ms ease;
    }
    .icon-btn:hover {
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-accent, #4f46e5);
    }
    .icon-btn.active {
      border-color: var(--id-accent, #4f46e5);
      color: var(--id-accent, #4f46e5);
      background: var(--id-accent-bg, rgb(79 70 229 / 0.1));
    }
    .empty {
      grid-column: 1 / -1;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      padding: 24px;
      font-style: italic;
    }
    .footer {
      padding: 12px 16px;
      border-top: 1px solid var(--id-divider, #c8b89b);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }
    .footer button {
      padding: 0 14px;
      height: var(--id-control-h, 40px);
      border-radius: 6px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      font: inherit;
      cursor: pointer;
    }
    .footer button:hover {
      color: var(--id-fg, #1a1612);
      background: var(--id-surface2, #f5e8d8);
    }
  `;

  constructor() {
    super();
    this.open = false;
    this.value = null;
    this.query = "";
    this._onKeydown = this._onKeydown.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();
    document.addEventListener("keydown", this._onKeydown);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener("keydown", this._onKeydown);
  }

  _onKeydown(e) {
    if (this.open && e.key === "Escape") this._close();
  }

  _close() {
    this.open = false;
    this.dispatchEvent(new CustomEvent("close"));
  }

  _pick(icon) {
    this.value = icon;
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { value: icon },
        bubbles: true,
        composed: true,
      })
    );
    this._close();
  }

  _filtered() {
    const q = this.query.trim().toLowerCase();
    if (!q) return ICON_LIBRARY;
    return ICON_LIBRARY.filter((icon) => labelFor(icon).includes(q));
  }

  render() {
    if (!this.open) return null;
    const filtered = this._filtered();
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="backdrop" @click=${(e) => e.target === e.currentTarget && this._close()}>
        <div class="panel" role="dialog" aria-label="Pick an icon">
          <div class="head">
            <h3>Pick an icon</h3>
            <button class="close" @click=${this._close} aria-label="Close">
              <i class="ph ph-x"></i>
            </button>
          </div>
          <div class="search">
            <i class="ph ph-magnifying-glass"></i>
            <input
              type="text"
              autofocus
              placeholder="Search icons…"
              .value=${this.query}
              @input=${(e) => (this.query = e.target.value)}
            />
          </div>
          <div class="grid">
            ${filtered.length === 0
              ? html`<div class="empty">No icons match "${this.query}".</div>`
              : filtered.map(
                  (icon) => html`
                    <button
                      type="button"
                      class="icon-btn ${this.value === icon ? "active" : ""}"
                      title=${labelFor(icon)}
                      aria-label=${labelFor(icon)}
                      @click=${() => this._pick(icon)}
                    >
                      <i class="ph ${icon}"></i>
                    </button>
                  `
                )}
          </div>
          <div class="footer">
            <span style="font-size: 12px; color: var(--id-fg-soft);">
              ${filtered.length} icon${filtered.length === 1 ? "" : "s"}
            </span>
            ${this.value
              ? html`<button @click=${() => this._pick(null)}>
                  <i class="ph ph-trash" style="margin-right: 4px;"></i>
                  Clear
                </button>`
              : null}
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define("id-icon-picker", IdIconPicker);
