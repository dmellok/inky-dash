// World clock widget — vertical stack of city rows. Each row shows a
// 24-hour day/night track with a cursor at the local "now" hour.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="wc error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const rows = Array.isArray(d.rows) ? d.rows : [];
  const dayStart = Number(d.day_start ?? 6);
  const dayEnd = Number(d.day_end ?? 18);
  const dayPctL = (dayStart / 24) * 100;
  const dayPctW = ((dayEnd - dayStart) / 24) * 100;

  host.innerHTML = `
    <article class="wc ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-globe"></i>
        <span class="label">WORLD CLOCK</span>
      </header>` : ""}

      <ul class="zone-list">
        ${rows.map((r) => zoneRow(r, dayPctL, dayPctW)).join("")}
      </ul>
    </article>
  `;
}

function zoneRow(r, dayLeft, dayWidth) {
  const cursorPct = ((r.hour_fraction || 0) / 24) * 100;
  return `
    <li class="zone ${r.is_day ? "day" : "night"}">
      <div class="meta">
        <span class="city">${escapeHtml(r.label || "")}</span>
        <span class="sub">${escapeHtml(r.weekday || "")} · ${escapeHtml(r.date || "")} · ${escapeHtml(r.offset || "")}</span>
      </div>
      <div class="time-block">
        <span class="time">${escapeHtml(r.time || "")}</span>
        ${r.ampm ? `<span class="ampm">${escapeHtml(r.ampm)}</span>` : ""}
      </div>
      <div class="track" aria-hidden="true">
        <span class="day-band" style="left: ${dayLeft}%; width: ${dayWidth}%"></span>
        <span class="cursor" style="left: ${cursorPct}%"></span>
        <span class="hour-tick" style="left: 0%">00</span>
        <span class="hour-tick" style="left: 25%">06</span>
        <span class="hour-tick" style="left: 50%">12</span>
        <span class="hour-tick" style="left: 75%">18</span>
      </div>
    </li>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
