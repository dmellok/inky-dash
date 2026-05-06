// Dashboard editor.
//
// Architecture: form is the single source of truth for the page model.
// Any change re-collects the model, debounces, POSTs to /api/preview-page-draft,
// and reloads the iframe — same DOM Playwright will screenshot at push time.
// Per brief rule 9: bind both `input` (debounced) and `change` (immediate).

const initial = JSON.parse(document.getElementById("initial-page").textContent);
const catalog = JSON.parse(document.getElementById("initial-catalog").textContent);

// Layouts hardcoded here so the picker works without a server roundtrip.
// (Server is the canonical source — see state/pages.py LAYOUTS — but these
// are display-only previews for the picker.)
const LAYOUTS = {
  single:                 [[0,0,1,1]],
  stack_2:                [[0,0,1,.5],[0,.5,1,.5]],
  row_2:                  [[0,0,.5,1],[.5,0,.5,1]],
  stack_3:                [[0,0,1,1/3],[0,1/3,1,1/3],[0,2/3,1,1/3]],
  grid_2x2:               [[0,0,.5,.5],[.5,0,.5,.5],[0,.5,.5,.5],[.5,.5,.5,.5]],
  hero_top_two_below:     [[0,0,1,.6],[0,.6,.5,.4],[.5,.6,.5,.4]],
  hero_bottom_two_above:  [[0,0,.5,.4],[.5,0,.5,.4],[0,.4,1,.6]],
};
const LAYOUT_LABELS = {
  single: "Single",
  stack_2: "Stack 2",
  row_2: "Row 2",
  stack_3: "Stack 3",
  grid_2x2: "Grid",
  hero_top_two_below: "Hero top",
  hero_bottom_two_above: "Hero bottom",
};

const form = document.getElementById("page-form");
const iframe = document.getElementById("preview-iframe");
const previewStatus = document.getElementById("preview-status");
const previewWrap = document.getElementById("preview-frame-wrap");
const previewDims = document.getElementById("preview-dims");

// ---------- Preview scaling ---------------------------------------------
// The iframe renders at the panel's native pixel resolution so widgets see
// the same viewport they will at push time. We pick the largest scale that
// fits within both the available column width AND the available viewport
// height — otherwise a portrait panel (e.g. 480×800) overflows into a tall
// canvas you have to scroll. Both width AND height matter.
const editorRoot = document.getElementById("editor");
const PANEL_W = parseFloat(getComputedStyle(editorRoot).getPropertyValue("--panel-w")) || 800;
const PANEL_H = parseFloat(getComputedStyle(editorRoot).getPropertyValue("--panel-h")) || 480;
if (previewDims) previewDims.textContent = `${PANEL_W}×${PANEL_H}`;

function rescalePreview() {
  if (!previewWrap) return;
  const outerWrap = previewWrap.parentElement; // .preview-frame-wrap
  if (!outerWrap) return;
  const colWidth = outerWrap.parentElement.clientWidth;
  if (!colWidth) return;
  // Outer wrap has 8px padding + 1px border on each side = 18px overhead.
  const availW = Math.max(0, colWidth - 18);
  // Available height: viewport minus chrome (header, top bar, meta line).
  const stickyTop = 60 /* header */ + 16 /* top offset */ + 60 /* top bar */;
  const metaSpace = 40;
  const availH = Math.max(200, window.innerHeight - stickyTop - metaSpace - 18);
  const scale = Math.min(availW / PANEL_W, availH / PANEL_H);
  const w = Math.floor(PANEL_W * scale);
  const h = Math.floor(PANEL_H * scale);
  previewWrap.style.width = `${w}px`;
  previewWrap.style.height = `${h}px`;
  previewWrap.style.setProperty("--preview-scale", String(scale));
}
rescalePreview();
window.addEventListener("resize", rescalePreview);
if (typeof ResizeObserver !== "undefined" && previewWrap?.parentElement?.parentElement) {
  new ResizeObserver(rescalePreview).observe(previewWrap.parentElement.parentElement);
}

// ---------- Module-level state (declared up front to satisfy TDZ) ------

let draftTimer = null;
let draftSeq = 0;
const choicesCache = new Map();

// ---------- Model -------------------------------------------------------

const state = {
  id: initial.id || null,
  page: deepClone(initial),
};
ensureCellsMatchLayout(state.page);

// ---------- Initial UI build --------------------------------------------

