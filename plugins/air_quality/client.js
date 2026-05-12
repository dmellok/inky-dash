// Air quality — header strip + big AQI hero + pollutant tile grid.
// Lightweight sibling of aqi_trend (which adds a Chart.js trend graph).

function aqiBand(aqi) {
  if (aqi == null) return { label: "—", token: "muted" };
  if (aqi <= 20) return { label: "Good", token: "ok" };
  if (aqi <= 40) return { label: "Fair", token: "ok" };
  if (aqi <= 60) return { label: "Moderate", token: "warn" };
  if (aqi <= 80) return { label: "Poor", token: "warn" };
  if (aqi <= 100) return { label: "Very poor", token: "danger" };
  return { label: "Extreme", token: "danger" };
}

function fmtPollutant(v) {
  if (v == null || Number.isNaN(v)) return "—";
  return v < 10 ? v.toFixed(1) : Math.round(v);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatTime(now) {
  return now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function render(host, ctx) {
  const { options } = ctx.cell;
  const { data } = ctx;
  const place = options.label || "";

  if (data && data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/air_quality/client.css">
      <div class="aq aq--error">
        <i class="ph ph-warning-circle"></i>
        <div class="msg">${escapeHtml(data.error)}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const band = aqiBand(data && data.aqi);
  const now = formatTime(new Date());

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/air_quality/client.css">
    <div class="aq band-${band.token}">
      <div class="head">
        <i class="ph ph-wind head-icon"></i>
        <span class="head-title">AIR QUALITY</span>
        ${place ? `<span class="head-place">${escapeHtml(place)}</span>` : ""}
        <span class="head-time">${escapeHtml(now)}</span>
      </div>

      <div class="hero">
        <div class="hero-num">${data && data.aqi != null ? Math.round(data.aqi) : "—"}</div>
        <div class="hero-band">${escapeHtml(band.label)}</div>
      </div>

      <div class="tiles">
        <div class="tile">
          <div class="tile-label">PM₂.₅</div>
          <div class="tile-value">${fmtPollutant(data && data.pm2_5)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">PM₁₀</div>
          <div class="tile-value">${fmtPollutant(data && data.pm10)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">NO₂</div>
          <div class="tile-value">${fmtPollutant(data && data.no2)}<span class="tile-unit"> µg/m³</span></div>
        </div>
        <div class="tile">
          <div class="tile-label">O₃</div>
          <div class="tile-value">${fmtPollutant(data && data.o3)}<span class="tile-unit"> µg/m³</span></div>
        </div>
      </div>
    </div>
  `;
  host.host.dataset.rendered = "true";
}
