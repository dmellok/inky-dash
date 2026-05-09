import { LitElement, html, css } from "lit";

// HSV-based 2D pad + hue slider + hex input. Emits a `change` event with
// `detail.value` as a 6-digit lowercase hex on every pointer move and on
// hex-input commit. Designed to drop in for `<input type="color">` callsites.

function hexToRgb(hex) {
  const h = String(hex).replace("#", "");
  if (h.length !== 6) return [255, 255, 255];
  return [
    parseInt(h.slice(0, 2), 16) || 0,
    parseInt(h.slice(2, 4), 16) || 0,
    parseInt(h.slice(4, 6), 16) || 0,
  ];
}

function rgbToHex(r, g, b) {
  const clamp = (n) => Math.max(0, Math.min(255, Math.round(n)));
  return (
    "#" +
    [clamp(r), clamp(g), clamp(b)]
      .map((n) => n.toString(16).padStart(2, "0"))
      .join("")
  );
}

function rgbToHsv(r, g, b) {
  const rr = r / 255;
  const gg = g / 255;
  const bb = b / 255;
  const mx = Math.max(rr, gg, bb);
  const mn = Math.min(rr, gg, bb);
  const d = mx - mn;
  const v = mx;
  const s = mx === 0 ? 0 : d / mx;
  let h = 0;
  if (d !== 0) {
    if (mx === rr) h = ((gg - bb) / d) % 6;
    else if (mx === gg) h = (bb - rr) / d + 2;
    else h = (rr - gg) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  return { h, s, v };
}

function hsvToRgb(h, s, v) {
  const c = v * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = v - c;
  let r;
  let g;
  let b;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [(r + m) * 255, (g + m) * 255, (b + m) * 255];
}

function hexToHsv(hex) {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHsv(r, g, b);
}

function hsvToHex(h, s, v) {
  return rgbToHex(...hsvToRgb(h, s, v));
}

const HEX_RE = /^#?([0-9a-fA-F]{6})$/;

export class IdColorPicker extends LitElement {
  static properties = {
    value: { type: String },
    /** Optional swatches shown beneath the picker for one-click pick. */
    palette: { type: Array },
    open: { state: true },
    hue: { state: true },
    sat: { state: true },
    val: { state: true },
    hexDraft: { state: true },
  };

  static styles = css`
    :host {
      display: inline-block;
      position: relative;
      font-family: inherit;
    }
    .trigger {
      display: flex;
      align-items: center;
      gap: 8px;
      width: 100%;
      box-sizing: border-box;
      height: var(--id-control-h, 40px);
      padding: 0 10px;
      border: 1px solid var(--id-divider, #e2e8f0);
      border-radius: var(--id-radius, 8px);
      background: var(--id-bg, #ffffff);
      cursor: pointer;
      font: inherit;
      color: inherit;
      overflow: hidden;
      min-width: 0;
    }
    .trigger .hex-label { flex: 1; text-align: left; }
    .trigger:hover { border-color: var(--id-fg-soft, #64748b); }
    .trigger:focus-visible {
      outline: none;
      border-color: var(--id-accent, #b06750);
      box-shadow: 0 0 0 3px var(--id-accent-bg, rgb(176 103 80 / 0.12));
    }
    .swatch {
      width: 22px;
      height: 22px;
      border-radius: 4px;
      border: 1px solid rgba(0, 0, 0, 0.12);
      flex-shrink: 0;
    }
    .hex-label {
      font: 13px ui-monospace, "SF Mono", Menlo, monospace;
      letter-spacing: 0.02em;
      color: var(--id-fg, #0f172a);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .chev {
      color: var(--id-fg-soft, #64748b);
      font-size: 10px;
      margin-left: 2px;
    }

    /* Popup panel — positions below the trigger via absolute placement.
       Z-index sits above id-card / form rows. */
    .popup {
      position: absolute;
      top: calc(100% + 4px);
      left: 0;
      z-index: 50;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #e2e8f0);
      border-radius: 12px;
      box-shadow: var(--id-shadow-lg, 0 12px 32px rgb(15 23 42 / 0.15));
      padding: 12px;
      display: grid;
      gap: 8px;
      width: 220px;
    }
    .popup[data-flip-x="true"] { left: auto; right: 0; }

    .sv-pad {
      position: relative;
      width: 100%;
      height: 140px;
      border-radius: 8px;
      cursor: crosshair;
      touch-action: none;
      overflow: hidden;
      border: 1px solid rgba(0, 0, 0, 0.08);
    }
    .sv-cursor {
      position: absolute;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid #ffffff;
      box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(0, 0, 0, 0.3);
      transform: translate(-50%, -50%);
      pointer-events: none;
    }

    .hue-slider {
      position: relative;
      width: 100%;
      height: 14px;
      border-radius: 7px;
      cursor: ew-resize;
      touch-action: none;
      background: linear-gradient(
        to right,
        #ff0000 0%,
        #ffff00 16.66%,
        #00ff00 33.33%,
        #00ffff 50%,
        #0000ff 66.66%,
        #ff00ff 83.33%,
        #ff0000 100%
      );
      border: 1px solid rgba(0, 0, 0, 0.08);
    }
    .hue-cursor {
      position: absolute;
      top: 50%;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      border: 2px solid #ffffff;
      box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(0, 0, 0, 0.3);
      transform: translate(-50%, -50%);
      pointer-events: none;
      background: hsl(var(--cursor-hue, 0), 100%, 50%);
    }

    .hex-row {
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .hex-row input {
      flex: 1;
      padding: 0 8px;
      min-height: 28px;
      border: 1px solid var(--id-divider, #e2e8f0);
      border-radius: 6px;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #0f172a);
      font: 12px ui-monospace, "SF Mono", Menlo, monospace;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }
    .hex-row input:focus {
      outline: none;
      border-color: var(--id-accent, #b06750);
      box-shadow: 0 0 0 3px var(--id-accent-bg, rgb(176 103 80 / 0.12));
    }

    .palette-strip {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 4px;
      padding-top: 6px;
      border-top: 1px solid var(--id-divider, #e2e8f0);
    }
    .palette-strip-label {
      grid-column: 1 / -1;
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      font-weight: 600;
    }
    .palette-swatch {
      width: 100%;
      aspect-ratio: 1;
      border: 1px solid rgba(0, 0, 0, 0.15);
      border-radius: 4px;
      cursor: pointer;
      padding: 0;
      transition: transform 80ms ease;
    }
    .palette-swatch:hover { transform: scale(1.12); }
  `;

  constructor() {
    super();
    this.value = "#ffffff";
    this.palette = [];
    this.open = false;
    this.hue = 0;
    this.sat = 0;
    this.val = 1;
    this.hexDraft = "#ffffff";
    this._dragging = false;
    this._onDocClick = this._onDocClick.bind(this);
    this._onDocKey = this._onDocKey.bind(this);
  }

  willUpdate(changed) {
    if (changed.has("value") && this.value && !this._dragging) {
      const m = HEX_RE.exec(this.value);
      if (m) {
        const hex = "#" + m[1].toLowerCase();
        const { h, s, v } = hexToHsv(hex);
        // Preserve the current hue when value collapses to a desaturated grey
        // (HSV hue is undefined at S=0 — without this, dragging onto the
        // grayscale axis would reset the hue slider to 0).
        if (s > 0) this.hue = h;
        this.sat = s;
        this.val = v;
        this.hexDraft = hex.toUpperCase();
      }
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener("click", this._onDocClick, true);
    document.removeEventListener("keydown", this._onDocKey, true);
  }

  render() {
    const v = String(this.value || "#ffffff");
    return html`
      <button
        type="button"
        class="trigger"
        @click=${this._togglePopup}
        aria-haspopup="dialog"
        aria-expanded=${String(this.open)}
      >
        <span class="swatch" style=${`background: ${v};`}></span>
        <span class="hex-label">${v.toUpperCase()}</span>
        <span class="chev">▾</span>
      </button>
      ${this.open ? this._renderPopup() : null}
    `;
  }

  _renderPopup() {
    const v = String(this.value || "#ffffff");
    const huePct = (this.hue / 360) * 100;
    const satPct = this.sat * 100;
    const valPct = (1 - this.val) * 100;
    return html`
      <div class="popup" role="dialog" @click=${(e) => e.stopPropagation()}>
        <div
          class="sv-pad"
          style=${`background:
            linear-gradient(to top, #000000, transparent),
            linear-gradient(to right, #ffffff, hsl(${this.hue}, 100%, 50%));`}
          @pointerdown=${this._onSvPointer}
        >
          <div class="sv-cursor" style=${`left: ${satPct}%; top: ${valPct}%;`}></div>
        </div>
        <div class="hue-slider" @pointerdown=${this._onHuePointer}>
          <div
            class="hue-cursor"
            style=${`left: ${huePct}%; --cursor-hue: ${this.hue};`}
          ></div>
        </div>
        <div class="hex-row">
          <span class="swatch" style=${`background: ${v};`}></span>
          <input
            type="text"
            spellcheck="false"
            maxlength="7"
            .value=${this.hexDraft}
            @input=${(e) => (this.hexDraft = e.target.value)}
            @keydown=${this._onHexKey}
            @blur=${this._commitHex}
          />
        </div>
        ${this.palette && this.palette.length
          ? html`
              <div class="palette-strip">
                <span class="palette-strip-label">Theme</span>
                ${this.palette.map(
                  (c) => html`
                    <button
                      type="button"
                      class="palette-swatch"
                      style=${`background: ${c};`}
                      title=${c}
                      @click=${() => this._applyHex(c)}
                    ></button>
                  `
                )}
              </div>
            `
          : null}
      </div>
    `;
  }

  _togglePopup(e) {
    e.stopPropagation();
    if (this.open) {
      this._close();
    } else {
      this.open = true;
      this.hexDraft = String(this.value || "#ffffff").toUpperCase();
      // Defer document listeners so the click that opened us doesn't immediately close.
      requestAnimationFrame(() => {
        document.addEventListener("click", this._onDocClick, true);
        document.addEventListener("keydown", this._onDocKey, true);
      });
    }
  }

  _close() {
    this.open = false;
    document.removeEventListener("click", this._onDocClick, true);
    document.removeEventListener("keydown", this._onDocKey, true);
  }

  _onDocClick(e) {
    if (this.contains(e.target) || (e.composedPath && e.composedPath().includes(this))) return;
    this._close();
  }

  _onDocKey(e) {
    if (e.key === "Escape") this._close();
  }

  _onSvPointer(e) {
    const pad = e.currentTarget;
    const update = (ev) => {
      const rect = pad.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (ev.clientY - rect.top) / rect.height));
      this.sat = x;
      this.val = 1 - y;
      this._emit();
    };
    this._dragging = true;
    update(e);
    const stop = () => {
      this._dragging = false;
      window.removeEventListener("pointermove", update);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", update);
    window.addEventListener("pointerup", stop);
  }

  _onHuePointer(e) {
    const slider = e.currentTarget;
    const update = (ev) => {
      const rect = slider.getBoundingClientRect();
      const x = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
      this.hue = x * 360;
      this._emit();
    };
    this._dragging = true;
    update(e);
    const stop = () => {
      this._dragging = false;
      window.removeEventListener("pointermove", update);
      window.removeEventListener("pointerup", stop);
    };
    window.addEventListener("pointermove", update);
    window.addEventListener("pointerup", stop);
  }

  _onHexKey(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      this._commitHex();
    }
  }

  _commitHex() {
    const m = HEX_RE.exec(this.hexDraft.trim());
    if (!m) {
      // Restore the input to the live value if the typed value isn't valid.
      this.hexDraft = String(this.value || "#ffffff").toUpperCase();
      return;
    }
    this._applyHex("#" + m[1].toLowerCase());
  }

  _applyHex(hex) {
    const { h, s, v } = hexToHsv(hex);
    if (s > 0) this.hue = h;
    this.sat = s;
    this.val = v;
    this.hexDraft = hex.toUpperCase();
    this._emit();
  }

  _emit() {
    const next = hsvToHex(this.hue, this.sat, this.val);
    this.value = next;
    this.hexDraft = next.toUpperCase();
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { value: next },
        bubbles: true,
        composed: true,
      })
    );
  }
}

customElements.define("id-color-picker", IdColorPicker);
