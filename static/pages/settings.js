import { LitElement, html, css } from "lit";
import "../components/index.js";

class SettingsPage extends LitElement {
  static properties = {
    plugins: { state: true },
    drafts: { state: true },
    saving: { state: true },
    saved: { state: true },
    error: { state: true },
    appSettings: { state: true },
    appDraft: { state: true },
    panelCatalog: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
    }
    .container {
      max-width: 760px;
      margin: 0 auto;
      padding: 24px 16px 48px;
    }
    h1 { margin: 0 0 4px; font-size: 22px; }
    p.lede { margin: 0 0 16px; color: var(--id-fg-soft, #5a4f44); }
    .form-row {
      display: grid;
      grid-template-columns: 200px 1fr;
      gap: 12px;
      align-items: center;
      padding: 8px 0;
    }
    @media (max-width: 700px) {
      .form-row { grid-template-columns: 1fr; gap: 4px; padding: 6px 0; }
    }
    label.field {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      font-weight: 500;
    }
    .field-help {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      margin-top: 2px;
      display: block;
    }
    input[type="text"], input[type="password"], input[type="number"], select {
      width: 100%;
      padding: 8px 10px;
      box-sizing: border-box;
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 6px;
      font: inherit;
      min-height: 38px;
      background: var(--id-bg, #ffffff);
    }
    label.checkbox {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 38px;
      font-size: 14px;
    }
    .actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
    .empty {
      padding: 24px;
      text-align: center;
      color: var(--id-fg-soft, #5a4f44);
      font-style: italic;
    }
    .secret-status {
      font-size: 11px;
      color: var(--id-fg-soft, #5a4f44);
      margin-left: 8px;
    }
    .secret-status.set { color: var(--id-ok, #7da670); }
    a.nav {
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.3em;
    }
    a.nav:hover { color: var(--id-accent, #d97757); }
    .save-status {
      font-size: 13px;
      margin-left: 8px;
    }
    .save-status.error { color: var(--id-danger, #c97c70); }
    .save-status.ok { color: var(--id-ok, #7da670); }
  `;

  constructor() {
    super();
    this.plugins = null;
    this.drafts = {};
    this.saving = {};
    this.saved = {};
    this.error = {};
    this.appSettings = null;
    this.appDraft = null;
    this.panelCatalog = [];
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const [pluginsRes, appRes, panelsRes] = await Promise.all([
        fetch("/api/settings"),
        fetch("/api/app/settings"),
        fetch("/api/app/panels"),
      ]);
      this.plugins = await pluginsRes.json();
      this.appSettings = await appRes.json();
      this.appDraft = JSON.parse(JSON.stringify(this.appSettings));
      this.panelCatalog = await panelsRes.json();

      // Initialise plugin drafts with current values (or default for missing).
      const drafts = {};
      for (const p of this.plugins) {
        drafts[p.plugin_id] = {};
        for (const f of p.settings) {
          drafts[p.plugin_id][f.name] = f.value ?? f.default ?? "";
        }
      }
      this.drafts = drafts;
    } catch (err) {
      this.plugins = [];
      this.error.global = err.message;
    }
  }

  _updateDraft(pluginId, name, value) {
    this.drafts = {
      ...this.drafts,
      [pluginId]: { ...this.drafts[pluginId], [name]: value },
    };
    // Mark as no-longer-saved so the "Saved" toast clears on edit.
    this.saved = { ...this.saved, [pluginId]: false };
  }

  async _save(pluginId) {
    this.saving = { ...this.saving, [pluginId]: true };
    this.error = { ...this.error, [pluginId]: null };
    try {
      const res = await fetch(`/api/settings/${encodeURIComponent(pluginId)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.drafts[pluginId] || {}),
      });
      if (!res.ok && res.status !== 204) {
        const body = await res.json().catch(() => ({ error: res.statusText }));
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      this.saved = { ...this.saved, [pluginId]: true };
      // Refresh server-side state so secret placeholders update.
      const refresh = await fetch("/api/settings");
      this.plugins = await refresh.json();
    } catch (err) {
      this.error = { ...this.error, [pluginId]: err.message };
    } finally {
      this.saving = { ...this.saving, [pluginId]: false };
    }
  }

  _renderField(pluginId, field) {
    const draft = this.drafts[pluginId]?.[field.name];
    const value = draft ?? "";
    const onInput = (e) =>
      this._updateDraft(pluginId, field.name, e.target.value);

    if (field.type === "boolean") {
      return html`
        <div class="form-row">
          <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
          <label class="checkbox">
            <input
              id=${`f-${pluginId}-${field.name}`}
              type="checkbox"
              ?checked=${draft === true || draft === "true"}
              @change=${(e) => this._updateDraft(pluginId, field.name, e.target.checked)}
            />
            ${draft ? "On" : "Off"}
          </label>
        </div>
      `;
    }

    if (field.type === "select" && Array.isArray(field.choices)) {
      return html`
        <div class="form-row">
          <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
          <select
            id=${`f-${pluginId}-${field.name}`}
            .value=${String(value)}
            @change=${onInput}
          >
            ${field.choices.map(
              (c) => html`<option value=${c.value} ?selected=${String(c.value) === String(value)}>${c.label}</option>`
            )}
          </select>
        </div>
      `;
    }

    if (field.secret) {
      return html`
        <div class="form-row">
          <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
          <div>
            <input
              id=${`f-${pluginId}-${field.name}`}
              type="password"
              placeholder=${field.is_set ? "(leave blank to keep)" : "(not set)"}
              .value=${value === "•••" ? "" : String(value)}
              autocomplete="new-password"
              @input=${onInput}
            />
            <span class="secret-status ${field.is_set ? "set" : ""}">
              ${field.is_set
                ? html`<i class="ph ph-check-circle"></i> stored`
                : html`<i class="ph ph-warning"></i> not configured`}
            </span>
          </div>
        </div>
      `;
    }

    if (field.type === "number") {
      return html`
        <div class="form-row">
          <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
          <input
            id=${`f-${pluginId}-${field.name}`}
            type="number"
            .value=${String(value)}
            @input=${onInput}
          />
        </div>
      `;
    }

    return html`
      <div class="form-row">
        <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
        <input
          id=${`f-${pluginId}-${field.name}`}
          type="text"
          .value=${String(value)}
          @input=${onInput}
        />
      </div>
    `;
  }

  _setApp(field, value) {
    const draft = JSON.parse(JSON.stringify(this.appDraft || {}));
    const parts = field.split(".");
    let cur = draft;
    for (let i = 0; i < parts.length - 1; i++) {
      cur[parts[i]] = cur[parts[i]] || {};
      cur = cur[parts[i]];
    }
    cur[parts[parts.length - 1]] = value;
    this.appDraft = draft;
    this.error = { ...this.error, app: null };
    this.saved = { ...this.saved, app: false };
  }

  async _saveApp() {
    this.saving = { ...this.saving, app: true };
    this.error = { ...this.error, app: null };
    try {
      const res = await fetch("/api/app/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(this.appDraft),
      });
      const body = await res.json();
      if (!res.ok) {
        const detail = body.details
          ? body.details.map((d) => `${d.loc}: ${d.msg}`).join("; ")
          : body.error || `HTTP ${res.status}`;
        throw new Error(detail);
      }
      this.appSettings = body;
      this.appDraft = JSON.parse(JSON.stringify(body));
      this.saved = { ...this.saved, app: true };
    } catch (err) {
      this.error = { ...this.error, app: err.message };
    } finally {
      this.saving = { ...this.saving, app: false };
    }
  }

  _renderPanelCard() {
    if (!this.appDraft) return null;
    const draft = this.appDraft;
    const panel = draft.panel || { model: "spectra_6_13_3", orientation: "landscape" };
    const spec = this.panelCatalog.find((p) => p.id === panel.model);
    const w = spec?.width ?? 0;
    const h = spec?.height ?? 0;
    const renderDims =
      panel.orientation === "landscape" ? `${w} × ${h}` : `${h} × ${w}`;
    const isSaving = this.saving.app;
    const isSaved = this.saved.app;
    const err = this.error.app;
    return html`
      <id-card heading="Panel" subheading="Hardware + how it's mounted">
        <div class="form-row">
          <label class="field">Model</label>
          <select
            .value=${panel.model}
            @change=${(e) => this._setApp("panel.model", e.target.value)}
          >
            ${this.panelCatalog.map(
              (p) => html`<option value=${p.id} ?selected=${p.id === panel.model}>
                ${p.label} — ${p.width} × ${p.height}
              </option>`
            )}
          </select>
        </div>
        <div class="form-row">
          <label class="field">Orientation</label>
          <div>
            <label class="checkbox" style="margin-right: 16px;">
              <input
                type="radio"
                name="orientation"
                value="portrait"
                ?checked=${panel.orientation === "portrait"}
                @change=${() => this._setApp("panel.orientation", "portrait")}
              />
              Portrait
            </label>
            <label class="checkbox">
              <input
                type="radio"
                name="orientation"
                value="landscape"
                ?checked=${panel.orientation === "landscape"}
                @change=${() => this._setApp("panel.orientation", "landscape")}
              />
              Landscape
            </label>
            <small class="field-help">
              ${panel.orientation === "portrait"
                ? html`<i class="ph ph-arrow-clockwise"></i>
                    Dashboards compose at <strong>${renderDims}</strong> and
                    rotate 90° before sending so they land right-side-up on
                    the panel's native pixel grid.`
                : html`Native pixel orientation — no rotation. Dashboards
                    compose at <strong>${renderDims}</strong>.`}
            </small>
          </div>
        </div>
        <div class="actions">
          <id-button
            variant="primary"
            ?disabled=${isSaving}
            @click=${() => this._saveApp()}
          >
            <i class="ph ph-floppy-disk"></i>
            ${isSaving ? "Saving…" : "Save panel"}
          </id-button>
          ${err
            ? html`<span class="save-status error">${err}</span>`
            : isSaved
              ? html`<span class="save-status ok"><i class="ph ph-check-circle"></i> saved</span>`
              : null}
        </div>
      </id-card>
    `;
  }

  _renderAppSettings() {
    if (!this.appDraft) return null;
    const draft = this.appDraft;
    const isSaving = this.saving.app;
    const isSaved = this.saved.app;
    const err = this.error.app;
    return html`
      <id-card heading="App settings" subheading="MQTT broker + companion URL">
        <div class="form-row">
          <label class="field">MQTT host</label>
          <input
            type="text"
            placeholder="mqtt.local or 192.168.1.50"
            .value=${draft.mqtt.host || ""}
            @input=${(e) => this._setApp("mqtt.host", e.target.value)}
          />
        </div>
        <div class="form-row">
          <label class="field">MQTT port</label>
          <input
            type="number"
            min="1"
            max="65535"
            .value=${String(draft.mqtt.port || 1883)}
            @input=${(e) => this._setApp("mqtt.port", Number(e.target.value) || 1883)}
          />
        </div>
        <div class="form-row">
          <label class="field">MQTT username</label>
          <input
            type="text"
            placeholder="(optional)"
            .value=${draft.mqtt.username || ""}
            @input=${(e) => this._setApp("mqtt.username", e.target.value)}
          />
        </div>
        <div class="form-row">
          <label class="field">MQTT password</label>
          <div>
            <input
              type="password"
              placeholder=${this.appSettings?.mqtt?.password === "•••" ? "(leave blank to keep)" : "(optional)"}
              .value=${draft.mqtt.password === "•••" ? "" : draft.mqtt.password || ""}
              autocomplete="new-password"
              @input=${(e) => this._setApp("mqtt.password", e.target.value)}
            />
            <span class="secret-status ${this.appSettings?.mqtt?.password === "•••" ? "set" : ""}">
              ${this.appSettings?.mqtt?.password === "•••"
                ? html`<i class="ph ph-check-circle"></i> stored`
                : html`<i class="ph ph-warning"></i> not configured`}
            </span>
          </div>
        </div>
        <div class="form-row">
          <label class="field">Update topic</label>
          <input
            type="text"
            .value=${draft.mqtt.topic_update || "inky/update"}
            @input=${(e) => this._setApp("mqtt.topic_update", e.target.value)}
          />
        </div>
        <div class="form-row">
          <label class="field">Status topic</label>
          <input
            type="text"
            .value=${draft.mqtt.topic_status || "inky/status"}
            @input=${(e) => this._setApp("mqtt.topic_status", e.target.value)}
          />
        </div>
        <div class="form-row">
          <label class="field">Companion base URL</label>
          <input
            type="text"
            placeholder="http://192.168.1.10:5555"
            .value=${draft.base_url || ""}
            @input=${(e) => this._setApp("base_url", e.target.value)}
          />
          <span></span>
          <small class="field-help" style="grid-column: 2;">
            How the Pi listener reaches this companion to fetch render PNGs.
          </small>
        </div>
        <div class="actions">
          <id-button
            variant="primary"
            ?disabled=${isSaving}
            @click=${() => this._saveApp()}
          >
            <i class="ph ph-floppy-disk"></i>
            ${isSaving ? "Saving…" : "Save & reconnect"}
          </id-button>
          ${err
            ? html`<span class="save-status error">${err}</span>`
            : isSaved
              ? html`<span class="save-status ok"><i class="ph ph-check-circle"></i> saved · bridge reconnected</span>`
              : null}
        </div>
      </id-card>
    `;
  }

  _renderPluginCard(plugin) {
    const isSaving = this.saving[plugin.plugin_id];
    const isSaved = this.saved[plugin.plugin_id];
    const err = this.error[plugin.plugin_id];
    return html`
      <id-card heading=${plugin.plugin_name} subheading=${plugin.plugin_id}>
        ${plugin.settings.map((f) => this._renderField(plugin.plugin_id, f))}
        <div class="actions">
          <id-button
            variant="primary"
            ?disabled=${isSaving}
            @click=${() => this._save(plugin.plugin_id)}
          >
            <i class="ph ph-floppy-disk"></i> ${isSaving ? "Saving…" : "Save"}
          </id-button>
          ${err
            ? html`<span class="save-status error">${err}</span>`
            : isSaved
              ? html`<span class="save-status ok"><i class="ph ph-check-circle"></i> saved</span>`
              : null}
        </div>
      </id-card>
    `;
  }

  render() {
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <id-nav current="settings"></id-nav>
      <div class="container">
      <h1>Settings</h1>
      <p class="lede">
        App-level config (MQTT broker, companion URL) and per-plugin
        configuration in one place.
      </p>
      ${this._renderPanelCard()}
      ${this._renderAppSettings()}
      <h2 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--id-fg-soft); margin: 24px 0 12px;">
        Plugins
      </h2>
      ${this.plugins === null
        ? html`<p class="empty">Loading…</p>`
        : this.plugins.length === 0
          ? html`<p class="empty">No plugins declare settings yet.</p>`
          : this.plugins.map((p) => this._renderPluginCard(p))}
      </div>
    `;
  }
}

customElements.define("settings-page", SettingsPage);
document.body.append(document.createElement("settings-page"));
