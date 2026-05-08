// Sticky note — wraps user-supplied text and auto-scales to fill the cell.
// Wrapping text needs a binary search over font-size: a single measurement
// at a reference size doesn't tell us how wrapping will reflow at other sizes.

const MAX_PX = 220;
const MIN_PX = 8;
const SAFETY = 0.96;

function fitWrapping(container, body, title, availW, availH) {
  if (availW <= 0 || availH <= 0) return;

  // Binary search for the largest font-size that keeps body+title within bounds.
  let lo = MIN_PX;
  let hi = MAX_PX;
  let best = MIN_PX;

  for (let i = 0; i < 14; i++) {
    const mid = (lo + hi) / 2;
    body.style.fontSize = `${mid}px`;
    if (title) title.style.fontSize = `${mid * 0.55}px`;

    const w = container.scrollWidth;
    const h = container.scrollHeight;

    if (w <= availW && h <= availH) {
      best = mid;
      lo = mid;
    } else {
      hi = mid;
    }
  }

  const final = best * SAFETY;
  body.style.fontSize = `${final}px`;
  if (title) title.style.fontSize = `${final * 0.55}px`;
}

export default function render(host, ctx) {
  const opts = ctx.cell?.options || {};
  const text = String(opts.text ?? "");
  const title = String(opts.title ?? "").trim();
  const align = opts.align || "center";
  const weight = opts.weight || "600";
  const bg = opts.bg_color || "#fff8b0";
  const fg = opts.fg_color || "#1a1612";

  const escape = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/note/client.css">
    <div class="note" style="--note-bg: ${bg}; --note-fg: ${fg}; --note-align: ${align}; --note-weight: ${weight};">
      <div class="inner">
        ${title ? `<div class="title">${escape(title)}</div>` : ""}
        <div class="body">${escape(text)}</div>
      </div>
    </div>
  `;

  const cell = host.host;
  const inner = host.querySelector(".inner");
  const titleEl = host.querySelector(".title");
  const bodyEl = host.querySelector(".body");

  function refit() {
    const cellW = cell.clientWidth;
    const cellH = cell.clientHeight;
    if (cellW === 0 || cellH === 0) return;
    const pad = Math.min(cellW, cellH) * 0.06;
    fitWrapping(inner, bodyEl, titleEl, cellW - pad * 2, cellH - pad * 2);
  }

  refit();

  const observer = new ResizeObserver(refit);
  observer.observe(cell);

  host.__inkyCleanup = () => observer.disconnect();
  host.host.dataset.rendered = "true";
}

export function cleanup(host) {
  if (host.__inkyCleanup) host.__inkyCleanup();
}
