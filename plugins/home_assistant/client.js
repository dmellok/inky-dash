// Home Assistant tile. Three layouts:
//   - auto: 2-col grid (1-col on narrow), with icon + name + state stacked
//   - list: one entity per row, label left, value right
//   - hero: first entity rendered large; remaining as small stat chips below

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

const BIN_ON = new Set(["on", "open", "home", "unlocked", "playing", "active"]);

function formatValue(e) {
  // Binary-ish states get an "ON" / "OFF" pill colouring; everything else
  // is rendered verbatim with the HA unit suffix.
  return escapeHtml(e.state);
}

function renderEntity(e) {
  const isBinaryish = e.kind === "binary_sensor"
    || e.kind === "switch"
    || e.kind === "light"
    || e.kind === "lock"
    || e.kind === "person"
    || e.kind === "device_tracker";
  const lower = String(e.state).toLowerCase();
  const onClass = isBinaryish && BIN_ON.has(lower) ? "is-on" : "";
  const valueHtml = isBinaryish
    ? `<span class="state-chip ${onClass}">${formatValue(e)}</span>`
    : `<span class="value">${formatValue(e)}</span>${e.unit ? `<span class="unit">${escapeHtml(e.unit)}</span>` : ""}`;
  return `
    <div class="tile">
      <div class="tile-head">
        <i class="ph ${escapeHtml(e.icon)} ico"></i>
        <span class="name" title="${escapeHtml(e.name)}">${escapeHtml(e.name)}</span>
      </div>
      <div class="tile-body">${valueHtml}</div>
    </div>
  `;
}

function renderListRow(e) {
  return `
    <div class="row">
      <i class="ph ${escapeHtml(e.icon)} ico"></i>
      <span class="name" title="${escapeHtml(e.name)}">${escapeHtml(e.name)}</span>
      <span class="value">${escapeHtml(e.state)}${e.unit ? ` <span class="unit">${escapeHtml(e.unit)}</span>` : ""}</span>
    </div>
  `;
}

export default function render(host, ctx) {
  const data = ctx.data || {};
  const title = (ctx.cell?.options?.title || "HOME").toUpperCase();
  const layout = ctx.cell?.options?.layout || "auto";

  if (data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/home_assistant/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="ha ha--error">
        <i class="ph ph-house-line"></i>
        <div class="msg">${escapeHtml(data.error)}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const entities = data.entities || [];
  let body = "";
  if (layout === "list") {
    body = `<div class="list">${entities.map(renderListRow).join("")}</div>`;
  } else if (layout === "hero" && entities.length) {
    const [first, ...rest] = entities;
    body = `
      <div class="hero">
        <i class="ph ${escapeHtml(first.icon)} hero-ico"></i>
        <div class="hero-meta">
          <div class="hero-name">${escapeHtml(first.name)}</div>
          <div class="hero-val">
            ${escapeHtml(first.state)}${first.unit ? `<span class="unit">${escapeHtml(first.unit)}</span>` : ""}
          </div>
        </div>
      </div>
      ${rest.length ? `<div class="grid">${rest.map(renderEntity).join("")}</div>` : ""}
    `;
  } else {
    body = `<div class="grid">${entities.map(renderEntity).join("")}</div>`;
  }

  const partial =
    (data.errors || []).length > 0
      ? `<div class="partial-note" title="${escapeHtml((data.errors || []).join("; "))}">
           <i class="ph ph-warning"></i> ${(data.errors || []).length} entity error${data.errors.length === 1 ? "" : "s"}
         </div>`
      : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/home_assistant/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="ha ha--${layout}">
      <div class="head">
        <i class="ph ph-house-line head-icon"></i>
        <span class="head-title">${escapeHtml(title)}</span>
        ${partial}
      </div>
      ${entities.length === 0
        ? `<div class="empty"><i class="ph ph-info"></i><span>No entities returned.</span></div>`
        : body}
    </div>
  `;
  host.host.dataset.rendered = "true";
}
