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
      max-width: 1200px;
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
    label.checkbox {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      min-height: var(--id-control-h, 40px);
      font-size: 14px;
      cursor: pointer;
    }

    /* Toggle switch — replaces native checkbox styling. */
    label.checkbox input[type="checkbox"] {
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
    label.checkbox input[type="checkbox"]::before {
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
    label.checkbox input[type="checkbox"]:checked {
      background: var(--id-accent, #b06750);
    }
    label.checkbox input[type="checkbox"]:checked::before {
      transform: translateX(16px);
    }
    label.checkbox input[type="checkbox"]:focus-visible {
      outline: 2px solid var(--id-accent, #b06750);
      outline-offset: 2px;
    }

    /* Custom radio dots. */
    label.radio {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;
      font-size: 14px;
      color: var(--id-fg, #0f172a);
    }
    label.radio input[type="radio"] {
      appearance: none;
      -webkit-appearance: none;
      width: 18px;
      height: 18px;
      border: 2px solid var(--id-divider, #c8b89b);
      border-radius: 50%;
      margin: 0;
      flex-shrink: 0;
      cursor: pointer;
      position: relative;
      transition: border-color 150ms ease;
    }
    label.radio input[type="radio"]:hover {
      border-color: var(--id-fg-soft, #5a4f44);
    }
    label.radio input[type="radio"]:checked {
      border-color: var(--id-accent, #b06750);
    }
    label.radio input[type="radio"]:checked::before {
      content: "";
      position: absolute;
      inset: 3px;
      border-radius: 50%;
      background: var(--id-accent, #b06750);
    }
    label.radio input[type="radio"]:focus-visible {
      outline: 2px solid var(--id-accent, #b06750);
      outline-offset: 2px;
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

    /* Appearance card */
    .theme-picks {
      display: flex;
      gap: 6px;
      flex-wrap: wrap;
    }
    .theme-pick {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 0 14px;
      height: var(--id-control-h, 40px);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: var(--id-radius, 8px);
      background: transparent;
      color: var(--id-fg, #1a1612);
      font: inherit;
      cursor: pointer;
      transition: border-color 100ms ease, background 100ms ease;
    }
    .theme-pick:hover {
      border-color: var(--id-accent, #4f46e5);
    }
    .theme-pick.active {
      border-color: var(--id-accent, #4f46e5);
      background: var(--id-accent-bg, rgba(79, 70, 229, 0.1));
      color: var(--id-accent, #4f46e5);
    }
    .accent-swatches {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
    }
    .accent-swatch {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      background: var(--swatch);
      border: 2px solid var(--id-bg, #ffffff);
      box-shadow: 0 0 0 1px var(--id-divider, #c8b89b);
      cursor: pointer;
      padding: 0;
      transition: transform 100ms ease, box-shadow 100ms ease;
    }
    .accent-swatch:hover {
      transform: scale(1.08);
    }
    .accent-swatch.active {
      box-shadow: 0 0 0 2px var(--swatch);
    }
    .accent-custom {
      position: relative;
      width: 32px;
      height: 32px;
      border-radius: 50%;
      border: 2px dashed var(--id-divider, #c8b89b);
      display: inline-grid;
      place-items: center;
      cursor: pointer;
      color: var(--id-fg-soft, #5a4f44);
    }
    .accent-custom:hover {
      border-color: var(--id-accent, #4f46e5);
      color: var(--id-accent, #4f46e5);
    }
    .accent-custom input[type="color"] {
      position: absolute;
      inset: 0;
      opacity: 0;
      cursor: pointer;
    }
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

    if (field.type === "textarea") {
      return html`
        <div class="form-row">
          <label class="field" for=${`f-${pluginId}-${field.name}`}>${field.label}</label>
          <textarea
            id=${`f-${pluginId}-${field.name}`}
            rows="6"
            .value=${String(value)}
            @input=${onInput}
            style="font: inherit; font-size: 13px; font-family: ui-monospace, 'SF Mono', Menlo, monospace;"
          ></textarea>
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

  // Apply user-selected appearance to the live document so the change is
  // visible immediately. Also write to localStorage so the appearance
  // bootstrap picks it up on the next page load (no flash).
  _applyAppearance(theme, accent) {
    try {
      const root = document.documentElement;
      const isDark =
        theme === "dark" ||
        (theme === "auto" &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);
      if (isDark) root.dataset.theme = "dark";
      else root.removeAttribute("data-theme");
      if (accent) root.style.setProperty("--id-accent", accent);
      localStorage.setItem("inky_theme", theme || "auto");
      if (accent) localStorage.setItem("inky_accent", accent);
    } catch {
      /* localStorage may be disabled */
    }
    // Tell id-nav (and anything else listening) that the theme flipped.
    window.dispatchEvent(new Event("storage"));
  }

  _renderAppearanceCard() {
    if (!this.appDraft) return null;
    const draft = this.appDraft;
    const appearance =
      draft.appearance || { theme: "auto", accent: "#b06750" };
    // Warm, dusty palette — less saturated and more grounded than the
    // standard tailwind brights. Each entry keeps the original hue but
    // shifts toward earth tones for a softer feel.
    const presets = [
      { value: "#b06750", label: "Terracotta" },
      { value: "#c4884e", label: "Mustard" },
      { value: "#8a9b6a", label: "Sage" },
      { value: "#5c8a82", label: "Teal" },
      { value: "#6c7c9a", label: "Dusty blue" },
      { value: "#8b6f9b", label: "Mauve" },
      { value: "#b07089", label: "Rose" },
      { value: "#857872", label: "Stone" },
    ];
    const isSaving = this.saving.app;
    const isSaved = this.saved.app;
    const err = this.error.app;
    return html`
      <id-card heading="Appearance" subheading="Theme + accent. Applies to every page.">
        <div class="form-row">
          <label class="field">Theme</label>
          <div class="theme-picks">
            ${[
              { id: "light", icon: "ph-sun", label: "Light" },
              { id: "dark", icon: "ph-moon", label: "Dark" },
              { id: "auto", icon: "ph-monitor", label: "Auto" },
            ].map(
              (t) => html`
                <button
                  type="button"
                  class="theme-pick ${appearance.theme === t.id ? "active" : ""}"
                  @click=${() => {
                    this._setApp("appearance.theme", t.id);
                    this._applyAppearance(t.id, appearance.accent);
                  }}
                >
                  <i class="ph ${t.icon}"></i>
                  <span>${t.label}</span>
                </button>
              `
            )}
          </div>
        </div>
        <div class="form-row">
          <label class="field">Accent</label>
          <div>
            <div class="accent-swatches">
              ${presets.map(
                (p) => html`
                  <button
                    type="button"
                    class="accent-swatch ${appearance.accent === p.value ? "active" : ""}"
                    style="--swatch: ${p.value};"
                    title=${p.label}
                    aria-label=${p.label}
                    @click=${() => {
                      this._setApp("appearance.accent", p.value);
                      this._applyAppearance(appearance.theme, p.value);
                    }}
                  ></button>
                `
              )}
              <label class="accent-custom" title="Custom color">
                <input
                  type="color"
                  .value=${appearance.accent || "#4f46e5"}
                  @input=${(e) => {
                    this._setApp("appearance.accent", e.target.value);
                    this._applyAppearance(appearance.theme, e.target.value);
                  }}
                />
                <i class="ph ph-eyedropper"></i>
              </label>
            </div>
          </div>
        </div>
        <div class="actions">
          <id-button
            variant="primary"
            ?disabled=${isSaving}
            @click=${() => this._saveApp()}
          >
            <i class="ph ph-floppy-disk"></i>
            ${isSaving ? "Saving…" : "Save appearance"}
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

  _renderPanelCard() {
    if (!this.appDraft) return null;
    const draft = this.appDraft;
    const panel = draft.panel || {
      model: "spectra_6_13_3",
      orientation: "landscape",
      underscan: 0,
    };
    const underscan = Number.isFinite(Number(panel.underscan)) ? Number(panel.underscan) : 0;
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
            <label class="radio" style="margin-right: 16px;">
              <input
                type="radio"
                name="orientation"
                value="portrait"
                ?checked=${panel.orientation === "portrait"}
                @change=${() => this._setApp("panel.orientation", "portrait")}
              />
              Portrait
            </label>
            <label class="radio">
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
        <div class="form-row">
          <label class="field" for="panel-underscan">Underscan</label>
          <div>
            <div style="display: flex; align-items: center; gap: 12px;">
              <input
                id="panel-underscan"
                type="range"
                min="0"
                max="100"
                step="1"
                .value=${String(underscan)}
                @input=${(e) =>
                  this._setApp("panel.underscan", Number(e.target.value))}
                style="flex: 1; accent-color: var(--id-accent);"
              />
              <span
                style="min-width: 48px; text-align: right; font-variant-numeric: tabular-nums;"
              >${underscan} px</span>
            </div>
            <small class="field-help">
              Insets every pushed frame by this many pixels on each edge, filling the
              border with white. Use to compensate for a physical mat or bezel that
              occludes the outer rim of the panel.
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
      ${this._renderAppearanceCard()}
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
