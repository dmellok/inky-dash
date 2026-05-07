// Todo — render-only widget. Items are added/removed at /plugins/todo/.

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const { data } = ctx;
  const items = data && data.items ? data.items : [];
  const visible = size === "xs" ? 3 : size === "sm" ? 5 : size === "md" ? 8 : 14;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/todo/client.css">
    <div class="todo todo--${size}">
      <div class="header">
        <i class="ph ph-list-checks header-icon"></i>
        <span class="title">Todo</span>
        <span class="count">${items.length}</span>
      </div>
      ${items.length === 0
        ? `<div class="empty"><i class="ph ph-check-circle empty-icon"></i><div>All clear.</div></div>`
        : `<ul class="list">
            ${items
              .slice(0, visible)
              .map((item) => `<li><i class="ph ph-circle bullet"></i><span>${escapeHtml(item.text)}</span></li>`)
              .join("")}
            ${items.length > visible
              ? `<li class="more">+ ${items.length - visible} more</li>`
              : ""}
          </ul>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
