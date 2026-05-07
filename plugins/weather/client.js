// Weather — current temp + daily outlook with Phosphor icons.

// WMO weather codes → Phosphor icon class names + label.
// https://open-meteo.com/en/docs#weathervariables
const WMO = {
  0: ["ph-sun-fill", "Clear"],
  1: ["ph-sun-fill", "Mostly clear"],
  2: ["ph-cloud-sun-fill", "Partly cloudy"],
  3: ["ph-cloud-fill", "Overcast"],
  45: ["ph-cloud-fog-fill", "Fog"],
  48: ["ph-cloud-fog-fill", "Rime fog"],
  51: ["ph-cloud-rain-fill", "Drizzle"],
  53: ["ph-cloud-rain-fill", "Drizzle"],
  55: ["ph-cloud-rain-fill", "Drizzle"],
  61: ["ph-cloud-rain-fill", "Rain"],
  63: ["ph-cloud-rain-fill", "Rain"],
  65: ["ph-cloud-rain-fill", "Heavy rain"],
  71: ["ph-cloud-snow-fill", "Snow"],
  73: ["ph-cloud-snow-fill", "Snow"],
  75: ["ph-cloud-snow-fill", "Heavy snow"],
  77: ["ph-cloud-snow-fill", "Snow grains"],
  80: ["ph-cloud-rain-fill", "Showers"],
  81: ["ph-cloud-rain-fill", "Showers"],
  82: ["ph-cloud-lightning-fill", "Heavy showers"],
  95: ["ph-cloud-lightning-fill", "Thunder"],
  96: ["ph-cloud-lightning-fill", "Thunder + hail"],
  99: ["ph-cloud-lightning-fill", "Thunder + hail"],
};

function code(c) {
  return WMO[c] || ["ph-question", `Code ${c}`];
}

function formatDay(iso) {
  const d = new Date(iso);
  return new Intl.DateTimeFormat("en-US", { weekday: "short" }).format(d);
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const { data } = ctx;
  const placeLabel = options.label || "";
  const units = options.units || "metric";
  const tempUnit = units === "imperial" ? "°F" : "°C";

  if (!data || data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <link rel="stylesheet" href="/plugins/weather/client.css">
      <div class="wx wx--${size} wx-error">
        <i class="ph ph-warning-circle wx-error-icon"></i>
        <div class="error-msg">${data && data.error ? data.error : "No data"}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const current = data.current || {};
  const daily = data.daily || {};
  const dailyDays = Math.min(
    (daily.time || []).length,
    size === "xs" ? 0 : size === "sm" ? 0 : size === "md" ? 3 : 4
  );

  const [iconClass, label] = code(current.weather_code);

  const dailyHtml =
    dailyDays > 0
      ? `<div class="daily">${(daily.time || [])
          .slice(0, dailyDays)
          .map((iso, i) => {
            const [di] = code(daily.weather_code[i]);
            return `
              <div class="daily-cell">
                <div class="day">${formatDay(iso)}</div>
                <i class="ph ${di} icon"></i>
                <div class="hi-lo">
                  <span class="hi">${Math.round(daily.temperature_2m_max[i])}°</span>
                  <span class="lo">${Math.round(daily.temperature_2m_min[i])}°</span>
                </div>
              </div>
            `;
          })
          .join("")}</div>`
      : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/weather/client.css">
    <div class="wx wx--${size}">
      <div class="hero">
        <i class="ph ${iconClass} hero-icon"></i>
        <div class="hero-temp">${Math.round(current.temperature_2m)}<span class="unit">${tempUnit}</span></div>
      </div>
      <div class="meta">
        ${placeLabel ? `<div class="place">${placeLabel}</div>` : ""}
        <div class="cond">${label}</div>
        ${
          size !== "xs"
            ? `<div class="extras">
                 <span><i class="ph ph-drop"></i> ${current.relative_humidity_2m ?? "—"}%</span>
                 <span><i class="ph ph-wind"></i> ${Math.round(current.wind_speed_10m ?? 0)} km/h</span>
               </div>`
            : ""
        }
      </div>
      ${dailyHtml}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
