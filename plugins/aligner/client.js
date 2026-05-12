// Frame aligner — draws concentric rectangle rings in alternating dark
// Spectra-6-friendly inks at the cell edge so you can see exactly which
// ring the paper mat opening lands on when mounting the panel in a frame.
//
// The full-bleed flag in plugin.json kills the cell's outline so the
// outermost ring sits flush against the panel edge.

// Six dark Spectra-6-native inks (or close to). Each renders as a solid
// colour on the panel rather than dithering down to an unrecognisable
// mid-grey, so adjacent rings stay distinguishable through a paper mat.
const INK_PALETTE = [
  "#000000", // black
  "#8b0000", // dark red
  "#00008b", // navy blue
  "#006400", // forest green
  "#b8860b", // dark goldenrod (orange-leaning, Spectra orange-ish)
  "#4b0082", // indigo
];

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

export default function render(host, ctx) {
  const cell = ctx.cell || {};
  const W = Math.max(1, Math.round(cell.w || 1200));
  const H = Math.max(1, Math.round(cell.h || 1600));
  const opts = cell.options || {};

  const ringCount = Math.max(1, Math.min(40, Number(opts.ring_count) || 10));
  const thickness = Math.max(2, Math.min(40, Number(opts.ring_thickness_px) || 10));
  const showLabels = opts.show_labels !== false;
  const showCrosshair = opts.show_crosshair !== false;

  // Build rings outside-in. Each ring is a stroked rect at offset
  // (i + 0.5) * thickness so the stroke centre lands at exactly that
  // offset; the visible band runs from i*t to (i+1)*t from the cell edge.
  // We use stroke + fill:none so adjacent rings can't bleed pixels into
  // each other on the panel.
  const rings = [];
  for (let i = 0; i < ringCount; i++) {
    const inset = (i + 0.5) * thickness;
    const x = inset;
    const y = inset;
    const w = W - inset * 2;
    const h = H - inset * 2;
    if (w <= thickness || h <= thickness) break;
    const ink = INK_PALETTE[i % INK_PALETTE.length];
    rings.push({ i, x, y, w, h, ink });
  }

  // Corner labels per ring — just the pixel offset from the edge so the
  // user can read it off through the mat opening. Skipped on tight cells.
  const labels = [];
  if (showLabels) {
    for (const r of rings) {
      const px = `${(r.i + 1) * thickness}px`;
      labels.push({
        x: r.x + thickness * 0.5 + 4,
        y: r.y + thickness * 0.5 + 4,
        text: px,
        fill: r.ink,
      });
    }
  }

  // Centre crosshair — long horizontal/vertical lines + a circular target
  // marker so the user can centre the panel inside the frame opening too.
  let crosshair = "";
  if (showCrosshair) {
    const cx = W / 2;
    const cy = H / 2;
    const armLength = Math.min(W, H) * 0.06;
    crosshair = `
      <line x1="${cx}" y1="${cy - armLength}" x2="${cx}" y2="${cy + armLength}"
            stroke="#000000" stroke-width="${Math.max(2, thickness * 0.25)}"/>
      <line x1="${cx - armLength}" y1="${cy}" x2="${cx + armLength}" y2="${cy}"
            stroke="#000000" stroke-width="${Math.max(2, thickness * 0.25)}"/>
      <circle cx="${cx}" cy="${cy}" r="${armLength * 0.4}" fill="none"
              stroke="#000000" stroke-width="${Math.max(2, thickness * 0.25)}"/>
      <circle cx="${cx}" cy="${cy}" r="2.5" fill="#000000"/>
    `;
  }

  // Mid-mark ticks on each edge — short stubs aligned to the cell midpoint.
  // Helps with horizontal/vertical centring inside the mat opening when the
  // crosshair is hidden by the mat at the centre.
  const midMarks = (() => {
    const cx = W / 2;
    const cy = H / 2;
    const tickLen = thickness * 1.5;
    const sw = Math.max(2, thickness * 0.3);
    return `
      <line x1="${cx}" y1="0" x2="${cx}" y2="${tickLen}" stroke="#000000" stroke-width="${sw}"/>
      <line x1="${cx}" y1="${H - tickLen}" x2="${cx}" y2="${H}" stroke="#000000" stroke-width="${sw}"/>
      <line x1="0" y1="${cy}" x2="${tickLen}" y2="${cy}" stroke="#000000" stroke-width="${sw}"/>
      <line x1="${W - tickLen}" y1="${cy}" x2="${W}" y2="${cy}" stroke="#000000" stroke-width="${sw}"/>
    `;
  })();

  const ringSvg = rings
    .map(
      (r) =>
        `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}"
               fill="none" stroke="${r.ink}" stroke-width="${thickness}"/>`,
    )
    .join("\n");

  const labelSvg = labels
    .map(
      (l) =>
        `<text x="${l.x}" y="${l.y}" fill="${l.fill}"
               font-size="${thickness * 0.9}" font-weight="700"
               dominant-baseline="hanging">${escapeHtml(l.text)}</text>`,
    )
    .join("\n");

  // A short legend at the bottom-centre tells the user the cell's actual
  // pixel dimensions, which is handy if you forgot the panel resolution.
  const legendY = H - thickness * 1.8;
  const legend = `
    <rect x="${W / 2 - 120}" y="${legendY - thickness * 0.6}" width="240" height="${thickness * 2.2}"
          fill="#ffffff" stroke="#000000" stroke-width="2"/>
    <text x="${W / 2}" y="${legendY + thickness * 0.6}" fill="#000000"
          font-size="${Math.max(11, thickness * 1.1)}" font-weight="700"
          text-anchor="middle" dominant-baseline="middle">
      ALIGNER · ${W}×${H} · ${thickness}px rings
    </text>
  `;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/aligner/client.css">
    <svg
      class="aligner"
      viewBox="0 0 ${W} ${H}"
      preserveAspectRatio="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect width="${W}" height="${H}" fill="#ffffff"/>
      ${ringSvg}
      ${midMarks}
      ${crosshair}
      ${labelSvg}
      ${legend}
    </svg>
  `;

  host.host.dataset.rendered = "true";
}
