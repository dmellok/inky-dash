// Crypto prices widget — same row layout as FX rates: ticker / price /
// 24h delta chip with up/down/flat arrow.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="crypto error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
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
    <article class="crypto ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-currency-btc"></i>
        <span class="label">CRYPTO</span>
        <span class="meta">vs ${escapeHtml(d.vs || "USD")}</span>
      </header>` : ""}
      ${rows.length === 0
        ? `<div class="empty">No prices returned</div>`
        : `<ul class="rate-list">${rows.map((r) => rowHtml(r, d.vs)).join("")}</ul>`}
    </article>
  `;
}

function rowHtml(r, vs) {
  const arrow =
    r.direction === "up"   ? `<i class="ph ph-arrow-up" aria-hidden="true"></i>` :
    r.direction === "down" ? `<i class="ph ph-arrow-down" aria-hidden="true"></i>` :
                             `<i class="ph ph-minus" aria-hidden="true"></i>`;
  const deltaText = r.delta_pct == null
    ? "—"
    : (r.delta_pct >= 0 ? "+" : "") + r.delta_pct.toFixed(2) + "%";
  return `
    <li class="rate dir-${r.direction}">
      <span class="ticker">${escapeHtml(r.label)}</span>
      <span class="value"><span class="ccy">${escapeHtml(currencySymbol(vs))}</span>${escapeHtml(r.value)}</span>
      <span class="delta">${arrow}<span>${escapeHtml(deltaText)}</span></span>
    </li>
  `;
}

function currencySymbol(code) {
  const c = (code || "USD").toUpperCase();
  return ({ USD: "$", EUR: "€", GBP: "£", AUD: "A$", JPY: "¥", CAD: "C$", CHF: "₣", NZD: "NZ$" }[c]) || "";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
