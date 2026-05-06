(function () {
  document.querySelectorAll(".page-list").forEach((list) => {
    list.addEventListener("click", async (ev) => {
      const btn = ev.target.closest("[data-action]");
      if (!btn) return;
      const li = btn.closest("[data-page-id]");
      if (!li) return;
      const id = li.dataset.pageId;
      const action = btn.dataset.action;

      if (action === "delete") {
        if (!confirm(`Delete "${li.querySelector(".page-name").textContent}"?`)) return;
        const r = await fetch(`/api/pages/${encodeURIComponent(id)}`, { method: "DELETE" });
        if (r.ok) li.remove();
        else alert(`Delete failed: HTTP ${r.status}`);
      } else if (action === "duplicate") {
        const r = await fetch(`/api/pages/${encodeURIComponent(id)}/duplicate`, { method: "POST" });
        if (r.ok) location.reload();
        else alert(`Duplicate failed: HTTP ${r.status}`);
      } else if (action === "push") {
        btn.disabled = true;
        try {
          const r = await fetch(`/api/push/${encodeURIComponent(id)}`, { method: "POST" });
          const body = await r.json().catch(() => ({}));
          if (r.status === 409) alert(body.error || "A push is already in progress");
          else if (!r.ok) alert(`Push failed: ${body.error || `HTTP ${r.status}`}`);
        } finally {
          btn.disabled = false;
        }
      }
    });
  });
})();
