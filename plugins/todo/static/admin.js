// Todo admin: quick-entry + list with done/delete + prune.

const listEl = document.getElementById("item-list");
const addForm = document.getElementById("add-form");
const newInput = document.getElementById("new-item");
const pruneBtn = document.getElementById("prune-btn");

addForm.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const text = newInput.value.trim();
  if (!text) return;
  setStatus("saving", "Adding…");
  const r = await fetch("/plugins/todo/api/items", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    setStatus("error", body.error || `HTTP ${r.status}`);
    return;
  }
  newInput.value = "";
  setStatus("saved", "Added");
  await load();
});

pruneBtn.addEventListener("click", async () => {
  setStatus("saving", "Pruning…");
  const r = await fetch("/plugins/todo/api/prune", { method: "POST" });
  if (!r.ok) { setStatus("error", `HTTP ${r.status}`); return; }
  const body = await r.json();
  setStatus("saved", `Dropped ${body.pruned} item(s)`);
  await load();
});

async function load() {
  const r = await fetch("/plugins/todo/api/items");
  if (!r.ok) {
    listEl.innerHTML = `<li class="muted small">HTTP ${r.status}</li>`;
    return;
  }
  const { items } = await r.json();
  render(items);
}

function render(items) {
  listEl.innerHTML = "";
  if (!items.length) {
    listEl.innerHTML = `<li class="muted small">No items yet.</li>`;
    return;
  }
  // Active first, completed last; within each group, newest first.
  const sorted = [...items].sort((a, b) => {
    if (a.completed !== b.completed) return a.completed ? 1 : -1;
    return (b.created_at || "").localeCompare(a.created_at || "");
  });
  const now = new Date();
  for (const it of sorted) {
    const li = document.createElement("li");
    const fresh = isFresh(it, now);
    li.className = "item-row" + (it.completed ? " completed" : "") + (fresh ? " fresh" : "");
    li.innerHTML = `
      <button type="button" class="check" data-action="toggle" title="${it.completed ? "Reopen" : "Mark done"}">
        <i class="ph ph-check"></i>
      </button>
      <span class="text">${escapeHtml(it.text)}</span>
      <span class="actions">
        <button type="button" class="btn ghost danger" data-action="delete" title="Delete">
          <i class="ph ph-trash"></i>
        </button>
      </span>
    `;
    li.querySelector('[data-action="toggle"]').addEventListener("click", () => toggle(it));
    li.querySelector('[data-action="delete"]').addEventListener("click", () => del(it));
    listEl.appendChild(li);
  }
}

function isFresh(item, now) {
  if (!item.completed || !item.completed_at) return false;
  try {
    const t = new Date(item.completed_at.replace(/Z$/, "+00:00"));
    return (now - t) < 60 * 60 * 1000;
  } catch (_) {
    return false;
  }
}

async function toggle(item) {
  const r = await fetch(`/plugins/todo/api/items/${encodeURIComponent(item.id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ completed: !item.completed }),
  });
  if (r.ok) load();
  else setStatus("error", `HTTP ${r.status}`);
}

async function del(item) {
  if (!confirm(`Delete "${item.text}"?`)) return;
  const r = await fetch(`/plugins/todo/api/items/${encodeURIComponent(item.id)}`, { method: "DELETE" });
  if (r.ok) load();
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
