// Year progress — day-of-year number + 52-week ribbon.

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
    /* */
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

function isLeap(y) {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function dayOfYear(d) {
  const start = new Date(d.getFullYear(), 0, 0);
  return Math.floor((d - start) / 86_400_000);
}

export default async function render(host, ctx) {
  const { size } = ctx.cell;
  const showRibbon = size !== "sm";
  const showStats = size === "lg";

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/year_progress/client.css">
    <div class="yp yp--${size}">
      <div class="hero">
        <span class="day"></span>
        <span class="of">of</span>
        <span class="total"></span>
      </div>
      <div class="pct"></div>
      ${showRibbon ? `<div class="ribbon"></div>` : ""}
      ${showStats ? `<div class="stats"></div>` : ""}
    </div>
  `;

  const dayEl = host.querySelector(".day");
  const totalEl = host.querySelector(".total");
  const pctEl = host.querySelector(".pct");
  const ribbonEl = host.querySelector(".ribbon");
  const statsEl = host.querySelector(".stats");
  const heroEl = host.querySelector(".hero");
  const cell = host.host;

  function buildRibbon(currentWeek) {
    if (!ribbonEl) return;
    ribbonEl.innerHTML = "";
    for (let i = 0; i < 52; i++) {
      const seg = document.createElement("span");
      seg.className = "seg" + (i < currentWeek ? " filled" : "");
      ribbonEl.appendChild(seg);
    }
  }

  function refit() {
    const cellW = cell.clientWidth;
    const cellH = cell.clientHeight;
    if (cellW === 0 || cellH === 0) return;
    const padding = Math.min(cellW, cellH) * 0.06;
    const availW = cellW - padding * 2;
    const heroH = cellH * (showRibbon ? 0.45 : 0.7);
    fitText(heroEl, availW, heroH);
    if (pctEl)
      pctEl.style.fontSize = `${Math.min(cellW * 0.05, cellH * 0.07)}px`;
    if (statsEl)
      statsEl.style.fontSize = `${Math.min(cellW * 0.04, cellH * 0.06)}px`;
  }

  function tick() {
    const now = new Date();
    const total = isLeap(now.getFullYear()) ? 366 : 365;
    const day = dayOfYear(now);
    const week = Math.min(52, Math.floor((day - 1) / 7) + 1);
    const pct = (day / total) * 100;

    dayEl.textContent = String(day);
    totalEl.textContent = String(total);
    pctEl.textContent = `${pct.toFixed(1)}% of ${now.getFullYear()}`;
    buildRibbon(week);
    if (statsEl) {
      const remaining = total - day;
      statsEl.textContent = `Week ${week} of 52 · ${remaining} days remaining`;
    }
    refit();
  }

  await ensureFontLoaded(cell);
  tick();

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
