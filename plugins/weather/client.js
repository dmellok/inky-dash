// Weather widget — Material-style dashboard with a Chart.js hourly curve
// and gradient daily bars. Chart.js itself lives in the shared vendor
// bundle at /static/vendor/chartjs/, so any plugin can import the loader
// without each plugin re-vendoring the library.
import { loadChart } from "/static/vendor/chartjs/loader.js";

export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="wx-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  // Progressive disclosure — hide the lowest-priority blocks first as the
  // cell shrinks. Priority (high→low): hero, top bar, stats, hourly chart,
  // daily forecast. Thresholds align with the CSS tier classes below.
  const W = ctx.width || 800, H = ctx.height || 480;
  const cellSize =
    H < 240 ? "h-xs" :
    H < 480 ? "h-sm" :
    H < 800 ? "h-md" :
    H < 1200 ? "h-lg" : "h-xl";
  const widthSize = W < 360 ? "w-xs" : W < 640 ? "w-sm" : "w-md";
  const sizeClasses = [cellSize, widthSize].join(" ");
  // Render gates (skip the work entirely when below a tier — saves the
  // chart.js init cost when the chart wouldn't be visible anyway).
  const showTop    = H >= 240 && W >= 320;   // h-sm and up
  const showStats  = H >= 480;               // h-md and up
  // The hourly chart is a horizontal element — at h-lg+ we always have
  // room, but stack_3 cells on a portrait panel land in h-md with plenty
  // of width to spare, so unlock it there too.
  const showHourly = H >= 800 || (H >= 480 && W >= 640);
  const showDaily  = H >= 1200;              // h-xl
  // The page panel-header (multi-cell pages) already shows a clock — don't
  // duplicate it inside the widget's top bar.
  const showClock  = !ctx.has_page_header;

  const compact = !!ctx.options?.compact || H < 360;
  const c = d.current || {};
  const sunTimes = formatSunTimes(d.sunrise, d.sunset);
  const loc = `${d.location || ""}${d.country ? ", " + d.country : ""}`;

  // --- Hero, metrics, daily are always built; chart only in non-compact. ---
  const hourly = d.hourly || [];
  const daily  = d.daily  || [];

  // Stat priority — at narrow widths only the most essential 2 stats fit.
  // Order by usefulness for "what to do today": rain → wind → UV → humid.
  const allStats = [
    sunTimes ? { klass:"sunrise", icon:iconFor(d,"sunrise","ph-sun-horizon"), key:"Sunrise", val: sunTimes.rise } : null,
    sunTimes ? { klass:"sunset",  icon:iconFor(d,"sunset","ph-moon"),         key:"Sunset",  val: sunTimes.set  } : null,
    { klass:"uv",    icon:iconFor(d,"uv","ph-sun"),         key:"UV index",   val: fmtUv(d.uv_index_max ?? c.uv_index) },
    { klass:"rain",  icon:iconFor(d,"rain","ph-umbrella"),  key:"Rain today", val: d.rain_today != null ? `${Math.round(d.rain_today)}<span class="u">%</span>` : "—" },
    { klass:"wind",  icon:iconFor(d,"wind","ph-wind"),      key:"Wind",       val: c.wind_speed != null ? `${Math.round(c.wind_speed)}<span class="u">km/h</span>` : "—" },
    { klass:"humid", icon:iconFor(d,"humidity","ph-drop"),  key:"Humidity",   val: c.humidity   != null ? `${Math.round(c.humidity)}<span class="u">%</span>` : "—" },
  ].filter(Boolean);
  // At very narrow widths drop down to "rain + wind" (most actionable).
  const PRIORITY_ORDER = ["rain", "wind", "uv", "humid", "sunrise", "sunset"];
  const statBudget = W < 360 ? 2 : W < 640 ? 4 : 6;
  const stats = PRIORITY_ORDER
    .map((k) => allStats.find((s) => s.klass === k))
    .filter(Boolean)
    .slice(0, statBudget);

  host.innerHTML = `
    <div class="wx ${compact ? "compact" : ""} ${sizeClasses}">
      ${showTop ? `
      <header class="top">
        <div class="lead">
          <span class="small-ic">${renderIcon(c.icon)}</span>
          <span class="label">Weather</span>
        </div>
        <div class="loc">${escapeHtml(loc)}</div>
        ${showClock ? `<div class="clock">${formatNow()}</div>` : ""}
      </header>` : ""}

      <section class="hero">
        <div class="big-ic">${renderIcon(c.icon)}</div>
        <div class="temp">${tempBig(c.temp)}</div>
      </section>

      <section class="cond">
        <div class="label">${escapeHtml(c.label || "")}</div>
        ${c.feels_like != null ? `<div class="feels">Feels like ${Math.round(c.feels_like)}°C</div>` : ""}
      </section>

      ${showStats ? `
      <section class="metrics">
        ${stats.map((s) => metricRow(s.klass, s.icon, s.key, s.val)).join("")}
      </section>` : ""}

      ${showHourly ? `
      <section class="hourly">
        <div class="chart-box"><canvas></canvas></div>
        <div class="axis">
          ${hourly.map((h) => `
            <div class="tick">
              ${renderIcon(h.icon)}
              <div class="h">${formatHour(h.time)}</div>
            </div>`).join("")}
        </div>
      </section>` : ""}

      ${showDaily ? `
      <section class="daily">
        ${renderDaily(daily)}
      </section>` : ""}
    </div>`;

  if (compact || !showHourly) return;

  // --- Hourly chart -------------------------------------------------------
  // Read computed theme colors from the host so the chart matches the
  // active palette. Done after innerHTML so the CSS variables resolve.
  try {
    const Chart = await loadChart();
    const canvas = host.querySelector(".hourly canvas");
    if (!canvas || !hourly.length) return;
    drawChart(Chart, canvas, hourly, host);
  } catch (err) {
    console.warn("[weather] chart failed:", err);
  }
}

