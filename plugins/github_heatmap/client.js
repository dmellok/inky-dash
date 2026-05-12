// GitHub contributions heatmap. The classic 7-row × N-column grid: rows are
// weekdays (Sun → Sat), columns are weeks, intensity tinted by the server's
// 0..4 "level" field. Falls back to recomputing level from count when the
// server didn't supply one.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function levelFor(count) {
  if (count <= 0) return 0;
  if (count < 3) return 1;
  if (count < 6) return 2;
  if (count < 10) return 3;
  return 4;
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const data = ctx.data || {};

  if (data.error || !data.contributions) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/github_heatmap/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="gh gh--error">
        <i class="ph ph-git-commit"></i>
        <div class="msg">${escapeHtml(data.error || "No contributions data.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const contribs = data.contributions;
  // Pad the start so column 0 begins on a Sunday — GitHub's convention.
  const first = contribs.length ? new Date(contribs[0].date + "T00:00:00Z") : new Date();
  const pad = first.getUTCDay(); // 0..6, Sunday = 0
  const cells = Array(pad).fill(null).concat(contribs);
  const weeks = Math.ceil(cells.length / 7);

  // Build column-major SVG so we can lay it out with viewBox math.
  const CELL = 10;
  const GAP = 2;
  const W = weeks * (CELL + GAP) - GAP;
  const H = 7 * (CELL + GAP) - GAP;

  let monthTicks = "";
  let lastMonth = -1;
  for (let w = 0; w < weeks; w++) {
    // Find the first non-null cell in this column for the date.
    let dateStr = null;
    for (let r = 0; r < 7; r++) {
      const c = cells[w * 7 + r];
      if (c) { dateStr = c.date; break; }
    }
    if (!dateStr) continue;
    const month = new Date(dateStr + "T00:00:00Z").getUTCMonth();
    if (month !== lastMonth) {
      const x = w * (CELL + GAP);
      monthTicks += `<text x="${x}" y="-4" class="gh-mtick">${MONTH_NAMES[month]}</text>`;
      lastMonth = month;
    }
  }

  let rects = "";
  for (let w = 0; w < weeks; w++) {
    for (let r = 0; r < 7; r++) {
      const c = cells[w * 7 + r];
      if (!c) continue;
      const lvl = c.level != null ? c.level : levelFor(c.count || 0);
      const x = w * (CELL + GAP);
      const y = r * (CELL + GAP);
      rects += `<rect x="${x}" y="${y}" width="${CELL}" height="${CELL}" rx="2" class="gh-cell gh-l${lvl}" />`;
    }
  }

  // Header strip: same shape as weather/aqi/note for visual consistency.
  const headerRight = data.total != null
    ? `<span class="head-stat">${data.total.toLocaleString()} <span class="head-stat-label">contributions</span></span>`
    : "";

  // Stat strip: current streak, longest streak, busiest day, weekday avg.
  // Skipped on the smallest cells where there's no room.
  const s = data.stats || {};
  const showStats = size !== "xs";
  const bestLabel = s.best_day
    ? formatShortDate(s.best_day.date)
    : "—";
  const stats = showStats
    ? `<div class="stat-strip">
        <div class="stat">
          <i class="ph ph-flame stat-ico"></i>
          <div class="stat-meta">
            <div class="stat-num">${s.current_streak ?? 0}</div>
            <div class="stat-label">DAY STREAK</div>
          </div>
        </div>
        <div class="stat">
          <i class="ph ph-trophy stat-ico"></i>
          <div class="stat-meta">
            <div class="stat-num">${s.longest_streak ?? 0}</div>
            <div class="stat-label">LONGEST</div>
          </div>
        </div>
        <div class="stat">
          <i class="ph ph-star stat-ico"></i>
          <div class="stat-meta">
            <div class="stat-num">${s.best_day?.count ?? 0}</div>
            <div class="stat-label">BEST DAY · ${escapeHtml(bestLabel)}</div>
          </div>
        </div>
        <div class="stat">
          <i class="ph ph-calendar-check stat-ico"></i>
          <div class="stat-meta">
            <div class="stat-num">${s.active_days ?? 0}</div>
            <div class="stat-label">ACTIVE DAYS</div>
          </div>
        </div>
      </div>`
    : "";

  // Footer strip: avg + busiest weekday + legend on the right.
  const showLegend = size !== "xs" && size !== "sm";
  const footerBits = [];
  if (s.avg_per_day != null) {
    footerBits.push(`<span class="foot-stat"><i class="ph ph-pulse"></i> ${s.avg_per_day}/day avg</span>`);
  }
  if (s.busiest_weekday) {
    footerBits.push(`<span class="foot-stat"><i class="ph ph-calendar-blank"></i> Best on ${escapeHtml(s.busiest_weekday)}</span>`);
  }
  const legend = showLegend
    ? `<div class="legend">
        <span class="legend-label">Less</span>
        <svg viewBox="0 0 ${5 * 14} 12" preserveAspectRatio="xMidYMid meet">
          ${[0, 1, 2, 3, 4]
            .map(l => `<rect x="${l * 14}" y="0" width="10" height="10" rx="2" class="gh-cell gh-l${l}" />`)
            .join("")}
        </svg>
        <span class="legend-label">More</span>
      </div>`
    : "";
  const footer = (footerBits.length || legend)
    ? `<div class="foot">
        <div class="foot-stats">${footerBits.join("")}</div>
        ${legend}
      </div>`
    : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/github_heatmap/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="gh gh--${size}">
      <div class="head">
        <i class="ph ph-git-commit head-icon"></i>
        <span class="head-title">GITHUB</span>
        <span class="head-name">@${escapeHtml(data.username)}</span>
        ${headerRight}
      </div>
      ${stats}
      <div class="grid-wrap">
        <svg
          class="grid"
          viewBox="0 -14 ${W} ${H + 14}"
          preserveAspectRatio="xMidYMid meet"
        >
          ${monthTicks}
          ${rects}
        </svg>
      </div>
      ${footer}
    </div>
  `;
  host.host.dataset.rendered = "true";
}

function formatShortDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00Z");
  if (Number.isNaN(d.getTime())) return iso;
  return `${MONTH_NAMES[d.getUTCMonth()]} ${d.getUTCDate()}`;
}
