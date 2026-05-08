import { LitElement, html, css } from "lit";
import "../components/index.js";

const DAYS = [
  { id: 0, label: "Mon", short: "M" },
  { id: 1, label: "Tue", short: "T" },
  { id: 2, label: "Wed", short: "W" },
  { id: 3, label: "Thu", short: "T" },
  { id: 4, label: "Fri", short: "F" },
  { id: 5, label: "Sat", short: "S" },
  { id: 6, label: "Sun", short: "S" },
];

function slugify(name) {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 32);
}

function newSchedule(pageId) {
  return {
    id: "",
    name: "",
    page_id: pageId || "",
    enabled: true,
    type: "interval",
    interval_minutes: 60,
    fires_at: null,
    days_of_week: [0, 1, 2, 3, 4, 5, 6],
    time_of_day_start: null,
    time_of_day_end: null,
    priority: 0,
    dither: "floyd-steinberg",
  };
}

class SchedulesPage extends LitElement {
  static properties = {
    schedules: { state: true },
    pages: { state: true },
    history: { state: true },
    listener: { state: true },
    now: { state: true },
    error: { state: true },
    editing: { state: true },
    saving: { state: true },
    firing: { state: true },
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
    h1 {
      margin: 0 0 4px;
      font-size: 22px;
    }
    p.lede {
      margin: 0 0 16px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 0 0 12px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr auto auto auto;
      gap: 12px;
      align-items: center;
      padding: 12px 14px;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      background: var(--id-surface, #ffffff);
      margin-bottom: 8px;
    }
    .row.disabled {
      opacity: 0.55;
    }
    .name { font-weight: 600; }
    .meta {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .meta .ph {
      margin-right: 0.3em;
      color: var(--id-accent, #d97757);
    }
    .actions { display: flex; gap: 6px; }
    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    /* Toggle switch — replaces native checkbox styling. */
    .toggle input[type="checkbox"] {
      appearance: none;
      -webkit-appearance: none;
      width: 36px;
      height: 20px;
      background: var(--id-divider, #c8b89b);
      border-radius: 999px;
      position: relative;
      cursor: pointer;
      margin: 0;
      flex-shrink: 0;
      transition: background 150ms ease;
    }
    .toggle input[type="checkbox"]::before {
      content: "";
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      border-radius: 50%;
      background: #ffffff;
      box-shadow: 0 1px 3px rgb(0 0 0 / 0.2);
      transition: transform 150ms ease;
    }
    .toggle input[type="checkbox"]:checked {
      background: var(--id-accent, #b06750);
    }
    .toggle input[type="checkbox"]:checked::before {
      transform: translateX(16px);
    }
    .toggle input[type="checkbox"]:focus-visible {
      outline: 2px solid var(--id-accent, #b06750);
      outline-offset: 2px;
    }
    .form {
      display: grid;
      gap: 12px;
    }
    .form-row {
      display: grid;
      grid-template-columns: 220px 1fr;
      gap: 12px;
      align-items: center;
    }
    @media (max-width: 700px) {
      .form-row { grid-template-columns: 1fr; gap: 4px; }
      .row { grid-template-columns: 1fr; }
    }
    label.field {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      font-weight: 500;
    }
    input[type="text"], input[type="number"], input[type="datetime-local"], input[type="time"], select {
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
    .day-picker {
      display: flex;
      gap: 4px;
      flex-wrap: wrap;
    }
    .day-picker button {
      min-width: 38px;
      min-height: var(--id-control-h, 40px);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      background: transparent;
      font: inherit;
      font-weight: 500;
      cursor: pointer;
    }
    .day-picker button[aria-pressed="true"] {
      background: var(--id-accent, #d97757);
      color: white;
      border-color: transparent;
    }
    .toolbar {
      display: flex;
      gap: 8px;
      margin-top: 16px;
      flex-wrap: wrap;
    }
    .empty {
      text-align: center;
      padding: 32px 12px;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
    }
    .error {
      color: var(--id-danger, #c97c70);
      padding: 8px 0;
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
    .badge {
      padding: 2px 8px;
      border-radius: 999px;
      background: var(--id-surface2, #f5e8d8);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Timeline */
    .timeline-card {
      border: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface, #ffffff);
      border-radius: 10px;
      padding: 16px 18px;
      margin-bottom: 24px;
    }
    .timeline-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
      flex-wrap: wrap;
    }
    .timeline-head h2 {
      margin: 0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
    }
    .timeline-head .now-label {
      font-size: 13px;
      font-variant-numeric: tabular-nums;
      color: var(--id-fg-soft, #5a4f44);
    }
    .timeline-head .live {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 10px;
      border-radius: 999px;
      background: var(--id-surface2, #f5e8d8);
      font-size: 12px;
      font-weight: 600;
    }
    .timeline-head .live .ph { color: var(--id-accent, #d97757); }
    .timeline-rows {
      display: grid;
      gap: 6px;
    }
    .timeline-row {
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 12px;
      align-items: center;
    }
    @media (max-width: 700px) {
      .timeline-row { grid-template-columns: 1fr; gap: 4px; }
    }
    .timeline-label {
      font-size: 13px;
      font-weight: 500;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .timeline-label.dim { opacity: 0.5; }
    .timeline-track {
      position: relative;
      height: 22px;
      border-radius: 4px;
      background: linear-gradient(
        to right,
        var(--id-surface2) 0%,
        var(--id-surface2) 100%
      );
      overflow: hidden;
      border: 1px solid var(--id-divider, #c8b89b);
    }
    .timeline-track .window {
      position: absolute;
      top: 0;
      bottom: 0;
      background: rgba(125, 166, 112, 0.12);
      border-left: 1px solid rgba(125, 166, 112, 0.4);
      border-right: 1px solid rgba(125, 166, 112, 0.4);
    }
    .timeline-track .marker {
      position: absolute;
      top: 4px;
      bottom: 4px;
      width: 3px;
      background: var(--id-accent, #d97757);
      border-radius: 2px;
      transition: opacity 120ms ease;
    }
    .timeline-track .marker.past { opacity: 0.35; }
    .timeline-track .now {
      position: absolute;
      top: -2px;
      bottom: -2px;
      width: 2px;
      background: var(--id-fg, #1a1612);
      pointer-events: none;
    }
    .timeline-track .now::before {
      content: "";
      position: absolute;
      top: -4px;
      left: -4px;
      width: 10px;
      height: 10px;
      background: var(--id-fg, #1a1612);
      border-radius: 50%;
    }
    .timeline-axis {
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 12px;
      margin-top: 4px;
    }
    @media (max-width: 700px) {
      .timeline-axis { grid-template-columns: 1fr; }
      .timeline-axis > span:first-child { display: none; }
    }
    .timeline-axis .ticks {
      display: grid;
      grid-template-columns: repeat(8, 1fr);
      font-size: 10px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .timeline-axis .ticks span {
      border-left: 1px solid var(--id-divider, #c8b89b);
      padding-left: 4px;
      font-variant-numeric: tabular-nums;
    }
    .timeline-axis .ticks span:first-child { border-left: 0; }
    .timeline-empty {
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      padding: 12px 0;
    }
  `;

  constructor() {
    super();
    this.schedules = [];
    this.pages = [];
    this.history = [];
    this.listener = null;
    this.now = new Date();
    this.error = null;
    this.editing = null; // null or schedule object being edited
    this.saving = false;
    this.firing = null; // id of schedule currently firing
    this._tickInterval = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._load();
    // Re-tick the timeline cursor every minute so the "now" indicator moves.
    this._tickInterval = setInterval(() => {
      this.now = new Date();
    }, 60_000);
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._tickInterval) clearInterval(this._tickInterval);
  }

  async _load() {
    try {
      const [schedulesRes, pagesRes, historyRes, listenerRes] = await Promise.all([
        fetch("/api/schedules"),
        fetch("/api/pages"),
        fetch("/api/history?limit=10"),
        fetch("/api/listener/status"),
      ]);
      this.schedules = await schedulesRes.json();
      this.pages = await pagesRes.json();
      this.history = await historyRes.json();
      this.listener = await listenerRes.json();
    } catch (err) {
      this.error = err.message;
    }
  }

  _startNew() {
    this.editing = newSchedule(this.pages[0]?.id || "");
  }

  _edit(s) {
    this.editing = JSON.parse(JSON.stringify(s));
  }

  _cancel() {
    this.editing = null;
    this.error = null;
  }

  async _save() {
    this.saving = true;
    this.error = null;
    const draft = { ...this.editing };
    if (!draft.id) draft.id = slugify(draft.name) || `sched-${Date.now()}`;
    if (draft.type === "interval") {
      draft.fires_at = null;
    } else {
      draft.interval_minutes = null;
    }
    try {
      const res = await fetch(`/api/schedules/${encodeURIComponent(draft.id)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(
          body.details
            ? `${body.error}: ${body.details.map((d) => d.msg).join("; ")}`
            : body.error || `HTTP ${res.status}`
        );
      }
      this.editing = null;
      await this._load();
    } catch (err) {
      this.error = err.message;
    } finally {
      this.saving = false;
    }
  }

  async _delete(s) {
    if (!confirm(`Delete schedule "${s.name}"?`)) return;
    try {
      await fetch(`/api/schedules/${encodeURIComponent(s.id)}`, { method: "DELETE" });
      await this._load();
    } catch (err) {
      this.error = err.message;
    }
  }

  async _toggleEnabled(s) {
    const updated = { ...s, enabled: !s.enabled };
    await fetch(`/api/schedules/${encodeURIComponent(s.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updated),
    });
    await this._load();
  }

  async _fireNow(s) {
    this.firing = s.id;
    try {
      const res = await fetch(`/api/schedules/${encodeURIComponent(s.id)}/fire`, {
        method: "POST",
      });
      const body = await res.json();
      if (!res.ok || body.status !== "sent") {
        this.error = `${s.name}: ${body.error || body.status}`;
      }
    } catch (err) {
      this.error = err.message;
    } finally {
      this.firing = null;
    }
  }

  // Compute the next ~24h of fire times for an interval/oneshot schedule, in
  // hour fractions [0, 24]. Returns ordered (relative-hours-from-now)
  // for placing markers on the timeline.
  _projectFires(schedule) {
    const out = [];
    const now = this.now;
    const horizonMs = 24 * 3600 * 1000;
    const isToday = (d) => {
      const dow = (d.getDay() + 6) % 7; // JS: 0=Sun → ISO 0=Mon
      return (schedule.days_of_week || [0, 1, 2, 3, 4, 5, 6]).includes(dow);
    };
    const inWindow = (d) => {
      if (!schedule.time_of_day_start && !schedule.time_of_day_end) return true;
      const hhmm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
      const start = schedule.time_of_day_start || "00:00";
      const end = schedule.time_of_day_end || "23:59";
      if (start <= end) return hhmm >= start && hhmm <= end;
      return hhmm >= start || hhmm <= end; // wrap
    };
    if (schedule.type === "oneshot") {
      const fires = schedule.fires_at ? new Date(schedule.fires_at) : null;
      if (fires) {
        const offsetH = (fires.getTime() - now.getTime()) / 3600000;
        if (offsetH >= -1 && offsetH <= 24) out.push(offsetH);
      }
      return out;
    }
    const intervalMin = Number(schedule.interval_minutes) || 60;
    let cursor = new Date(now.getTime());
    let safetyMax = Math.ceil((24 * 60) / Math.max(1, intervalMin)) + 5;
    while (safetyMax-- > 0) {
      const offsetH = (cursor.getTime() - now.getTime()) / 3600000;
      if (offsetH > 24) break;
      if (isToday(cursor) && inWindow(cursor)) out.push(offsetH);
      cursor = new Date(cursor.getTime() + intervalMin * 60_000);
    }
    return out;
  }

  _renderTimelineRow(schedule) {
    const fires = schedule.enabled ? this._projectFires(schedule) : [];
    const xPct = (offsetH) => Math.max(0, Math.min(100, (offsetH / 24) * 100));
    // Time-of-day window highlight
    let windowBlock = null;
    if (schedule.enabled && (schedule.time_of_day_start || schedule.time_of_day_end)) {
      const startMins = (() => {
        const v = schedule.time_of_day_start || "00:00";
        const [h, m] = v.split(":").map(Number);
        return h * 60 + m;
      })();
      const endMins = (() => {
        const v = schedule.time_of_day_end || "23:59";
        const [h, m] = v.split(":").map(Number);
        return h * 60 + m;
      })();
      const nowMins = this.now.getHours() * 60 + this.now.getMinutes();
      // Convert to "hours from now": startOffsetH = (startMins - nowMins)/60 (today)
      // For wrap-around windows, render as up to two blocks.
      const startOffsetH = (startMins - nowMins) / 60;
      const endOffsetH = (endMins - nowMins) / 60;
      if (startMins <= endMins) {
        const a = startOffsetH < 0 ? 0 : startOffsetH;
        const b = endOffsetH < 0 ? 0 : endOffsetH;
        if (b > a)
          windowBlock = html`<div class="window" style="left:${xPct(a)}%; right:${100 - xPct(b)}%"></div>`;
      }
    }
    return html`
      <div class="timeline-row">
        <div class="timeline-label ${schedule.enabled ? "" : "dim"}">
          ${schedule.name}
          <span style="color: var(--id-fg-soft); font-size: 11px;"> · ${schedule.page_id}</span>
        </div>
        <div class="timeline-track">
          ${windowBlock}
          ${fires.map(
            (offsetH) => html`
              <div
                class="marker ${offsetH < 0 ? "past" : ""}"
                style="left: calc(${xPct(offsetH)}% - 1.5px);"
                title="+${offsetH.toFixed(1)}h"
              ></div>
            `
          )}
          <div class="now" style="left: 0;"></div>
        </div>
      </div>
    `;
  }

  _renderTimeline() {
    const enabledSchedules = this.schedules.filter((s) => s.enabled);
    const ticks = Array.from({ length: 8 }, (_, i) => {
      const offsetH = i * 3;
      const t = new Date(this.now.getTime() + offsetH * 3600_000);
      return `${String(t.getHours()).padStart(2, "0")}:00`;
    });
    const lastPush = this.history && this.history.length ? this.history[0] : null;
    const liveDashboard = lastPush?.status === "sent" ? lastPush.page_id : null;
    return html`
      <div class="timeline-card">
        <div class="timeline-head">
          <h2><i class="ph ph-clock-clockwise" style="color: var(--id-accent); margin-right: 4px;"></i>Next 24h</h2>
          <span class="now-label">
            now ${this.now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          ${liveDashboard
            ? html`<span class="live"><i class="ph ph-broadcast"></i> on panel: ${liveDashboard}</span>`
            : html`<span class="now-label">no recent push</span>`}
        </div>
        ${enabledSchedules.length === 0
          ? html`<p class="timeline-empty">No enabled schedules to plot.</p>`
          : html`
              <div class="timeline-rows">
                ${enabledSchedules.map((s) => this._renderTimelineRow(s))}
              </div>
              <div class="timeline-axis">
                <span></span>
                <div class="ticks">${ticks.map((t) => html`<span>${t}</span>`)}</div>
              </div>
            `}
      </div>
    `;
  }

  _renderRow(s) {
    const dowSet = new Set(s.days_of_week || []);
    const allDays = dowSet.size === 7;
    const dayLabel = allDays
      ? "Every day"
      : DAYS.filter((d) => dowSet.has(d.id))
          .map((d) => d.label)
          .join(", ");
    return html`
      <div class="row ${!s.enabled ? "disabled" : ""}">
        <div>
          <div class="name">${s.name} <span class="badge">${s.type}</span></div>
          <div class="meta">
            <span><i class="ph ph-cube"></i>${s.page_id}</span>
            ${s.type === "interval"
              ? html`<span><i class="ph ph-clock-clockwise"></i>every ${s.interval_minutes} min</span>`
              : html`<span><i class="ph ph-calendar"></i>${s.fires_at}${s.fired ? " (fired)" : ""}</span>`}
            <span><i class="ph ph-calendar-blank"></i>${dayLabel}</span>
            ${s.priority
              ? html`<span><i class="ph ph-arrow-up"></i>priority ${s.priority}</span>`
              : null}
          </div>
        </div>
        <label class="toggle">
          <input
            type="checkbox"
            ?checked=${s.enabled}
            @change=${() => this._toggleEnabled(s)}
          />
          ${s.enabled ? "On" : "Off"}
        </label>
        <div class="actions">
          <id-button @click=${() => this._fireNow(s)} ?disabled=${this.firing === s.id}>
            <i class="ph ph-paper-plane-tilt"></i>
            ${this.firing === s.id ? "Firing…" : "Fire now"}
          </id-button>
        </div>
        <div class="actions">
          <id-button @click=${() => this._edit(s)}>
            <i class="ph ph-pencil-simple"></i>
          </id-button>
          <id-button variant="danger" @click=${() => this._delete(s)}>
            <i class="ph ph-trash"></i>
          </id-button>
        </div>
      </div>
    `;
  }

  _renderEditor() {
    const e = this.editing;
    const toggleDay = (dayId) => {
      const set = new Set(e.days_of_week || []);
      if (set.has(dayId)) set.delete(dayId);
      else set.add(dayId);
      this.editing = { ...e, days_of_week: [...set].sort((a, b) => a - b) };
    };
    return html`
      <id-card heading=${e.id ? `Edit "${e.name || e.id}"` : "New schedule"}>
        <div class="form">
          <div class="form-row">
            <label class="field">Name</label>
            <input
              type="text"
              .value=${e.name}
              placeholder="e.g. Morning weather"
              @input=${(ev) => (this.editing = { ...e, name: ev.target.value })}
            />
          </div>
          <div class="form-row">
            <label class="field">Page</label>
            <select
              @change=${(ev) => (this.editing = { ...e, page_id: ev.target.value })}
            >
              ${this.pages.map(
                (p) => html`<option value=${p.id} ?selected=${p.id === e.page_id}>${p.name} (${p.id})</option>`
              )}
            </select>
          </div>
          <div class="form-row">
            <label class="field">Type</label>
            <select
              @change=${(ev) => (this.editing = { ...e, type: ev.target.value })}
            >
              <option value="interval" ?selected=${e.type === "interval"}>Interval (every N minutes)</option>
              <option value="oneshot" ?selected=${e.type === "oneshot"}>Daily (once a day at this time)</option>
            </select>
          </div>
          ${e.type === "interval"
            ? html`
                <div class="form-row">
                  <label class="field">Every (minutes)</label>
                  <input
                    type="number"
                    min="1"
                    max="10080"
                    .value=${String(e.interval_minutes ?? 60)}
                    @input=${(ev) =>
                      (this.editing = { ...e, interval_minutes: Number(ev.target.value) })}
                  />
                </div>
                <div class="form-row">
                  <label class="field">Days of week</label>
                  <div class="day-picker">
                    ${DAYS.map(
                      (d) => html`
                        <button
                          type="button"
                          aria-pressed=${(e.days_of_week || []).includes(d.id) ? "true" : "false"}
                          @click=${() => toggleDay(d.id)}
                        >
                          ${d.short}
                        </button>
                      `
                    )}
                  </div>
                </div>
                <div class="form-row">
                  <label class="field">Time-of-day window</label>
                  <div style="display:flex;gap:8px;align-items:center;">
                    <input
                      type="time"
                      .value=${e.time_of_day_start || ""}
                      @input=${(ev) =>
                        (this.editing = { ...e, time_of_day_start: ev.target.value || null })}
                      style="flex:1;"
                    />
                    <span style="color:var(--id-fg-soft);">to</span>
                    <input
                      type="time"
                      .value=${e.time_of_day_end || ""}
                      @input=${(ev) =>
                        (this.editing = { ...e, time_of_day_end: ev.target.value || null })}
                      style="flex:1;"
                    />
                  </div>
                </div>
              `
            : html`
                <div class="form-row">
                  <label class="field">Fires at</label>
                  <input
                    type="time"
                    .value=${(e.fires_at || "").slice(11, 16)}
                    @input=${(ev) => {
                      // Build a datetime with today's date; only the time
                      // portion matters for daily schedules.
                      const t = ev.target.value;
                      if (!t) return;
                      const today = new Date();
                      const yyyy = today.getFullYear();
                      const mm = String(today.getMonth() + 1).padStart(2, "0");
                      const dd = String(today.getDate()).padStart(2, "0");
                      this.editing = { ...e, fires_at: `${yyyy}-${mm}-${dd}T${t}` };
                    }}
                  />
                </div>
              `}
          <div class="form-row">
            <label class="field">Priority</label>
            <input
              type="number"
              .value=${String(e.priority || 0)}
              @input=${(ev) => (this.editing = { ...e, priority: Number(ev.target.value) || 0 })}
            />
          </div>
          <div class="form-row">
            <label class="field">Dither</label>
            <select
              @change=${(ev) => (this.editing = { ...e, dither: ev.target.value })}
            >
              <option value="floyd-steinberg" ?selected=${e.dither === "floyd-steinberg"}>Floyd–Steinberg</option>
              <option value="none" ?selected=${e.dither === "none"}>None</option>
            </select>
          </div>
        </div>
        ${this.error ? html`<p class="error">${this.error}</p>` : null}
        <div class="toolbar">
          <id-button variant="primary" ?disabled=${this.saving} @click=${() => this._save()}>
            <i class="ph ph-floppy-disk"></i> ${this.saving ? "Saving…" : "Save"}
          </id-button>
          <id-button @click=${() => this._cancel()}>
            <i class="ph ph-x"></i> Cancel
          </id-button>
        </div>
      </id-card>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="schedules"></id-nav>
      <div class="container">
      <h1>Schedules</h1>
      <p class="lede">
        Trigger pushes on a recurring interval or at a specific time.
        Schedules run in the background as long as the companion is up.
      </p>

      ${this.schedules.length > 0 ? this._renderTimeline() : null}

      ${this.editing ? this._renderEditor() : null}

      <div class="section-head">
        <span>${this.schedules.length} schedule${this.schedules.length === 1 ? "" : "s"}</span>
        ${!this.editing
          ? html`<id-button variant="primary" @click=${() => this._startNew()}>
              <i class="ph ph-plus"></i> New schedule
            </id-button>`
          : null}
      </div>

      ${!this.editing && this.error ? html`<p class="error">${this.error}</p>` : null}

      ${this.schedules.length === 0
        ? html`<div class="empty">No schedules yet.</div>`
        : this.schedules.map((s) => this._renderRow(s))}
      </div>
    `;
  }
}

customElements.define("schedules-page", SchedulesPage);
document.body.append(document.createElement("schedules-page"));
