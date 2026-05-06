export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="age-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  // bg: cover (default fills cell), contain (letterbox), or blurred (foreground
  // contained, blurred zoomed copy behind it). show_header toggles the floating
  // pill — useful when the cell is small or the image is the whole story.
  const bg = ctx.options?.bg || "cover";
  const showHeader = ctx.options?.show_header !== false;
  host.innerHTML = `
    <div class="age-wrap bg-${bg}">
      ${bg === "blurred" ? `<img class="age-bg" aria-hidden="true" src="${d.img}">` : ""}
      <img class="age" alt="The Age front page" src="${d.img}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-newspaper"></i>
        <span class="label">The Age</span>
        <span class="meta">Front page</span>
      </header>` : ""}
    </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
