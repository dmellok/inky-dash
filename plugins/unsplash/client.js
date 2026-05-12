// Unsplash random-photo widget. Server already chose a photo + tracked
// the required download endpoint; client just renders it with the user's
// scale + credit preferences.

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;
  const showCredit = ctx.cell?.options?.show_credit !== false;
  const scale = ctx.cell?.options?.scale || "fill";

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/unsplash/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="usp empty">
        <i class="ph ph-camera"></i>
        <div class="message">${error || "No photo loaded."}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const safe = url.replace(/"/g, "&quot;");
  const alt = escapeHtml(data.alt || "Unsplash photo");
  const body =
    scale === "blurred"
      ? `
        <img class="bg" src="${safe}" alt="" aria-hidden="true" />
        <img class="fg" src="${safe}" alt="${alt}" />
      `
      : `<img class="single" src="${safe}" alt="${alt}" />`;

  let credit = "";
  if (showCredit && data.credit_name) {
    credit = `<div class="credit">📷 ${escapeHtml(data.credit_name)} · Unsplash</div>`;
  }

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/unsplash/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="usp scale-${scale}">
      ${body}
      ${credit}
    </div>
  `;

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
