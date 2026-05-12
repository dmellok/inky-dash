// Weather radar — 3×3 tile mosaic, basemap underneath, radar layer on top.
// Server returns URL templates with {z}/{x}/{y} placeholders + the center
// (tile_x, tile_y) at the chosen zoom. We render a 3-col × 3-row grid with
// the surrounding 8 tiles for context.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function fmtAge(seconds) {
  if (seconds == null) return "";
  if (seconds < 60) return "just now";
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins} min ago`;
  return `${Math.round(mins / 60)}h ago`;
}

export default function render(host, ctx) {
  const data = ctx.data || {};
  if (data.error || !data.radar_template) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/radar/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="rdr rdr--error">
        <i class="ph ph-cloud-x"></i>
        <div class="msg">${escapeHtml(data.error || "No radar data.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const z = data.zoom;
  const cx = data.tile_x;
  const cy = data.tile_y;
  const fill = (tpl, x, y) =>
    tpl.replace("{z}", z).replace("{x}", x).replace("{y}", y);

  // 3×3 surrounding tiles.
  let tiles = "";
  for (let dy = -1; dy <= 1; dy++) {
    for (let dx = -1; dx <= 1; dx++) {
      const x = cx + dx;
      const y = cy + dy;
      const baseUrl = data.basemap_template ? fill(data.basemap_template, x, y) : null;
      const radarUrl = fill(data.radar_template, x, y);
      tiles += `
        <div class="cell" style="grid-column: ${dx + 2}; grid-row: ${dy + 2};">
          ${baseUrl ? `<img class="base" src="${escapeHtml(baseUrl)}" alt="" />` : ""}
          <img class="radar" src="${escapeHtml(radarUrl)}" alt="" />
        </div>
      `;
    }
  }

  const ageSec = data.radar_ts
    ? Math.max(0, Math.floor(Date.now() / 1000) - data.radar_ts)
    : null;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/radar/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="rdr">
      <div class="mosaic">
        ${tiles}
        <div class="pin" aria-hidden="true">
          <i class="ph ph-map-pin-fill"></i>
        </div>
      </div>
      <div class="badge">
        <i class="ph ph-cloud-rain"></i>
        <span class="label">${escapeHtml(data.label || "Radar")}</span>
        ${ageSec != null ? `<span class="age">${fmtAge(ageSec)}</span>` : ""}
      </div>
      <div class="credit">© OpenStreetMap · RainViewer</div>
    </div>
  `;

  // Hold rendered flag until all tiles have loaded.
  const imgs = Array.from(host.querySelectorAll("img"));
  let pending = imgs.length;
  if (pending === 0) {
    host.host.dataset.rendered = "true";
    return;
  }
  const done = () => {
    pending -= 1;
    if (pending <= 0) host.host.dataset.rendered = "true";
  };
  for (const img of imgs) {
    if (img.complete) done();
    else {
      img.addEventListener("load", done, { once: true });
      img.addEventListener("error", done, { once: true });
    }
  }
}
