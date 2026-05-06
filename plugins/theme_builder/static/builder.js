// Theme Builder admin.
//
// Lists every theme (bundled + user). Bundled themes are read-only: clicking
// "edit" on one clones it into a new user theme so the user can tweak the
// palette without touching shipped data.

let PALETTE_KEYS = [];
let FONTS = [];
let themes = [];
let activeId = null;
let isDirtyClone = false;  // true when user clicked "Clone" on a bundled theme

const listEl = document.getElementById("theme-list");
const editorCard = document.getElementById("editor-card");
const previewCard = document.getElementById("preview-card");
const titleEl = document.getElementById("editor-title");
const badgeEl = document.getElementById("editor-badge");
const labelInput = document.getElementById("theme-label");
const idInput = document.getElementById("theme-id");
// Single global font picker + body weight in the sidebar — apply globally.
const fontSelect = document.getElementById("default-font-select");
const weightSelect = document.getElementById("default-font-weight");
const paletteEditor = document.getElementById("palette-editor");
const previewEl = document.getElementById("theme-preview");

document.getElementById("new-theme-btn").addEventListener("click", () => startBlank());
document.getElementById("save-btn").addEventListener("click", save);
document.getElementById("delete-btn").addEventListener("click", del);
document.getElementById("clone-btn").addEventListener("click", clone);
labelInput.addEventListener("input", () => {
  if (isDirtyClone || !activeId || activeId === "__new__") {
    idInput.value = slugify(labelInput.value);
  }
});

load();

async function load() {
  const r = await fetch("/plugins/theme_builder/api/themes");
  if (!r.ok) {
    listEl.innerHTML = `<li class="muted small">Failed to load: HTTP ${r.status}</li>`;
    return;
  }
  const body = await r.json();
  themes = body.themes;
  PALETTE_KEYS = body.palette_keys;
  FONTS = body.fonts || [];
  buildFontSelect();
  await loadGlobalFont();
  renderList();
  // Open the Light theme by default so the editor + preview aren't empty on load.
  if (!activeId) {
    const seed = themes.find((t) => t.id === "light") || themes[0];
    if (seed) loadTheme(seed.id);
  }
}

function buildFontSelect() {
  fontSelect.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "(system default)";
  fontSelect.appendChild(blank);
  for (const f of FONTS) {
    if (f.is_system) continue;  // already represented by the blank option
    const o = document.createElement("option");
    o.value = f.id;
    o.textContent = f.label;
    fontSelect.appendChild(o);
  }
}

async function loadGlobalFont() {
  try {
    const r = await fetch("/plugins/theme_builder/api/font-default");
    if (!r.ok) return;
    const body = await r.json();
    fontSelect.value = body.font || "";
  } catch (_) { /* leave blank */ }
  try {
    const r = await fetch("/plugins/theme_builder/api/font-weight");
    if (!r.ok) return;
    const body = await r.json();
    rebuildWeightSelect(parseInt(body.weight, 10) || 400);
  } catch (_) { /* leave default */ }
}

// Restrict the weight dropdown to weights the chosen font actually ships.
// System default ("") allows the full CSS range. Each font lists its
// supported weight numbers in its `weights` map.
const WEIGHT_LABELS = {
  100: "Thin",
  200: "Extra light",
  300: "Light",
  400: "Regular",
  500: "Medium",
  600: "Semibold",
  700: "Bold",
  800: "Extra bold",
  900: "Heavy",
};

function availableWeights() {
  const id = fontSelect.value;
  if (!id) return [300, 400, 500, 600, 700, 800, 900];  // system fallback
  const f = FONTS.find((x) => x.id === id);
  if (!f || !Array.isArray(f.weights) || !f.weights.length) return [400];
  // f.weights is an array of {weight, url} objects from the API.
  const nums = f.weights.map((w) => parseInt(w.weight, 10)).filter((n) => Number.isFinite(n));
  return [...new Set(nums)].sort((a, b) => a - b);
}

