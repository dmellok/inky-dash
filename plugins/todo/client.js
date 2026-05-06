export default async function render(host, ctx) {
  const items = ctx.data?.items || [];
  const now = ctx.data?.now ? new Date(ctx.data.now) : new Date();
  const style = ctx.data?.style || "stacked";
  const W = ctx.width || 600, H = ctx.height || 400;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 400 ? "h-sm" :
    H < 700 ? "h-md" :
    H < 1100 ? "h-lg" : "h-xl";
  const compact = H < 240 || W < 280;

  if (!items.length) {
    host.innerHTML = `
      <div class="todo ${sizeClass}">
        <div class="todo-empty">
          <p class="lead">All clear</p>
          <p class="sub">Nothing to do.</p>
        </div>
      </div>`;
    return;
  }

  // Cap items by tier so smaller cells aren't overflowing — show pending
  // items first (most actionable), then recently-completed if room.
  const sorted = [...items].sort((a, b) => Number(!!a.completed) - Number(!!b.completed));
  const cap = sizeClass === "h-xs" ? 2
            : sizeClass === "h-sm" ? 4
            : sizeClass === "h-md" ? 8
            : 100;
  const visible = sorted.slice(0, cap);
  const overflow = sorted.length - visible.length;

  // Progress stats — drives the header chip + progress bar.
  const total = items.length;
  const done  = items.filter((it) => it.completed).length;
  const pending = total - done;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const bigItems = sizeClass === "h-lg" || sizeClass === "h-xl";
  const fewItems = visible.length <= 3 && bigItems;

  const itemsHtml = visible.map((it) => {
    const fresh = isRecentlyCompleted(it, now);
    const cls = [
      "todo-item",
      it.completed ? "completed" : "",
      fresh ? "fresh" : "",
    ].filter(Boolean).join(" ");
    return `
      <li class="${cls}">
        <span class="dot"></span>
        <span class="text">${escapeHtml(it.text)}</span>
        ${fresh ? `<span class="badge">Just done</span>` : ""}
      </li>`;
  }).join("");

  // Pending count gets the punchy display number; muted "of N" reads underneath.
  const showHead = sizeClass !== "h-xs";

  host.innerHTML = `
    <div class="todo todo-${style} ${sizeClass} ${compact ? "compact" : ""} ${fewItems ? "few" : ""}">
      ${showHead ? `
      <header class="todo-head">
        <div class="head-row">
          <div class="lead">
            <i class="ph ph-list-checks"></i>
            <span class="eyebrow">Tasks${total === done ? "" : " left"}</span>
          </div>
          <span class="ratio">
            <span class="big">${pending}</span><span class="of">/${total}</span>
          </span>
        </div>
        <div class="progress" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100">
          <div class="fill" style="width: ${pct}%"></div>
        </div>
      </header>` : ""}
      <ol class="todo-list">${itemsHtml}</ol>
      ${overflow > 0 ? `<p class="overflow">+${overflow} more</p>` : ""}
    </div>`;
}

function isRecentlyCompleted(item, now) {
  if (!item.completed || !item.completed_at) return false;
  try {
    const t = new Date(item.completed_at.replace(/Z$/, "+00:00"));
    return (now - t) < 60 * 60 * 1000;  // last hour
  } catch (_) {
    return false;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
