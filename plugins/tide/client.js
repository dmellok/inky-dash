// Tide chart widget — area-filled sea-level curve with high/low markers
// and a "now" cursor.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="td error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const series = Array.isArray(d.series) ? d.series : [];
  const extrema = Array.isArray(d.extrema) ? d.extrema : [];
  // Find the next high + next low after "now" — these are the headlines
  // the user actually cares about: "next low at 13:42 (-0.21m)".
  const nowMs = parseISO(d.now_iso);
  const future = extrema.filter((e) => parseISO(e.t) > nowMs);
  const nextHigh = future.find((e) => e.kind === "high");
  const nextLow  = future.find((e) => e.kind === "low");
  const currentHeight = currentValue(series, nowMs);

  host.innerHTML = `
    <article class="td ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-wave-triangle"></i>
        <span class="label">TIDE</span>
        <span class="meta">${escapeHtml(d.place || "")}</span>
      </header>` : ""}

      <div class="hero">
        <div class="now-block">
          <span class="num">${currentHeight == null ? "—" : currentHeight.toFixed(2)}</span>
          <span class="unit">m</span>
        </div>
        <div class="next-block">
          ${nextHigh ? extremaPill("high", nextHigh) : ""}
          ${nextLow  ? extremaPill("low",  nextLow)  : ""}
        </div>
      </div>

      <div class="chart-wrap">
        <canvas></canvas>
      </div>
    </article>
  `;

  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const fg     = styles.getPropertyValue("--theme-fg").trim() || "#111";
    const muted  = styles.getPropertyValue("--theme-muted").trim() || "#888";
    const fillRgb = hexToRgb(accent) || "120,120,120";
    const fill = `rgba(${fillRgb}, 0.22)`;
    const canvas = host.querySelector(".chart-wrap canvas");
    if (!canvas) return;
    // Mark the "now" point with an accent dot (single non-zero radius
    // entry in the dataset's pointRadius array).
    const nowIdx = closestIndex(series, nowMs);
    const pointRadius = series.map((_, i) => i === nowIdx ? 5 : 0);
    const pointBackgroundColor = series.map((_, i) => i === nowIdx ? fg : "transparent");
    const pointBorderColor = series.map((_, i) => i === nowIdx ? "#fff" : "transparent");
    new Chart(canvas, {
      type: "line",
      data: {
        labels: series.map((p) => fmtHour(p.t)),
        datasets: [{
          data: series.map((p) => p.v),
          borderColor: accent,
          backgroundColor: fill,
          borderWidth: 2.5,
          pointRadius,
          pointBackgroundColor,
          pointBorderColor,
          pointBorderWidth: 2,
          tension: 0.4,
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
            ticks: { color: muted, font: { size: 10, weight: 700 }, maxTicksLimit: 7, autoSkip: true },
            grid: { display: false },
            border: { display: false },
          },
          y: {
            display: false,
            min: d.y_min,
            max: d.y_max,
          },
        },
        animation: false,
      },
    });
  } catch (err) {
    console.warn("[tide] chart failed:", err);
  }
}

function extremaPill(kind, e) {
  const icon = kind === "high" ? "ph-arrow-up" : "ph-arrow-down";
  const lbl = kind === "high" ? "Next high" : "Next low";
  return `
    <div class="next next-${kind}">
      <i class="ph ${icon}" aria-hidden="true"></i>
      <div class="np">
        <span class="k">${lbl}</span>
        <span class="v">${fmtHour(e.t)} <em>${e.v.toFixed(2)}m</em></span>
      </div>
    </div>
  `;
}

function fmtHour(iso) {
  if (typeof iso !== "string" || iso.length < 13) return "";
  return iso.slice(11, 16);
}
function parseISO(iso) {
  if (typeof iso !== "string") return 0;
  // Pad missing timezone with Z so Date parses consistently across browsers.
  const t = iso.length === 16 ? `${iso}:00` : iso;
  const d = new Date(t);
  return isFinite(d.getTime()) ? d.getTime() : 0;
}
function closestIndex(series, ms) {
  let best = 0, bestDiff = Infinity;
  for (let i = 0; i < series.length; i++) {
    const diff = Math.abs(parseISO(series[i].t) - ms);
    if (diff < bestDiff) { bestDiff = diff; best = i; }
  }
  return best;
}
function currentValue(series, ms) {
  // Linear interpolation between the two flanking hourly samples — the
  // tide curve is smooth so the interp is a faithful estimate.
  if (!series.length) return null;
  for (let i = 1; i < series.length; i++) {
    const t0 = parseISO(series[i - 1].t);
    const t1 = parseISO(series[i].t);
    if (ms >= t0 && ms <= t1 && t1 > t0) {
      const k = (ms - t0) / (t1 - t0);
      return series[i - 1].v + k * (series[i].v - series[i - 1].v);
    }
  }
  return series[closestIndex(series, ms)].v;
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
