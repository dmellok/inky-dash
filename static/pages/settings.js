import { LitElement, html, css } from "lit";
import "../components/index.js";

class SettingsPage extends LitElement {
  static properties = {
    plugins: { state: true },
    drafts: { state: true },
    saving: { state: true },
    saved: { state: true },
    error: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      max-width: 760px;
      margin: 0 auto;
      padding: 24px 16px;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      color: var(--id-fg, #1a1612);
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
  }

  async connectedCallback() {
    super.connectedCallback();
    try {
      const res = await fetch("/api/settings");
      this.plugins = await res.json();
      // Initialise drafts with current values (or default for missing).
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
      <a class="nav" href="/editor"><i class="ph ph-arrow-left"></i> back to editor</a>
      <h1>Settings</h1>
      <p class="lede">
        Plugin-level configuration (API keys, defaults). Each plugin declares its
        own settings in <code>plugin.json</code> — only plugins that need them
        appear here.
      </p>
      ${this.plugins === null
        ? html`<p class="empty">Loading…</p>`
        : this.plugins.length === 0
          ? html`<p class="empty">No plugins declare settings yet.</p>`
          : this.plugins.map((p) => this._renderPluginCard(p))}
    `;
  }
}

customElements.define("settings-page", SettingsPage);
document.body.append(document.createElement("settings-page"));
