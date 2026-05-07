// Air quality — European AQI hero + four pollutant tiles.

function aqiBand(aqi) {
  if (aqi == null) return { label: "—", color: "var(--theme-fgSoft)" };
  if (aqi <= 20) return { label: "Good", color: "var(--theme-ok)" };
  if (aqi <= 40) return { label: "Fair", color: "var(--theme-ok)" };
  if (aqi <= 60) return { label: "Moderate", color: "var(--theme-warn)" };
  if (aqi <= 80) return { label: "Poor", color: "var(--theme-warn)" };
  if (aqi <= 100) return { label: "Very poor", color: "var(--theme-danger)" };
  return { label: "Extreme", color: "var(--theme-danger)" };
}

function fmt(v, precision = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return precision === 0 ? String(Math.round(v)) : v.toFixed(precision);
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const { data } = ctx;
  const placeLabel = options.label || "";
  const error = data && data.error;

  if (error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <link rel="stylesheet" href="/plugins/air_quality/client.css">
      <div class="aq aq--${size}">
        <div class="error-block">
          <i class="ph ph-warning-circle"></i>
          <div class="error">${error}</div>
        </div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const band = aqiBand(data && data.aqi);
  const heroIcon =
    band.label === "Good" || band.label === "Fair"
      ? "ph-leaf-fill"
      : band.label === "Moderate"
        ? "ph-wind"
        : "ph-cloud-warning-fill";

  const pollutants =
    size === "sm"
      ? ""
      : `<div class="pollutants">
          <div class="tile"><span class="t-label">PM2.5</span><span class="t-val">${fmt(data && data.pm2_5)}</span><span class="t-unit">µg/m³</span></div>
          <div class="tile"><span class="t-label">PM10</span><span class="t-val">${fmt(data && data.pm10)}</span><span class="t-unit">µg/m³</span></div>
          <div class="tile"><span class="t-label">NO₂</span><span class="t-val">${fmt(data && data.no2)}</span><span class="t-unit">µg/m³</span></div>
          <div class="tile"><span class="t-label">O₃</span><span class="t-val">${fmt(data && data.o3)}</span><span class="t-unit">µg/m³</span></div>
        </div>`;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/air_quality/client.css">
    <div class="aq aq--${size}">
      <div class="hero">
        <i class="ph ${heroIcon} hero-icon" style="color: ${band.color};"></i>
        <div class="aqi" style="color: ${band.color};">${fmt(data && data.aqi)}</div>
        <div class="band" style="color: ${band.color};">${band.label}</div>
        ${placeLabel ? `<div class="place">${placeLabel}</div>` : ""}
      </div>
      ${pollutants}
    </div>
  `;
  host.host.dataset.rendered = "true";
}
