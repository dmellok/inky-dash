// Star map — circular horizon view. Server hands back projected (x, y) in
// [-1, 1] for each visible star (zenith at center, horizon at radius 1)
// plus optional constellation line segments and moon position.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

// Apparent magnitude → dot radius. Brightest (mag ~ -1.5) ≈ 5, dim
// (mag ~ 4) ≈ 1. Beyond mag 4 we don't render anything by default.
function radiusForMag(mag) {
  return Math.max(0.6, 5 - mag * 0.9);
}

export default function render(host, ctx) {
  const data = ctx.data || {};
  const showNames = data.show_names !== false;

  if (data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/starmap/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="sky sky--error">
        <i class="ph ph-warning-circle"></i>
        <div class="msg">${escapeHtml(data.error)}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  // Use a virtual canvas of 200 (radius 100) so the SVG math is integer-ish.
  // The disc is centered at (100, 100).
  const S = 200;
  const R = 96; // small inset so labels don't clip the disc edge

  // Lines first so they sit beneath the dots.
  const lines = (data.lines || []).map(
    (l) =>
      `<line
        x1="${(100 + l.x1 * R).toFixed(1)}"
        y1="${(100 + l.y1 * R).toFixed(1)}"
        x2="${(100 + l.x2 * R).toFixed(1)}"
        y2="${(100 + l.y2 * R).toFixed(1)}"
        class="con-line"
      />`,
  ).join("");

  // Stars — circles + optional labels for the brightest few.
  const stars = data.stars || [];
  stars.sort((a, b) => a.mag - b.mag);
  const dots = stars
    .map((s) => {
      const cx = (100 + s.x * R).toFixed(1);
      const cy = (100 + s.y * R).toFixed(1);
      const r = radiusForMag(s.mag).toFixed(2);
      return `<circle cx="${cx}" cy="${cy}" r="${r}" class="star"/>`;
    })
    .join("");
  const labels = showNames
    ? stars
        .filter((s) => s.mag < 1.5)
        .slice(0, 8)
        .map((s) => {
          const cx = 100 + s.x * R;
          const cy = 100 + s.y * R;
          const offset = radiusForMag(s.mag) + 2.5;
          return `<text
            x="${(cx + offset).toFixed(1)}"
            y="${(cy + 1).toFixed(1)}"
            class="star-label"
          >${escapeHtml(s.name)}</text>`;
        })
        .join("")
    : "";

  // Cardinal points around the horizon disc — N at top, then E/S/W clockwise.
  const cardinals = [
    { l: "N", x: 100, y: 100 - R - 1.5, anchor: "middle", baseline: "after-edge" },
    { l: "E", x: 100 + R + 3, y: 100, anchor: "start", baseline: "middle" },
    { l: "S", x: 100, y: 100 + R + 5, anchor: "middle", baseline: "before-edge" },
    { l: "W", x: 100 - R - 3, y: 100, anchor: "end", baseline: "middle" },
  ]
    .map(
      (c) =>
        `<text x="${c.x}" y="${c.y}" text-anchor="${c.anchor}" dominant-baseline="${c.baseline}" class="cardinal">${c.l}</text>`,
    )
    .join("");

  const moon = data.moon
    ? `<g class="moon">
         <circle cx="${(100 + data.moon.x * R).toFixed(1)}"
                 cy="${(100 + data.moon.y * R).toFixed(1)}"
                 r="3" class="moon-dot"/>
         <circle cx="${(100 + data.moon.x * R).toFixed(1)}"
                 cy="${(100 + data.moon.y * R).toFixed(1)}"
                 r="5.5" class="moon-glow"/>
       </g>`
    : "";

  const locationLabel = data.label
    ? `<span class="head-place">${escapeHtml(data.label)}</span>`
    : "";
  const timeLabel = data.time_local
    ? `<span class="head-time">${escapeHtml(data.time_local)} local</span>`
    : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/starmap/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="sky">
      <div class="head">
        <i class="ph ph-star head-icon"></i>
        <span class="head-title">SKY</span>
        ${locationLabel}
        ${timeLabel}
      </div>
      <div class="chart-wrap">
        <svg viewBox="0 0 ${S} ${S}" preserveAspectRatio="xMidYMid meet" class="chart">
          <circle cx="100" cy="100" r="${R}" class="horizon"/>
          <circle cx="100" cy="100" r="${R * 0.5}" class="alt-ring"/>
          <line x1="100" y1="${100 - R}" x2="100" y2="${100 + R}" class="alt-cross"/>
          <line x1="${100 - R}" y1="100" x2="${100 + R}" y2="100" class="alt-cross"/>
          ${lines}
          ${dots}
          ${moon}
          ${labels}
          ${cardinals}
        </svg>
      </div>
    </div>
  `;
  host.host.dataset.rendered = "true";
}
