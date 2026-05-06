// Habits admin: name + icon + colour CRUD, plus check-today toggle.

const listEl = document.getElementById("habit-list");
const form = document.getElementById("add-form");

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  setStatus("saving", "Creating…");
  const r = await fetch("/plugins/habits/api/habits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const resp = await r.json().catch(() => ({}));
  if (!r.ok) { setStatus("error", resp.error || `HTTP ${r.status}`); return; }
  setStatus("saved", `Created '${resp.name || body.name}'`);
  form.reset();
  form.elements.icon.value = "ph-check-square";
  await load();
});

async function load() {
  const r = await fetch("/plugins/habits/api/habits");
  if (!r.ok) {
    listEl.innerHTML = `<li class="muted small">HTTP ${r.status}</li>`;
    return;
  }
  const { habits } = await r.json();
  render(habits);
}

function render(habits) {
  listEl.innerHTML = "";
  if (!habits.length) {
    listEl.innerHTML = `<li class="muted small">No habits yet — create one above.</li>`;
    return;
  }
  for (const h of habits) {
    const li = document.createElement("li");
    li.className = `habit-row color-${h.color}`;
    li.innerHTML = `
      <i class="ph ${escapeHtml(h.icon)} habit-icon" aria-hidden="true"></i>
      <div class="meta">
        <strong>${escapeHtml(h.name)}</strong>
        <div class="sub">streak ${h.streak} · ${h.total} total</div>
      </div>
      <span class="actions">
        <button type="button" class="btn ${h.today_done ? 'primary' : 'outline-accent'}" data-action="toggle">
          <i class="ph ${h.today_done ? 'ph-check-fat' : 'ph-circle'}"></i> ${h.today_done ? "Done today" : "Mark today"}
        </button>
        <button type="button" class="btn ghost danger" data-action="delete" title="Delete">
          <i class="ph ph-trash"></i>
        </button>
      </span>
    `;
    li.querySelector('[data-action="toggle"]').addEventListener("click", () => toggleToday(h));
    li.querySelector('[data-action="delete"]').addEventListener("click", () => del(h));
    listEl.appendChild(li);
  }
}

async function toggleToday(h) {
  const r = await fetch(`/plugins/habits/api/habits/${encodeURIComponent(h.id)}/toggle`, { method: "POST" });
  if (!r.ok) { setStatus("error", `HTTP ${r.status}`); return; }
  const body = await r.json();
  setStatus("saved", body.done ? "Checked in" : "Un-checked");
  await load();
}

async function del(h) {
  if (!confirm(`Delete habit "${h.name}"?`)) return;
  const r = await fetch(`/plugins/habits/api/habits/${encodeURIComponent(h.id)}`, { method: "DELETE" });
  if (r.ok) load();
  else setStatus("error", `HTTP ${r.status}`);
}

function setStatus(kind, msg) {
  if (window.inkyStatus) window.inkyStatus(kind, msg);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}

load();
