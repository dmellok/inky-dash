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

function fitWrapping(bodyEl, availH) {
  if (!bodyEl || availH <= 0) return;
  // Width-fit happens for free: the body has ``width: 100%`` of its
  // padded grid cell, and ``word-break: break-word`` means even
  // unbreakable strings wrap at that width. So bodyEl.scrollWidth
  // collapses to bodyEl.clientWidth at every font size — there's no
  // useful width comparison to make. Earlier versions of this function
  // computed an availW from cell.clientWidth - hand-rolled pad, came
  // out tighter than the body's actual CSS-imposed width, and the
  // ``scrollWidth <= availW`` check failed at every size → the binary
  // search silently fell back to MIN_PX and the body rendered at ~8px.
  // Just fit by height.
  let lo = MIN_PX;
  let hi = MAX_PX;
  let best = MIN_PX;
  for (let i = 0; i < 14; i++) {
    const mid = (lo + hi) / 2;
    bodyEl.style.fontSize = `${mid}px`;
    if (bodyEl.scrollHeight <= availH) {
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
    <link rel="stylesheet" href="/static/style/widget-base.css">
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
    if (cell.clientWidth === 0 || cell.clientHeight === 0) return;
    // Read the actual CSS padding + row gap off ``.note`` so we don't
    // double-count them. The body's available height is whatever's left
    // of the note's content box after the head row + the row gap.
    const noteEl = bodyEl.parentElement;
    if (!noteEl) return;
    const cs = getComputedStyle(noteEl);
    const padT = parseFloat(cs.paddingTop) || 0;
    const padB = parseFloat(cs.paddingBottom) || 0;
    const gap = parseFloat(cs.rowGap || cs.gap) || 0;
    const headVisible =
      headEl && getComputedStyle(headEl).display !== "none";
    const headH = headVisible ? headEl.offsetHeight : 0;
    const availH =
      cell.clientHeight - padT - padB - headH - (headVisible ? gap : 0);
    fitWrapping(bodyEl, availH);
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
