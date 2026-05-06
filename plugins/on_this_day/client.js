// On this day widget — Wikipedia OTD feed. Hero year + headline event,
// then 3-4 supporting bullets. Optional thumbnail.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="otd error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const widthClass = W < 480 ? "w-xs" : W < 800 ? "w-sm" : "w-md";

  const hero = d.hero || {};
  const rest = (d.rest || []).slice(0, sizeClass === "h-xs" ? 0 : sizeClass === "h-sm" ? 2 : 5);
  const hasImage = !!d.image;

  host.innerHTML = `
    <article class="otd ${sizeClass} ${widthClass} ${hasImage ? 'with-img' : 'no-img'}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-clock-counter-clockwise"></i>
        <span class="label">ON THIS DAY</span>
        <span class="meta">${escapeHtml(d.date_pretty || "")}</span>
      </header>` : ""}

      <div class="hero">
        ${hasImage ? `<div class="img"><img src="${d.image}" alt=""></div>` : ""}
        <div class="hero-text">
          ${hero.year ? `<div class="year">${hero.year}</div>` : ""}
          <p class="text">${escapeHtml(hero.text || "")}</p>
        </div>
      </div>

      ${rest.length ? `
      <ul class="rest">
        ${rest.map((e) => `
          <li>
            ${e.year ? `<span class="year">${e.year}</span>` : ""}
            <span class="text">${escapeHtml(e.text || "")}</span>
          </li>
        `).join("")}
      </ul>` : ""}
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
