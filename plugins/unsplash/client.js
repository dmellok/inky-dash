export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="us-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  // bg: cover/contain/blurred for image rendering, or white/black letterbox.
  const bg = ctx.options?.bg || "cover";
  const showHeader = ctx.options?.show_header !== false;
  host.innerHTML = `
    <div class="us bg-${bg}">
      ${bg === "blurred" ? `<img class="us-bg" aria-hidden="true" src="${d.img}">` : ""}
      <img alt="${escapeHtml(d.alt_description || "")}" src="${d.img}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-image"></i>
        <span class="label">Unsplash</span>
      </header>` : ""}
      <div class="credit">${escapeHtml(d.credit || "Unsplash")}</div>
    </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
