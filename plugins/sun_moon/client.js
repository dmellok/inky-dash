// Sun & Moon widget — sunrise/sunset hero, civil dawn/dusk, day length,
// moon phase tile.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="sm error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const moon = d.moon || {};

  host.innerHTML = `
    <article class="sm ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-sun-horizon"></i>
        <span class="label">SUN &amp; MOON</span>
        <span class="meta">${escapeHtml(d.place || "")}</span>
      </header>` : ""}

      <div class="hero">
        <div class="sun-pair">
          <div class="block sunrise">
            <i class="ph ph-sun-horizon" aria-hidden="true"></i>
            <div class="vals">
              <span class="k">SUNRISE</span>
              <span class="v">${escapeHtml(d.sunrise || "—")}</span>
            </div>
          </div>
          <div class="block sunset">
            <i class="ph ph-sun-dim" aria-hidden="true"></i>
            <div class="vals">
              <span class="k">SUNSET</span>
              <span class="v">${escapeHtml(d.sunset || "—")}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="strip">
        <div class="metric">
          <span class="k">CIVIL DAWN</span>
          <span class="v">${escapeHtml(d.dawn || "—")}</span>
        </div>
        <div class="metric">
          <span class="k">CIVIL DUSK</span>
          <span class="v">${escapeHtml(d.dusk || "—")}</span>
        </div>
        <div class="metric">
          <span class="k">DAY LENGTH</span>
          <span class="v">${escapeHtml(d.day_length || "—")}</span>
        </div>
      </div>

      <div class="moon">
        <div class="moon-vis">
          ${moonSVG(moon)}
        </div>
        <div class="moon-meta">
          <div class="phase">${escapeHtml(moon.phase_name || "—")}</div>
          <div class="illum">
            <span class="num">${moon.illumination_pct ?? 0}%</span>
            <span class="lbl">illuminated · ${escapeHtml(moon.waxing ? "waxing" : "waning")} · day ${moon.age_days ?? 0}</span>
          </div>
        </div>
      </div>
    </article>
  `;
}

// Pure SVG moon rendering — two stacked circles clipped to draw the lit
// fraction. Index 0..7 maps to new → waning crescent.
function moonSVG(moon) {
  const idx = Math.max(0, Math.min(7, Number(moon.phase_index ?? 0)));
  const fraction = (moon.illumination_pct ?? 0) / 100;
  const waxing = !!moon.waxing;
  // Build a half-disc + an ellipse to carve the terminator. Adapted from
  // a common moon-phase SVG technique: use an elliptical mask whose
  // x-radius proportional to (1 - 2·fraction)·R; sign flips for waxing.
  const R = 50;
  // Lit half: right side for waxing, left side for waning.
  const half = waxing
    ? `<path d="M50 0 A50 50 0 0 1 50 100 Z" fill="var(--theme-accent, currentColor)"/>`
    : `<path d="M50 0 A50 50 0 0 0 50 100 Z" fill="var(--theme-accent, currentColor)"/>`;
  // Terminator ellipse — narrow at full, wide at new. rx = |1 - 2f|·R.
  const rx = Math.abs(1 - 2 * fraction) * R;
  // For waxing: when fraction < 0.5 the dark side eats from the right (cover lit half partially) — but
  // we drew lit half on right; so the terminator ellipse should be drawn in dark (bg) when fraction<0.5
  // and in lit (accent) when fraction>0.5 (gibbous). Same idea inverted for waning.
  let termFill;
  if (waxing) {
    termFill = fraction < 0.5
      ? "var(--theme-surface-2, var(--theme-surface, #222))"
      : "var(--theme-accent, currentColor)";
  } else {
    termFill = fraction < 0.5
      ? "var(--theme-surface-2, var(--theme-surface, #222))"
      : "var(--theme-accent, currentColor)";
  }
  const term = `<ellipse cx="50" cy="50" rx="${rx}" ry="50" fill="${termFill}" />`;
  return `
    <svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-label="${escapeHtml(moon.phase_name || "moon")}">
      <circle cx="50" cy="50" r="50" fill="var(--theme-surface-2, var(--theme-surface, #222))" />
      ${half}
      ${term}
      <circle cx="50" cy="50" r="49.5" fill="none" stroke="var(--theme-divider, currentColor)" stroke-opacity="0.4" stroke-width="1" />
    </svg>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
