// Trakt watchlist → random poster.
//
// Server hands back a single resolved TMDB poster URL (already CDN-prefixed)
// plus title/year metadata. The user opted for poster-only — no overlay —
// so the cell is just the image plus a fallback empty state when something
// upstream is unconfigured/broken.

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;
  const scale = ctx.cell?.options?.scale || "fill";

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/trakt_watchlist/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="trakt empty">
        <i class="ph ph-film-slate"></i>
        <div class="message">${escapeHtml(error || "No poster available.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const safe = url.replace(/"/g, "&quot;");
  const alt = escapeHtml(
    data.title ? `${data.title}${data.year ? ` (${data.year})` : ""}` : "Trakt poster"
  );
  const body =
    scale === "blurred"
      ? `
        <img class="bg" src="${safe}" alt="" aria-hidden="true" />
        <img class="fg" src="${safe}" alt="${alt}" />
      `
      : `<img class="single" src="${safe}" alt="${alt}" />`;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/trakt_watchlist/client.css">
    <div class="trakt scale-${scale}">${body}</div>
  `;

  // Hold off the screenshot until the poster image has actually loaded.
  // Otherwise the panel push fires while the IMG element is still a
  // 0×0 placeholder and the cell goes out as a black square.
  const imgs = Array.from(host.querySelectorAll("img"));
  if (imgs.length === 0) {
    host.host.dataset.rendered = "true";
    return;
  }
  let pending = imgs.length;
  const done = () => {
    pending -= 1;
    if (pending <= 0) host.host.dataset.rendered = "true";
  };
  for (const img of imgs) {
    if (img.complete) done();
    else {
      img.addEventListener("load", done, { once: true });
      img.addEventListener("error", done, { once: true });
    }
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}
