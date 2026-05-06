// Schedule editor: kind tabs, common fields, advanced push options, save+delete.

const initial = JSON.parse(document.getElementById("initial-schedule").textContent);

const state = {
  id: initial?.id || null,
  kind: initial?.kind || "interval",
};

initKindTabs();
populateForm();
bindFormHandlers();
document.getElementById("save-btn").addEventListener("click", save);
document.getElementById("delete-btn")?.addEventListener("click", del);

function initKindTabs() {
  document.querySelectorAll(".kind-tabs .tab").forEach((t) => {
    t.classList.toggle("active", t.dataset.kind === state.kind);
    t.addEventListener("click", () => setKind(t.dataset.kind));
  });
  applyKindVisibility();
}

function setKind(kind) {
  state.kind = kind;
  document.querySelectorAll(".kind-tabs .tab").forEach((t) =>
    t.classList.toggle("active", t.dataset.kind === kind));
  applyKindVisibility();
}

function applyKindVisibility() {
  document.querySelectorAll(".kind-pane").forEach((pane) => {
    pane.hidden = pane.dataset.kind !== state.kind;
  });
}

function populateForm() {
  if (!initial) return;
  document.getElementById("schedule-name").value = initial.name || "";
  document.getElementById("target-page").value = initial.target?.page_id || "";
  document.getElementById("schedule-color").value = initial.color || "#b85a3f";
  document.getElementById("schedule-color-text").value = initial.color || "#b85a3f";
  document.getElementById("schedule-enabled").checked = initial.enabled !== false;

  if (initial.kind === "one_shot") {
    // `at` is HH:MM in the new model; tolerate legacy ISO datetimes by
    // extracting the time portion (e.g. "2026-05-10T18:00:00" → "18:00").
    let at = initial.at || "";
    if (at.includes("T")) at = at.slice(11, 16);
    document.getElementById("one-shot-at").value = at;
  } else {
    document.getElementById("every-minutes").value = initial.every_minutes ?? 15;
    document.getElementById("start-time").value = initial.start_time || "08:00";
    document.getElementById("end-time").value = initial.end_time || "20:00";
  }

  // Days of week — used by both kinds.
  const dow = new Set(initial.days_of_week || []);
  document.querySelectorAll(".dow-cb").forEach((cb) => {
    cb.checked = dow.has(parseInt(cb.value, 10));
  });

  // Advanced options
  const opts = initial.options || {};
  for (const k of ["rotate", "scale", "bg"]) {
    const el = document.querySelector(`select[name="${k}"]`);
    if (el && k in opts) el.value = String(opts[k]);
  }
  const sat = document.querySelector('input[name="saturation"]');
  if ("saturation" in opts) sat.value = String(opts.saturation);
  updateSaturationReadout();
}

function bindFormHandlers() {
  // Color text + picker round-trip
  const color = document.getElementById("schedule-color");
  const colorText = document.getElementById("schedule-color-text");
  color.addEventListener("input", () => { colorText.value = color.value; });
  colorText.addEventListener("input", () => {
    if (/^#[0-9a-fA-F]{6}$/.test(colorText.value)) color.value = colorText.value;
  });
  // Saturation readout
  const sat = document.querySelector('input[name="saturation"]');
  sat.addEventListener("input", updateSaturationReadout);

  // Days-of-week shortcuts (All / Weekdays / Weekends / Clear).
  document.querySelectorAll("[data-dow-set]").forEach((b) => {
    b.addEventListener("click", () => applyDowShortcut(b.dataset.dowSet));
  });
}

function applyDowShortcut(set) {
  document.querySelectorAll(".dow-cb").forEach((cb) => {
    const idx = parseInt(cb.value, 10);
    if (set === "all") cb.checked = true;
    else if (set === "weekdays") cb.checked = idx <= 4;
    else if (set === "weekends") cb.checked = idx >= 5;
    else if (set === "none") cb.checked = false;
  });
}

function updateSaturationReadout() {
  const sat = document.querySelector('input[name="saturation"]');
  const out = document.querySelector('[data-readout="saturation"]');
  if (sat.value === "" || sat.value === null) {
    out.textContent = "use default (0.50)";
  } else {
    out.textContent = parseFloat(sat.value).toFixed(2);
  }
}

function collectForm() {
  const name = document.getElementById("schedule-name").value.trim();
  const targetPage = document.getElementById("target-page").value;
  const color = document.getElementById("schedule-color").value;
  const enabled = document.getElementById("schedule-enabled").checked;

  const body = {
    name,
    kind: state.kind,
    target: { type: "page", page_id: targetPage },
    color,
    enabled,
  };

  if (state.kind === "one_shot") {
    const at = document.getElementById("one-shot-at").value;
    if (at) body.at = at;
  } else {
    body.every_minutes = parseInt(document.getElementById("every-minutes").value, 10) || 15;
    body.start_time = document.getElementById("start-time").value;
    body.end_time = document.getElementById("end-time").value;
  }

  // Days of week — applies to both kinds now.
  const dow = [...document.querySelectorAll(".dow-cb:checked")].map((cb) => parseInt(cb.value, 10));
  if (dow.length) body.days_of_week = dow;

  // Advanced options
  const opts = {};
  for (const k of ["rotate", "scale", "bg"]) {
    const el = document.querySelector(`select[name="${k}"]`);
    if (el && el.value !== "") {
      opts[k] = (k === "rotate") ? parseInt(el.value, 10) : el.value;
    }
  }
  const sat = document.querySelector('input[name="saturation"]');
  if (sat.value !== "" && sat.value !== null) opts.saturation = parseFloat(sat.value);
  if (Object.keys(opts).length) body.options = opts;

  if (state.id) body.id = state.id;
  return body;
}

async function save() {
  const body = collectForm();

  // Quick client-side validation
  if (!body.name) { setStatus("error", "Name is required"); return; }
  if (!body.target.page_id) { setStatus("error", "Target dashboard is required"); return; }
  if (state.kind === "one_shot" && !body.at) {
    setStatus("error", "Pick a time of day"); return;
  }
  if (state.kind === "interval") {
    if (!body.start_time || !body.end_time) {
      setStatus("error", "Start and end times are required"); return;
    }
    if (body.start_time >= body.end_time) {
      setStatus("error", "End time must be after start time"); return;
    }
  }

  setStatus("saving", "Saving…");
  try {
    const url = state.id ? `/api/schedules/${encodeURIComponent(state.id)}` : "/api/schedules";
    const method = state.id ? "PUT" : "POST";
    const r = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const respBody = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(respBody.error || `HTTP ${r.status}`);
    state.id = respBody.id;
    if (location.pathname.endsWith("/new")) {
      history.replaceState(null, "", `/schedules/${encodeURIComponent(respBody.id)}/edit`);
    }
    setStatus("saved", `Saved · id=${respBody.id}`);
  } catch (err) {
    setStatus("error", `Save failed: ${err.message}`);
  }
}

async function del() {
  if (!state.id) return;
  if (!confirm("Delete this schedule?")) return;
  const r = await fetch(`/api/schedules/${encodeURIComponent(state.id)}`, { method: "DELETE" });
  if (r.ok) location.href = "/schedules";
  else alert(`Delete failed: HTTP ${r.status}`);
}

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}
