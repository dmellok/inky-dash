// Air quality + 24h hourly trend.

const BAND_COLOR = {
  good: "ok",
  fair: "ok",
  moderate: "warn",
  poor: "warn",
  "very poor": "danger",
  extreme: "danger",
  unknown: "muted",
};

export default function render(host, ctx) {
  const data = ctx.data || {};
  if (data.error || !data.points) {
    host.innerHTML = `
      <link rel="stylesheet" href="/plugins/aqi_trend/client.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="aqi error">
        <i class="ph ph-warning-circle"></i>
        <div class="message">${escapeHtml(data.error || "No air quality data.")}</div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const { current, band, points } = data;
  const aqiNow = current.european_aqi;
  const bandColor = BAND_COLOR[band] || "muted";
  const place = ctx.cell?.options?.label || "";

  const aqis = points.map((p) => p.aqi).filter((v) => typeof v === "number");
  const aMin = aqis.length ? Math.min(...aqis) : 0;
  const aMax = aqis.length ? Math.max(...aqis) : 100;
  const aRange = Math.max(10, aMax - aMin);

  const W = 100;
  const H = 28;
  const pts = points
    .filter((p) => typeof p.aqi === "number")
    .map((p, i, arr) => {
      const x = (i / Math.max(1, arr.length - 1)) * W;
      const y = H - ((p.aqi - aMin) / aRange) * (H - 6) - 3;
      return [x.toFixed(2), y.toFixed(2)];
    });
  const path = pts.map(([x, y], i) => (i === 0 ? `M${x} ${y}` : `L${x} ${y}`)).join(" ");
  const fillPath = pts.length > 0 ? `${path} L${W} ${H} L0 ${H} Z` : "";

  const step = Math.max(1, Math.ceil(points.length / 6));
  const ticks = points
    .map((p, i) => ({ p, i }))
    .filter(({ i }) => i % step === 0 || i === points.length - 1);

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/aqi_trend/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="aqi band-${bandColor}">
      <div class="head">
        <div class="hero">
          <div class="aqi-num">${aqiNow != null ? Math.round(aqiNow) : "—"}</div>
          <div class="label">
            <div class="band">${escapeHtml(band)}</div>
            ${place ? `<div class="place">${escapeHtml(place)}</div>` : ""}
          </div>
        </div>
      </div>
      <div class="chart">
        <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
          ${fillPath ? `<path class="fill" d="${fillPath}"></path>` : ""}
          ${path ? `<path class="line" d="${path}"></path>` : ""}
        </svg>
        <div class="axis">
          ${ticks.map(({ p }) => `<span>${escapeHtml(p.label)}</span>`).join("")}
        </div>
      </div>
      <div class="tiles">
        <div class="tile"><span class="k">PM₂.₅</span><span class="v">${fmt(current.pm2_5)}</span></div>
        <div class="tile"><span class="k">PM₁₀</span><span class="v">${fmt(current.pm10)}</span></div>
        <div class="tile"><span class="k">NO₂</span><span class="v">${fmt(current.nitrogen_dioxide)}</span></div>
        <div class="tile"><span class="k">O₃</span><span class="v">${fmt(current.ozone)}</span></div>
      </div>
    </div>
  `;
  host.host.dataset.rendered = "true";
}

function fmt(v) {
  if (typeof v !== "number") return "—";
  return v < 10 ? v.toFixed(1) : Math.round(v);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
