// Air quality widget — AQI hero + category, scale bar, pollutant tiles.

export default function render(host, ctx) {
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

  host.innerHTML = `
    <article class="aq ${sizeClass} sev-${severity}">
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
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
