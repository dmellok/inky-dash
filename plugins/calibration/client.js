// Calibration widget — renders the test card on the panel.
// 8 rows (hues A-H) × 6 cols (lightness 1-6) of HSL swatches, each with the
// coordinate + hex code drawn in BOTH black and white text overlapping the
// swatch. After dithering on the panel, at least one of the two labels will
// remain legible regardless of which ink the swatch quantises to.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

export default function render(host, ctx) {
  const data = ctx.data || {};
  const cells = Array.isArray(data.cells) ? data.cells : [];

  if (cells.length === 0) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/calibration/client.css">
      <div class="cal cal--empty">
        <i class="ph ph-warning-circle"></i>
        <div>No calibration loaded.</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const rows = 8;
  const cols = 6;
  const grouped = Array.from({ length: rows }, () => []);
  for (const cell of cells) {
    if (cell.row >= 0 && cell.row < rows) grouped[cell.row].push(cell);
  }
  for (const row of grouped) row.sort((a, b) => a.col - b.col);

  const swatches = grouped
    .flat()
    .map(
      (cell) => `
        <div class="swatch" style="background:${cell.hex}">
          <span class="l-tl">${escapeHtml(cell.id)}</span>
          <span class="l-br">${escapeHtml(cell.hex.toUpperCase())}</span>
        </div>
      `,
    )
    .join("");

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/calibration/client.css">
    <div class="cal">
      <div class="caption">
        <span class="name">${escapeHtml(data.name || "Calibration")}</span>
        <span class="sat">S=${data.saturation ?? 80}%</span>
      </div>
      <div class="grid" style="grid-template-columns: repeat(${cols}, 1fr); grid-template-rows: repeat(${rows}, 1fr);">
        ${swatches}
      </div>
    </div>
  `;

  host.host.dataset.rendered = "true";
}
