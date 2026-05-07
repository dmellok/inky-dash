// Gallery — display one image full-bleed.

export default function render(host, ctx) {
  const { data } = ctx;
  const url = data && data.url;
  const error = data && data.error;

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

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/gallery/client.css">
    <div class="gallery">
      <img src="${url}" alt="" />
    </div>
  `;

  // Mark rendered after the image loads (or fails) so the screenshot waits.
  const img = host.querySelector("img");
  if (img.complete) {
    host.host.dataset.rendered = "true";
  } else {
    const done = () => (host.host.dataset.rendered = "true");
    img.addEventListener("load", done, { once: true });
    img.addEventListener("error", done, { once: true });
  }
}
