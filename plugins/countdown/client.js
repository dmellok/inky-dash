// Countdown — days until / since a target date.

const REFERENCE_PX = 200;

async function ensureFontLoaded(cell) {
  if (!document.fonts || !document.fonts.load) return;
  const family = (getComputedStyle(cell).fontFamily || "")
    .split(",")[0]
    .trim()
    .replace(/^['"]|['"]$/g, "");
  if (!family) return;
  try {
    await Promise.all([
      document.fonts.load(`700 100px "${family}"`),
      document.fonts.load(`500 100px "${family}"`),
    ]);
  } catch {
    /* fall through */
  }
}

function fitText(el, availW, availH) {
  if (!el || availW <= 0 || availH <= 0) return;
  el.style.fontSize = `${REFERENCE_PX}px`;
  const w = el.scrollWidth;
  const h = el.scrollHeight;
  if (w === 0 || h === 0) return;
  el.style.fontSize = `${REFERENCE_PX * Math.min(availW / w, availH / h) * 0.94}px`;
}

function diffDays(target) {
  const now = new Date();
  const t = new Date(target);
  // Normalise to local midnight on both sides.
  const a = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const b = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  return Math.round((b - a) / 86_400_000);
}

export default async function render(host, ctx) {
  const { size, options } = ctx.cell;
  const target = options.target_date || "2026-12-31";
  const userLabel = options.label || "Until";

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/countdown/client.css">
    <div class="countdown countdown--${size}">
      <div class="big"></div>
      <div class="unit">days</div>
      <div class="label"></div>
    </div>
  `;

  const bigEl = host.querySelector(".big");
  const unitEl = host.querySelector(".unit");
  const labelEl = host.querySelector(".label");
  const cell = host.host;

  function refit() {
    const cellW = cell.clientWidth;
    const cellH = cell.clientHeight;
    if (cellW === 0 || cellH === 0) return;
    const padding = Math.min(cellW, cellH) * 0.06;
    const availW = cellW - padding * 2;
    const availH = cellH - padding * 2;
    fitText(bigEl, availW, availH * 0.62);
    if (unitEl) unitEl.style.fontSize = `${Math.min(cellW * 0.07, cellH * 0.12)}px`;
    if (labelEl) labelEl.style.fontSize = `${Math.min(cellW * 0.06, cellH * 0.1)}px`;
  }

  function tick() {
    const days = diffDays(target);
    const absolute = Math.abs(days);
    let labelText;
    if (days > 0) labelText = `${userLabel} ${target}`;
    else if (days < 0) labelText = `Since ${target}`;
    else labelText = `Today is ${target}`;
    bigEl.textContent = String(absolute);
    if (unitEl) unitEl.textContent = absolute === 1 ? "day" : "days";
    if (labelEl) labelEl.textContent = labelText;
    refit();
  }

  await ensureFontLoaded(cell);
  tick();

  // Tick once an hour — days only flip at midnight.
  const interval = setInterval(tick, 3600 * 1000);
  const observer = new ResizeObserver(refit);
  observer.observe(cell);

  host.__inkyCleanup = () => {
    clearInterval(interval);
    observer.disconnect();
  };

  host.host.dataset.rendered = "true";
}

export function cleanup(host) {
  if (host.__inkyCleanup) host.__inkyCleanup();
}
