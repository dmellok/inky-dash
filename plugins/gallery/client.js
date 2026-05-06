export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="gal-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  // bg: cover (default fills cell), contain (letterbox), or blurred (foreground
  // contained, blurred zoomed copy behind it). show_header toggles the floating
  // pill — useful when the cell is small or the image is the whole story.
  const bg = ctx.options?.bg || "cover";
  const showHeader = ctx.options?.show_header !== false;
  host.innerHTML = `
    <div class="gal-wrap bg-${bg}">
      ${bg === "blurred" ? `<img class="gal-bg" aria-hidden="true" src="${d.img}">` : ""}
      <img class="gal" alt="${escapeHtml(d.name || "")}" src="${d.img}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-images-square"></i>
        <span class="label">Gallery</span>
        ${d.name ? `<span class="meta">${escapeHtml(d.name)}</span>` : ""}
      </header>` : ""}
    </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
