// Year progress widget — hero count, progress bar, supporting stats.

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

  // 52 micro-bars: one per ISO week, lit through the current week.
  const weekOfYear = Math.max(1, Math.min(52, Number(d.week_of_year || 1)));
  const weekBars = Array.from({ length: 52 }, (_, i) =>
    `<span class="wk ${i < weekOfYear ? "lit" : ""}"></span>`
  ).join("");

  host.innerHTML = `
    <article class="yp ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-chart-line-up"></i>
        <span class="label">YEAR PROGRESS</span>
        <span class="meta">${escapeHtml(String(d.year ?? ""))}</span>
      </header>` : ""}

      <div class="hero">
        <div class="num-wrap">
          <span class="num">${d.day_of_year ?? 0}</span>
          <span class="of">/ ${d.days_in_year ?? 365}</span>
        </div>
        <div class="lbl">days into ${escapeHtml(String(d.year ?? ""))}</div>
      </div>

      <div class="bar">
        <div class="bar-fill" style="width: ${d.pct ?? 0}%"></div>
        <span class="pct">${d.pct ?? 0}%</span>
      </div>

      <div class="weeks" aria-hidden="true">${weekBars}</div>

      <div class="stats">
        <div class="stat">
          <span class="k">REMAINING</span>
          <span class="v">${d.days_remaining ?? 0}<span class="u">days</span></span>
        </div>
        <div class="stat">
          <span class="k">WEEK</span>
          <span class="v">${d.week_of_year ?? 0}<span class="u">/52</span></span>
        </div>
        <div class="stat">
          <span class="k">QUARTER</span>
          <span class="v">Q${d.quarter ?? 0}</span>
        </div>
      </div>

      <div class="footer">${escapeHtml(d.today_label || "")}</div>
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
