// Earthquakes widget — list of recent quakes with magnitude-tinted bars.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="eq error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const quakes = Array.isArray(d.quakes) ? d.quakes : [];

  // Mag bar normalised against M9 — visually matches the way news outlets
  // size mag readouts ("a 5 fills half"). Each row's bar is `mag/9 * 100%`.
  const rows = quakes.map((q) => {
    const pct = Math.max(6, Math.min(100, Math.round((q.mag / 9) * 100)));
    return `
      <li class="quake sev-${q.severity}">
        <div class="mag-block">
          <span class="mag">${q.mag}</span>
          <div class="bar"><div class="fill" style="width: ${pct}%"></div></div>
        </div>
        <div class="meta">
          <div class="place">${escapeHtml(q.place || "")}</div>
          <div class="sub">
            <span class="ago">${escapeHtml(q.ago || "")}</span>
            ${q.depth_km != null ? `<span class="depth">${q.depth_km} km deep</span>` : ""}
            ${q.tsunami ? `<span class="tsunami"><i class="ph ph-warning"></i> tsunami</span>` : ""}
          </div>
        </div>
      </li>
    `;
  }).join("");

  host.innerHTML = `
    <article class="eq ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-wave-sine"></i>
        <span class="label">EARTHQUAKES</span>
        <span class="meta">${escapeHtml(d.feed_label || "")}</span>
      </header>` : ""}
      ${quakes.length === 0
        ? `<div class="empty">No quakes in this window. Quiet day.</div>`
        : `<ol class="list">${rows}</ol>`}
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
