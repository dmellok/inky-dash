// Schedules list page.
//
// Renders:
//   - Daily timeline: a 24-hour bar with per-schedule rows. Interval schedules
//     show a windowed band with tick marks at every fire slot; one-shots show
//     a single dot (only if scheduled for today).
//   - Schedules table with row colour stripe, kind badge, next-fire summary,
//     enable/disable toggle, edit/delete actions.

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

initAxis();
load();
setInterval(updateNowLine, 30 * 1000);

async function load() {
  try {
    const r = await fetch("/api/schedules");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { schedules } = await r.json();
    renderTimeline(schedules);
    renderList(schedules);
  } catch (err) {
    document.getElementById("schedule-list").innerHTML =
      `<li class="muted small">Failed to load: ${escapeHtml(err.message)}</li>`;
  }
}

// ---------- Daily timeline ---------------------------------------------

function initAxis() {
  const axis = document.getElementById("timeline-axis");
  axis.innerHTML = "";
  for (let h = 0; h <= 24; h += 3) {
    const tick = document.createElement("div");
    tick.className = "tick";
    tick.style.left = `${(h / 24) * 100}%`;
    axis.appendChild(tick);
    if (h === 24) continue;
    const lbl = document.createElement("span");
    lbl.className = "hour";
    lbl.textContent = String(h).padStart(2, "0");
    lbl.style.left = `${(h / 24) * 100}%`;
    axis.appendChild(lbl);
  }
  updateNowLine();
}

function updateNowLine() {
  const axis = document.getElementById("timeline-axis");
  let line = axis.querySelector(".now-line");
  if (!line) {
    line = document.createElement("div");
    line.className = "now-line";
    axis.appendChild(line);
  }
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  line.style.left = `${(minutes / (24 * 60)) * 100}%`;
  document.getElementById("timeline-now").textContent =
    `${pad(now.getHours())}:${pad(now.getMinutes())} · ${DAY_NAMES[(now.getDay() + 6) % 7]}`;
}

function renderTimeline(schedules) {
  const rows = document.getElementById("timeline-rows");
  const empty = document.getElementById("timeline-empty");
  rows.innerHTML = "";
  const today = new Date();
  const todayDow = (today.getDay() + 6) % 7; // ISO Mon=0
  const ymd = today.toISOString().slice(0, 10);

  // `enabled` is omitted from JSON when it's the default (true) per rule 7,
  // so check explicitly against false rather than truthy.
  const visible = schedules.filter((s) => s.enabled !== false);
  if (!visible.length) { empty.hidden = false; return; }
  empty.hidden = true;

  for (const s of visible) {
    const row = document.createElement("div");
    row.className = "timeline-row";
    row.style.setProperty("--row-color", s.color);

    const label = document.createElement("span");
    label.className = "label";
    label.textContent = s.name;
    row.appendChild(label);

    if (s.kind === "interval") {
      const dow = s.days_of_week || [];
      if (dow.length && !dow.includes(todayDow)) {
        // Off today: render an empty row to show it exists.
      } else {
        const startMin = parseHmMinutes(s.start_time);
        const endMin = parseHmMinutes(s.end_time);
        if (Number.isFinite(startMin) && Number.isFinite(endMin) && endMin > startMin) {
          const win = document.createElement("div");
          win.className = "window";
          win.style.left = `${(startMin / (24 * 60)) * 100}%`;
          win.style.width = `${((endMin - startMin) / (24 * 60)) * 100}%`;
          row.appendChild(win);
        }
      }
    } else if (s.kind === "one_shot" && s.at) {
      // One-shot fires once per day at HH:MM (with optional day-of-week mask).
      // Tolerate the legacy ISO datetime form by extracting the time portion.
      const dow = s.days_of_week || [];
      if (dow.length && !dow.includes(todayDow)) {
        // Off today
      } else {
        const at = s.at.includes("T") ? s.at.slice(11, 16) : s.at.slice(0, 5);
        const min = parseHmMinutes(at);
        if (Number.isFinite(min)) {
          const dot = document.createElement("div");
          dot.className = "one-shot";
          dot.style.left = `${(min / (24 * 60)) * 100}%`;
          row.appendChild(dot);
        }
      }
    }
    rows.appendChild(row);
  }
}

// ---------- Schedule table ---------------------------------------------

