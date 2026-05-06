export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="wp-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  if (d.mode === "image") {
    // Push render — display the server-side screenshot.
    host.innerHTML = `<img class="wp-image" alt="${escapeHtml(d.url || "")}" src="${d.img}">`;
    return;
  }
  // Preview mode — try an iframe, fall back to a placeholder card if the load
  // event never fires (common on sites with `X-Frame-Options: DENY`).
  const safeUrl = String(d.url || "");
  host.innerHTML = `
    <div class="wp">
      <div class="wp-loading">Loading…</div>
      <iframe class="wp-iframe" src="${escapeAttr(safeUrl)}" hidden
              sandbox="allow-same-origin allow-scripts allow-popups allow-forms"></iframe>
    </div>`;

  const wrap = host.querySelector(".wp");
  const iframe = host.querySelector("iframe");
  const loader = host.querySelector(".wp-loading");

  let settled = false;
  const showFallback = () => {
    if (settled) return;
    settled = true;
    wrap.innerHTML = `
      <div class="wp-fallback">
        <strong>${escapeHtml(safeUrl)}</strong>
        <span>Live preview unavailable — push will use a server-side screenshot.</span>
      </div>`;
  };
  const showFrame = () => {
    if (settled) return;
    settled = true;
    iframe.hidden = false;
    if (loader) loader.remove();
  };

  iframe.addEventListener("load", () => {
    setTimeout(showFrame, Math.max(50, Number(d.extra_wait_ms) || 0));
  });
  // 6-second budget for the iframe to fire `load`. Past that, assume blocked.
  setTimeout(showFallback, 6000);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
function escapeAttr(s) {
  // Prevent breaking out of the src attribute. URLs with quotes are unusual
  // but better safe.
  return String(s).replace(/"/g, "%22");
}
