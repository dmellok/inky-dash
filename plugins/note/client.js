// Note — header strip + auto-scaling body. Uses theme tokens so it looks
// like the rest of the widget set; for a sticky-yellow look, override the
// cell's bg via the editor's per-cell colour overrides instead of hardcoding
// colours here.
//
// Wrapping text needs a binary search over font-size: a single measurement
// at a reference size doesn't tell us how wrapping will reflow at other sizes.

const MAX_PX = 220;
const MIN_PX = 8;
const SAFETY = 0.96;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fitWrapping(bodyEl, availW, availH) {
  if (!bodyEl || availW <= 0 || availH <= 0) return;
  let lo = MIN_PX;
  let hi = MAX_PX;
  let best = MIN_PX;
  for (let i = 0; i < 14; i++) {
    const mid = (lo + hi) / 2;
    bodyEl.style.fontSize = `${mid}px`;
    const w = bodyEl.scrollWidth;
    const h = bodyEl.scrollHeight;
    if (w <= availW && h <= availH) {
      best = mid;
      lo = mid;
    } else {
      hi = mid;
    }
  }
  bodyEl.style.fontSize = `${best * SAFETY}px`;
}

export default function render(host, ctx) {
  const opts = ctx.cell?.options || {};
  const text = String(opts.text ?? "");
  const title = String(opts.title ?? "").trim();
  const align = opts.align || "left";
  const weight = opts.weight || "500";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/note/client.css">
    <div class="note" style="--note-align: ${align}; --note-weight: ${weight};">
      <div class="head">
        <i class="ph ph-note head-icon"></i>
        <span class="head-title">NOTE</span>
        ${title ? `<span class="head-place">${escapeHtml(title)}</span>` : ""}
      </div>
      <div class="body">${escapeHtml(text)}</div>
    </div>
  `;

  const cell = host.host;
  const bodyEl = host.querySelector(".body");
  const headEl = host.querySelector(".head");

  function refit() {
    const cellW = cell.clientWidth;
    const cellH = cell.clientHeight;
    if (cellW === 0 || cellH === 0) return;
    const pad = Math.min(cellW, cellH) * 0.06;
    // Subtract the header's actual rendered height (if visible) from the
    // body's available area so the auto-fit doesn't over-allocate.
    const headH = headEl && getComputedStyle(headEl).display !== "none"
      ? headEl.offsetHeight + pad * 0.3
      : 0;
    fitWrapping(bodyEl, cellW - pad * 2, cellH - pad * 2 - headH);
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