function rebuildWeightSelect(preferred = null) {
  const current = preferred ?? (parseInt(weightSelect.value, 10) || 400);
  const weights = availableWeights();
  weightSelect.innerHTML = "";
  for (const w of weights) {
    const o = document.createElement("option");
    o.value = String(w);
    o.textContent = `${WEIGHT_LABELS[w] || w} (${w})`;
    weightSelect.appendChild(o);
  }
  // Snap to the closest available weight if the persisted one isn't offered.
  const exact = weights.includes(current) ? current : weights.reduce(
    (best, w) => Math.abs(w - current) < Math.abs(best - current) ? w : best,
    weights[0] || 400,
  );
  weightSelect.value = String(exact);
}

fontSelect.addEventListener("change", async () => {
  const font = fontSelect.value;
  window.inkyStatus("saving", "Saving font…");
  try {
    const r = await fetch("/plugins/theme_builder/api/font-default", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ font }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    window.inkyStatus("saved", font ? `Font · ${font}` : "Font reset");
    // Filter the weight dropdown to what this new font supports. If the
    // current weight is no longer offered, snap to the nearest neighbor and
    // persist that change so the rendered page matches the UI.
    const before = parseInt(weightSelect.value, 10) || 400;
    rebuildWeightSelect();
    const after = parseInt(weightSelect.value, 10) || 400;
    if (after !== before) {
      await fetch("/plugins/theme_builder/api/font-weight", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ weight: after }),
      });
    }
    if (!previewCard.hidden) updatePreview();
  } catch (err) {
    window.inkyStatus("error", err.message);
  }
});

weightSelect.addEventListener("change", async () => {
  const weight = parseInt(weightSelect.value, 10) || 400;
  window.inkyStatus("saving", "Saving weight…");
  try {
    const r = await fetch("/plugins/theme_builder/api/font-weight", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weight }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    const opt = weightSelect.options[weightSelect.selectedIndex];
    window.inkyStatus("saved", `Weight · ${opt ? opt.textContent : weight}`);
    if (!previewCard.hidden) updatePreview();
  } catch (err) {
    window.inkyStatus("error", err.message);
  }
});

// Light/dark heuristic — relative luminance of `bg` against an empirical
// midpoint. Same formula the dashboard editor uses; keep them in sync.
function isLightTheme(t) {
  const m = /^#?([0-9a-f]{6})$/i.exec((t && t.palette && t.palette.bg) || "");
  if (!m) return false;
  const r = parseInt(m[1].slice(0, 2), 16);
  const g = parseInt(m[1].slice(2, 4), 16);
  const b = parseInt(m[1].slice(4, 6), 16);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140;
}

function renderList() {
  listEl.innerHTML = "";
  if (!themes.length) {
    listEl.innerHTML = `<li class="muted small">No themes yet.</li>`;
    return;
  }
  const light = themes.filter(isLightTheme);
  const dark = themes.filter((t) => !isLightTheme(t));
  appendThemeGroup("Light", light);
  appendThemeGroup("Dark", dark);
}

function appendThemeGroup(label, group) {
  if (!group.length) return;
  const header = document.createElement("li");
  header.className = "theme-group-head";
  header.textContent = label;
  listEl.appendChild(header);
  for (const t of group) {
    const li = document.createElement("li");
    li.className = "theme-row" + (t.id === activeId ? " active" : "");
    li.dataset.id = t.id;
    const previewKeys = ["bg", "surface", "fg", "accent"];
    const swatches = previewKeys.map((k) =>
      `<span class="swatch" style="background:${t.palette[k]}"></span>`).join("");
    li.innerHTML = `
      <div class="meta">
        <strong>${escapeHtml(t.label)}</strong>
        ${!t.is_user ? `<span class="kind">Bundled</span>` : ""}
      </div>
      <div class="swatches" title="${escapeHtml(t.is_user ? 'user theme' : 'bundled')}">${swatches}</div>
    `;
    li.addEventListener("click", () => loadTheme(t.id));
    listEl.appendChild(li);
  }
}

function loadTheme(id) {
  const t = themes.find((x) => x.id === id);
  if (!t) return;
  activeId = id;
  isDirtyClone = false;
  renderList();
  editorCard.hidden = false;
  previewCard.hidden = false;
  labelInput.value = t.label;
  idInput.value = t.id;
  idInput.disabled = !t.is_user;  // bundled IDs not editable here
  titleEl.textContent = t.label;
  badgeEl.textContent = t.is_user
    ? "user theme · editable"
    : `bundled (${t.source_plugin}) · clone to edit`;
  badgeEl.className = "muted small";
  buildPaletteEditor(t.palette);
  setSaveButtonsForTheme(t);
  updatePreview();
  setStatus("", "");
}

