// Todo — render-only widget. Items are added/done/undone at /plugins/todo/.
// Server returns items pre-sorted: open (newest first) then completed
// (most-recent first). Completed items linger 24h then prune themselves.
//
// Layout matches the design screenshot:
//   - Header: "TASKS LEFT" caps + big open-count / total
//   - Filled accent progress bar (only when there are tasks AND some progress)
//   - List of tasks: open with hollow circle, completed with filled circle +
//     strikethrough text + JUST DONE badge (within ~10 min of completion)

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

const VISIBLE_BY_SIZE = { xs: 3, sm: 6, md: 10, lg: 16 };
const JUST_DONE_WINDOW_S = 10 * 60;

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const items = (ctx.data && ctx.data.items) || [];
  const visible = VISIBLE_BY_SIZE[size] ?? 8;

  const open = items.filter((i) => !i.completed_at);
  const done = items.filter((i) => i.completed_at);
  const total = items.length;
  const openCount = open.length;
  const pct = total === 0 ? 0 : (done.length / total) * 100;
  const nowS = Date.now() / 1000;

  const shown = items.slice(0, visible);
  const remaining = Math.max(0, items.length - shown.length);

  const itemRows = shown
    .map((item) => {
      const isDone = !!item.completed_at;
      const icon = isDone ? "ph-check-circle-fill" : "ph-circle";
      const justDone = isDone && (nowS - item.completed_at) < JUST_DONE_WINDOW_S;
      return `
        <li class="${isDone ? "done" : "open"}">
          <i class="ph ${icon} bullet"></i>
          <span class="text">${escapeHtml(item.text)}</span>
          ${justDone ? `<span class="badge">JUST DONE</span>` : ""}
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

  // Show progress bar only when there's work AND some of it is done — an
  // empty/full bar adds visual weight without information.
  const showProgress = total > 0 && done.length > 0 && done.length < total && size !== "xs";
  const progress = showProgress
    ? `<div class="progress" role="progressbar" aria-valuenow="${pct.toFixed(0)}" aria-valuemin="0" aria-valuemax="100">
         <div class="progress-fill" style="width: ${pct.toFixed(2)}%;"></div>
       </div>`
    : "";

  const headerCount =
    total === 0
      ? ""
      : `<span class="count">
           <span class="count-num">${openCount}</span><span class="count-total">/${total}</span>
         </span>`;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/todo/client.css">
    <div class="todo todo--${size}">
      <div class="header">
        <i class="ph ph-list-checks header-icon"></i>
        <span class="title">TASKS LEFT</span>
        ${headerCount}
      </div>
      ${progress}
      ${body}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
