// Settings page controller.
//
// Loads /api/settings, renders one card per section (base + each plugin),
// collects values into a single typed dict, POSTs back. After save the
// server schedules a restart; we poll /api/status until the new instance
// answers, then reload to show the fresh values.

const sectionsEl = document.getElementById("sections");
const sectionsNav = document.getElementById("sections-nav");
const saveBtn = document.getElementById("save-btn");
const envHint = document.getElementById("env-hint");

const fieldRefs = new Map(); // key → { type, getValue, hasInitialSecret }

// Inky Impression panel presets — width × height in landscape (long side first).
const PANEL_PRESETS = [
  { id: "impression_4",    label: "Inky Impression 4\"",     w: 640,  h: 400 },
  { id: "impression_5_7",  label: "Inky Impression 5.7\"",   w: 600,  h: 448 },
  { id: "impression_7_3",  label: "Inky Impression 7.3\"",   w: 800,  h: 480 },
  { id: "impression_13_3", label: "Inky Impression 13.3\"",  w: 1600, h: 1200 },
];

function detectPreset(w, h) {
  for (const p of PANEL_PRESETS) {
    if (p.w === w && p.h === h) return { preset: p, portrait: false };
    if (p.h === w && p.w === h) return { preset: p, portrait: true };
  }
  return { preset: null, portrait: h > w };
}

load();
saveBtn.addEventListener("click", save);

async function load() {
  try {
    const r = await fetch("/api/settings");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const body = await r.json();
    envHint.textContent = `Persisted to ${body.env_path}`;
    renderSections(body.sections);
  } catch (err) {
    sectionsEl.innerHTML = `<p class="muted small">Failed to load: ${escapeHtml(err.message)}</p>`;
  }
}

function renderSections(sections) {
  sectionsEl.innerHTML = "";
  if (sectionsNav) sectionsNav.innerHTML = "";
  fieldRefs.clear();
  if (!sections.length) {
    sectionsEl.innerHTML = `<p class="muted small">No settings declared.</p>`;
    return;
  }
  for (const s of sections) {
    const card = renderSection(s);
    sectionsEl.appendChild(card);
    if (sectionsNav) sectionsNav.appendChild(buildNavLink(s, card.id));
  }
  wireScrollSpy();
}

function sectionSlug(s) {
  const base = (s.plugin_id || s.title || "section")
    .toString()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
  return `section-${base || "untitled"}`;
}

function buildNavLink(s, id) {
  const a = document.createElement("a");
  a.className = "settings-nav-link";
  a.href = `#${id}`;
  a.dataset.target = id;
  a.textContent = s.title;
  if (s.plugin_id) {
    const tag = document.createElement("span");
    tag.className = "settings-nav-tag";
    tag.textContent = "plugin";
    a.appendChild(tag);
  }
  a.addEventListener("click", (ev) => {
    ev.preventDefault();
    const card = document.getElementById(id);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "start" });
    history.replaceState(null, "", `#${id}`);
    sectionsNav.querySelectorAll(".settings-nav-link.active").forEach((x) => x.classList.remove("active"));
    a.classList.add("active");
  });
  return a;
}