function drawChart(Chart, canvas, hourly, host) {
  const cs = getComputedStyle(host);
  const accent = cs.getPropertyValue("--theme-accent").trim() || "#3478f6";
  const fg     = cs.getPropertyValue("--theme-fg").trim() || "#111";
  const muted  = cs.getPropertyValue("--theme-fg-soft").trim()
              || cs.getPropertyValue("--theme-muted").trim() || "#888";

  const labels = hourly.map((h) => formatHour(h.time));
  const temps  = hourly.map((h) => h.temp ?? null);

  // Stretch the y-axis so the curve sits visually centered: pad ±2°.
  const valid = temps.filter((t) => t != null);
  const pad = 3;
  const ymin = Math.min(...valid) - pad;
  const ymax = Math.max(...valid) + pad;

  // High-contrast gradient under the line — accent is the source of
  // visual emphasis so it carries through here too.
  const ctx = canvas.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
  grad.addColorStop(0, hexA(accent, 0.75));
  grad.addColorStop(1, hexA(accent, 0.25));

  // Plugin: draw "13°" labels above each point, after the dataset draws.
  const labelPlugin = {
    id: "tempLabels",
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const meta = chart.getDatasetMeta(0);
      ctx.save();
      ctx.fillStyle = fg;
      ctx.font = `800 22px ${cs.fontFamily}`;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      meta.data.forEach((pt, i) => {
        const v = temps[i];
        if (v == null) return;
        ctx.fillText(`${Math.round(v)}°`, pt.x, pt.y - 10);
      });
      ctx.restore();
    },
  };

  new Chart(canvas, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: temps,
        borderColor: accent,
        backgroundColor: grad,
        borderWidth: 3.5,
        tension: 0.45,
        fill: true,
        pointRadius: 7,
        pointBorderWidth: 3,
        pointBorderColor: accent,
        pointBackgroundColor: cs.getPropertyValue("--theme-surface").trim() || "#fff",
        spanGaps: true,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { top: 36, bottom: 6, left: 14, right: 14 } },
      plugins: {
        legend:  { display: false },
        tooltip: { enabled: false },
      },
      scales: {
        x: { display: false },
        y: { display: false, min: ymin, max: ymax, beginAtZero: false },
      },
    },
    plugins: [labelPlugin],
  });
}

function renderDaily(daily) {
  if (!daily.length) return "";
  // Compute the global temp range so each bar's [min..max] maps onto the
  // shared scale — visually shows which days are warmer/cooler.
  const allMins = daily.map((x) => x.min).filter((v) => v != null);
  const allMaxs = daily.map((x) => x.max).filter((v) => v != null);
  const lo = Math.min(...allMins, ...allMaxs);
  const hi = Math.max(...allMins, ...allMaxs);
  const range = Math.max(1, hi - lo);
  return daily.map((dy) => {
    const left  = ((dy.min - lo) / range) * 100;
    const width = Math.max(4, ((dy.max - dy.min) / range) * 100);
    return `
      <div class="row">
        ${renderIcon(dy.icon)}
        <span class="day">${formatDay(dy.date)}</span>
        <div class="bar"><div class="fill" style="left:${left.toFixed(1)}%; width:${width.toFixed(1)}%"></div></div>
        <span class="hi">${dy.max != null ? Math.round(dy.max) + "°" : "—"}</span>
        <span class="lo">${dy.min != null ? Math.round(dy.min) + "°" : "—"}</span>
      </div>`;
  }).join("");
}

function metricRow(klass, iconHtml, key, value) {
  return `
    <div class="metric ${klass}">
      <span class="m-ic">${iconHtml}</span>
      <div class="k">${escapeHtml(key)}</div>
      <div class="v">${value}</div>
    </div>`;
}

// Pick the meteocon SVG for this metric when the data carries `ui_icons`,
// otherwise fall back to a Phosphor icon class for the phosphor icon-set.
function iconFor(d, key, phosphorClass) {
  const svg = (d.ui_icons || {})[key];
  if (svg) return svg;
  return `<i class="ph ${phosphorClass}"></i>`;
}

// ---- helpers --------------------------------------------------------------

function renderIcon(ic) {
  if (!ic) return "";
  if (ic.set === "phosphor") return `<i class="ph ${ic.name}"></i>`;
  return ic.svg || "";
}

function tempBig(t) {
  if (t == null) return "—";
  return `${Math.round(t)}<span class="u">°C</span>`;
}

function fmtUv(v) { return v == null ? "—" : `${Math.round(v)}`; }

function formatHour(iso) {
  if (!iso) return "";
  const m = iso.match(/T(\d{2}):(\d{2})/);
  return m ? `${m[1]}:${m[2]}` : iso;
}

function formatDay(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T12:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { weekday: "short" });
}

function formatNow() {
  const d = new Date();
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function formatSunTimes(rise, set) {
  if (!rise || !set) return null;
  const r = (rise.match(/T(\d{2}:\d{2})/) || [])[1] || rise;
  const s = (set.match(/T(\d{2}:\d{2})/)  || [])[1] || set;
  return { rise: r, set: s };
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}

function hexA(hex, alpha) {
  const m = hex.trim().match(/^#?([0-9a-f]{6})$/i);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n>>16)&255}, ${(n>>8)&255}, ${n&255}, ${alpha})`;
}
