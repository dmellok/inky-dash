// Wind compass widget — pure SVG rose, no Chart.js needed. Cardinal
// labels (N/E/S/W) anchor the dial; an accent arrow rotates to the
// reported wind direction; the centre stack shows speed + gusts +
// 16-point cardinal name.
//
// Meteorological convention: wind direction is *where the wind is
// coming from*, so 90° = "from the east" — the arrow points TOWARD the
// origin.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="wd error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const dir = Number(d.direction_deg ?? 0);
  const speed = Number(d.speed ?? 0);
  const gust = d.gust;

  host.innerHTML = `
    <article class="wd ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-wind"></i>
        <span class="label">WIND</span>
        <span class="meta">${escapeHtml(d.place || "")}</span>
      </header>` : ""}

      <div class="dial-wrap">
        <svg class="dial" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <circle cx="100" cy="100" r="92" class="ring"/>
          ${ticks()}
          <text x="100" y="22"  class="label-cardinal" text-anchor="middle">N</text>
          <text x="180" y="105" class="label-cardinal" text-anchor="middle">E</text>
          <text x="100" y="188" class="label-cardinal" text-anchor="middle">S</text>
          <text x="20"  y="105" class="label-cardinal" text-anchor="middle">W</text>
          <!-- Arrow head at the rim of the bearing the wind is coming
               from (meteorological convention). NW wind → head in NW. -->
          <g class="arrow" transform="rotate(${dir} 100 100)">
            <line x1="100" y1="100" x2="100" y2="42" />
            <polygon points="100,30 92,48 108,48" />
          </g>
          <circle cx="100" cy="100" r="6" class="hub"/>
        </svg>
      </div>

      <!-- Speed / cardinal / gust block sits below the dial so it can't
           collide with the cardinal labels at any size class. -->
      <div class="readout">
        <div class="speed-row">
          <span class="num">${speed}</span>
          <span class="unit">${escapeHtml(d.unit_label || "")}</span>
        </div>
        <div class="meta-row">
          <span class="cardinal">${escapeHtml(d.cardinal || "")} · ${Math.round(dir)}°</span>
          ${gust != null ? `<span class="gust">gust ${gust} ${escapeHtml(d.unit_label || "")}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function ticks() {
  const out = [];
  for (let i = 0; i < 16; i++) {
    const angle = i * 22.5;
    const major = i % 4 === 0;
    const inner = major ? 84 : 88;
    const outer = 92;
    // Convert polar (angle, r) → cartesian, with 0° at the top.
    const a = (angle - 90) * Math.PI / 180;
    const x1 = 100 + Math.cos(a) * inner;
    const y1 = 100 + Math.sin(a) * inner;
    const x2 = 100 + Math.cos(a) * outer;
    const y2 = 100 + Math.sin(a) * outer;
    out.push(`<line x1="${x1.toFixed(2)}" y1="${y1.toFixed(2)}" x2="${x2.toFixed(2)}" y2="${y2.toFixed(2)}" class="tick ${major ? 'major' : ''}"/>`);
  }
  return out.join("");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