function wireScrollSpy() {
  if (!sectionsNav) return;
  const links = Array.from(sectionsNav.querySelectorAll(".settings-nav-link"));
  const cards = links
    .map((a) => document.getElementById(a.dataset.target))
    .filter(Boolean);
  if (!cards.length) return;
  const setActive = (id) => {
    for (const a of links) a.classList.toggle("active", a.dataset.target === id);
  };
  setActive(cards[0].id);
  const io = new IntersectionObserver(
    (entries) => {
      // Pick the topmost card that's intersecting the viewport.
      const visible = entries
        .filter((e) => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
      if (visible[0]) setActive(visible[0].target.id);
    },
    { rootMargin: "-20% 0px -60% 0px", threshold: 0 },
  );
  for (const card of cards) io.observe(card);
}

function renderSection(s) {
  const card = document.createElement("section");
  card.className = "card settings-section";
  card.id = sectionSlug(s);
  const head = document.createElement("header");
  const h2 = document.createElement("h2");
  h2.textContent = s.title;
  head.appendChild(h2);
  if (s.plugin_id) {
    const badge = document.createElement("span");
    badge.className = "plugin-badge";
    badge.textContent = `from plugin: ${s.plugin_id}`;
    head.appendChild(badge);
  }
  card.appendChild(head);
  for (const f of s.fields) {
    card.appendChild(renderField(f));
  }
  if (s.title === "Panel") {
    attachPanelPresets(card);
  }
  return card;
}

function attachPanelPresets(card) {
  const wInput = card.querySelector("#field-PANEL_WIDTH");
  const hInput = card.querySelector("#field-PANEL_HEIGHT");
  if (!wInput || !hInput) return;

  const row = document.createElement("div");
  row.className = "field panel-preset-row";

  const labelRow = document.createElement("div");
  labelRow.className = "label-row";
  const label = document.createElement("label");
  label.textContent = "Preset";
  label.htmlFor = "panel-preset-select";
  labelRow.appendChild(label);
  row.appendChild(labelRow);

  const controls = document.createElement("div");
  controls.className = "panel-preset-controls";

  const sel = document.createElement("select");
  sel.id = "panel-preset-select";
  for (const p of PANEL_PRESETS) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.label;
    sel.appendChild(opt);
  }
  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "Custom";
  sel.appendChild(customOpt);
  controls.appendChild(sel);

  const orient = document.createElement("label");
  orient.className = "panel-orient";
  const orientText = document.createElement("span");
  orientText.className = "panel-orient-label";
  orientText.textContent = "Portrait";
  orient.appendChild(orientText);
  const sw = document.createElement("label");
  sw.className = "switch";
  const cb = document.createElement("input");
  cb.type = "checkbox";
  cb.id = "panel-orient-toggle";
  sw.appendChild(cb);
  const track = document.createElement("span"); track.className = "track"; sw.appendChild(track);
  const thumb = document.createElement("span"); thumb.className = "thumb"; sw.appendChild(thumb);
  orient.appendChild(sw);
  controls.appendChild(orient);

  row.appendChild(controls);

  const help = document.createElement("p");
  help.className = "help";
  help.textContent = "Picks PANEL_WIDTH/HEIGHT for the chosen Impression panel. Toggle for portrait orientation.";
  row.appendChild(help);

  // Insert preset row above the width/height fields.
  const wField = wInput.closest(".field");
  card.insertBefore(row, wField);

  let suppressDetect = false;
  const syncFromInputs = () => {
    if (suppressDetect) return;
    const w = parseInt(wInput.value, 10);
    const h = parseInt(hInput.value, 10);
    if (!Number.isFinite(w) || !Number.isFinite(h)) {
      sel.value = "custom";
      return;
    }
    const { preset, portrait } = detectPreset(w, h);
    sel.value = preset ? preset.id : "custom";
    cb.checked = portrait;
  };

  const applyPreset = () => {
    if (sel.value === "custom") return;
    const p = PANEL_PRESETS.find((x) => x.id === sel.value);
    if (!p) return;
    suppressDetect = true;
    if (cb.checked) {
      wInput.value = p.h;
      hInput.value = p.w;
    } else {
      wInput.value = p.w;
      hInput.value = p.h;
    }
    suppressDetect = false;
  };

  sel.addEventListener("change", () => {
    if (sel.value === "custom") return;
    applyPreset();
  });
  cb.addEventListener("change", () => {
    if (sel.value === "custom") {
      // Swap the current values so the user can flip a custom panel too.
      const w = wInput.value, h = hInput.value;
      suppressDetect = true;
      wInput.value = h;
      hInput.value = w;
      suppressDetect = false;
      return;
    }
    applyPreset();
  });
  wInput.addEventListener("input", syncFromInputs);
  hInput.addEventListener("input", syncFromInputs);

  syncFromInputs();
}

