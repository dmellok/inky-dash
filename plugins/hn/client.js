// Hacker News widget — list of top/new/best/ask/show stories. Two views:
// numbered list (default) or horizontal score chart, switchable per cell.
import { loadChart } from "/static/vendor/chartjs/loader.js";

const FEED_LABEL = {
  top: "TOP",
  new: "NEW",
  best: "BEST",
  ask: "ASK HN",
  show: "SHOW HN",
};

export default async function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="hn error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const stories = Array.isArray(d.stories) ? d.stories : [];
  const feedLabel = FEED_LABEL[d.feed] || "HN";
  const view = (opts.view || "list").trim();
  // Mini cells can't fit a useful chart — fall back to the list there.
  const useChart = view === "chart" && H >= 240 && stories.length;

  host.innerHTML = `
    <article class="hn ${sizeClass} view-${useChart ? "chart" : "list"}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-flame"></i>
        <span class="label">HACKER NEWS</span>
        <span class="meta">${escapeHtml(feedLabel)}</span>
      </header>` : ""}

      ${stories.length === 0
        ? `<div class="empty">No stories</div>`
        : useChart
          ? `<div class="chart-wrap"><canvas></canvas></div>`
          : `<ol class="story-list">${stories.map((s, i) => storyRow(s, i + 1)).join("")}</ol>`}
    </article>
  `;

  if (!useChart) return;
  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const fg     = styles.getPropertyValue("--theme-fg").trim() || "#111";
    const muted  = styles.getPropertyValue("--theme-muted").trim() || "#888";
    const accentSoft = `rgba(${hexToRgb(accent) || "120,120,120"}, 0.55)`;
    const canvas = host.querySelector(".chart-wrap canvas");
    if (!canvas) return;
    // Trim long titles so the y-axis labels stay legible — chart.js
    // doesn't truncate for us. Limit varies with cell width.
    const limit = W < 600 ? 32 : W < 900 ? 48 : 64;
    const labels = stories.map((s) => {
      const t = s.title || "";
      return t.length > limit ? t.slice(0, limit - 1).trimEnd() + "…" : t;
    });
    new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          data: stories.map((s) => s.score || 0),
          backgroundColor: accentSoft,
          borderColor: accent,
          borderWidth: 0,
          borderRadius: 6,
          barPercentage: 0.92,
          categoryPercentage: 0.85,
        }],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        scales: {
          x: {
            display: true,
            ticks: { color: muted, font: { size: 11, weight: 600 }, maxTicksLimit: 4 },
            grid: { color: "rgba(0,0,0,0.04)" },
            border: { display: false },
          },
          y: {
            ticks: { color: fg, font: { size: 12, weight: 700 } },
            grid: { display: false },
            border: { display: false },
          },
        },
        animation: false,
      },
    });
  } catch (err) {
    console.warn("[hn] chart failed:", err);
  }
}

function storyRow(s, rank) {
  const meta = [
    `${s.score} pts`,
    `${s.comments} comments`,
    s.author ? `by ${s.author}` : null,
    s.domain && !s.self ? s.domain : null,
  ].filter(Boolean).join(" · ");
  return `
    <li class="story">
      <span class="rank">${rank}</span>
      <div class="body">
        <div class="title">${escapeHtml(s.title || "")}</div>
        <div class="meta">${escapeHtml(meta)}</div>
      </div>
      <span class="score-chip">
        <i class="ph ph-arrow-fat-up" aria-hidden="true"></i>
        <span>${s.score}</span>
      </span>
    </li>
  `;
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
