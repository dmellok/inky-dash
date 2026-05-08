// Todo — render-only widget. Items are added/done/undone at /plugins/todo/.
// Server returns items pre-sorted: open (newest first) then completed
// (most-recent first). Completed items linger 24h then prune themselves.

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const VISIBLE_BY_SIZE = { xs: 3, sm: 6, md: 10, lg: 16 };

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const items = (ctx.data && ctx.data.items) || [];
  const visible = VISIBLE_BY_SIZE[size] ?? 8;

  const open = items.filter((i) => !i.completed_at);
  const done = items.filter((i) => i.completed_at);
  const total = items.length;
  const pct = total === 0 ? 0 : Math.round((done.length / total) * 100);

  const shown = items.slice(0, visible);
  const remaining = Math.max(0, items.length - shown.length);

  const itemRows = shown
    .map((item) => {
      const isDone = !!item.completed_at;
      const icon = isDone ? "ph-check-square-fill" : "ph-square";
      return `
        <li class="${isDone ? "done" : "open"}">
          <i class="ph ${icon} bullet"></i>
          <span class="text">${escapeHtml(item.text)}</span>
        </li>
      `;
    })
    .join("");

  const moreRow =
    remaining > 0
      ? `<li class="more">+${remaining} more</li>`
      : "";

  const body =
    items.length === 0
      ? `<div class="empty">
           <i class="ph ph-check-circle-fill empty-icon"></i>
           <div>All clear.</div>
         </div>`
      : `<ul class="list">${itemRows}${moreRow}</ul>`;

  const headerCount =
    total === 0
      ? ""
      : `<span class="count">${done.length}<span class="count-sep">/</span>${total}</span>`;

  const progressBar =
    total > 0 && size !== "xs"
      ? `<div class="progress" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
           <div class="progress-fill" style="width: ${pct}%"></div>
         </div>`
      : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/todo/client.css">
    <div class="todo todo--${size}">
      <div class="header">
        <i class="ph ph-list-checks header-icon"></i>
        <span class="title">Todo</span>
        ${headerCount}
      </div>
      ${progressBar}
      ${body}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
