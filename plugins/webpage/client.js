// Webpage widget — render an iframe filling the cell. Playwright sees
// the iframe and screenshots whatever the embedded page paints.

export default function render(host, ctx) {
  const data = ctx.data || {};
  const url = data.url;
  const error = data.error;
  const opts = (ctx.cell && ctx.cell.options) || {};
  const zoom = Math.max(10, Math.min(400, Number(opts.zoom) || 100)) / 100;
  const scrollX = Math.max(0, Number(opts.scroll_x) || 0);
  const scrollY = Math.max(0, Number(opts.scroll_y) || 0);

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/webpage/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="page error">
        <i class="ph ph-globe"></i>
        <div class="message">${escapeHtml(error || "No URL set.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const safeUrl = url.replace(/"/g, "&quot;");
  // The iframe is sized at the inverse of the zoom factor so when scaled
  // up by `transform: scale(zoom)`, the visible area still equals the
  // cell. scroll_x/y allow framing a specific portion of long pages.
  const inverseScale = 1 / zoom;
  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/webpage/client.css">
    <div class="page">
      <iframe
        src="${safeUrl}"
        title="Embedded webpage"
        loading="eager"
        sandbox="allow-scripts allow-same-origin allow-popups-to-escape-sandbox"
        referrerpolicy="no-referrer"
        style="
          width: ${(100 * inverseScale).toFixed(2)}%;
          height: ${(100 * inverseScale).toFixed(2)}%;
          transform: scale(${zoom}) translate(${-scrollX}px, ${-scrollY}px);
          transform-origin: 0 0;
        "
      ></iframe>
    </div>
  `;

  // Mark as rendered when the iframe finishes loading (or errors). Cap at
  // 8s so a hung embed doesn't block the screenshot indefinitely.
  const iframe = host.querySelector("iframe");
  let settled = false;
  const done = () => {
    if (settled) return;
    settled = true;
    host.host.dataset.rendered = "true";
  };
  iframe.addEventListener("load", () => setTimeout(done, 600), { once: true });
  setTimeout(done, 8000);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
