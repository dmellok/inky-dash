// Sun clock widget — 24-hour polar ring built as a Chart.js doughnut.
// Segments: night → civil dawn → daylight → civil dusk → night, plus
// a thin cursor line showing "now" overlaid on top.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="sc error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  // Order around the day: 0h → 24h. Build segment widths in hours.
  const dawn = num(d.dawn_h, d.sunrise_h - 0.5);
  const sunrise = num(d.sunrise_h, 6);
  const sunset = num(d.sunset_h, 18);
  const dusk = num(d.dusk_h, sunset + 0.5);
  const segments = [
    Math.max(0, dawn),                     // pre-dawn night
    Math.max(0, sunrise - dawn),           // civil dawn
    Math.max(0, sunset - sunrise),         // daylight
    Math.max(0, dusk - sunset),            // civil dusk
    Math.max(0, 24 - dusk),                // post-dusk night
  ];
  const nowHour = clamp(num(d.now_hour, 0), 0, 23.999);

  host.innerHTML = `
    <article class="sc ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-sun"></i>
        <span class="label">SUN CLOCK</span>
        <span class="meta">${escapeHtml(d.place || "")}</span>
      </header>` : ""}

      <div class="dial-wrap">
        <canvas class="dial"></canvas>
        <div class="dial-center">
          <span class="num">${escapeHtml(d.day_length || "")}</span>
          <span class="lbl">daylight</span>
        </div>
        <span class="cursor" style="--ang: ${(nowHour / 24 * 360).toFixed(2)}deg" aria-hidden="true"></span>
        <span class="hour-label hr-0">00</span>
        <span class="hour-label hr-6">06</span>
        <span class="hour-label hr-12">12</span>
        <span class="hour-label hr-18">18</span>
      </div>

      <div class="legend">
        <div class="leg"><span class="dot dot-rise"></span>Sunrise<span class="v">${escapeHtml(d.sunrise || "—")}</span></div>
        <div class="leg"><span class="dot dot-set"></span>Sunset<span class="v">${escapeHtml(d.sunset || "—")}</span></div>
      </div>
    </article>
  `;

  try {
    const Chart = await loadChart();
    const styles = getComputedStyle(host.host || host);
    const accent = styles.getPropertyValue("--theme-accent").trim() || "#666";
    const surface2 = styles.getPropertyValue("--theme-surface-2").trim() || "#eee";
    const muted = styles.getPropertyValue("--theme-muted").trim() || "#888";
    // Daylight = accent; civil twilight = mid-tone between accent and
    // muted; night = surface-2 (the deeper-tonal token in dark themes).
    const twilight = `color-mix(in srgb, ${accent} 50%, ${muted})`;
    const canvas = host.querySelector("canvas.dial");
    if (!canvas) return;
    new Chart(canvas, {
      type: "doughnut",
      data: {
        datasets: [{
          data: segments,
          backgroundColor: [surface2, twilight, accent, twilight, surface2],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "70%",
        rotation: -180,           // 0:00 at the top
        circumference: 360,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: false,
      },
    });
  } catch (err) {
    console.warn("[sun_clock] dial failed:", err);
  }
}

function num(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}
function clamp(n, lo, hi) {
  return Math.max(lo, Math.min(hi, n));
}
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
