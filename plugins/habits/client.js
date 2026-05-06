// Habits widget — 26-week contribution grid for one habit.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="hb error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const grid = Array.isArray(d.grid) ? d.grid : [];

  // Build the grid as a CSS grid: 7 rows × N columns. Each cell is a
  // <span> with classes that the CSS hooks ("done", "today", "future").
  const today = d.today_iso;
  const cells = [];
  for (let row = 0; row < 7; row++) {
    for (let col = 0; col < grid.length; col++) {
      const c = grid[col][row];
      const cls = [
        "cell",
        c.done ? "done" : "",
        c.iso === today ? "today" : "",
        c.future ? "future" : "",
      ].filter(Boolean).join(" ");
      cells.push(`<span class="${cls}" style="grid-column:${col + 1}; grid-row:${row + 1}" title="${c.iso}"></span>`);
    }
  }

  host.innerHTML = `
    <article class="hb ${sizeClass} color-${escapeHtml(d.color || "accent")}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ${escapeHtml(d.icon || "ph-check-square")}"></i>
        <span class="label">${escapeHtml((d.name || "HABIT").toUpperCase())}</span>
        <span class="meta">${d.weeks ?? 26}w</span>
      </header>` : ""}

      <div class="hero">
        <div class="hero-block">
          <span class="num">${d.streak ?? 0}</span>
          <span class="lbl">day streak</span>
        </div>
        <div class="meta-block">
          <div class="m"><span class="k">BEST</span><span class="v">${d.best ?? 0}</span></div>
          <div class="m"><span class="k">30D</span><span class="v">${d.last_30 ?? 0}</span></div>
          <div class="m"><span class="k">TOTAL</span><span class="v">${d.total ?? 0}</span></div>
        </div>
      </div>

      <div class="grid" aria-hidden="true">${cells.join("")}</div>
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
