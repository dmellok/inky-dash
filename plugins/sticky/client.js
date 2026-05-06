// Sticky note widget — punchy display-weight text in any cell.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  const showHeader = opts.show_header === true && !ctx.has_page_header;
  const align = (d.align || "center").trim();
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  // Auto-shrink for very long notes — the JS picks a tighter type tier
  // based on character count so paragraph-length notes still fit. Tiers
  // are advisory; CSS does the actual sizing.
  const len = (d.text || "").length;
  const lenClass = len < 30 ? "len-short" : len < 90 ? "len-mid" : "len-long";

  host.innerHTML = `
    <article class="st ${sizeClass} ${lenClass} align-${align}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ${escapeHtml(d.icon || "ph-note")}"></i>
        <span class="label">NOTE</span>
      </header>` : ""}
      <div class="body">
        ${d.icon ? `<i class="ph ${escapeHtml(d.icon)} accent" aria-hidden="true"></i>` : ""}
        <div class="text">${escapeHtml(d.text || "")}</div>
        ${d.subtitle ? `<div class="sub">${escapeHtml(d.subtitle)}</div>` : ""}
      </div>
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