function startBlank() {
  activeId = "__new__";
  isDirtyClone = false;
  renderList();
  editorCard.hidden = false;
  previewCard.hidden = false;
  titleEl.textContent = "New theme";
  badgeEl.textContent = "draft · save to create";
  labelInput.value = "";
  idInput.value = "";
  idInput.disabled = false;
  // Seed from `light` if available, else from any theme, else from blanks.
  const seed = themes.find((t) => t.id === "light") || themes[0];
  buildPaletteEditor(seed ? { ...seed.palette } : Object.fromEntries(PALETTE_KEYS.map((k) => [k, "#888888"])));
  document.getElementById("delete-btn").hidden = true;
  document.getElementById("clone-btn").hidden = true;
  document.getElementById("save-btn").disabled = false;
  updatePreview();
  setStatus("", "");
}

function buildPaletteEditor(palette) {
  paletteEditor.innerHTML = "";
  for (const key of PALETTE_KEYS) {
    const value = palette[key] || "#000000";
    const wrap = document.createElement("div");
    wrap.className = "palette-field";
    wrap.innerHTML = `
      <input type="color" class="swatch-input" data-key="${key}" value="${value}">
      <span class="text-wrap">
        <label>${key}</label>
        <input type="text" class="hex-input" data-key="${key}" value="${value}" maxlength="7">
      </span>
    `;
    const colorInput = wrap.querySelector(".swatch-input");
    const textInput = wrap.querySelector(".hex-input");
    colorInput.addEventListener("input", () => {
      textInput.value = colorInput.value;
      updatePreview();
    });
    textInput.addEventListener("input", () => {
      if (/^#[0-9a-fA-F]{6}$/.test(textInput.value)) {
        colorInput.value = textInput.value;
        updatePreview();
      }
    });
    paletteEditor.appendChild(wrap);
  }
}

function setSaveButtonsForTheme(t) {
  const deleteBtn = document.getElementById("delete-btn");
  const cloneBtn = document.getElementById("clone-btn");
  const saveBtn = document.getElementById("save-btn");
  deleteBtn.hidden = !t.is_user;
  cloneBtn.hidden = t.is_user;
  saveBtn.disabled = !t.is_user;  // bundled themes are read-only — must clone
}

function clone() {
  const palette = collectPalette();
  const baseLabel = labelInput.value || "Theme";
  labelInput.value = `${baseLabel} (copy)`;
  idInput.value = uniqueSlug(slugify(`${idInput.value}-copy`));
  idInput.disabled = false;
  isDirtyClone = true;
  activeId = "__new__";
  renderList();
  badgeEl.textContent = "clone · save to create";
  document.getElementById("delete-btn").hidden = true;
  document.getElementById("clone-btn").hidden = true;
  document.getElementById("save-btn").disabled = false;
  buildPaletteEditor(palette);
  updatePreview();
}

function uniqueSlug(seed) {
  const taken = new Set(themes.map((t) => t.id));
  if (!taken.has(seed)) return seed;
  let i = 2;
  while (taken.has(`${seed}-${i}`)) i++;
  return `${seed}-${i}`;
}

function collectPalette() {
  const out = {};
  paletteEditor.querySelectorAll(".hex-input").forEach((el) => {
    out[el.dataset.key] = el.value;
  });
  return out;
}