buildLayoutPicker();
injectFontFaces();
buildThemeSelect(form.elements.theme, "Default");
form.elements.theme.value = state.page.theme || "";
buildThemeSelect(form.elements.header_theme, "(use page theme)");
form.elements.name.value = state.page.name || "";
form.elements.layout.value = state.page.layout;
setColorInput("bg_color", state.page.bg_color || "#ffffff");
// Use ?? so an explicit 0 in initial_page is preserved; only a missing
// field falls back to the new-dashboard defaults (38 / 20).
setSlider("cell_gap", state.page.cell_gap ?? 38);
setSlider("cell_radius", state.page.cell_radius ?? 20);
form.elements.theme.value = state.page.theme || "";
form.elements.header_theme.value = state.page.header_theme || "";
setIcon(state.page.icon || "");
markActiveLayoutTile(state.page.layout);
renderCells();
attachFormListeners();
attachActionButtons();
attachIconPicker();

scheduleDraft({ immediate: true });

// ---------- Layout picker ----------------------------------------------

function buildLayoutPicker() {
  const host = document.getElementById("layout-picker");
  for (const id of Object.keys(LAYOUTS)) {
    const tile = document.createElement("button");
    tile.type = "button";
    tile.className = "layout-tile";
    tile.dataset.layout = id;
    tile.title = LAYOUT_LABELS[id];
    tile.innerHTML = layoutSvg(LAYOUTS[id]) + `<span>${LAYOUT_LABELS[id]}</span>`;
    tile.addEventListener("click", () => onLayoutChange(id));
    host.appendChild(tile);
  }
}

function layoutSvg(rects) {
  const inner = rects.map(([x, y, w, h]) =>
    `<rect x="${x*56+1}" y="${y*36+1}" width="${w*56-2}" height="${h*36-2}" rx="2"/>`
  ).join("");
  return `<svg viewBox="0 0 56 36">${inner}</svg>`;
}

function markActiveLayoutTile(id) {
  document.querySelectorAll(".layout-tile").forEach((t) =>
    t.classList.toggle("active", t.dataset.layout === id)
  );
}

function onLayoutChange(layout) {
  state.page.layout = layout;
  form.elements.layout.value = layout;
  markActiveLayoutTile(layout);
  ensureCellsMatchLayout(state.page);
  renderCells();
  scheduleDraft();
}

// ---------- Theme picker -----------------------------------------------

// Inject @font-face for the single global font (if any), so theme tile
// labels render in the actual app font. Done once on editor boot.
function injectFontFaces() {
  if (document.getElementById("editor-font-faces")) return;
  const f = globalFont();
  if (!f || f.is_system || !Array.isArray(f.weights)) return;
  const sheet = document.createElement("style");
  sheet.id = "editor-font-faces";
  let css = "";
  for (const w of f.weights) {
    css += `@font-face{font-family:"${f.family}";src:url("${w.url}") format("woff2");font-weight:${w.weight};font-style:normal;font-display:block;}`;
  }
  sheet.textContent = css;
  document.head.appendChild(sheet);
}

function globalFont() {
  if (!catalog.default_font) return null;
  return catalog.fonts.find((x) => x.id === catalog.default_font) || null;
}

function globalFontFamily() {
  const f = globalFont();
  if (!f) return null;
  return `"${f.family}", ${f.fallback_stack || "system-ui, sans-serif"}`;
}

// Light vs dark heuristic — relative luminance of the bg palette key.
// Using the standard sRGB luma weights so the split matches what the eye sees.
function isLightTheme(theme) {
  const hex = (theme && theme.palette && theme.palette.bg) || "#000000";
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return false;
  const r = parseInt(m[1].slice(0, 2), 16);
  const g = parseInt(m[1].slice(2, 4), 16);
  const b = parseInt(m[1].slice(4, 6), 16);
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) > 140;
}

// Page theme + header theme are both dropdowns. The "Default" entry maps to
// an empty value (no override). Light and dark themes are split into two
// optgroups so the picker is easier to scan as the catalog grows.
function buildThemeSelect(selectEl, blankLabel) {
  selectEl.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = ""; blank.textContent = blankLabel;
  selectEl.appendChild(blank);
  const light = catalog.themes.filter(isLightTheme);
  const dark = catalog.themes.filter((t) => !isLightTheme(t));
  appendOptgroup(selectEl, "Light", light);
  appendOptgroup(selectEl, "Dark", dark);
}

function appendOptgroup(selectEl, label, themes) {
  if (!themes.length) return;
  const group = document.createElement("optgroup");
  group.label = label;
  for (const t of themes) {
    const o = document.createElement("option");
    o.value = t.id;
    o.textContent = t.label;
    group.appendChild(o);
  }
  selectEl.appendChild(group);
}

