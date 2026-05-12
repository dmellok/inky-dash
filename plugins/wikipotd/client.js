// Wikimedia Picture of the Day — server returns a resolved image URL +
// title + artist string. Layout mirrors APOD: optional caption overlay
// with a gradient mat, scale switchable between fit / fill / stretch /
// blurred-fit.

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;
  const showCaption = ctx.cell?.options?.show_caption !== false;
  const scale = ctx.cell?.options?.scale || "fit";

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/wikipotd/client.css">
      <div class="wpotd empty">
        <i class="ph ph-camera-slash"></i>
        <div class="message">${error || "No image available."}</div>
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
        <img class="fg" src="${safe}" alt="${escapeHtml(data.title || "POTD")}" />
      `
      : `<img class="single" src="${safe}" alt="${escapeHtml(data.title || "POTD")}" />`;

  const captionParts = [];
  if (data.title) captionParts.push(escapeHtml(data.title));
  if (data.artist) captionParts.push(`© ${escapeHtml(data.artist)}`);
  else if (data.date) captionParts.push(escapeHtml(data.date));

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/wikipotd/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="wpotd scale-${scale}">
      ${body}
      ${showCaption && captionParts.length
        ? `<div class="caption">${captionParts.join(" · ")}</div>`
        : ""}
    </div>
  `;

  // Hold off marking as rendered until every image has resolved — otherwise
  // the screenshot can fire mid-load and capture a blank cell.
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
