// FX rates widget — base + watchlist with up/down 24h delta arrows.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="fx error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const rows = Array.isArray(d.rows) ? d.rows : [];

  host.innerHTML = `
    <article class="fx ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-currency-circle-dollar"></i>
        <span class="label">FX RATES</span>
        <span class="meta">1 ${escapeHtml(d.base || "USD")} =</span>
      </header>` : ""}
      ${rows.length === 0
        ? `<div class="empty">No rates returned</div>`
        : `<ul class="rate-list">
            ${rows.map((r) => rowHtml(r)).join("")}
          </ul>`}
      <div class="footer">As of ${escapeHtml(d.as_of || "")}</div>
    </article>
  `;
}

function rowHtml(r) {
  const arrow =
    r.direction === "up"   ? `<i class="ph ph-arrow-up" aria-hidden="true"></i>` :
    r.direction === "down" ? `<i class="ph ph-arrow-down" aria-hidden="true"></i>` :
                             `<i class="ph ph-minus" aria-hidden="true"></i>`;
  const deltaText = r.delta_pct == null
    ? "—"
    : (r.delta_pct >= 0 ? "+" : "") + r.delta_pct.toFixed(2) + "%";
  return `
    <li class="rate dir-${r.direction}">
      <span class="code">${escapeHtml(r.code)}</span>
      <span class="value">${escapeHtml(r.value)}</span>
      <span class="delta">${arrow}<span>${escapeHtml(deltaText)}</span></span>
    </li>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
