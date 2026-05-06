// Year progress widget — hero count, progress bar / radial ring, stats.
// "linear" = horizontal accent bar with mix-blend pct label (default).
// "radial" = Chart.js doughnut + day-of-year centred inside the ring.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;
  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const style = (opts.style || "linear").trim();

  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  // Radial only makes sense on h-md and up; below that the ring would
  // crush against the stats so we fall back to the linear bar.
  const useRadial = style === "radial" && H >= 360;

  // 52 micro-bars: one per ISO week, lit through the current week.
  const weekOfYear = Math.max(1, Math.min(52, Number(d.week_of_year || 1)));
  const weekBars = Array.from({ length: 52 }, (_, i) =>
    `<span class="wk ${i < weekOfYear ? "lit" : ""}"></span>`
  ).join("");

  host.innerHTML = `
    <article class="yp ${sizeClass} style-${useRadial ? "radial" : "linear"}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-chart-line-up"></i>
        <span class="label">YEAR PROGRESS</span>
        <span class="meta">${escapeHtml(String(d.year ?? ""))}</span>
      </header>` : ""}

      ${useRadial ? `
      <div class="ring-wrap">
        <canvas class="ring"></canvas>
        <div class="ring-center">
          <span class="num">${d.day_of_year ?? 0}</span>
          <span class="lbl">/ ${d.days_in_year ?? 365}</span>
          <span class="sub">${d.pct ?? 0}%</span>
        </div>
      </div>` : `
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

      <div class="weeks" aria-hidden="true">${weekBars}</div>`}

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

  if (!useRadial) return;
  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const surface2 = styles.getPropertyValue("--theme-surface-2").trim() || "#eee";
    const canvas = host.querySelector("canvas.ring");
    if (!canvas) return;
    const pct = Math.max(0, Math.min(100, Number(d.pct || 0)));
    new Chart(canvas, {
      type: "doughnut",
      data: {
        datasets: [{
          data: [pct, 100 - pct],
          backgroundColor: [accent, surface2],
          borderWidth: 0,
          // Round the leading edge of the lit arc — Chart.js v4 doesn't
          // actually round, but a small spacing keeps the join soft.
          spacing: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "78%",
        rotation: -90,
        circumference: 360,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: false,
      },
    });
  } catch (err) {
    console.warn("[year_progress] ring failed:", err);
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