function renderField(f) {
  const row = document.createElement("div");
  row.className = `field type-${f.type}` + (f.type === "bool" ? " bool" : "") + (f.type === "secret" ? " secret" : "");

  const labelRow = document.createElement("div");
  labelRow.className = "label-row";
  const label = document.createElement("label");
  label.textContent = f.label;
  label.htmlFor = `field-${f.key}`;
  labelRow.appendChild(label);
  const keyTag = document.createElement("span");
  keyTag.className = "key-tag";
  keyTag.textContent = f.key;
  labelRow.appendChild(keyTag);
  row.appendChild(labelRow);

  let getValue;
  if (f.type === "bool") {
    const sw = document.createElement("label");
    sw.className = "switch";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.id = `field-${f.key}`;
    cb.checked = !!f.value;
    sw.appendChild(cb);
    const track = document.createElement("span"); track.className = "track"; sw.appendChild(track);
    const thumb = document.createElement("span"); thumb.className = "thumb"; sw.appendChild(thumb);
    row.appendChild(sw);
    getValue = () => cb.checked;
  } else if (f.type === "secret") {
    const wrap = document.createElement("div");
    wrap.className = "secret-row";
    const input = document.createElement("input");
    input.type = "password";
    input.id = `field-${f.key}`;
    input.placeholder = f.has_value ? "(set — leave blank to keep)" : "(unset)";
    input.autocomplete = "new-password";
    wrap.appendChild(input);
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "btn ghost";
    toggle.innerHTML = `<i class="ph ph-eye"></i>`;
    toggle.addEventListener("click", () => {
      input.type = input.type === "password" ? "text" : "password";
      toggle.innerHTML = input.type === "password" ? `<i class="ph ph-eye"></i>` : `<i class="ph ph-eye-slash"></i>`;
    });
    wrap.appendChild(toggle);
    const state = document.createElement("span");
    state.className = "secret-state";
    state.textContent = f.has_value ? "stored" : "not set";
    wrap.appendChild(state);
    row.appendChild(wrap);
    getValue = () => input.value;  // empty = keep current (server-side)
  } else if (f.type === "select") {
    const sel = document.createElement("select");
    sel.id = `field-${f.key}`;
    const choices = f.choices || [];
    for (const c of choices) {
      const opt = document.createElement("option");
      const val = typeof c === "object" ? c.value : c;
      const lbl = typeof c === "object" ? (c.label || c.value) : c;
      opt.value = val; opt.textContent = lbl;
      sel.appendChild(opt);
    }
    sel.value = f.value ?? f.default ?? "";
    row.appendChild(sel);
    getValue = () => sel.value;
  } else if (f.type === "color") {
    const input = document.createElement("input");
    input.type = "color";
    input.id = `field-${f.key}`;
    input.value = (f.value && /^#[0-9a-fA-F]{6}$/.test(f.value)) ? f.value : (f.default || "#000000");
    row.appendChild(input);
    getValue = () => input.value;
  } else if (f.type === "int" || f.type === "float") {
    const input = document.createElement("input");
    input.type = "number";
    input.id = `field-${f.key}`;
    if (f.type === "int") input.step = "1";
    input.value = f.value ?? f.default ?? "";
    row.appendChild(input);
    getValue = () => input.value === "" ? "" : (f.type === "int" ? parseInt(input.value, 10) : parseFloat(input.value));
  } else {
    const input = document.createElement("input");
    input.type = "text";
    input.id = `field-${f.key}`;
    input.value = f.value ?? f.default ?? "";
    row.appendChild(input);
    getValue = () => input.value;
  }

  if (f.help) {
    const help = document.createElement("p");
    help.className = "help";
    help.textContent = f.help;
    row.appendChild(help);
  }

  fieldRefs.set(f.key, { type: f.type, getValue });
  return row;
}

async function save() {
  const values = {};
  for (const [key, ref] of fieldRefs) {
    const v = ref.getValue();
    if (ref.type === "secret" && (v === "" || v === null || v === undefined)) {
      // empty = keep existing — don't include in payload
      continue;
    }
    values[key] = v;
  }

  setStatus("saving", "Saving…");
  saveBtn.disabled = true;
  let response;
  try {
    const r = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ values }),
    });
    response = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(response.error || `HTTP ${r.status}`);
  } catch (err) {
    setStatus("error", `Save failed: ${err.message}`);
    saveBtn.disabled = false;
    return;
  }

  setStatus("restarting", `Saved ${response.updated_keys.length} key(s) — restarting…`);
  await waitForRestart();
}

async function waitForRestart() {
  // Wait for the current process to die (next request fails), then for the
  // new process to come back. If the request keeps succeeding for too long
  // the server probably wasn't restarted (e.g., _no_restart was set).
  const deadline = Date.now() + 30_000;
  let sawDown = false;
  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (r.ok && sawDown) {
        // Came back up.
        location.reload();
        return;
      }
      if (!sawDown && !r.ok) sawDown = true;
    } catch (_) {
      sawDown = true;
    }
  }
  setStatus("error", "Server didn't come back within 30s. Check the terminal.");
  saveBtn.disabled = false;
}

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
