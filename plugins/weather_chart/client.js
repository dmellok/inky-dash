// Hourly weather chart. Header: current temp + condition + place label.
// Body: SVG sparkline of hourly temps with min/max markers + axis labels.

const WEATHER = {
  0: ["ph-sun", "Clear"], 1: ["ph-sun", "Mostly clear"],
  2: ["ph-cloud-sun", "Partly cloudy"], 3: ["ph-cloud", "Overcast"],
  45: ["ph-cloud-fog", "Fog"], 48: ["ph-cloud-fog", "Rime fog"],
  51: ["ph-cloud-rain", "Drizzle"], 53: ["ph-cloud-rain", "Drizzle"],
  55: ["ph-cloud-rain", "Drizzle"], 61: ["ph-cloud-rain", "Light rain"],
  63: ["ph-cloud-rain", "Rain"], 65: ["ph-cloud-rain", "Heavy rain"],
  71: ["ph-cloud-snow", "Snow"], 73: ["ph-cloud-snow", "Snow"],
  75: ["ph-cloud-snow", "Heavy snow"], 80: ["ph-cloud-rain", "Showers"],
  81: ["ph-cloud-rain", "Showers"], 82: ["ph-cloud-rain", "Heavy showers"],
  95: ["ph-lightning", "Thunder"], 96: ["ph-lightning", "Thunder"],
  99: ["ph-lightning", "Thunder"],
};

export default function render(host, ctx) {
  const data = ctx.data || {};
  if (data.error || !data.points) {
    host.innerHTML = `
      <link rel="stylesheet" href="/plugins/weather_chart/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="wx-chart error">
        <i class="ph ph-warning-circle"></i>
        <div class="message">${escapeHtml(data.error || "No forecast data.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const { current, points, units } = data;
  const tempUnit = units === "imperial" ? "°F" : "°C";
  const speedUnit = units === "imperial" ? "mph" : "km/h";
  const code = current.weather_code ?? 0;
  const [icon, condition] = WEATHER[code] || ["ph-cloud", "—"];
  const place = ctx.cell?.options?.label || "";

  const temps = points.map((p) => p.temp).filter((t) => typeof t === "number");
  const tMin = Math.min(...temps);
  const tMax = Math.max(...temps);
  const tRange = Math.max(1, tMax - tMin);

  // Build SVG path.
  const W = 100;
  const H = 28;
  const pts = points.map((p, i) => {
    const x = (i / Math.max(1, points.length - 1)) * W;
    const y = H - ((p.temp - tMin) / tRange) * (H - 6) - 3;
    return [x.toFixed(2), y.toFixed(2)];
  });
  const path = pts.map(([x, y], i) => (i === 0 ? `M${x} ${y}` : `L${x} ${y}`)).join(" ");
  const fillPath = `${path} L${W} ${H} L0 ${H} Z`;

  // X-axis labels: every Nth hour so the strip doesn't crowd.
  const step = Math.max(1, Math.ceil(points.length / 8));
  const ticks = points
    .map((p, i) => ({ p, i }))
    .filter(({ i }) => i % step === 0 || i === points.length - 1);

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/weather_chart/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="wx-chart">
      <div class="head">
        <div class="hero">
          <i class="ph ${icon} hero-icon"></i>
          <div class="hero-temp">${Math.round(current.temperature_2m)}<span class="unit">${tempUnit}</span></div>
        </div>
        <div class="meta">
          ${place ? `<div class="place">${escapeHtml(place)}</div>` : ""}
          <div class="condition">${condition}</div>
          <div class="stats">
            <span><i class="ph ph-drop"></i>${Math.round(current.relative_humidity_2m ?? 0)}%</span>
            <span><i class="ph ph-wind"></i>${Math.round(current.wind_speed_10m ?? 0)} ${speedUnit}</span>
          </div>
        </div>
      </div>
      <div class="chart">
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
          <path class="fill" d="${fillPath}"></path>
          <path class="line" d="${path}"></path>
        </svg>
        <div class="axis">
          ${ticks
            .map(({ p }) => `<span>${escapeHtml(p.label)}</span>`)
            .join("")}
        </div>
        <div class="bounds">
          <span>min ${Math.round(tMin)}${tempUnit}</span>
          <span>max ${Math.round(tMax)}${tempUnit}</span>
        </div>
      </div>
    </div>
  `;

  host.host.dataset.rendered = "true";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}