function renderList(schedules) {
  const list = document.getElementById("schedule-list");
  list.innerHTML = "";
  if (!schedules.length) {
    list.innerHTML = `<li class="muted small">No schedules yet — <a href="/schedules/new">create one</a>.</li>`;
    return;
  }
  for (const s of schedules) {
    const li = document.createElement("li");
    const enabled = s.enabled !== false;
    li.className = "schedule-row" + (enabled ? "" : " disabled");
    li.style.setProperty("--row-color", s.color);
    li.dataset.id = s.id;

    const dow = (s.days_of_week || []).map((d) => DAY_NAMES[d]).join(",");
    const kindBadge = s.kind === "one_shot"
      ? `<span class="badge-pill kind-one_shot">one-shot</span>`
      : `<span class="badge-pill kind-interval">interval</span>`;
    const at = s.at ? (s.at.includes("T") ? s.at.slice(11, 16) : s.at.slice(0, 5)) : null;
    const summary = s.kind === "one_shot"
      ? (at ? `daily at ${at}${dow ? ` · ${dow}` : ""}` : "(no time set)")
      : `every ${s.every_minutes}min · ${s.start_time}–${s.end_time}${dow ? ` · ${dow}` : ""}`;
    const errorBadge = s.last_result === "error"
      ? `<span class="badge-pill error" title="${escapeHtml(s.last_error || '')}">error</span>`
      : "";

    // The drag handle is the only element marked `draggable` so clicks on
    // the action buttons don't accidentally start a drag.
    li.innerHTML = `
      <span class="drag-handle" draggable="true" title="Drag to reorder priority" aria-label="Reorder">
        <i class="ph ph-dots-six-vertical"></i>
      </span>
      <span class="indicator"></span>
      <div class="meta">
        <div class="row-1">
          <strong>${escapeHtml(s.name)}</strong>
          ${kindBadge}
          ${errorBadge}
        </div>
        <div class="row-2">${escapeHtml(summary)} · target: ${escapeHtml(s.target?.page_id || '?')}${s.last_fired_at ? ` · last fired ${formatLocalIso(s.last_fired_at)}` : ''}</div>
      </div>
      <div class="actions">
        <button type="button" class="btn ghost" data-action="toggle" title="${enabled ? "Disable" : "Enable"}">
          <i class="ph ${enabled ? 'ph-pause' : 'ph-play'}"></i>
        </button>
        <a class="btn ghost" href="/schedules/${encodeURIComponent(s.id)}/edit" title="Edit">
          <i class="ph ph-pencil-simple"></i>
        </a>
        <button type="button" class="btn ghost danger" data-action="delete" title="Delete">
          <i class="ph ph-trash"></i>
        </button>
      </div>
    `;
    li.querySelector('[data-action="toggle"]').addEventListener("click", () => toggleEnabled(s));
    li.querySelector('[data-action="delete"]').addEventListener("click", () => del(s));
    list.appendChild(li);
  }
  attachDragReorder();
}

// ---------- Drag-to-reorder --------------------------------------------

function attachDragReorder() {
  const list = document.getElementById("schedule-list");
  let dragRow = null;
  list.querySelectorAll(".schedule-row").forEach((row) => {
    const handle = row.querySelector(".drag-handle");
    if (!handle) return;

    handle.addEventListener("dragstart", (e) => {
      dragRow = row;
      row.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
      // Firefox requires data to be set, otherwise the drag never starts.
      e.dataTransfer.setData("text/plain", row.dataset.id || "");
    });
    handle.addEventListener("dragend", async () => {
      if (!dragRow) return;
      dragRow.classList.remove("dragging");
      dragRow = null;
      await persistOrder();
    });
  });

  // Drop targeting on the row itself: hovering over a row's top half drops
  // the dragged row above it; bottom half drops below. Updating DOM as the
  // user moves means the visible order is always the order we'll persist.
  list.addEventListener("dragover", (e) => {
    if (!dragRow) return;
    e.preventDefault();
    const target = e.target.closest(".schedule-row");
    if (!target || target === dragRow) return;
    const rect = target.getBoundingClientRect();
    const before = e.clientY < rect.top + rect.height / 2;
    list.insertBefore(dragRow, before ? target : target.nextSibling);
  });
}

async function persistOrder() {
  const ids = [...document.querySelectorAll("#schedule-list .schedule-row")]
    .map((r) => r.dataset.id)
    .filter(Boolean);
  try {
    const r = await fetch("/api/schedules/reorder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    if (window.inkyStatus) window.inkyStatus("saved", "Priority updated");
  } catch (err) {
    if (window.inkyStatus) window.inkyStatus("error", `Reorder failed: ${err.message}`);
  }
  // Refetch either way: on success to rerender the timeline in the new
  // priority order; on failure to drop the optimistic DOM change.
  load();
}

async function toggleEnabled(s) {
  const currentlyEnabled = s.enabled !== false;
  const updated = { ...s, enabled: !currentlyEnabled };
  // Strip state fields the server treats as managed.
  delete updated.last_fired_at; delete updated.last_result; delete updated.last_error;
  const r = await fetch(`/api/schedules/${encodeURIComponent(s.id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updated),
  });
  if (r.ok) load();
  else alert(`Toggle failed: HTTP ${r.status}`);
}

async function del(s) {
  if (!confirm(`Delete schedule "${s.name}"?`)) return;
  const r = await fetch(`/api/schedules/${encodeURIComponent(s.id)}`, { method: "DELETE" });
  if (r.ok) load();
  else alert(`Delete failed: HTTP ${r.status}`);
}

// ---------- helpers ----------------------------------------------------

function parseHmMinutes(hm) {
  if (!hm || typeof hm !== "string") return NaN;
  const [h, m] = hm.split(":").map((n) => parseInt(n, 10));
  if (!Number.isFinite(h) || !Number.isFinite(m)) return NaN;
  return h * 60 + m;
}

function formatLocalIso(iso) {
  // "2026-05-10T14:30:00" → "5/10 14:30"
  if (!iso) return "";
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
  if (!m) return iso;
  return `${parseInt(m[2], 10)}/${parseInt(m[3], 10)} ${m[4]}:${m[5]}`;
}

function pad(n) { return String(n).padStart(2, "0"); }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
