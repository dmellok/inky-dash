export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="apod-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  const imageOnly = !!ctx.options?.image_only;
  const showHeader = ctx.options?.show_header !== false;
  const bg = ctx.options?.bg || "cover";
  const head = showHeader ? `
    <header class="widget-head">
      <i class="ph ph-planet"></i>
      <span class="label">NASA APOD</span>
      ${d.date ? `<span class="meta">${escapeHtml(d.date)}</span>` : ""}
    </header>` : "";
  const imgEl = `<img class="apod-fg" alt="${escapeHtml(d.title || "")}" src="${d.img}">`;
  const blurEl = bg === "blurred" ? `<img class="apod-bg" aria-hidden="true" src="${d.img}">` : "";

  if (imageOnly) {
    host.innerHTML = `
      <div class="apod image-only bg-${bg}">
        ${blurEl}
        ${imgEl}
        ${head}
      </div>`;
    return;
  }
  host.innerHTML = `
    <div class="apod bg-${bg}">
      ${blurEl}
      <div class="img">${imgEl}</div>
      ${head}
      <div class="caption">
        <h3>${escapeHtml(d.title || "")}</h3>
        ${d.copyright ? `<p class="cred">© ${escapeHtml(d.copyright)}</p>` : ""}
      </div>
    </div>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
