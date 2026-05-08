import { LitElement, html, css } from "lit";

// Modern datetime picker. Click the trigger button to open a popover with
// a calendar grid + 24-hour time inputs. Emits a `change` event with
// detail.value as an ISO-ish "YYYY-MM-DDTHH:MM" string (matches the
// browser's <input type="datetime-local"> contract so callers can
// drop-in replace).

const DAYS = ["S", "M", "T", "W", "T", "F", "S"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function pad(n) {
  return String(n).padStart(2, "0");
}

function parseValue(value) {
  // "YYYY-MM-DDTHH:MM" or "" / null. Returns Date in local time, or null.
  if (!value) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value);
  if (!m) return null;
  return new Date(
    Number(m[1]),
    Number(m[2]) - 1,
    Number(m[3]),
    Number(m[4]),
    Number(m[5]),
  );
}

function formatValue(d) {
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function formatDisplay(d) {
  if (!d) return "";
  return (
    `${MONTHS[d.getMonth()].slice(0, 3)} ${d.getDate()}, ${d.getFullYear()} ` +
    `· ${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

export class IdDateTime extends LitElement {
  static properties = {
    value: { type: String },
    placeholder: { type: String },
    open: { state: true },
    cursor: { state: true }, // first-of-month Date for the visible calendar
  };

  static styles = css`
    :host {
      display: inline-block;
      width: 100%;
      position: relative;
    }
    .trigger {
      width: 100%;
      box-sizing: border-box;
      min-height: var(--id-control-h, 40px);
      padding: 0 12px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: var(--id-radius, 8px);
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      font: inherit;
      cursor: pointer;
      text-align: left;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .trigger:hover {
      border-color: var(--id-fg-soft, #5a4f44);
    }
    .trigger.open {
      border-color: var(--id-accent, #4f46e5);
    }
    .trigger.placeholder {
      color: var(--id-fg-soft, #5a4f44);
    }
    .trigger .ph {
      color: var(--id-fg-soft, #5a4f44);
      font-size: 16px;
    }
    .trigger .label {
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .pop {
      position: absolute;
      top: calc(100% + 6px);
      left: 0;
      z-index: 30;
      width: 320px;
      max-width: calc(100vw - 32px);
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: var(--id-radius, 8px);
      box-shadow: var(--id-shadow-lg, 0 12px 32px rgb(0 0 0 / 0.15));
      padding: 12px;
      box-sizing: border-box;
    }
    .month-nav {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }
    .month-nav .label {
      flex: 1;
      text-align: center;
      font-size: 14px;
      font-weight: 600;
      color: var(--id-fg, #1a1612);
    }
    .nav-btn {
      width: 28px;
      height: 28px;
      border: 0;
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      cursor: pointer;
      border-radius: 6px;
      display: inline-grid;
      place-items: center;
    }
    .nav-btn:hover {
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-fg, #1a1612);
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(7, 1fr);
      gap: 2px;
    }
    .dow {
      font-size: 11px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      padding: 4px 0;
      font-weight: 600;
      text-transform: uppercase;
    }
    .day {
      aspect-ratio: 1;
      display: grid;
      place-items: center;
      border: 0;
      background: transparent;
      color: var(--id-fg, #1a1612);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      border-radius: 6px;
    }
    .day.muted { color: var(--id-fg-soft, #5a4f44); opacity: 0.55; }
    .day:hover { background: var(--id-surface2, #f5e8d8); }
    .day.today { font-weight: 700; color: var(--id-accent, #4f46e5); }
    .day.selected {
      background: var(--id-accent, #4f46e5);
      color: var(--id-accent-fg, #ffffff);
    }
    .day.selected:hover {
      background: var(--id-accent-soft, #4338ca);
    }
    .time-row {
      display: flex;
      gap: 8px;
      align-items: center;
      margin-top: 12px;
      padding-top: 12px;
      border-top: 1px solid var(--id-divider, #c8b89b);
    }
    .time-row label {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .time-row input {
      width: 64px;
      box-sizing: border-box;
      text-align: center;
      padding: 6px 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      background: var(--id-bg, #ffffff);
      color: var(--id-fg, #1a1612);
      font: inherit;
      font-variant-numeric: tabular-nums;
    }
    .time-row input:focus {
      outline: none;
      border-color: var(--id-accent, #4f46e5);
    }
    .pop-actions {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-top: 12px;
    }
    .pop-actions button {
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: transparent;
      color: var(--id-fg, #1a1612);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
    }
    .pop-actions button:hover {
      background: var(--id-surface2, #f5e8d8);
    }
    .pop-actions .primary {
      background: var(--id-accent, #4f46e5);
      border-color: transparent;
      color: var(--id-accent-fg, #ffffff);
    }
    .pop-actions .primary:hover {
      background: var(--id-accent-soft, #4338ca);
    }
  `;

  constructor() {
    super();
    this.value = "";
    this.placeholder = "Pick a date & time";
    this.open = false;
    const initial = parseValue(this.value) || new Date();
    this.cursor = new Date(initial.getFullYear(), initial.getMonth(), 1);
    this._onDocClick = this._onDocClick.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();
    document.addEventListener("click", this._onDocClick);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener("click", this._onDocClick);
  }

  willUpdate(changed) {
    if (changed.has("value")) {
      const d = parseValue(this.value);
      if (d) this.cursor = new Date(d.getFullYear(), d.getMonth(), 1);
    }
  }

  _onDocClick(e) {
    if (!this.open) return;
    const path = e.composedPath();
    if (!path.includes(this)) this.open = false;
  }

  _toggle() {
    this.open = !this.open;
  }

  _emit(value) {
    this.value = value;
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { value },
        bubbles: true,
        composed: true,
      })
    );
  }

  _setDay(day) {
    const current = parseValue(this.value) || new Date();
    const next = new Date(
      this.cursor.getFullYear(),
      this.cursor.getMonth(),
      day,
      current.getHours(),
      current.getMinutes(),
    );
    this._emit(formatValue(next));
  }

  _setTime(field, raw) {
    const n = Math.max(0, Math.min(field === "h" ? 23 : 59, Number(raw) || 0));
    const current = parseValue(this.value) || new Date();
    const next = new Date(
      current.getFullYear(),
      current.getMonth(),
      current.getDate(),
      field === "h" ? n : current.getHours(),
      field === "m" ? n : current.getMinutes(),
    );
    this._emit(formatValue(next));
  }

  _shiftMonth(delta) {
    this.cursor = new Date(
      this.cursor.getFullYear(),
      this.cursor.getMonth() + delta,
      1,
    );
  }

  _today() {
    const now = new Date();
    this.cursor = new Date(now.getFullYear(), now.getMonth(), 1);
    const current = parseValue(this.value);
    const next = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
      current ? current.getHours() : now.getHours(),
      current ? current.getMinutes() : now.getMinutes(),
    );
    this._emit(formatValue(next));
  }

  _renderGrid() {
    const sel = parseValue(this.value);
    const today = new Date();
    const y = this.cursor.getFullYear();
    const m = this.cursor.getMonth();
    const firstDow = new Date(y, m, 1).getDay();
    const daysInMonth = new Date(y, m + 1, 0).getDate();
    const prevDays = new Date(y, m, 0).getDate();

    const cells = [];
    // Pad with previous-month tail.
    for (let i = firstDow - 1; i >= 0; i--) {
      cells.push({ d: prevDays - i, muted: true, ym: [y, m - 1] });
    }
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ d, ym: [y, m] });
    }
    // Pad to a multiple of 7 with next-month head.
    while (cells.length % 7) {
      cells.push({ d: cells.length - daysInMonth - firstDow + 1, muted: true, ym: [y, m + 1] });
    }

    return html`
      <div class="grid">
        ${DAYS.map((d) => html`<div class="dow">${d}</div>`)}
        ${cells.map((c) => {
          const isSel =
            sel &&
            !c.muted &&
            sel.getFullYear() === c.ym[0] &&
            sel.getMonth() === c.ym[1] &&
            sel.getDate() === c.d;
          const isToday =
            !c.muted &&
            today.getFullYear() === c.ym[0] &&
            today.getMonth() === c.ym[1] &&
            today.getDate() === c.d;
          return html`
            <button
              class="day ${c.muted ? "muted" : ""} ${isSel ? "selected" : ""} ${isToday ? "today" : ""}"
              ?disabled=${c.muted}
              @click=${() => !c.muted && this._setDay(c.d)}
            >
              ${c.d}
            </button>
          `;
        })}
      </div>
    `;
  }

  render() {
    const sel = parseValue(this.value);
    const display = sel ? formatDisplay(sel) : this.placeholder;
    const hh = sel ? pad(sel.getHours()) : "00";
    const mm = sel ? pad(sel.getMinutes()) : "00";
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <button
        class="trigger ${this.open ? "open" : ""} ${sel ? "" : "placeholder"}"
        @click=${this._toggle}
        type="button"
      >
        <i class="ph ph-calendar-blank"></i>
        <span class="label">${display}</span>
        <i class="ph ph-caret-down"></i>
      </button>
      ${this.open
        ? html`
            <div class="pop" @click=${(e) => e.stopPropagation()}>
              <div class="month-nav">
                <button class="nav-btn" @click=${() => this._shiftMonth(-1)} aria-label="Previous month">
                  <i class="ph ph-caret-left"></i>
                </button>
                <span class="label">
                  ${MONTHS[this.cursor.getMonth()]} ${this.cursor.getFullYear()}
                </span>
                <button class="nav-btn" @click=${() => this._shiftMonth(1)} aria-label="Next month">
                  <i class="ph ph-caret-right"></i>
                </button>
              </div>
              ${this._renderGrid()}
              <div class="time-row">
                <label>Time</label>
                <input
                  type="number"
                  min="0"
                  max="23"
                  .value=${hh}
                  aria-label="Hour"
                  @input=${(e) => this._setTime("h", e.target.value)}
                />
                <span style="color: var(--id-fg-soft);">:</span>
                <input
                  type="number"
                  min="0"
                  max="59"
                  .value=${mm}
                  aria-label="Minute"
                  @input=${(e) => this._setTime("m", e.target.value)}
                />
              </div>
              <div class="pop-actions">
                <button @click=${this._today}>Today</button>
                <button class="primary" @click=${() => (this.open = false)}>Done</button>
              </div>
            </div>
          `
        : null}
    `;
  }
}

customElements.define("id-date-time", IdDateTime);