// ---------- Cells -------------------------------------------------------

function ensureCellsMatchLayout(page) {
  const need = LAYOUTS[page.layout]?.length ?? 1;
  page.cells = page.cells || [];
  if (page.cells.length > need) page.cells.length = need;
  while (page.cells.length < need) {
    page.cells.push({ widget: defaultWidgetId(), options: {} });
  }
  // Fill in any empty widget refs (e.g., the blank-cell default for new pages).
  for (const c of page.cells) {
    if (!c.widget) c.widget = defaultWidgetId();
    if (!c.options) c.options = {};
  }
}

function defaultWidgetId() {
  const enabled = catalog.widgets.find((w) => w.enabled);
  return enabled ? enabled.id : (catalog.widgets[0]?.id || "");
}

function renderCells() {
  const list = document.getElementById("cell-list");
  const empty = document.getElementById("cells-empty");
  list.innerHTML = "";
  if (!state.page.cells.length) {
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  state.page.cells.forEach((cell, i) => {
    const node = document.getElementById("cell-template").content.firstElementChild.cloneNode(true);
    node.querySelector(".cell-index").textContent = String(i + 1);
    const widgetSel = node.querySelector(".cell-widget");
    const themeSel = node.querySelector(".cell-theme");
    populateWidgetSelect(widgetSel, cell.widget);
    populateCellThemeSelect(themeSel, cell.theme || "");
    widgetSel.addEventListener("change", () => {
      state.page.cells[i].widget = widgetSel.value;
      state.page.cells[i].options = {};
      renderCellOptions(node.querySelector(".cell-options"), i);
      scheduleDraft();
    });
    themeSel.addEventListener("change", () => {
      state.page.cells[i].theme = themeSel.value || null;
      scheduleDraft();
    });
    list.appendChild(node);
    renderCellOptions(node.querySelector(".cell-options"), i);
  });
}

function populateWidgetSelect(sel, current) {
  sel.innerHTML = "";
  for (const w of catalog.widgets) {
    const o = document.createElement("option");
    o.value = w.id;
    o.textContent = w.enabled ? w.label : `${w.label} (disabled)`;
    sel.appendChild(o);
  }
  if (current && !catalog.widgets.some((w) => w.id === current)) {
    // Page references a widget not currently loaded — keep it visible but mark.
    const o = document.createElement("option");
    o.value = current;
    o.textContent = `${current} (missing)`;
    sel.appendChild(o);
  }
  sel.value = current || "";
}

function populateCellThemeSelect(sel, current) {
  sel.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = ""; blank.textContent = "(use page theme)";
  sel.appendChild(blank);
  appendOptgroup(sel, "Light", catalog.themes.filter(isLightTheme));
  appendOptgroup(sel, "Dark", catalog.themes.filter((t) => !isLightTheme(t)));
  sel.value = current || "";
}

async function renderCellOptions(host, cellIndex) {
  host.innerHTML = "";
  const cell = state.page.cells[cellIndex];
  const widget = catalog.widgets.find((w) => w.id === cell.widget);
  if (!widget || !widget.cell_options?.length) return;
  for (const opt of widget.cell_options) {
    const node = await buildOptionField(opt, cell.options[opt.name], (val) => {
      if (val === "" || val === undefined || val === null) {
        delete state.page.cells[cellIndex].options[opt.name];
      } else {
        state.page.cells[cellIndex].options[opt.name] = val;
      }
      scheduleDraft();
    });
    host.appendChild(node);
  }
}

async function buildOptionField(opt, value, onChange) {
  const wrap = document.createElement("label");
  wrap.textContent = opt.label || opt.name;
  const initial = value ?? opt.default ?? "";
  let input;
  switch (opt.type) {
    case "bool": {
      // Use the global switch component (CSS-only, see base.css `.switch`).
      wrap.classList.add("opt-bool");
      const sw = document.createElement("span");
      sw.className = "switch";
      input = document.createElement("input");
      input.type = "checkbox";
      input.checked = !!initial;
      bind(input, "change", () => onChange(input.checked));
      sw.appendChild(input);
      const track = document.createElement("span"); track.className = "track"; sw.appendChild(track);
      const thumb = document.createElement("span"); thumb.className = "thumb"; sw.appendChild(thumb);
      // Replace the standard "label above input" layout with an inline row.
      wrap.style.display = "flex";
      wrap.style.flexDirection = "row";
      wrap.style.justifyContent = "space-between";
      wrap.style.alignItems = "center";
      wrap.appendChild(sw);
      return wrap;  // skip the default `wrap.appendChild(input)` below
    }
    case "int":
    case "float": {
      input = document.createElement("input");
      input.type = "number";
      if (opt.type === "int") input.step = "1";
      input.value = initial;
      bind(input, "input", () => {
        const v = input.value === "" ? "" : (opt.type === "int" ? parseInt(input.value, 10) : parseFloat(input.value));
        onChange(v);
      });
      break;
    }
    case "select": {
      input = document.createElement("select");
      const blank = document.createElement("option");
      blank.value = ""; blank.textContent = "(none)";
      input.appendChild(blank);
      const choices = opt.choices ?? (opt.choices_from ? await fetchChoices(opt.choices_from) : []);
      for (const c of choices || []) {
        const o = document.createElement("option");
        o.value = c.value; o.textContent = c.label || c.value;
        input.appendChild(o);
      }
      input.value = initial;
      bind(input, "change", () => onChange(input.value));
      break;
    }
    case "color": {
      input = document.createElement("input");
      input.type = "color";
      input.value = (typeof initial === "string" && initial) ? initial : "#000000";
      bind(input, "input", () => onChange(input.value));
      break;
    }
    case "date": {
      // HTML5 date input. Pre-populates from the current value if it parses
      // as YYYY-MM-DD; falls back to the option's default (which can be
      // either a literal date string OR the sentinel "today+Nd" — server-
      // side resolves that, but the editor still needs to render *some*
      // value, so we expand the sentinel here too).
      input = document.createElement("input");
      input.type = "date";
      let dv = (typeof initial === "string" ? initial : "").trim();
      if (dv.startsWith("today")) dv = expandTodaySentinel(dv);
      // Trim any time portion so the date input accepts it.
      if (dv.includes("T")) dv = dv.slice(0, 10);
      input.value = dv;
      bind(input, "input", () => onChange(input.value));
      break;
    }
    case "image":
    case "text":
    case "secret":
    default: {
      input = document.createElement("input");
      input.type = opt.type === "secret" ? "password" : "text";
      input.value = initial;
      bind(input, "input", () => onChange(input.value));
      break;
    }
  }
  wrap.appendChild(input);
  return wrap;
}

function bind(el, event, handler) {
  el.addEventListener(event, handler);
  // Per rule 9: text/range get debounced input + immediate change to keep
  // sliders smooth and selects snappy.
  if (event === "input") el.addEventListener("change", handler);
}

// Expand a "today+Nd" sentinel into a YYYY-MM-DD string so the date
// picker can render it. Plugin servers also accept this sentinel and
// resolve it on their side, but the picker UI needs a literal date.
function expandTodaySentinel(s) {
  const m = /^today(?:([+-])(\d+)d)?$/i.exec(s.trim());
  if (!m) return "";
  const offset = m[1] && m[2] ? (m[1] === "-" ? -1 : 1) * parseInt(m[2], 10) : 0;
  const d = new Date();
  d.setDate(d.getDate() + offset);
  return d.toISOString().slice(0, 10);
}

async function fetchChoices(name) {
  if (choicesCache.has(name)) return choicesCache.get(name);
  const r = await fetch(`/api/choices/${encodeURIComponent(name)}`);
  if (!r.ok) return [];
  const body = await r.json();
  const arr = body.choices || [];
  choicesCache.set(name, arr);
  return arr;
}

// ---------- Page-level form bindings -----------------------------------

function attachFormListeners() {
  // Name
  bind(form.elements.name, "input", () => { state.page.name = form.elements.name.value; scheduleDraft(); });

  // bg_color (color picker + linked text input)
  const colorEl = form.elements.bg_color;
  const colorTxt = form.querySelector('.color-text[data-bind="bg_color"]');
  bind(colorEl, "input", () => {
    state.page.bg_color = colorEl.value;
    colorTxt.value = colorEl.value;
    scheduleDraft();
  });
  bind(colorTxt, "input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(colorTxt.value)) {
      colorEl.value = colorTxt.value;
      state.page.bg_color = colorTxt.value;
      scheduleDraft();
    }
  });

  // Sliders
  bindSlider("cell_gap");
  bindSlider("cell_radius");

  bind(form.elements.theme, "change", () => { state.page.theme = form.elements.theme.value || null; scheduleDraft(); });
  bind(form.elements.header_theme, "change", () => { state.page.header_theme = form.elements.header_theme.value || null; scheduleDraft(); });

  // Submit-via-enter is no-op
  form.addEventListener("submit", (e) => e.preventDefault());
}

