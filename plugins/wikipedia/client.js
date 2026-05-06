// Wikipedia featured article widget — title hero, lede paragraph, optional
// thumbnail. Mirrors the news-card visual idiom.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="wk error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const widthClass = W < 400 ? "w-xs" : W < 720 ? "w-sm" : "w-md";

  const hasImage = !!d.image;

  host.innerHTML = `
    <article class="wk ${sizeClass} ${widthClass} ${hasImage ? "with-img" : "no-img"}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-book-open"></i>
        <span class="label">FEATURED</span>
        <span class="meta">${escapeHtml(d.date_pretty || "")}</span>
      </header>` : ""}

      <div class="body">
        ${hasImage ? `<div class="img"><img src="${d.image}" alt=""></div>` : ""}
        <div class="text">
          <h1 class="title">${escapeHtml(d.title || "")}</h1>
          <p class="extract">${escapeHtml(d.extract || "")}</p>
        </div>
      </div>
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
