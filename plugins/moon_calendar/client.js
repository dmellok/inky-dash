// Moon calendar widget — month grid with a small SVG moon per day.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const cells = Array.isArray(d.cells) ? d.cells : [];
  const labels = Array.isArray(d.weekday_labels) ? d.weekday_labels : [];
  const todayPhase = d.today_phase || {};

  host.innerHTML = `
    <article class="mc ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-moon"></i>
        <span class="label">${escapeHtml((d.month_name || "MOON").toUpperCase())} ${escapeHtml(String(d.year || ""))}</span>
        <span class="meta">${escapeHtml(todayPhase.name || "")} · ${todayPhase.illumination ?? 0}%</span>
      </header>` : ""}

      <div class="dow-row">
        ${labels.map((l, i) => `<span class="dow ${i >= 5 ? 'we' : ''}">${escapeHtml(l)}</span>`).join("")}
      </div>

      <div class="grid">
        ${cells.map((c) => c ? cellHtml(c) : `<span class="cell empty"></span>`).join("")}
      </div>
    </article>
  `;
}

function cellHtml(c) {
  return `
    <span class="cell ${c.is_today ? 'today' : ''} ${c.is_weekend ? 'we' : ''}">
      <span class="moon-vis">${moonSVG(c)}</span>
      <span class="day">${c.day}</span>
    </span>
  `;
}

// Same SVG technique as the sun_moon widget — a half-disc + an
// elliptical mask carves the terminator. Lit hemisphere is on the
// right for waxing, on the left for waning. Terminator ellipse
// rx = |1-2f|·R; sign flips for waxing vs waning by switching which
// path renders on top.
function moonSVG(c) {
  const fraction = (c.illumination || 0) / 100;
  const waxing = !!c.waxing;
  const R = 50;
  const half = waxing
    ? `<path d="M50 0 A50 50 0 0 1 50 100 Z" fill="var(--theme-accent, currentColor)"/>`
    : `<path d="M50 0 A50 50 0 0 0 50 100 Z" fill="var(--theme-accent, currentColor)"/>`;
  const rx = Math.abs(1 - 2 * fraction) * R;
  const termFill = fraction < 0.5
    ? "var(--theme-surface-2, var(--theme-surface, #222))"
    : "var(--theme-accent, currentColor)";
  return `
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <circle cx="50" cy="50" r="50" fill="var(--theme-surface-2, var(--theme-surface, #222))" />
      ${half}
      <ellipse cx="50" cy="50" rx="${rx}" ry="50" fill="${termFill}" />
    </svg>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
