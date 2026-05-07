// Generic RSS/Atom feed reader.

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function fmtAge(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const { data } = ctx;
  const items = data && data.items ? data.items : [];
  const error = data && data.error;
  const title = (data && data.title) || "News";
  const visible = size === "sm" ? 3 : size === "md" ? 6 : 9;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/news/client.css">
    <div class="news news--${size}">
      <div class="header">
        <span class="title"><i class="ph ph-newspaper-fill"></i> ${escapeHtml(title)}</span>
      </div>
      ${error
        ? `<div class="error"><i class="ph ph-warning-circle"></i> ${escapeHtml(error)}</div>`
        : items.length === 0
          ? `<div class="empty">No items.</div>`
          : `<ul class="list">${items
              .slice(0, visible)
              .map(
                (item) => `
                  <li>
                    <div class="entry-title">${escapeHtml(item.title)}</div>
                    <div class="entry-meta"><i class="ph ph-clock"></i> ${fmtAge(item.published)}</div>
                  </li>
                `
              )
              .join("")}</ul>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
