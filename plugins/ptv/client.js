// PTV departures — header strip + a stack of departure rows. Each row
// shows route+platform on the left, destination in the middle, and a
// "due"/"3 min"/"HH:MM" pill on the right.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function whenLabel(d) {
  // d.in_minutes is signed: negative = already left (rare given filter)
  const m = d.in_minutes;
  if (m == null) return d.scheduled_local;
  if (m <= 0) return "now";
  if (m < 60) return `${m} min`;
  return d.scheduled_local;
}

const ROWS_BY_SIZE = { xs: 3, sm: 4, md: 6, lg: 8 };

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const data = ctx.data || {};
  const title = (ctx.cell?.options?.title || "").trim();

  if (data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/ptv/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="ptv ptv--error">
        <i class="ph ph-train"></i>
        <div class="msg">${escapeHtml(data.error)}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const visible = (data.departures || []).slice(0, ROWS_BY_SIZE[size] ?? 6);
  const rows = visible
    .map((d) => {
      const route = escapeHtml((d.route_number || d.route_name || "").toString());
      const dest = escapeHtml(d.destination || "");
      const platform = d.platform
        ? `<span class="platform" title="Platform">Pl ${escapeHtml(d.platform)}</span>`
        : "";
      const estimated = d.is_estimated ? "" : `<span class="sched-flag" title="Scheduled time — no live estimate">·</span>`;
      return `
        <div class="row">
          <span class="route">${route}</span>
          <span class="dest" title="${dest}">${dest}</span>
          ${platform}
          <span class="when">${escapeHtml(whenLabel(d))}${estimated}</span>
        </div>
      `;
    })
    .join("");

  const stop = escapeHtml(data.stop_name || "");
  const head = title || data.route_type_label || "Departures";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/ptv/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="ptv ptv--${size}">
      <div class="head">
        <i class="ph ph-train head-icon"></i>
        <span class="head-title">${escapeHtml(head.toUpperCase())}</span>
        <span class="head-stop">${stop}</span>
      </div>
      ${visible.length
        ? `<div class="rows">${rows}</div>`
        : `<div class="empty"><i class="ph ph-clock-countdown"></i><span>No upcoming departures.</span></div>`}
    </div>
  `;
  host.host.dataset.rendered = "true";
}
