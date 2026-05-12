import { LitElement, html, css } from "lit";
import "../components/index.js";
import {
  isPushing,
  onPushStateChange,
  pushSource,
  runWithPushLock,
} from "../lib/push-state.js";

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
      position: relative;
    }
    /* Single unified now-cursor that spans every row vertically. Uses the
       same column layout as .timeline-row so the line's left% maps to the
       track column exactly the way per-row markers do. */
    .now-overlay {
      position: absolute;
      inset: 0;
      display: grid;
      grid-template-columns: 160px 1fr;
      gap: 12px;
      pointer-events: none;
    }
    @media (max-width: 700px) {
      .now-overlay { display: none; }
    }
    .now-overlay > .spacer {}
    .now-overlay > .track-area {
      position: relative;
    }
    .now-overlay .now-line {
      position: absolute;
      top: -2px;
      bottom: -2px;
      width: 2px;
      background: var(--id-fg, #1a1612);
      transform: translateX(-1px);
    }
    .now-overlay .now-line::before {
      content: "";
      position: absolute;
      top: -5px;
      left: -4px;
      width: 10px;
      height: 10px;
      background: var(--id-fg, #1a1612);
      border-radius: 50%;
    }
    .now-overlay .now-time {
      position: absolute;
      top: -22px;
      transform: translateX(-50%);
      font-size: 11px;
      font-weight: 600;
      font-variant-numeric: tabular-nums;
      color: var(--id-fg, #1a1612);
      background: var(--id-surface, #ffffff);
      padding: 1px 6px;
      border-radius: 999px;
      border: 1px solid var(--id-divider, #c8b89b);
      white-space: nowrap;
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
    /* Per-row swatch dot sits in front of the schedule name so it's easy
       to match the label to its bar on the timeline. --row-color is set
       inline on the .timeline-row by _renderTimelineRow. */
    .row-dot {
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 3px;
      background: var(--row-color, var(--id-accent, #d97757));
      margin-right: 8px;
      vertical-align: middle;
      flex-shrink: 0;
    }
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
    /* Time-of-day window: tinted by the row's colour so two overlapping
       windows on adjacent rows don't visually merge. */
    .timeline-track .window {
      position: absolute;
      top: 0;
      bottom: 0;
      background: color-mix(in oklab, var(--row-color, #7ea16b) 14%, transparent);
      border-left: 1px solid color-mix(in oklab, var(--row-color, #7ea16b) 55%, transparent);
      border-right: 1px solid color-mix(in oklab, var(--row-color, #7ea16b) 55%, transparent);
    }
    .timeline-track .marker {
      position: absolute;
      top: 4px;
      bottom: 4px;
      width: 3px;
      background: var(--row-color, var(--id-accent, #d97757));
      border-radius: 2px;
      transition: opacity 120ms ease;
    }
    .timeline-track .marker.past { opacity: 0.35; }
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
    this.globalPushing = isPushing();
    this.globalPushSource = pushSource();
    this._unsubPushState = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    await this._load();
    // Re-tick the timeline cursor every minute so the "now" indicator moves.
    this._tickInterval = setInterval(() => {
      this.now = new Date();
    }, 60_000);
    this._unsubPushState = onPushStateChange(() => {
      this.globalPushing = isPushing();
      this.globalPushSource = pushSource();
    });
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._tickInterval) clearInterval(this._tickInterval);
    this._unsubPushState?.();
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
    if (isPushing()) {
      this.error = "Another push is already in flight. Wait for it to finish.";
      return;
    }
    this.firing = s.id;
    try {
      await runWithPushLock(`schedule:${s.id}`, async () => {
        const res = await fetch(`/api/schedules/${encodeURIComponent(s.id)}/fire`, {
          method: "POST",
        });
        const body = await res.json();
        if (!res.ok || body.status !== "sent") {
          this.error = `${s.name}: ${body.error || body.status}`;
        }
      });
    } catch (err) {
      this.error = err.message;
    } finally {
      this.firing = null;
    }
  }

  // Fixed timeline window: a day-band from DAY_START_H to (DAY_START_H + 24)
  // wrapped at 24h. With DAY_START_H = 6, that's "06:00 today → 05:59
  // tomorrow" — schedule markers stay anchored to their actual times of day,
  // and the now-cursor slides through the band.
  static DAY_START_H = 6;

  // X-axis position (0–100) of an HH:MM within the fixed day-band.
  _xPctFromTime(h, m) {
    const start = SchedulesPage.DAY_START_H * 60;
    const shifted = (h * 60 + m - start + 1440) % 1440;
    return (shifted / 1440) * 100;
  }

  _isPastTime(h, m) {
    return (
      this._xPctFromTime(h, m) <
      this._xPctFromTime(this.now.getHours(), this.now.getMinutes())
    );
  }

  // ISO weekday (0=Mon..6=Sun) of the day-band we're currently inside.
  // At 04:00 the active band actually started at 06:00 yesterday, so we
  // back up a day before reading the weekday.
  _bandDow() {
    const dt = new Date(this.now);
    if (dt.getHours() < SchedulesPage.DAY_START_H) {
      dt.setDate(dt.getDate() - 1);
    }
    return (dt.getDay() + 6) % 7;
  }

  // Each schedule's fires within the 24h band, as {h, m, past} entries.
  _projectFires(schedule) {
    if (schedule.type === "oneshot") {
      if (!schedule.fires_at) return [];
      const fa = new Date(schedule.fires_at);
      const h = fa.getHours();
      const m = fa.getMinutes();
      return [{ h, m, past: this._isPastTime(h, m) }];
    }
    const allowedDow = schedule.days_of_week || [0, 1, 2, 3, 4, 5, 6];
    if (!allowedDow.includes(this._bandDow())) return [];
    const interval = Math.max(1, Number(schedule.interval_minutes) || 60);
    const parse = (v) => {
      const [h, m] = v.split(":").map(Number);
      return h * 60 + m;
    };
    const startMin = parse(schedule.time_of_day_start || "00:00");
    const endMin = parse(schedule.time_of_day_end || "23:59");
    const fires = [];
    if (startMin <= endMin) {
      for (let mm = startMin; mm <= endMin; mm += interval) fires.push(mm);
    } else {
      for (let mm = startMin; mm < 1440; mm += interval) fires.push(mm);
      for (let mm = 0; mm <= endMin; mm += interval) fires.push(mm);
    }
    return fires.map((mm) => {
      const h = Math.floor(mm / 60);
      const m = mm % 60;
      return { h, m, past: this._isPastTime(h, m) };
    });
  }

  // 10-colour categorical palette tuned for the timeline. Picked for mutual
  // contrast on both light and dark themes plus reasonable Spectra 6 dither
  // performance — every colour stays distinct after quantizing to the panel.
  static ROW_PALETTE = [
    "#d97757", // orange
    "#3c6e91", // deep blue
    "#7ea16b", // sage green
    "#b34a5a", // rose
    "#6a4c93", // purple
    "#2a8a8a", // teal
    "#d4a957", // gold
    "#c97c70", // terracotta
    "#4a72b8", // sky blue
    "#9b3838", // brick red
  ];

  // Stable colour per schedule id — same id always gets the same swatch
  // even as schedules are added/removed/reordered.
  _colorFor(scheduleId) {
    if (!scheduleId) return SchedulesPage.ROW_PALETTE[0];
    let h = 2166136261 >>> 0;
    for (let i = 0; i < scheduleId.length; i++) {
      h = Math.imul(h ^ scheduleId.charCodeAt(i), 16777619) >>> 0;
    }
    return SchedulesPage.ROW_PALETTE[h % SchedulesPage.ROW_PALETTE.length];
  }

  _renderTimelineRow(schedule) {
    const fires = schedule.enabled ? this._projectFires(schedule) : [];
    const xPct = (v) => Math.max(0, Math.min(100, v));
    const color = this._colorFor(schedule.id);
    // Time-of-day window highlight, also pinned to fixed times of day.
    // If the window straddles the band's 06:00 cut it renders as two pieces.
    let windowBlocks = null;
    if (schedule.enabled && (schedule.time_of_day_start || schedule.time_of_day_end)) {
      const parse = (v) => {
        const [h, m] = v.split(":").map(Number);
        return [h, m];
      };
      const [sh, sm] = parse(schedule.time_of_day_start || "00:00");
      const [eh, em] = parse(schedule.time_of_day_end || "23:59");
      const a = this._xPctFromTime(sh, sm);
      const b = this._xPctFromTime(eh, em);
      windowBlocks =
        b >= a
          ? [html`<div class="window" style="left:${xPct(a)}%; right:${100 - xPct(b)}%"></div>`]
          : [
              html`<div class="window" style="left:${xPct(a)}%; right:0%"></div>`,
              html`<div class="window" style="left:0%; right:${100 - xPct(b)}%"></div>`,
            ];
    }
    return html`
      <div class="timeline-row" style="--row-color: ${color};">
        <div class="timeline-label ${schedule.enabled ? "" : "dim"}">
          <span class="row-dot" aria-hidden="true"></span>
          ${schedule.name}
          <span style="color: var(--id-fg-soft); font-size: 11px;"> · ${schedule.page_id}</span>
        </div>
        <div class="timeline-track">
          ${windowBlocks}
          ${fires.map(
            ({ h, m, past }) => html`
              <div
                class="marker ${past ? "past" : ""}"
                style="left: calc(${xPct(this._xPctFromTime(h, m))}% - 1.5px);"
                title="${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}"
              ></div>
            `
          )}
        </div>
      </div>
    `;
  }

  _renderTimeline() {
    const enabledSchedules = this.schedules.filter((s) => s.enabled);
    // Axis: 8 ticks spaced 3h apart, anchored to the band start (06:00).
    const ticks = Array.from({ length: 8 }, (_, i) => {
      const h = (SchedulesPage.DAY_START_H + i * 3) % 24;
      return `${String(h).padStart(2, "0")}:00`;
    });
    const lastPush = this.history && this.history.length ? this.history[0] : null;
    const liveDashboard = lastPush?.status === "sent" ? lastPush.page_id : null;
    return html`
      <div class="timeline-card">
        <div class="timeline-head">
          <h2><i class="ph ph-clock-clockwise" style="color: var(--id-accent); margin-right: 4px;"></i>Day · ${String(SchedulesPage.DAY_START_H).padStart(2, "0")}:00 → ${String(SchedulesPage.DAY_START_H).padStart(2, "0")}:00</h2>
          <span class="now-label">
            now ${this.now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
          </span>
          ${liveDashboard
            ? html`<span class="live"><i class="ph ph-broadcast"></i> on panel: ${liveDashboard}</span>`
            : html`<span class="now-label">no recent push</span>`}
        </div>
        ${enabledSchedules.length === 0
          ? html`<p class="timeline-empty">No enabled schedules to plot.</p>`
          : (() => {
              const nowX = this._xPctFromTime(
                this.now.getHours(),
                this.now.getMinutes(),
              );
              const nowLabel = this.now.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              });
              return html`
                <div class="timeline-rows">
                  ${enabledSchedules.map((s) => this._renderTimelineRow(s))}
                  <div class="now-overlay">
                    <div class="spacer"></div>
                    <div class="track-area">
                      <div class="now-line" style="left: ${nowX}%;">
                        <span class="now-time">${nowLabel}</span>
                      </div>
                    </div>
                  </div>
                </div>
                <div class="timeline-axis">
                  <span></span>
                  <div class="ticks">${ticks.map((t) => html`<span>${t}</span>`)}</div>
                </div>
              `;
            })()}
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
          <id-button
            @click=${() => this._fireNow(s)}
            ?disabled=${this.firing === s.id ||
              (this.globalPushing && this.firing !== s.id)}
            title=${this.globalPushing && this.firing !== s.id
              ? `Another push is in flight${this.globalPushSource ? ` (${this.globalPushSource})` : ""}`
              : "Fire this schedule once, now"}
          >
            <i class="ph ph-paper-plane-tilt"></i>
            ${this.firing === s.id
              ? "Firing…"
              : this.globalPushing
                ? "Push in flight"
                : "Fire now"}
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
