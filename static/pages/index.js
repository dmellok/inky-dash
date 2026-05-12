import { LitElement, html, css } from "lit";
import "../components/index.js";

class IndexPage extends LitElement {
  static properties = {
    health: { state: true },
    pages: { state: true },
    schedules: { state: true },
    history: { state: true },
    listener: { state: true },
    listenerLog: { state: true },
    error: { state: true },
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
    .hero {
      display: grid;
      grid-template-columns: 1fr;
      gap: 12px;
      padding: 28px 24px;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 12px;
      margin-bottom: 24px;
    }
    .hero h1 {
      margin: 0;
      font-size: 26px;
      letter-spacing: -0.02em;
    }
    .hero p.lede {
      margin: 0;
      color: var(--id-fg-soft, #5a4f44);
      font-size: 15px;
    }
    .hero .actions {
      display: flex;
      gap: 8px;
      margin-top: 8px;
      flex-wrap: wrap;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }
    .stat {
      padding: 16px 18px;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      display: grid;
      gap: 4px;
    }
    .stat .label {
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .stat .value {
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      font-variant-numeric: tabular-nums;
    }
    .stat .sub {
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
    }
    .stat.ok .value { color: var(--id-ok, #7da670); }
    .stat.warn .value { color: var(--id-accent, #d97757); }
    .stat.off .value { color: var(--id-fg-soft, #5a4f44); }
    .stat.error .value { color: var(--id-danger, #c97c70); }

    .columns {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }
    @media (max-width: 800px) {
      .columns { grid-template-columns: 1fr; }
    }
    .panel {
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 10px;
      padding: 16px 18px;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 10px;
    }
    .panel-head h3 {
      margin: 0;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
    }
    .panel-head a {
      font-size: 12px;
      color: var(--id-accent, #d97757);
      text-decoration: none;
    }

    ul.list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 6px;
    }
    ul.list li {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      padding: 8px 0;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      font-size: 14px;
      gap: 8px;
    }
    ul.list li:last-child { border-bottom: 0; }
    ul.list li .name { font-weight: 500; }
    ul.list li .meta { font-size: 12px; color: var(--id-fg-soft, #5a4f44); }
    ul.list li a {
      color: var(--id-accent, #d97757);
      text-decoration: none;
      font-size: 13px;
    }
    .empty-msg {
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
      padding: 8px 0;
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
    .pill.sent,
    .pill.idle { background: rgba(125, 166, 112, 0.15); color: var(--id-ok, #7da670); }
    .pill.failed,
    .pill.error,
    .pill.offline { background: rgba(201, 124, 112, 0.15); color: var(--id-danger, #c97c70); }
    .pill.busy,
    .pill.rendering { background: rgba(217, 119, 87, 0.15); color: var(--id-accent, #d97757); }
    .pill.not_found,
    .pill.unknown { background: rgba(90, 79, 68, 0.15); color: var(--id-fg-soft, #5a4f44); }

    /* Listener-log rows: pill + raw JSON payload stacked. */
    .history-row {
      display: block !important;
      padding: 0 !important;
    }
    .history-line {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      padding: 8px 0;
    }
    .payload-json {
      margin: 0;
      padding: 6px 8px;
      background: var(--id-bg, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 4px;
      font: 12px ui-monospace, "SF Mono", Menlo, monospace;
      color: var(--id-fg, #1a1612);
      overflow-x: auto;
      white-space: pre;
    }
    .footer {
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      font-size: 12px;
      margin-top: 32px;
    }
  `;

  constructor() {
    super();
    this.health = null;
    this.pages = [];
    this.schedules = [];
    this.history = [];
    this.listener = null;
    this.listenerLog = [];
    this.error = null;
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const [health, pages, schedules, history, listener, listenerLog] =
        await Promise.all([
          fetch("/healthz").then((r) => r.json()),
          fetch("/api/pages").then((r) => r.json()),
          fetch("/api/schedules").then((r) => r.json()),
          fetch("/api/history?limit=10").then((r) => r.json()),
          fetch("/api/listener/status").then((r) => r.json()),
          fetch("/api/listener/log").then((r) => r.json()),
        ]);
      this.health = health;
      this.pages = pages;
      this.schedules = schedules;
      this.history = history;
      this.listener = listener;
      this.listenerLog = Array.isArray(listenerLog) ? listenerLog : [];
    } catch (err) {
      this.error = err.message;
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

  _renderStats() {
    const widgetsLoaded = (this.health?.plugins?.loaded || []).length;
    const errors = (this.health?.plugins?.errors || []).length;
    const mqttConnected = this.health?.mqtt?.connected;
    const listenerState = this.listener?.state || "unknown";
    const lastResult = this.history?.[0]?.status;

    return html`
      <div class="stats">
        <div class="stat ${errors > 0 ? "error" : "ok"}">
          <span class="label"><i class="ph ph-puzzle-piece"></i> Plugins</span>
          <span class="value">${widgetsLoaded}</span>
          <span class="sub">${errors > 0 ? `${errors} error(s)` : "all healthy"}</span>
        </div>
        <div class="stat ${mqttConnected ? "ok" : "off"}">
          <span class="label"><i class="ph ph-broadcast"></i> MQTT</span>
          <span class="value">${mqttConnected ? "Connected" : "Off"}</span>
          <span class="sub">${mqttConnected ? "ready to push" : "set MQTT_HOST to enable"}</span>
        </div>
        <div class="stat ${listenerState === "idle" ? "ok" : listenerState === "rendering" ? "warn" : "off"}">
          <span class="label"><i class="ph ph-monitor"></i> Listener</span>
          <span class="value">${listenerState}</span>
          <span class="sub">
            ${this.listener?.received_at
              ? this._fmtAge(this.listener.received_at)
              : "no status received"}
          </span>
        </div>
        <div class="stat ${lastResult === "sent" ? "ok" : lastResult === "failed" ? "error" : "off"}">
          <span class="label"><i class="ph ph-clock-counter-clockwise"></i> Last push</span>
          <span class="value">
            ${this.history.length === 0
              ? "—"
              : this._fmtAge(this.history[0].ts)}
          </span>
          <span class="sub">
            ${this.history.length === 0
              ? "no push attempts yet"
              : `${lastResult} · ${this.history[0].page_id}`}
          </span>
        </div>
      </div>
    `;
  }

  _renderPagesList() {
    if (this.pages.length === 0) {
      return html`<p class="empty-msg">No pages yet. Open the editor to create one.</p>`;
    }
    return html`
      <ul class="list">
        ${this.pages.slice(0, 8).map(
          (p) => html`
            <li>
              <span>
                <span class="name">${p.name}</span>
                <span class="meta"> · ${p.cells.length} cell${p.cells.length === 1 ? "" : "s"}</span>
              </span>
              <a href="/editor/${encodeURIComponent(p.id)}">
                Edit <i class="ph ph-arrow-right"></i>
              </a>
            </li>
          `
        )}
      </ul>
    `;
  }

  _renderSchedulesList() {
    if (this.schedules.length === 0) {
      return html`<p class="empty-msg">No schedules. Set one up to push automatically.</p>`;
    }
    return html`
      <ul class="list">
        ${this.schedules.slice(0, 6).map(
          (s) => html`
            <li>
              <span>
                <span class="name" style="${s.enabled ? "" : "opacity:0.5;"}">${s.name}</span>
                <span class="meta">
                  · ${s.type === "interval" ? `every ${s.interval_minutes}m` : s.fires_at}
                </span>
              </span>
              <span class="meta">${s.page_id}</span>
            </li>
          `
        )}
      </ul>
    `;
  }

  _renderListenerLog() {
    if (this.listenerLog.length === 0) {
      return html`
        <p class="empty-msg">
          No status messages received from the panel listener yet. The
          listener publishes to <code>inky/status</code>; if nothing shows
          up here, the listener may not be running, or the broker topic
          doesn't match.
        </p>
      `;
    }
    return html`
      <ul class="list">
        ${this.listenerLog.map(
          (s) => html`
            <li class="history-row">
              <div class="history-line">
                <span>
                  <span class="pill ${s.state}">${s.state}</span>
                </span>
                <span class="meta">${this._fmtAge(s.received_at)}</span>
              </div>
              <pre class="payload-json">${JSON.stringify(s.raw, null, 2)}</pre>
            </li>
          `
        )}
      </ul>
    `;
  }

  render() {
    if (this.error) {
      return html`
        <id-nav current="home"></id-nav>
        <div class="container">
          <p style="color: var(--id-danger);">Failed to load: ${this.error}</p>
        </div>
      `;
    }
    if (!this.health) {
      return html`
        <id-nav current="home"></id-nav>
        <div class="container">
          <p>Loading…</p>
        </div>
      `;
    }
    return html`
      <id-nav current="home"></id-nav>
      <div class="container">
        <div class="hero">
          <h1>Inky Dash <span style="color: var(--id-fg-soft); font-weight: 400; font-size: 16px;">v${this.health.version}</span></h1>
          <p class="lede">
            Compose dashboards in the browser, render them, push to the panel.
          </p>
          <div class="actions">
            <id-button variant="primary" @click=${() => (window.location.href = "/editor")}>
              <i class="ph ph-cube"></i> Edit dashboards
            </id-button>
            <id-button @click=${() => (window.location.href = "/send")}>
              <i class="ph ph-paper-plane"></i> Send to panel
            </id-button>
            <id-button @click=${() => (window.location.href = "/schedules")}>
              <i class="ph ph-clock-clockwise"></i> Schedules
            </id-button>
          </div>
        </div>

        ${this._renderStats()}

        <div class="columns">
          <div class="panel">
            <div class="panel-head">
              <h3>Pages</h3>
              <a href="/editor">manage →</a>
            </div>
            ${this._renderPagesList()}
          </div>
          <div class="panel">
            <div class="panel-head">
              <h3>Schedules</h3>
              <a href="/schedules">manage →</a>
            </div>
            ${this._renderSchedulesList()}
          </div>
          <div class="panel" style="grid-column: 1 / -1;">
            <div class="panel-head">
              <h3>
                Listener log
                <span style="font-size: 12px; color: var(--id-fg-soft); font-weight: 400;">
                  · inky/status messages from the panel
                </span>
              </h3>
              <a href="/api/listener/log">JSON →</a>
            </div>
            ${this._renderListenerLog()}
          </div>
        </div>

        <p class="footer">
          Inky Dash v${this.health.version} · Pi listener:
          <a href="https://github.com/dmellok/inky-dash-listener" style="color: var(--id-fg-soft);">dmellok/inky-dash-listener</a>
        </p>
      </div>
    `;
  }
}

customElements.define("index-page", IndexPage);
document.body.append(document.createElement("index-page"));