function bindSlider(name) {
  const el = form.elements[name];
  const readout = form.querySelector(`[data-readout="${name}"]`);
  bind(el, "input", () => {
    const v = parseInt(el.value, 10) || 0;
    state.page[name] = v;
    readout.textContent = `${v}px`;
    scheduleDraft();
  });
}

function setSlider(name, value) {
  form.elements[name].value = value;
  const readout = form.querySelector(`[data-readout="${name}"]`);
  if (readout) readout.textContent = `${value}px`;
  state.page[name] = value;
}

function setColorInput(name, value) {
  form.elements[name].value = value;
  const txt = form.querySelector(`.color-text[data-bind="${name}"]`);
  if (txt) txt.value = value;
  state.page[name] = value;
}

// ---------- Icon picker -------------------------------------------------

function setIcon(iconId) {
  state.page.icon = iconId || null;
  form.elements.icon.value = iconId || "";
  const preview = document.getElementById("icon-preview");
  const nameEl = document.getElementById("icon-name");
  preview.className = iconId ? `ph ph-${iconId}` : "ph ph-image-square";
  nameEl.textContent = iconId || "none";
}

function attachIconPicker() {
  const wrap = document.getElementById("icon-dropdown");
  const trigger = document.getElementById("icon-trigger");
  const popover = document.getElementById("icon-popover");
  const grid = document.getElementById("icon-grid");
  const searchInput = document.getElementById("icon-search");
  const emptyMsg = document.getElementById("icon-empty");
  let icons = [];
  let loaded = false;
  let query = "";

  function open() {
    wrap.dataset.open = "true";
    trigger.setAttribute("aria-expanded", "true");
    popover.hidden = false;
    setTimeout(() => searchInput.focus(), 0);
  }
  function close() {
    wrap.dataset.open = "false";
    trigger.setAttribute("aria-expanded", "false");
    popover.hidden = true;
  }
  function isOpen() { return wrap.dataset.open === "true"; }

  trigger.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (isOpen()) { close(); return; }
    if (!loaded) {
      icons = await fetch("/static/data/phosphor-icons.json").then((r) => r.json());
      loaded = true;
    }
    render();
    open();
  });

  document.addEventListener("click", (ev) => {
    if (!isOpen()) return;
    if (!wrap.contains(ev.target)) close();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && isOpen()) { close(); trigger.focus(); }
  });
  document.getElementById("icon-clear").addEventListener("click", () => {
    setIcon("");
    scheduleDraft();
  });

  searchInput.addEventListener("input", () => {
    query = searchInput.value.trim().toLowerCase();
    render();
  });

  function render() {
    grid.innerHTML = "";
    const filtered = query
      ? icons.filter((i) => i.name.includes(query))
      : icons;
    const fragment = document.createDocumentFragment();
    for (const i of filtered) {
      const cell = document.createElement("button");
      cell.type = "button";
      cell.className = "icon-cell" + (state.page.icon === i.name ? " active" : "");
      cell.title = i.name;
      cell.innerHTML = `<i class="ph ph-${i.name}"></i>`;
      cell.addEventListener("click", () => {
        setIcon(i.name);
        scheduleDraft();
        close();
      });
      fragment.appendChild(cell);
    }
    grid.appendChild(fragment);
    emptyMsg.hidden = filtered.length > 0;
  }
}

