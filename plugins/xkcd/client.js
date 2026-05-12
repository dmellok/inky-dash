export default function render(host, ctx) {
  const data = ctx.data || {};
  const showTitle = ctx.cell?.options?.show_title !== false;

  if (data.error || !data.img) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/xkcd/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="xkcd error">
        <i class="ph ph-smiley-meh"></i>
        <div class="message">${escapeHtml(data.error || "No comic loaded.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const safeImg = data.img.replace(/"/g, "&quot;");
  const titleBar = showTitle
    ? `
        <div class="title">
          <span class="num">#${data.num}</span>
          <span class="name">${escapeHtml(data.title)}</span>
          <span class="date">${escapeHtml(data.date || "")}</span>
        </div>
      `
    : "";

  const altText = (data.alt || "").trim();
  const altBar = altText
    ? `<div class="alt">${escapeHtml(altText)}</div>`
    : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/xkcd/client.css">
    <div class="xkcd${altText ? " has-alt" : ""}">
      ${titleBar}
      <div class="frame">
        <img src="${safeImg}" alt="${escapeHtml(data.alt || data.title)}" />
      </div>
      ${altBar}
    </div>
  `;

  const img = host.querySelector("img");
  const done = () => (host.host.dataset.rendered = "true");
  if (img.complete) done();
  else {
    img.addEventListener("load", done, { once: true });
    img.addEventListener("error", done, { once: true });
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
