// Widget manager. List every loaded plugin and let the user flip enable/disable.
// Toggles are hot — the API updates `widget_settings.json` and the registry's
// in-memory override; the per-blueprint `before_request` gate makes disabled
// plugins return 404 immediately for both asset routes and admin pages.

const listEl = document.getElementById("widgets-list");

load();

async function load() {
  try {
    const r = await fetch("/api/widgets");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { plugins } = await r.json();
    render(plugins);
  } catch (err) {
    listEl.innerHTML = `<p class="muted small">Failed to load: ${escapeHtml(err.message)}</p>`;
  }
}

function render(plugins) {
  listEl.innerHTML = "";
  if (!plugins.length) {
    listEl.innerHTML = `<p class="muted small">No plugins discovered. Drop a folder into <code>plugins/</code> and restart.</p>`;
    return;
  }
  for (const p of plugins) {
    listEl.appendChild(renderRow(p));
  }
}

function renderRow(p) {
  const row = document.createElement("div");
  row.className = "widget-row" + (p.enabled ? "" : " disabled") + (p.error ? " errored" : "");
  row.dataset.pluginId = p.id;

  const icon = document.createElement("span");
  icon.className = "icon";
  if (p.icon) icon.innerHTML = `<i class="ph ${p.icon}"></i>`;
  else icon.innerHTML = `<i class="ph ph-puzzle-piece"></i>`;
  row.appendChild(icon);

  const meta = document.createElement("div");
  meta.className = "meta";
  const row1 = document.createElement("div");
  row1.className = "row-1";
  const name = document.createElement("strong");
  name.textContent = p.label;
  row1.appendChild(name);
  const id = document.createElement("span");
  id.className = "id-tag";
  id.textContent = `${p.id} · v${p.version}`;
  row1.appendChild(id);
  meta.appendChild(row1);

  const row2 = document.createElement("div");
  row2.className = "row-2";
  for (const k of (p.kinds || [])) {
    const b = document.createElement("span");
    b.className = `kind-badge kind-${k}`;
    b.textContent = k;
    row2.appendChild(b);
  }
  if (p.has_blueprint) {
    const tag = document.createElement("span");
    tag.className = "kind-badge";
    tag.textContent = "admin pages";
    row2.appendChild(tag);
  }
  if (p.settings_keys.length) {
    const tag = document.createElement("span");
    tag.className = "kind-badge";
    tag.textContent = `${p.settings_keys.length} setting${p.settings_keys.length === 1 ? "" : "s"}`;
    row2.appendChild(tag);
  }
  meta.appendChild(row2);

  if (p.error) {
    const err = document.createElement("span");
    err.className = "error-text";
    err.textContent = p.error;
    meta.appendChild(err);
  }
  row.appendChild(meta);

  const sw = document.createElement("label");
  sw.className = "switch";
  sw.title = p.enabled ? "Disable" : "Enable";
  const input = document.createElement("input");
  input.type = "checkbox";
  input.checked = !!p.enabled;
  if (p.error || p.synthetic) input.disabled = true;
  input.addEventListener("change", () => onToggle(p, input));
  sw.appendChild(input);
  const track = document.createElement("span");
  track.className = "track";
  sw.appendChild(track);
  const thumb = document.createElement("span");
  thumb.className = "thumb";
  sw.appendChild(thumb);
  row.appendChild(sw);

  return row;
}

async function onToggle(plugin, input) {
  const desired = input.checked;
  setStatus("saving", `Updating ${plugin.id}…`);
  input.disabled = true;
  try {
    const r = await fetch(`/api/widgets/${encodeURIComponent(plugin.id)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: desired }),
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${r.status}`);
    }
    setStatus("saved", `${plugin.id} → ${desired ? "enabled" : "disabled"}`);
    await load();
  } catch (err) {
    setStatus("error", `Toggle failed: ${err.message}`);
    input.checked = !desired;
    input.disabled = false;
  }
}

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
