// FX rates widget — base + watchlist with up/down 24h delta arrows.
// Optional 30-day sparkline rendered via the shared Chart.js loader.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
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
  const wantSpark = !!d.sparkline && W >= 320;

  host.innerHTML = `
    <article class="fx ${sizeClass} ${wantSpark ? "with-spark" : ""}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-currency-circle-dollar"></i>
        <span class="label">FX RATES</span>
        <span class="meta">1 ${escapeHtml(d.base || "USD")} =</span>
      </header>` : ""}
      ${rows.length === 0
        ? `<div class="empty">No rates returned</div>`
        : `<ul class="rate-list">
            ${rows.map((r, i) => rowHtml(r, i, wantSpark)).join("")}
          </ul>`}
      <div class="footer">As of ${escapeHtml(d.as_of || "")}</div>
    </article>
  `;

  if (!wantSpark) return;
  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const ok     = styles.getPropertyValue("--theme-ok").trim() || "#2f855a";
    const danger = styles.getPropertyValue("--theme-danger").trim() || "#c00";
    rows.forEach((r, i) => {
      if (!Array.isArray(r.spark) || r.spark.length < 2) return;
      const canvas = host.querySelector(`canvas[data-spark="${i}"]`);
      if (!canvas) return;
      const stroke = r.direction === "down" ? danger : (r.direction === "up" ? ok : accent);
      new Chart(canvas, {
        type: "line",
        data: {
          labels: r.spark.map((_, j) => j),
          datasets: [{
            data: r.spark,
            borderColor: stroke,
            borderWidth: 2,
            pointRadius: 0,
            tension: 0.35,
            fill: false,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { enabled: false } },
          scales: { x: { display: false }, y: { display: false, beginAtZero: false } },
          animation: false,
          elements: { line: { borderJoinStyle: "round" } },
        },
      });
    });
  } catch (err) {
    console.warn("[fx] sparkline failed:", err);
  }
}

function rowHtml(r, index, wantSpark) {
  const arrow =
    r.direction === "up"   ? `<i class="ph ph-arrow-up" aria-hidden="true"></i>` :
    r.direction === "down" ? `<i class="ph ph-arrow-down" aria-hidden="true"></i>` :
                             `<i class="ph ph-minus" aria-hidden="true"></i>`;
  const deltaText = r.delta_pct == null
    ? "—"
    : (r.delta_pct >= 0 ? "+" : "") + r.delta_pct.toFixed(2) + "%";
  const spark = wantSpark && Array.isArray(r.spark) && r.spark.length >= 2
    ? `<span class="spark"><canvas data-spark="${index}"></canvas></span>`
    : "";
  return `
    <li class="rate dir-${r.direction}">
      <span class="code">${escapeHtml(r.code)}</span>
      ${spark}
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
