// Air quality widget — AQI hero + category, scale bar, pollutant tiles,
// optional 24-hour AQI line chart.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="aq error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const aqi = d.aqi;
  const max = d.scale_max || 500;
  const pct = aqi != null ? Math.max(2, Math.min(100, Math.round((aqi / max) * 100))) : 0;
  const severity = d.severity || "unknown";

  const pollutants = (d.pollutants || []).filter((p) => p.v != null);
  const chart = Array.isArray(d.chart) && d.chart.length >= 2 ? d.chart : null;
  // Chart only has room on h-md and up; on smaller cells we hide it.
  const showChart = !!chart && H >= 360 && W >= 320;

  host.innerHTML = `
    <article class="aq ${sizeClass} sev-${severity} ${showChart ? "with-chart" : ""}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-wind"></i>
        <span class="label">AIR QUALITY</span>
        <span class="meta">${escapeHtml(d.place || "")}</span>
      </header>` : ""}

      <div class="hero">
        <div class="num-wrap">
          <span class="num">${aqi == null ? "—" : aqi}</span>
          <span class="of">/ ${max}</span>
        </div>
        <div class="cat">${escapeHtml(d.category || "—")}</div>
      </div>

      <div class="scale-bar" aria-hidden="true">
        <div class="scale-fill" style="width: ${pct}%"></div>
        <span class="scale-cursor" style="left: ${pct}%"></span>
      </div>

      ${showChart ? `
      <div class="chart-wrap">
        <span class="chart-label">Last 24 hours</span>
        <canvas></canvas>
      </div>` : ""}

      <div class="pollutants">
        ${pollutants.map((p) => `
          <div class="poll">
            <span class="k">${escapeHtml(p.k)}</span>
            <span class="v">${p.v}<span class="u">${escapeHtml(p.u)}</span></span>
          </div>
        `).join("")}
      </div>
    </article>
  `;

  if (!showChart) return;
  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const muted  = styles.getPropertyValue("--theme-muted").trim() || "#888";
    const fill   = `rgba(${hexToRgb(accent) || "120,120,120"}, 0.18)`;
    const canvas = host.querySelector(".chart-wrap canvas");
    if (!canvas) return;
    new Chart(canvas, {
      type: "line",
      data: {
        labels: chart.map((p) => fmtHour(p.t)),
        datasets: [{
          data: chart.map((p) => p.v),
          borderColor: accent,
          backgroundColor: fill,
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: {
            display: true,
            ticks: {
              maxTicksLimit: 6,
              color: muted,
              font: { size: 10, weight: 600 },
              autoSkip: true,
            },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            display: false,
            beginAtZero: true,
          },
        },
        animation: false,
      },
    });
  } catch (err) {
    console.warn("[aq] chart failed:", err);
  }
}

function fmtHour(iso) {
  // iso like "2026-05-07T05:00" → "05"
  if (typeof iso !== "string" || iso.length < 13) return "";
  return iso.slice(11, 13);
}
function hexToRgb(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return null;
  const n = parseInt(m[1], 16);
  return `${(n >> 16) & 0xff},${(n >> 8) & 0xff},${n & 0xff}`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
