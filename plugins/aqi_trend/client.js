// Air quality + 24h hourly trend.
// Layout (matches the design screenshot):
//   - Big hero AQI number with "/ 500" max
//   - Band label below (GOOD / FAIR / MODERATE / POOR / ...)
//   - Thin range indicator showing where AQI sits within the 0–500 scale
//   - "LAST 24 HOURS" caps + Chart.js line chart
//   - 6 pollutant tiles in a 3×2 grid (PM2.5, PM10, O3, NO2, SO2, CO)

const BAND_TOKEN = {
  good: "ok",
  fair: "ok",
  moderate: "warn",
  poor: "warn",
  "very poor": "danger",
  extreme: "danger",
  unknown: "muted",
};

const AQI_MAX = 500;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function readVar(host, name, fallback) {
  try {
    const v = getComputedStyle(host.host).getPropertyValue(name).trim();
    return v || fallback;
  } catch {
    return fallback;
  }
}

function fmtPollutant(v) {
  if (typeof v !== "number") return "—";
  return v < 10 ? v.toFixed(1) : Math.round(v);
}

function mountTrendChart(host, canvas, points, bandToken) {
  if (!window.Chart || !canvas || !points.length) return null;
  const tokenVar = `--theme-${bandToken}`;
  const accent = readVar(host, tokenVar, readVar(host, "--theme-accent", "#d97757"));
  const fgSoft = readVar(host, "--theme-fgSoft", "#5a4f44");
  const labels = points.map((p) => p.label);
  const aqis = points.map((p) => (typeof p.aqi === "number" ? p.aqi : null));
  return new window.Chart(canvas.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data: aqis,
          borderColor: accent,
          backgroundColor: accent + "30",
          tension: 0.4,
          fill: true,
          pointRadius: 0,
          borderWidth: 2,
          spanGaps: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { top: 8, bottom: 4, left: 4, right: 4 } },
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: {
        x: {
          grid: { display: false, drawBorder: false },
          ticks: {
            color: fgSoft,
            font: { family: "ui-monospace, monospace", size: 9, weight: "600" },
            padding: 4,
            maxTicksLimit: 6,
            autoSkip: true,
          },
          border: { display: false },
        },
        y: { display: false, grace: "10%" },
      },
    },
  });
}

export default function render(host, ctx) {
  const data = ctx.data || {};
  if (data.error || !data.points) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/aqi_trend/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="aqi aqi--error">
        <i class="ph ph-warning-circle"></i>
        <div class="msg">${escapeHtml(data.error || "No air quality data.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const { current, band, points } = data;
  const aqiNow = current.european_aqi;
  const bandToken = BAND_TOKEN[band] || "muted";
  // Range indicator — where AQI sits within 0..500.
  const rangePct = aqiNow != null
    ? Math.max(0, Math.min(100, (aqiNow / AQI_MAX) * 100))
    : 0;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/aqi_trend/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="widget aqi band-${bandToken}">
      <div class="head">
        <i class="ph ph-wind head-icon"></i>
        <span class="head-title">AIR QUALITY</span>
        ${ctx.cell?.options?.label
          ? `<span class="head-place">${escapeHtml(ctx.cell.options.label)}</span>`
          : ""}
      </div>
      <div class="hero">
        <div class="hero-num">${aqiNow != null ? Math.round(aqiNow) : "—"}</div>
        <div class="hero-max">/ ${AQI_MAX}</div>
      </div>
      <div class="hero-band">${escapeHtml(band).toUpperCase()}</div>

      <div class="range">
        <div class="range-track"></div>
        <div class="range-marker" style="left: ${rangePct.toFixed(2)}%;"></div>
      </div>

      <div class="chart-block">
        <div class="chart-label">LAST 24 HOURS</div>
        <div class="chart-wrap"><canvas class="chart-canvas"></canvas></div>
      </div>

      <div class="tiles">
        <div class="tile">
          <div class="tile-label">PM₂.₅</div>
          <div class="tile-value">${fmtPollutant(current.pm2_5)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">PM₁₀</div>
          <div class="tile-value">${fmtPollutant(current.pm10)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">O₃</div>
          <div class="tile-value">${fmtPollutant(current.ozone)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">NO₂</div>
          <div class="tile-value">${fmtPollutant(current.nitrogen_dioxide)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">SO₂</div>
          <div class="tile-value">${fmtPollutant(current.sulphur_dioxide)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">CO</div>
          <div class="tile-value">${fmtPollutant(current.carbon_monoxide)}<span class="tile-unit"> µg/m³</span></div>
        </div>
      </div>
    </div>
  `;

  if (host.__inkyChart && host.__inkyChart.destroy) {
    host.__inkyChart.destroy();
  }
  const canvas = host.querySelector(".chart-canvas");
  host.__inkyChart = mountTrendChart(host, canvas, points, bandToken);

  host.host.dataset.rendered = "true";
}

export function cleanup(host) {
  if (host.__inkyChart && host.__inkyChart.destroy) {
    host.__inkyChart.destroy();
    host.__inkyChart = null;
  }
}
