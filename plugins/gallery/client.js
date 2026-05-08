// Gallery — display one image full-bleed, with user-chosen scaling.
//
// Scale modes (from cell.options.scale):
//   fit      — letterboxed (object-fit: contain)
//   fill     — fill the cell, may crop (object-fit: cover)
//   stretch  — distort to fill (object-fit: fill)
//   center   — original size, no scaling, centered
//   blurred  — fit + a zoomed/blurred copy as the background

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;
  const scale = (ctx.cell && ctx.cell.options && ctx.cell.options.scale) || "fit";

  if (!url) {
    host.innerHTML = `
      <link rel="stylesheet" href="/plugins/gallery/client.css">
      <div class="gallery empty">
        <div class="message">${error || "No image."}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const escaped = url.replace(/"/g, "&quot;");
  // For "blurred" we layer two <img>s: a zoomed/blurred backdrop + a fit
  // foreground. For every other mode, one <img> is enough — CSS class
  // picks the object-fit value.
  const body =
    scale === "blurred"
      ? `
        <img class="bg" src="${escaped}" alt="" aria-hidden="true" />
        <img class="fg" src="${escaped}" alt="" />
      `
      : `<img class="single" src="${escaped}" alt="" />`;

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/gallery/client.css">
    <div class="gallery scale-${scale}">
      ${body}
    </div>
  `;

  // Mark rendered after every <img> has finished loading (or errored) so
  // the screenshot doesn't fire mid-load and skip the blurred backdrop.
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