// ---------- Draft preview (debounced) ----------------------------------

function scheduleDraft({ immediate = false } = {}) {
  clearTimeout(draftTimer);
  if (immediate) return pushDraft();
  draftTimer = setTimeout(pushDraft, 250);
}

async function pushDraft() {
  const seq = ++draftSeq;
  previewStatus.textContent = "Updating preview…";
  try {
    const r = await fetch("/api/preview-page-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(serializePage()),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { draft_id } = await r.json();
    if (seq !== draftSeq) return;  // a newer draft is in flight
    iframe.src = `/compose/draft/${draft_id}?preview=1`;
    previewStatus.textContent = `Live · draft ${draft_id}`;
  } catch (err) {
    previewStatus.textContent = `Preview error: ${err.message}`;
  }
}

function serializePage() {
  // Collect what we have; the server applies defaults + slug.
  const p = state.page;
  const out = {
    name: p.name || "Untitled",
    layout: p.layout,
    cells: p.cells.map((c) => ({
      widget: c.widget,
      options: c.options || {},
      ...(c.theme ? { theme: c.theme } : {}),
    })),
  };
  if (p.id) out.id = p.id;
  if (p.cell_gap) out.cell_gap = p.cell_gap;
  if (p.cell_radius) out.cell_radius = p.cell_radius;
  if (p.bg_color && p.bg_color.toLowerCase() !== "#ffffff") out.bg_color = p.bg_color;
  if (p.icon) out.icon = p.icon;
  if (p.theme) out.theme = p.theme;
  if (p.header_theme) out.header_theme = p.header_theme;
  if (p.font) out.font = p.font;
  return out;
}

// ---------- Action buttons ---------------------------------------------

function attachActionButtons() {
  document.querySelectorAll('[data-action]').forEach((btn) => {
    btn.addEventListener("click", () => onAction(btn.dataset.action));
  });
}

async function onAction(action) {
  const wantsPush = action === "save-push" || action === "push-no-save";
  const wantsSave = action === "save-only" || action === "save-push";

  if (wantsSave) {
    setStatus("saving", "Saving…");
    try {
      const saved = await savePage();
      state.id = saved.id;
      state.page.id = saved.id;
      // If we were on /dashboards/new, swap URL to the canonical edit URL
      if (location.pathname.endsWith("/new")) {
        history.replaceState(null, "", `/dashboards/${encodeURIComponent(saved.id)}/edit`);
      }
      setStatus("saved", `Saved · id=${saved.id}`);
    } catch (err) {
      setStatus("error", `Save failed: ${err.message}`);
      return;
    }
  }

  if (wantsPush) {
    setStatus("saving", "Rendering & pushing…");
    setPushButtonsEnabled(false);
    try {
      let r;
      if (action === "save-push") {
        r = await fetch(`/api/push/${encodeURIComponent(state.id)}`, { method: "POST" });
      } else {
        const draft = await fetch("/api/preview-page-draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(serializePage()),
        }).then((x) => x.json());
        r = await fetch(`/api/push-draft/${encodeURIComponent(draft.draft_id)}`, { method: "POST" });
      }
      const body = await r.json().catch(() => ({}));
      if (r.status === 409) {
        setStatus("error", body.error || "A push is already running");
      } else if (r.status === 400) {
        setStatus("error", body.error || "Invalid push options");
      } else if (!r.ok) {
        throw new Error(body.error || `HTTP ${r.status}`);
      } else {
        const dur = body.duration_s ? `${body.duration_s.toFixed(2)}s` : "";
        setStatus("saved", `Pushed · history #${body.history_id} · ${dur}`);
        startLockoutCountdown();
      }
    } catch (err) {
      setStatus("error", `Push failed: ${err.message}`);
    } finally {
      // Buttons are re-enabled by the lockout countdown if it kicked off,
      // or here if we never started it (error path).
      if (!lockoutTimer) setPushButtonsEnabled(true);
    }
  }
}

