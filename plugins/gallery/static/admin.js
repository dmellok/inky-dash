// Galleries admin: name + folder + mode CRUD.

const listEl = document.getElementById("gallery-list");
const form = document.getElementById("add-form");

form.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const fd = new FormData(form);
  const body = Object.fromEntries(fd.entries());
  setStatus("saving", "Creating…");
  const r = await fetch("/plugins/gallery/api/galleries", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const resp = await r.json().catch(() => ({}));
  if (!r.ok) { setStatus("error", resp.error || `HTTP ${r.status}`); return; }
  setStatus("saved", `Created '${resp.name || body.name}'`);
  form.reset();
  await load();
});

async function load() {
  const r = await fetch("/plugins/gallery/api/galleries");
  if (!r.ok) {
    listEl.innerHTML = `<li class="muted small">HTTP ${r.status}</li>`;
    return;
  }
  const { galleries } = await r.json();
  render(galleries);
}

function render(galleries) {
  listEl.innerHTML = "";
  if (!galleries.length) {
    listEl.innerHTML = `<li class="muted small">No galleries yet — create one above.</li>`;
    return;
  }
  for (const g of galleries) {
    const li = document.createElement("li");
    li.className = "gallery-row" + (g.valid ? "" : " invalid");
    // Mode is set per-cell in the dashboard editor — galleries themselves
    // are just a name + folder + the (advancing) cursor used by any cell
    // that picks them in sequential mode.
    li.innerHTML = `
      <div class="meta">
        <div class="top">
          <strong>${escapeHtml(g.name)}</strong>
          ${g.valid ? "" : `<span class="kind-tag invalid">folder missing</span>`}
        </div>
        <div class="folder">${escapeHtml(g.folder)}</div>
        <div class="stats">
          ${g.image_count} image${g.image_count === 1 ? "" : "s"}
          · cursor <input type="number" class="cursor-edit" data-id="${g.id}" value="${g.cursor}" min="0">
        </div>
      </div>
      <span class="actions">
        <button type="button" class="btn ghost danger" data-action="delete" title="Delete"><i class="ph ph-trash"></i></button>
      </span>
    `;
    li.querySelector('[data-action="delete"]').addEventListener("click", () => del(g));
    const cursor = li.querySelector(".cursor-edit");
    if (cursor) cursor.addEventListener("change", () => updateCursor(g.id, parseInt(cursor.value, 10) || 0));
    listEl.appendChild(li);
  }
}

async function del(g) {
  if (!confirm(`Delete gallery "${g.name}"?`)) return;
  const r = await fetch(`/plugins/gallery/api/galleries/${encodeURIComponent(g.id)}`, { method: "DELETE" });
  if (r.ok) load();
  else setStatus("error", `HTTP ${r.status}`);
}

async function updateCursor(gid, cursor) {
  const r = await fetch(`/plugins/gallery/api/galleries/${encodeURIComponent(gid)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cursor }),
  });
  if (r.ok) setStatus("saved", `Cursor updated`);
  else setStatus("error", `HTTP ${r.status}`);
}

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}

load();
