export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="news-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  const items = d.items || [];
  if (!items.length) {
    host.innerHTML = `<div class="news-error">no items</div>`;
    return;
  }
  const W = ctx.width || 600, H = ctx.height || 400;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 380 ? "h-sm" :
    H < 700 ? "h-md" :
    H < 1100 ? "h-lg" : "h-xl";

  // Cap the list by tier — at small sizes only the highlighted lead reads.
  const cap = sizeClass === "h-xs" ? 1
            : sizeClass === "h-sm" ? 2
            : sizeClass === "h-md" ? 4
            : sizeClass === "h-lg" ? 6
            : 10;

  // Reorder so the highlighted item is always first (it's the lead card).
  const hi = Number.isInteger(d.highlighted_index) ? d.highlighted_index : -1;
  let ordered = items.slice();
  if (hi >= 0 && hi < ordered.length) {
    const lead = ordered.splice(hi, 1)[0];
    ordered = [lead, ...ordered];
  }
  const visible = ordered.slice(0, cap);
  const hasLead = hi >= 0;

  const showHead = sizeClass !== "h-xs";

  host.innerHTML = `
    <div class="news-wrap ${sizeClass}">
      ${showHead ? `
      <header class="widget-head">
        <i class="ph ph-newspaper-clipping"></i>
        <span class="label">News</span>
        <span class="meta">${visible.length} story${visible.length === 1 ? "" : "ies"}</span>
      </header>` : ""}
    <ul class="news">
      ${visible.map((it, i) => `
        <li class="article ${i === 0 && hasLead ? "highlight" : ""}">
          <span class="bar" aria-hidden="true"></span>
          <div class="body">
            <h3 class="t">${escapeHtml(it.title)}</h3>
            ${it.summary ? `<p class="s">${escapeHtml(it.summary)}</p>` : ""}
            <p class="m">
              ${it.author ? `<span class="author">${escapeHtml(it.author)}</span>` : ""}
              ${it.author && it.published ? `<span class="sep">·</span>` : ""}
              ${it.published ? `<time>${escapeHtml(formatPub(it.published))}</time>` : ""}
            </p>
          </div>
        </li>`).join("")}
    </ul>
    </div>`;
}

function formatPub(s) {
  // RFC 2822 / ISO — let Date parse.
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return s;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