let lockoutTimer = null;
function setPushButtonsEnabled(enabled) {
  document.querySelectorAll('[data-action="save-push"], [data-action="push-no-save"]').forEach((b) => {
    b.disabled = !enabled;
  });
}

async function startLockoutCountdown() {
  // Re-enables push buttons after the configured lockout while the panel paints.
  // Reads the lockout from the server so REFRESH_LOCKOUT_SECONDS stays the source of truth.
  let secs = 30;
  try {
    const s = await fetch("/api/push/state").then((r) => r.json());
    if (Number.isFinite(s.lockout_seconds)) secs = s.lockout_seconds;
  } catch (_) { /* keep default */ }
  setPushButtonsEnabled(false);
  let remaining = secs;
  if (lockoutTimer) clearInterval(lockoutTimer);
  lockoutTimer = setInterval(() => {
    remaining -= 1;
    if (remaining <= 0) {
      clearInterval(lockoutTimer);
      lockoutTimer = null;
      setPushButtonsEnabled(true);
    }
  }, 1000);
}

async function savePage() {
  const body = serializePage();
  const isNew = !state.id;
  const url = isNew ? "/api/pages" : `/api/pages/${encodeURIComponent(state.id)}`;
  const method = isNew ? "POST" : "PUT";
  const r = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text();
    throw new Error(`HTTP ${r.status}: ${detail.slice(0, 80)}`);
  }
  return r.json();
}

function setStatus(state, msg) {
  window.inkyStatus(state, msg);
}

function deepClone(x) { return JSON.parse(JSON.stringify(x)); }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
