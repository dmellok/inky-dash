// Full example plugin — client renderer.
//
// Reads every piece of the ``ctx`` the loader provides and demonstrates
// the common patterns:
//   * Pull values from ``ctx.cell.options`` (configured in the editor)
//   * Pull data the server's fetch() returned via ``ctx.data``
//   * React to the cell size with a container-query class
//   * Lean on the shared widget-base.css for header / card / pill chrome
//   * Apply the optional ``tint`` colour override as an inline CSS var
//   * Surface an error state through the shared .state-error block
//
// All the visual chrome (.head, .head-icon, .head-title, .head-place,
// .head-time, .stat, .state-error, .pill, .pill.is-*) comes from
// /static/style/widget-base.css. Plugin-local CSS only adds the bits
// that are specific to this widget.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

const TONE_TO_PILL = {
  info: "",                  // default neutral pill
  ok: "is-ok",
  warn: "is-warn",
  danger: "is-danger",
};

export default function render(host, ctx) {
  const opts = ctx.cell?.options || {};
  const data = ctx.data || {};

  // Surface server-side fetch errors via the shared error state.
  if (data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="widget">
        <div class="state-error">
          <i class="ph ph-warning-circle"></i>
          <div class="msg">${escapeHtml(data.error)}</div>
        </div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const title = (opts.title || "EXAMPLE").toString().toUpperCase();
  const subtitle = opts.subtitle || "";
  const tone = TONE_TO_PILL[opts.tone] ?? "";
  const compact = !!opts.compact;
  const items = data.items || [];

  // Optional per-cell colour override — written through to a CSS var so
  // it overrides the theme accent only for this widget instance. Empty
  // strings fall through to the theme.
  const tintStyle = opts.tint
    ? `--theme-accent: ${opts.tint};`
    : "";

  const headTime = new Date().toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // Items: one .stat tile per server-side row.
  const tiles = items
    .map(
      (i) => `
        <div class="stat">
          <i class="ph ph-circle stat-ico"></i>
          <div class="stat-text">
            <div class="stat-label">${escapeHtml(i.label)}</div>
            <div class="stat-value">${escapeHtml(String(i.value))}</div>
          </div>
        </div>
      `,
    )
    .join("");

  const debugBlock = data.debug
    ? `<pre class="debug">${escapeHtml(JSON.stringify(data.debug, null, 2))}</pre>`
    : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/example_full/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="widget example ${compact ? "is-compact" : ""}" style="${tintStyle}">
      <div class="head">
        <i class="ph ph-puzzle-piece head-icon"></i>
        <span class="head-title">${escapeHtml(title)}</span>
        ${data.category_label
          ? `<span class="head-place">${escapeHtml(data.category_label)}</span>`
          : ""}
        <span class="head-time">${escapeHtml(headTime)}</span>
      </div>
      ${subtitle ? `<p class="subtitle">${escapeHtml(subtitle)}</p>` : ""}
      <div class="tone-row">
        <span class="pill ${tone}">tone: ${escapeHtml(opts.tone || "info")}</span>
        <span class="pill">size: ${escapeHtml(ctx.cell.size)}</span>
        <span class="pill">panel: ${ctx.panel.w}×${ctx.panel.h}</span>
      </div>
      <div class="tiles">${tiles}</div>
      ${debugBlock}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
