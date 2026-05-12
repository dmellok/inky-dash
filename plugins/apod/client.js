// NASA APOD — Astronomy Picture of the Day. Server hands back a single
// resolved image URL (after walking back past any video entries) plus
// title/date metadata.

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;
  const showCaption =
    ctx.cell?.options?.show_caption !== false; // default on
  const scale = ctx.cell?.options?.scale || "fit";

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/apod/client.css">
      <div class="apod empty">
        <i class="ph ph-planet"></i>
        <div class="message">${error || "No APOD image."}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const safe = url.replace(/"/g, "&quot;");
  const body =
    scale === "blurred"
      ? `
        <img class="bg" src="${safe}" alt="" aria-hidden="true" />
        <img class="fg" src="${safe}" alt="${escapeHtml(data.title || "APOD")}" />
      `
      : `<img class="single" src="${safe}" alt="${escapeHtml(data.title || "APOD")}" />`;

  const captionParts = [];
  if (data.title) captionParts.push(escapeHtml(data.title));
  if (data.copyright) captionParts.push(`© ${escapeHtml(data.copyright)}`);
  else if (data.date) captionParts.push(escapeHtml(data.date));

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/apod/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="apod scale-${scale}">
      ${body}
      ${showCaption && captionParts.length
        ? `<div class="caption">${captionParts.join(" · ")}</div>`
        : ""}
    </div>
  `;

  // Wait for every <img> so the screenshot doesn't fire mid-load.
  const imgs = Array.from(host.querySelectorAll("img"));
  let pending = imgs.length;
  if (pending === 0) {
    host.host.dataset.rendered = "true";
    return;
  }
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