function updatePreview() {
  const p = collectPalette();
  // Apply as scoped CSS variables to the preview block (`--p-*`) so they
  // don't bleed into the surrounding admin UI.
  const set = (k, v) => previewEl.style.setProperty("--p-" + k, v);
  for (const k of PALETTE_KEYS) set(k, p[k]);
  applyPreviewFont(fontSelect.value);
  // Mirror the chosen body weight so the preview reads the same as the
  // composer will render.
  previewEl.style.fontWeight = String(parseInt(weightSelect.value, 10) || 400);
  // Mirrors the widget visual idiom: outer card is `surface`, inner tonal
  // tiles are `surface-2`, hero number / icons in `accent`. This way every
  // palette key is exercised by the preview.
  previewEl.innerHTML = `
    <div class="preview-header">
      <i class="ph ph-cloud-sun preview-icon" aria-hidden="true"></i>
      <strong>${escapeHtml(labelInput.value || "Theme")}</strong>
      <time>14:32</time>
    </div>
    <div class="preview-cell hero">
      <div class="hero-row">
        <i class="ph ph-cloud-sun hero-icon" aria-hidden="true"></i>
        <div class="hero-temp">12°<span class="hero-unit">C</span></div>
      </div>
      <div class="hero-cond">Drizzle · Melbourne</div>
      <div class="metrics">
        <div class="metric"><span class="m-k">Wind</span><span class="m-v">14<span class="m-u">km/h</span></span></div>
        <div class="metric"><span class="m-k">Humid</span><span class="m-v">78<span class="m-u">%</span></span></div>
        <div class="metric"><span class="m-k">UV</span><span class="m-v">3</span></div>
      </div>
    </div>
    <div class="preview-cell todo">
      <div class="todo-head">
        <span class="todo-count">3</span>
        <span class="todo-label">tasks today</span>
      </div>
      <div class="todo-bar"><div class="todo-bar-fill" style="width: 34%"></div></div>
      <div class="todo-list">
        <div class="todo-item"><i class="ph ph-circle"></i> Empty bins</div>
        <div class="todo-item"><i class="ph ph-circle"></i> Tea with N.</div>
        <div class="todo-item done"><i class="ph ph-check-circle"></i> <s>Push v3</s></div>
      </div>
    </div>
    <div class="preview-cell" style="grid-column: 1 / -1">
      <div class="m">Status</div>
      <div class="sem">
        <span class="pill ok">ok · synced</span>
        <span class="pill warn">warn · 1 retry</span>
        <span class="pill danger">danger · 3 errors</span>
      </div>
    </div>
  `;
}

async function save() {
  const palette = collectPalette();
  const label = labelInput.value.trim();
  const id = idInput.value.trim() || slugify(label);
  if (!label) { setStatus("error", "Label is required"); return; }
  // Validate every hex client-side
  for (const k of PALETTE_KEYS) {
    if (!/^#[0-9a-fA-F]{6}$/.test(palette[k] || "")) {
      setStatus("error", `Invalid hex for ${k}`); return;
    }
  }
  setStatus("saving", "Saving…");
  const r = await fetch("/plugins/theme_builder/api/themes", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, label, palette }),
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) { setStatus("error", body.error || `HTTP ${r.status}`); return; }
  setStatus("saved", `Saved · ${body.label || label}`);
  await load();
  loadTheme(body.id);
}

async function del() {
  if (!activeId || activeId === "__new__") return;
  const t = themes.find((x) => x.id === activeId);
  if (!confirm(`Delete theme "${t ? t.label : activeId}"?`)) return;
  const r = await fetch(`/plugins/theme_builder/api/themes/${encodeURIComponent(activeId)}`, {
    method: "DELETE",
  });
  if (!r.ok) { setStatus("error", `HTTP ${r.status}`); return; }
  activeId = null;
  editorCard.hidden = true;
  previewCard.hidden = true;
  await load();
}

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}

// Load the chosen font's woff2 via @font-face on demand and apply its family
// to the preview area. We add one rule per loaded font so switching back is
// instant; the `data-font-loaded` attribute prevents duplicates.
const fontStyleEl = document.createElement("style");
document.head.appendChild(fontStyleEl);
const loadedFonts = new Set();

function applyPreviewFont(fontId) {
  if (!fontId) {
    previewEl.style.fontFamily = "";
    return;
  }
  const f = FONTS.find((x) => x.id === fontId);
  if (!f) return;
  if (f.is_system) {
    previewEl.style.fontFamily = `${f.label}, system-ui, sans-serif`;
    return;
  }
  if (!loadedFonts.has(fontId) && Array.isArray(f.weights)) {
    let css = "";
    for (const w of f.weights) {
      css += `@font-face{font-family:"${f.label}";src:url("${w.url}") format("woff2");font-weight:${w.weight};font-style:normal;font-display:block;}`;
    }
    fontStyleEl.appendChild(document.createTextNode(css));
    loadedFonts.add(fontId);
  }
  previewEl.style.fontFamily = `"${f.label}", system-ui, sans-serif`;
}

function slugify(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "theme";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
