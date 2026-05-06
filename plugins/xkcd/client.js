export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="xkcd error"><p>${escapeHtml(d.error)}</p></div>`;
    return;
  }
  const W = ctx.width || 800, H = ctx.height || 480;
  // Progressive disclosure: priority comic > title chip > alt text caption.
  const showHeader = H >= 200 && W >= 320;
  const showAlt    = H >= 480;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  host.innerHTML = `
    <article class="xkcd ${sizeClass}">
      <header class="widget-head">
        <i class="ph ph-image-square"></i>
        <span class="label">XKCD</span>
        ${d.num ? `<span class="num">#${d.num}</span>` : ""}
      </header>
      ${showHeader ? `
      <header class="title-row">
        <h1 class="title">${escapeHtml(d.title || "")}</h1>
      </header>` : ""}
      <div class="comic-wrap">
        <div class="comic-stack">
          <figure>
            <img alt="${escapeHtml(d.alt || "")}" src="${d.img}">
          </figure>
          ${showAlt && d.alt ? `<p class="alt">${escapeHtml(d.alt)}</p>` : ""}
        </div>
      </div>
    </article>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
